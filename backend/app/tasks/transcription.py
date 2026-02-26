import asyncio
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.integrations.aws.s3 import get_s3_client
from app.integrations.deepgram.client import DeepgramClient
from app.integrations.deepgram.processor import DiarizationProcessor
from app.services.meeting_service import MeetingService
from app.services.transcript_service import TranscriptService
from app.tasks.base import BaseTask
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a sync context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(base=BaseTask, bind=True, queue="transcription")
def validate_and_store(self, meeting_id: str, org_id: str) -> str:
    """Validate uploaded file exists in S3 and update meeting status."""

    async def _validate():
        settings = get_settings()
        s3_client = get_s3_client()

        async with async_session_factory() as session:
            try:
                meeting_svc = MeetingService(db=session, s3_client=s3_client, settings=settings)
                meeting = await meeting_svc.get_meeting(UUID(meeting_id))

                # Verify the S3 file exists
                if not meeting.file_key:
                    raise ValueError(f"Meeting {meeting_id} has no file_key set")

                file_exists = await s3_client.file_exists(meeting.file_key)
                if not file_exists:
                    raise FileNotFoundError(
                        f"S3 file not found for meeting {meeting_id}: {meeting.file_key}"
                    )

                # Update status from 'uploading' to 'transcribing'
                await meeting_svc.update_meeting_status(UUID(meeting_id), "transcribing")
                await session.commit()

                logger.info(
                    "validate_and_store_complete",
                    meeting_id=meeting_id,
                    file_key=meeting.file_key,
                )
            except Exception:
                await session.rollback()
                raise

    _run_async(_validate())
    return meeting_id


@celery_app.task(base=BaseTask, bind=True, queue="transcription")
def extract_audio(self, meeting_id: str) -> str:
    """Extract audio from video file using ffmpeg. Skip if already audio."""
    logger.info(
        "extract_audio_skipped",
        meeting_id=meeting_id,
        reason="already_audio_format",
    )
    return meeting_id


@celery_app.task(base=BaseTask, bind=True, queue="transcription")
def transcribe_with_deepgram(self, meeting_id: str) -> str:
    """Send audio to Deepgram API with financial vocabulary. Store raw response."""

    async def _transcribe():
        settings = get_settings()
        s3_client = get_s3_client()

        async with async_session_factory() as session:
            try:
                meeting_svc = MeetingService(db=session, s3_client=s3_client, settings=settings)
                meeting = await meeting_svc.get_meeting(UUID(meeting_id))

                if not meeting.file_key:
                    raise ValueError(f"Meeting {meeting_id} has no file_key set")

                # Generate a presigned download URL for the S3 file
                presigned_url = await s3_client.generate_presigned_download_url(meeting.file_key)

                # Transcribe using Deepgram
                deepgram_client = DeepgramClient(api_key=settings.deepgram_api_key)
                deepgram_response = await deepgram_client.transcribe_file(presigned_url)

                # Assemble full_text from the Deepgram response
                alternatives = (
                    deepgram_response.get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [])
                )
                full_text = ""
                if alternatives:
                    full_text = alternatives[0].get("transcript", "")

                # Extract overall confidence score
                confidence_score = None
                if alternatives:
                    confidence_score = alternatives[0].get("confidence")

                # Store the transcript
                transcript_svc = TranscriptService(db=session)
                await transcript_svc.create_transcript(
                    meeting_id=UUID(meeting_id),
                    org_id=meeting.org_id,
                    full_text=full_text,
                    deepgram_response=deepgram_response,
                    confidence_score=confidence_score,
                )

                # Update meeting status to 'analyzing'
                await meeting_svc.update_meeting_status(UUID(meeting_id), "analyzing")
                await session.commit()

                logger.info(
                    "transcribe_with_deepgram_complete",
                    meeting_id=meeting_id,
                    word_count=len(full_text.split()) if full_text else 0,
                )
            except Exception:
                await session.rollback()
                raise

    _run_async(_transcribe())
    return meeting_id


@celery_app.task(base=BaseTask, bind=True, queue="transcription")
def process_diarization(self, meeting_id: str) -> str:
    """Parse Deepgram response into transcript segments with speaker attribution."""

    async def _diarize():
        settings = get_settings()
        s3_client = get_s3_client()

        async with async_session_factory() as session:
            try:
                # Get the transcript for this meeting
                transcript_svc = TranscriptService(db=session)
                transcript = await transcript_svc.get_transcript(UUID(meeting_id))

                if not transcript.deepgram_response:
                    raise ValueError(
                        f"No deepgram_response stored for meeting {meeting_id}"
                    )

                # Process the Deepgram response into diarized segments
                processor = DiarizationProcessor()
                segments = processor.process_response(transcript.deepgram_response)

                # Merge short consecutive segments from the same speaker
                segments = processor.merge_short_segments(segments)

                # Store the segments
                await transcript_svc.store_segments(
                    transcript_id=transcript.id,
                    meeting_id=UUID(meeting_id),
                    segments=segments,
                )

                # Extract unique participants and store them
                participants = processor.extract_participants(segments)
                meeting_svc = MeetingService(db=session, s3_client=s3_client, settings=settings)
                await meeting_svc.add_participants(
                    meeting_id=UUID(meeting_id),
                    participants=participants,
                )

                await session.commit()

                logger.info(
                    "process_diarization_complete",
                    meeting_id=meeting_id,
                    segment_count=len(segments),
                    participant_count=len(participants),
                )
            except Exception:
                await session.rollback()
                raise

    _run_async(_diarize())
    return meeting_id
