from __future__ import annotations


class DiarizationProcessor:
    """Processes Deepgram responses to extract speaker-diarized segments."""

    def process_response(self, deepgram_response: dict) -> list[dict]:
        """Parse a Deepgram response into speaker-attributed transcript segments.

        Walks the ``words`` array from the first channel/alternative and groups
        consecutive words that share the same ``speaker`` value into segments.

        Parameters
        ----------
        deepgram_response:
            The full JSON dict returned by the Deepgram API.

        Returns
        -------
        list[dict]
            A list of segment dicts, each containing ``speaker_label``,
            ``speaker_name``, ``text``, ``start_time``, ``end_time``,
            ``confidence``, and ``segment_index``.
        """
        words = (
            deepgram_response.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("words", [])
        )

        if not words:
            return []

        segments: list[dict] = []
        current_speaker: int | None = None
        current_words: list[dict] = []

        for word in words:
            speaker = word.get("speaker")

            if speaker != current_speaker and current_words:
                # Flush the accumulated group as a new segment.
                segments.append(self._build_segment(current_words, len(segments)))
                current_words = []

            current_speaker = speaker
            current_words.append(word)

        # Flush the final group.
        if current_words:
            segments.append(self._build_segment(current_words, len(segments)))

        return segments

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_segment(words: list[dict], index: int) -> dict:
        """Construct a segment dict from a group of words."""
        speaker_id = words[0].get("speaker", 0)
        speaker_label = f"Speaker {speaker_id}"

        # Prefer the punctuated form when available, fall back to plain word.
        text = " ".join(w.get("punctuated_word", w.get("word", "")) for w in words)

        confidences = [w.get("confidence", 0.0) for w in words]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "speaker_label": speaker_label,
            "speaker_name": speaker_label,
            "text": text,
            "start_time": words[0].get("start", 0.0),
            "end_time": words[-1].get("end", 0.0),
            "confidence": round(avg_confidence, 4),
            "segment_index": index,
        }

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def merge_short_segments(
        self, segments: list[dict], gap_threshold: float = 2.0
    ) -> list[dict]:
        """Merge consecutive segments from the same speaker within a gap threshold.

        Two adjacent segments are merged when they share the same
        ``speaker_label`` **and** the time gap between the end of the first
        and the start of the next is strictly less than *gap_threshold*
        seconds.

        After merging, ``segment_index`` values are re-numbered starting from
        zero.

        Parameters
        ----------
        segments:
            The list of segment dicts produced by :meth:`process_response`.
        gap_threshold:
            Maximum gap (in seconds) between two segments for them to be
            merged.  Defaults to ``2.0``.

        Returns
        -------
        list[dict]
            A new list of (potentially fewer) segment dicts.
        """
        if not segments:
            return []

        merged: list[dict] = [segments[0].copy()]

        for seg in segments[1:]:
            prev = merged[-1]
            gap = seg["start_time"] - prev["end_time"]

            if seg["speaker_label"] == prev["speaker_label"] and gap < gap_threshold:
                # Merge: extend text, update end time, recalculate confidence.
                prev_word_count = len(prev["text"].split())
                seg_word_count = len(seg["text"].split())
                total_words = prev_word_count + seg_word_count

                prev["text"] = f"{prev['text']} {seg['text']}"
                prev["end_time"] = seg["end_time"]

                # Weighted average of confidence by word count.
                if total_words > 0:
                    prev["confidence"] = round(
                        (prev["confidence"] * prev_word_count
                         + seg["confidence"] * seg_word_count)
                        / total_words,
                        4,
                    )
            else:
                merged.append(seg.copy())

        # Re-index after merging.
        for idx, seg in enumerate(merged):
            seg["segment_index"] = idx

        return merged

    def extract_participants(self, segments: list[dict]) -> list[dict]:
        """Extract unique participant information from diarized segments.

        Parameters
        ----------
        segments:
            The list of segment dicts (merged or unmerged).

        Returns
        -------
        list[dict]
            One entry per unique speaker with ``speaker_label``,
            ``speaker_name``, ``segment_count``, ``total_duration``, and
            ``word_count``.
        """
        stats: dict[str, dict] = {}

        for seg in segments:
            label = seg["speaker_label"]

            if label not in stats:
                stats[label] = {
                    "speaker_label": label,
                    "speaker_name": seg.get("speaker_name", label),
                    "segment_count": 0,
                    "total_duration": 0.0,
                    "word_count": 0,
                }

            entry = stats[label]
            entry["segment_count"] += 1
            entry["total_duration"] += seg["end_time"] - seg["start_time"]
            entry["word_count"] += len(seg["text"].split())

        # Round durations for tidiness.
        for entry in stats.values():
            entry["total_duration"] = round(entry["total_duration"], 4)

        return list(stats.values())
