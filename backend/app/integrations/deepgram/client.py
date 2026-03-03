from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
from deepgram import AsyncDeepgramClient as DGClient

from app.integrations.deepgram.config import DEEPGRAM_CONFIG

logger = structlog.get_logger(__name__)


class DeepgramClient:
    """Client for Deepgram speech-to-text API (SDK v6)."""

    def __init__(self, api_key: str) -> None:
        """Initialize the Deepgram client with an API key."""
        self.api_key = api_key

    def _build_options(self, config: dict | None = None) -> dict:
        """Build transcription options by merging default config with overrides.

        The base configuration comes from DEEPGRAM_CONFIG. Any keys supplied in
        *config* will override the defaults.
        """
        merged = {**DEEPGRAM_CONFIG}
        if config:
            merged.update(config)

        # Map 'keywords' to 'keyterm' (list of strings) for v6 SDK
        keywords = merged.pop("keywords", [])
        if keywords:
            merged["keyterm"] = keywords

        return merged

    async def transcribe_file(
        self, audio_url: str, config: dict | None = None
    ) -> dict:
        """Transcribe an audio file from a URL using Deepgram.

        Parameters
        ----------
        audio_url:
            Publicly-accessible URL of the audio file to transcribe.
        config:
            Optional dictionary of Deepgram option overrides.  Keys are merged
            on top of the project-wide ``DEEPGRAM_CONFIG`` defaults.

        Returns
        -------
        dict
            The full Deepgram JSON response.
        """
        logger.info(
            "deepgram.transcribe_file.start",
            audio_url=audio_url,
        )

        options = self._build_options(config)

        try:
            client = DGClient(api_key=self.api_key)
            response = await client.listen.v1.media.transcribe_url(
                url=audio_url, **options
            )

            logger.info(
                "deepgram.transcribe_file.complete",
                audio_url=audio_url,
            )

            return response.model_dump()

        except Exception as exc:
            logger.error(
                "deepgram.transcribe_file.error",
                audio_url=audio_url,
                error=str(exc),
            )
            raise

    async def transcribe_bytes(
        self,
        audio_data: bytes,
        mimetype: str = "audio/wav",
        config: dict | None = None,
    ) -> dict:
        """Transcribe raw audio bytes using Deepgram.

        Parameters
        ----------
        audio_data:
            Raw audio content as bytes.
        mimetype:
            MIME type of the audio data (e.g. ``"audio/wav"``).
        config:
            Optional dictionary of Deepgram option overrides.

        Returns
        -------
        dict
            The full Deepgram JSON response.
        """
        logger.info(
            "deepgram.transcribe_bytes.start",
            mimetype=mimetype,
            size_bytes=len(audio_data),
        )

        options = self._build_options(config)

        try:
            client = DGClient(api_key=self.api_key)
            response = await client.listen.v1.media.transcribe_file(
                request=audio_data, **options
            )

            logger.info(
                "deepgram.transcribe_bytes.complete",
                mimetype=mimetype,
                size_bytes=len(audio_data),
            )

            return response.model_dump()

        except Exception as exc:
            logger.error(
                "deepgram.transcribe_bytes.error",
                mimetype=mimetype,
                error=str(exc),
            )
            raise

    async def transcribe_stream(
        self, audio_stream, config: dict | None = None
    ) -> AsyncIterator[dict]:
        """Transcribe a live audio stream using Deepgram."""
        raise NotImplementedError
