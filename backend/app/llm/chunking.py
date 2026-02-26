import re
from dataclasses import dataclass


def _estimate_tokens(text: str) -> int:
    """Rough token estimation: word count * 4/3."""
    return len(text.split()) * 4 // 3


@dataclass
class Chunk:
    text: str
    index: int
    source_type: str  # transcript_segment, document_chunk
    source_id: str
    metadata: dict

    @property
    def token_count(self) -> int:
        return _estimate_tokens(self.text)


class TranscriptChunker:
    def __init__(self, max_chunk_tokens: int = 500, overlap_tokens: int = 50) -> None:
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_segments(self, segments: list[dict]) -> list[Chunk]:
        """Chunk transcript segments into overlapping windows for embedding.

        Each segment dict has: text, speaker_label, speaker_name, start_time, end_time, id.
        Groups segments into chunks that respect speaker turns and include speaker
        attribution in the text. Chunks overlap by approximately overlap_tokens.
        """
        if not segments:
            return []

        # Build annotated lines: each segment becomes "Speaker Name: text"
        annotated: list[dict] = []
        for seg in segments:
            speaker = seg.get("speaker_name") or seg.get("speaker_label", "Unknown")
            line_text = f"{speaker}: {seg['text'].strip()}"
            annotated.append({
                "text": line_text,
                "tokens": _estimate_tokens(line_text),
                "segment": seg,
            })

        chunks: list[Chunk] = []
        chunk_index = 0
        i = 0  # current segment pointer

        while i < len(annotated):
            # Build a chunk starting from segment i
            chunk_lines: list[str] = []
            chunk_token_count = 0
            segment_ids: list[str] = []
            start_time = annotated[i]["segment"].get("start_time")
            end_time = annotated[i]["segment"].get("end_time")
            j = i

            while j < len(annotated):
                line_tokens = annotated[j]["tokens"]

                # If adding this line would exceed the limit and we already have content, stop
                if chunk_token_count + line_tokens > self.max_chunk_tokens and chunk_lines:
                    break

                chunk_lines.append(annotated[j]["text"])
                chunk_token_count += line_tokens
                segment_ids.append(annotated[j]["segment"].get("id", str(j)))
                end_time = annotated[j]["segment"].get("end_time", end_time)
                j += 1

            chunk_text = "\n".join(chunk_lines)

            chunks.append(Chunk(
                text=chunk_text,
                index=chunk_index,
                source_type="transcript_segment",
                source_id=segment_ids[0] if segment_ids else "",
                metadata={
                    "segment_ids": segment_ids,
                    "start_time": start_time,
                    "end_time": end_time,
                    "segment_count": len(chunk_lines),
                },
            ))
            chunk_index += 1

            # Advance pointer with overlap: find the segment to start from so that
            # approximately overlap_tokens worth of content from the end of this
            # chunk are included in the next chunk.
            if j >= len(annotated):
                break

            overlap_accum = 0
            overlap_start = j
            for k in range(j - 1, i - 1, -1):
                overlap_accum += annotated[k]["tokens"]
                if overlap_accum >= self.overlap_tokens:
                    overlap_start = k
                    break

            # Ensure we make forward progress (at least one new segment)
            if overlap_start <= i:
                overlap_start = i + 1
            i = overlap_start

        return chunks


class DocumentChunker:
    def __init__(self, max_chunk_tokens: int = 500, overlap_tokens: int = 50) -> None:
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_text(self, text: str, source_id: str) -> list[Chunk]:
        """Chunk document text into overlapping windows for embedding.

        Splits by paragraphs first, then by sentences if a paragraph is too large.
        Maintains overlap between consecutive chunks.
        """
        if not text or not text.strip():
            return []

        # Split into paragraphs (double newline or more)
        paragraphs = re.split(r"\n\s*\n", text.strip())
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # Further split large paragraphs into sentences
        units: list[str] = []
        for para in paragraphs:
            para_tokens = _estimate_tokens(para)
            if para_tokens <= self.max_chunk_tokens:
                units.append(para)
            else:
                # Split paragraph into sentences
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence:
                        units.append(sentence)

        if not units:
            return []

        chunks: list[Chunk] = []
        chunk_index = 0
        i = 0

        while i < len(units):
            # Build a chunk starting from unit i
            chunk_parts: list[str] = []
            chunk_token_count = 0
            j = i

            while j < len(units):
                unit_tokens = _estimate_tokens(units[j])

                # If adding this unit would exceed the limit and we already have content, stop
                if chunk_token_count + unit_tokens > self.max_chunk_tokens and chunk_parts:
                    break

                chunk_parts.append(units[j])
                chunk_token_count += unit_tokens
                j += 1

            chunk_text = "\n\n".join(chunk_parts)

            chunks.append(Chunk(
                text=chunk_text,
                index=chunk_index,
                source_type="document_chunk",
                source_id=source_id,
                metadata={
                    "char_start": text.find(chunk_parts[0]) if chunk_parts else 0,
                    "unit_count": len(chunk_parts),
                },
            ))
            chunk_index += 1

            # Advance with overlap
            if j >= len(units):
                break

            overlap_accum = 0
            overlap_start = j
            for k in range(j - 1, i - 1, -1):
                overlap_accum += _estimate_tokens(units[k])
                if overlap_accum >= self.overlap_tokens:
                    overlap_start = k
                    break

            # Ensure forward progress
            if overlap_start <= i:
                overlap_start = i + 1
            i = overlap_start

        return chunks
