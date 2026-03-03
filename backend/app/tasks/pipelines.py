from celery import chain, chord, group

from app.tasks.analysis import run_analysis
from app.tasks.embedding import generate_embeddings
from app.tasks.notifications import send_completion_notification
from app.tasks.transcription import (
    extract_audio,
    process_diarization,
    transcribe_with_deepgram,
    validate_and_store,
)


def create_meeting_pipeline(meeting_id: str, org_id: str) -> chain:
    """Full meeting processing pipeline.

    Flow: validate → extract audio → transcribe → diarize → (embed + analyze) → notify
    """
    return chain(
        validate_and_store.si(meeting_id, org_id),
        extract_audio.si(meeting_id),
        transcribe_with_deepgram.si(meeting_id),
        process_diarization.si(meeting_id),
        chord(
            group(
                generate_embeddings.si(meeting_id),
                run_analysis.si(meeting_id),
            ),
            send_completion_notification.si(meeting_id),
        ),
    )


def create_reanalysis_pipeline(meeting_id: str, call_type: str, requested_by: str) -> chain:
    """Re-analysis pipeline — skips transcription, runs analysis only."""
    return chain(
        run_analysis.si(meeting_id, call_type, requested_by),
        send_completion_notification.si(meeting_id, "analysis_completed"),
    )


def create_document_pipeline(document_id: str, deal_id: str, org_id: str) -> chain:
    """Document processing pipeline — text extraction + embedding generation."""
    from app.tasks.embedding import generate_document_embeddings

    return chain(
        generate_document_embeddings.si(document_id, deal_id, org_id),
        send_completion_notification.si(document_id, "document_processed"),
    )
