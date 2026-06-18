package deepgram

import "testing"

// A trimmed Deepgram response: two speakers, words carrying punctuated_word +
// speaker + start/end/confidence — the shape ProcessResponse walks.
const sampleResponse = `{
  "results": {
    "channels": [{
      "alternatives": [{
        "words": [
          {"word": "we",      "punctuated_word": "We",       "start": 0.0, "end": 0.3, "confidence": 0.99, "speaker": 0},
          {"word": "reviewed", "punctuated_word": "reviewed", "start": 0.3, "end": 0.8, "confidence": 0.97, "speaker": 0},
          {"word": "ebitda",   "punctuated_word": "EBITDA.",  "start": 0.8, "end": 1.4, "confidence": 0.95, "speaker": 0},
          {"word": "what",     "punctuated_word": "What",     "start": 1.6, "end": 1.9, "confidence": 0.98, "speaker": 1},
          {"word": "margin",   "punctuated_word": "margin?",  "start": 1.9, "end": 2.4, "confidence": 0.90, "speaker": 1},
          {"word": "strong",   "punctuated_word": "Strong.",  "start": 2.6, "end": 3.0, "confidence": 0.93, "speaker": 0}
        ]
      }]
    }]
  }
}`

func TestProcessResponseGroupsBySpeaker(t *testing.T) {
	segs, err := ProcessResponse([]byte(sampleResponse))
	if err != nil {
		t.Fatalf("ProcessResponse: %v", err)
	}
	// Speaker runs: [0,0,0] -> [1,1] -> [0]  => 3 segments.
	if len(segs) != 3 {
		t.Fatalf("got %d segments, want 3: %+v", len(segs), segs)
	}

	if segs[0].SpeakerLabel != "Speaker 0" || segs[0].Text != "We reviewed EBITDA." {
		t.Fatalf("seg0=%+v", segs[0])
	}
	if segs[0].StartTime != 0.0 || segs[0].EndTime != 1.4 {
		t.Fatalf("seg0 times=%v..%v want 0..1.4", segs[0].StartTime, segs[0].EndTime)
	}
	// avg(0.99,0.97,0.95)=0.9700 rounded to 4dp.
	if segs[0].Confidence != 0.97 {
		t.Fatalf("seg0 conf=%v want 0.97", segs[0].Confidence)
	}

	if segs[1].SpeakerLabel != "Speaker 1" || segs[1].Text != "What margin?" {
		t.Fatalf("seg1=%+v", segs[1])
	}
	if segs[2].SpeakerLabel != "Speaker 0" || segs[2].Text != "Strong." || segs[2].SegmentIndex != 2 {
		t.Fatalf("seg2=%+v", segs[2])
	}
	// punctuated_word preferred over word.
	if segs[1].SpeakerName != "Speaker 1" {
		t.Fatalf("seg1 speaker_name=%q", segs[1].SpeakerName)
	}
}

func TestProcessResponseEmpty(t *testing.T) {
	for _, in := range []string{
		`{"results":{"channels":[]}}`,
		`{"results":{"channels":[{"alternatives":[{"words":[]}]}]}}`,
		`{"results":{}}`,
	} {
		segs, err := ProcessResponse([]byte(in))
		if err != nil {
			t.Fatalf("ProcessResponse(%s): %v", in, err)
		}
		if len(segs) != 0 {
			t.Fatalf("ProcessResponse(%s): got %d segments, want 0", in, len(segs))
		}
	}
}

func TestProcessResponseMissingSpeakerIsOneGroup(t *testing.T) {
	// No speaker key on any word (diarize off / mono) -> all nil -> one segment.
	in := `{"results":{"channels":[{"alternatives":[{"words":[
	  {"punctuated_word":"Hello","start":0,"end":0.5,"confidence":0.9},
	  {"punctuated_word":"there","start":0.5,"end":1.0,"confidence":0.8}
	]}]}]}}`
	segs, err := ProcessResponse([]byte(in))
	if err != nil {
		t.Fatalf("ProcessResponse: %v", err)
	}
	if len(segs) != 1 || segs[0].Text != "Hello there" || segs[0].SpeakerLabel != "Speaker 0" {
		t.Fatalf("segs=%+v", segs)
	}
}
