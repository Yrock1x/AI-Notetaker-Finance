ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "audio/x-wav",
    "audio/x-m4a",
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
}

ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
    "text/plain",
    "text/csv",
}

MAX_FILE_SIZE_MB = 500


def validate_file_type(content_type: str, category: str) -> bool:
    """Check if a content type is allowed for the given category."""
    allowed = {
        "audio": ALLOWED_AUDIO_TYPES,
        "video": ALLOWED_VIDEO_TYPES,
        "document": ALLOWED_DOCUMENT_TYPES,
        "meeting": ALLOWED_AUDIO_TYPES | ALLOWED_VIDEO_TYPES,
    }
    return content_type in allowed.get(category, set())


def get_file_category(content_type: str) -> str | None:
    """Determine file category from content type."""
    if content_type in ALLOWED_AUDIO_TYPES:
        return "audio"
    if content_type in ALLOWED_VIDEO_TYPES:
        return "video"
    if content_type in ALLOWED_DOCUMENT_TYPES:
        return "document"
    return None


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from a PDF file."""
    raise NotImplementedError


async def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text content from a DOCX file."""
    raise NotImplementedError


async def extract_text_from_xlsx(file_bytes: bytes) -> str:
    """Extract text content from an XLSX file."""
    raise NotImplementedError
