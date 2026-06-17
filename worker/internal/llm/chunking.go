package llm

import (
	"regexp"
	"strings"
)

// EstimateTokens is the rough word-count*4/3 estimate from app/llm/chunking.py.
func EstimateTokens(text string) int {
	return len(strings.Fields(text)) * 4 / 3
}

// Chunk is an embeddable unit (ports the Chunk dataclass).
type Chunk struct {
	Text       string
	Index      int
	SourceType string // transcript_segment | document_chunk
	SourceID   string
	Metadata   map[string]any
}

// Segment is one transcript segment fed to the transcript chunker.
type Segment struct {
	ID           string
	SpeakerLabel string
	SpeakerName  string
	Text         string
	StartTime    float64
	EndTime      float64
}

// ChunkSegments groups transcript segments into ~500-token overlapping windows
// with speaker attribution (ports TranscriptChunker.chunk_segments).
func ChunkSegments(segments []Segment, maxChunkTokens, overlapTokens int) []Chunk {
	if len(segments) == 0 {
		return nil
	}
	type line struct {
		text   string
		tokens int
		seg    Segment
	}
	annotated := make([]line, len(segments))
	for i, s := range segments {
		speaker := s.SpeakerName
		if speaker == "" {
			speaker = s.SpeakerLabel
		}
		if speaker == "" {
			speaker = "Unknown"
		}
		lt := speaker + ": " + strings.TrimSpace(s.Text)
		annotated[i] = line{text: lt, tokens: EstimateTokens(lt), seg: s}
	}

	var chunks []Chunk
	chunkIndex, i := 0, 0
	for i < len(annotated) {
		var lines []string
		var segIDs []string
		tokenCount := 0
		startTime := annotated[i].seg.StartTime
		endTime := annotated[i].seg.EndTime
		j := i
		for j < len(annotated) {
			lt := annotated[j].tokens
			if tokenCount+lt > maxChunkTokens && len(lines) > 0 {
				break
			}
			lines = append(lines, annotated[j].text)
			tokenCount += lt
			segIDs = append(segIDs, annotated[j].seg.ID)
			endTime = annotated[j].seg.EndTime
			j++
		}
		sourceID := ""
		if len(segIDs) > 0 {
			sourceID = segIDs[0]
		}
		chunks = append(chunks, Chunk{
			Text: strings.Join(lines, "\n"), Index: chunkIndex,
			SourceType: "transcript_segment", SourceID: sourceID,
			Metadata: map[string]any{"segment_ids": segIDs, "start_time": startTime,
				"end_time": endTime, "segment_count": len(lines)},
		})
		chunkIndex++
		if j >= len(annotated) {
			break
		}
		// overlap: back up until ~overlapTokens accumulated
		overlapAccum, overlapStart := 0, j
		for k := j - 1; k >= i; k-- {
			overlapAccum += annotated[k].tokens
			if overlapAccum >= overlapTokens {
				overlapStart = k
				break
			}
		}
		if overlapStart <= i {
			overlapStart = i + 1
		}
		i = overlapStart
	}
	return chunks
}

var paraSplit = regexp.MustCompile(`\n\s*\n`)
var sentenceSplit = regexp.MustCompile(`(?:[.!?])\s+`)

// ChunkText splits document text into ~500-token overlapping windows by
// paragraph then sentence (ports DocumentChunker.chunk_text).
func ChunkText(text, sourceID string, maxChunkTokens, overlapTokens int) []Chunk {
	if strings.TrimSpace(text) == "" {
		return nil
	}
	var paras []string
	for _, p := range paraSplit.Split(strings.TrimSpace(text), -1) {
		if s := strings.TrimSpace(p); s != "" {
			paras = append(paras, s)
		}
	}
	var units []string
	for _, p := range paras {
		if EstimateTokens(p) <= maxChunkTokens {
			units = append(units, p)
			continue
		}
		for _, s := range sentenceSplit.Split(p, -1) {
			if s = strings.TrimSpace(s); s != "" {
				units = append(units, s)
			}
		}
	}
	if len(units) == 0 {
		return nil
	}

	var chunks []Chunk
	chunkIndex, i := 0, 0
	for i < len(units) {
		var parts []string
		tokenCount, j := 0, i
		for j < len(units) {
			ut := EstimateTokens(units[j])
			if tokenCount+ut > maxChunkTokens && len(parts) > 0 {
				break
			}
			parts = append(parts, units[j])
			tokenCount += ut
			j++
		}
		charStart := 0
		if len(parts) > 0 {
			charStart = strings.Index(text, parts[0])
		}
		chunks = append(chunks, Chunk{
			Text: strings.Join(parts, "\n\n"), Index: chunkIndex,
			SourceType: "document_chunk", SourceID: sourceID,
			Metadata: map[string]any{"char_start": charStart, "unit_count": len(parts)},
		})
		chunkIndex++
		if j >= len(units) {
			break
		}
		overlapAccum, overlapStart := 0, j
		for k := j - 1; k >= i; k-- {
			overlapAccum += EstimateTokens(units[k])
			if overlapAccum >= overlapTokens {
				overlapStart = k
				break
			}
		}
		if overlapStart <= i {
			overlapStart = i + 1
		}
		i = overlapStart
	}
	return chunks
}
