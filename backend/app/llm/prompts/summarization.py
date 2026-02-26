from app.llm.prompts.base import BasePromptTemplate

MEETING_SUMMARIZATION = BasePromptTemplate(
    name="meeting_summarization",
    version="v1",
    system_prompt="""You are DealWise AI, an expert meeting summarization assistant for private equity and M&A professionals. Your role is to produce clear, actionable summaries of deal-related meetings from transcripts.

## Your Role
You produce meeting summaries that are immediately useful to busy deal professionals. Your summaries should allow someone who missed the meeting to quickly understand what was discussed, what was decided, and what needs to happen next.

## Summary Principles
1. CONCISENESS: Be thorough but not verbose. Prioritize signal over noise.
2. STRUCTURE: Use clear headings and bullet points for scannability.
3. ACTIONABILITY: Highlight decisions made, action items assigned, and deadlines committed.
4. ATTRIBUTION: Note who said what when it matters for accountability or context.
5. PRIORITIZATION: Lead with the most important topics and decisions.
6. CONTEXT: Provide enough context for each point to be understood in isolation.

## Output Requirements
You MUST return valid JSON matching the output schema exactly. Do not include any text outside the JSON object.

## Citation Rules (CRITICAL)
1. Every factual claim and attributed statement MUST include a citation.
2. Citations use the format [S:XX] where XX is the segment index number from the transcript.
3. If a topic spans multiple segments, cite the most relevant segment or use ranges: [S:12][S:13].
4. If you cannot find a source segment for a claim, DO NOT include that claim.

## Anti-Hallucination Rules (CRITICAL)
1. Only extract information that is EXPLICITLY stated in the transcript.
2. Do not infer conclusions that were not reached in the meeting.
3. Do not add action items that were not discussed or assigned.
4. If participants left a topic unresolved, report it as unresolved.
5. Do not invent attendee names or roles not mentioned in the transcript.
6. If timing or deadlines are vague in the transcript, report them as vague.
7. Preserve the speakers' actual level of certainty (do not upgrade "maybe" to "will").""",
    user_prompt_template="""Summarize the following meeting transcript into a structured, actionable meeting summary.

## Meeting Information
Meeting Type: {meeting_type}
Deal Name: {deal_name}

## Transcript
{transcript}

## Instructions
Produce a comprehensive yet concise meeting summary. Capture all key discussion points, decisions, and action items. Follow all citation and anti-hallucination rules strictly.

Return your summary as a JSON object matching the output schema.""",
    output_schema={
        "type": "object",
        "required": [
            "meeting_metadata",
            "executive_summary",
            "key_topics_discussed",
            "decisions_made",
            "action_items",
            "key_takeaways",
            "parking_lot",
            "next_meeting_agenda_suggestions",
        ],
        "properties": {
            "meeting_metadata": {
                "type": "object",
                "properties": {
                    "meeting_type": {"type": "string"},
                    "deal_name": {"type": "string"},
                    "participants_identified": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"},
                                "affiliation": {"type": "string"},
                            },
                        },
                    },
                    "duration_estimate": {
                        "type": "string",
                        "description": "Estimated meeting duration based on transcript length and timestamps if available.",
                    },
                    "overall_tone": {
                        "type": "string",
                        "enum": ["positive", "constructive", "neutral", "tense", "contentious"],
                    },
                },
                "description": "Basic meeting metadata extracted from the transcript.",
            },
            "executive_summary": {
                "type": "string",
                "description": "2-3 paragraph summary covering the purpose of the meeting, key outcomes, and most important takeaways. Must include citations.",
            },
            "key_topics_discussed": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "summary": {"type": "string"},
                        "key_points": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["resolved", "partially_resolved", "tabled", "needs_follow_up"],
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Major topics discussed during the meeting, in order of importance.",
            },
            "decisions_made": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string"},
                        "rationale": {"type": "string"},
                        "decided_by": {"type": "string"},
                        "implications": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Explicit decisions made during the meeting.",
            },
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "owner": {"type": "string"},
                        "deadline": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "context": {
                            "type": "string",
                            "description": "Brief context on why this action item was assigned.",
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Action items assigned during the meeting. Only include items explicitly discussed.",
            },
            "key_takeaways": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "takeaway": {"type": "string"},
                        "significance": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "The top 3-7 takeaways from the meeting, ranked by importance.",
            },
            "parking_lot": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "reason_deferred": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Topics raised but deferred or left for future discussion.",
            },
            "next_meeting_agenda_suggestions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggested agenda items for the next meeting based on unresolved topics and action items.",
            },
        },
    },
)
