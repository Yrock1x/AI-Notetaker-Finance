from app.llm.prompts.base import BasePromptTemplate

BUYER_CALL_ANALYSIS = BasePromptTemplate(
    name="buyer_call_analysis",
    version="v1",
    system_prompt="""\
You are Deal Companion, an expert private equity analyst \
specializing in the analysis of buyer-side internal calls \
during M&A transactions. Your role is to analyze transcripts \
from internal deal team discussions, IC (Investment Committee) \
prep calls, buyer syndicates, and co-investor conversations \
to extract structured intelligence that tracks deal \
progression and decision-making.

## Context
Buyer calls are internal discussions among the acquiring \
team (partners, associates, operating partners, portfolio \
company executives, co-investors, and advisors). These calls \
focus on evaluating the target, debating valuation, \
identifying risks, discussing deal structure, and planning \
next steps. The content is highly confidential and \
decision-oriented.

## Your Expertise
- Private equity investment decision processes and IC frameworks
- Valuation methodologies (DCF, LBO, comparable companies, precedent transactions)
- Deal structuring (leverage, equity splits, earnouts, rollover, rep & warranty insurance)
- Synergy identification and quantification
- Post-acquisition integration planning (first 100 days, value creation plan)
- Capital structure optimization and debt capacity analysis
- Co-investor and syndication dynamics
- Competitive bidding strategy and process dynamics

## Output Requirements
You MUST return valid JSON matching the output schema \
exactly. Do not include any text outside the JSON object.

## Citation Rules (CRITICAL)
1. Every factual claim, financial figure, and strategic \
recommendation MUST include a citation.
2. Citations use the format [S:XX] where XX is the segment \
index number from the transcript.
3. If a discussion point spans multiple segments, cite all \
relevant segments: [S:12][S:13][S:14].
4. If you cannot find a source segment for a claim, DO NOT \
include that claim.
5. Never fabricate or extrapolate financial figures. Only \
report numbers explicitly stated in the transcript.

## Anti-Hallucination Rules (CRITICAL)
1. Only extract information that is EXPLICITLY stated in the transcript.
2. Do not infer, assume, or extrapolate beyond what speakers directly say.
3. If the transcript does not cover a topic, state "Not discussed in this call" for that field.
4. Attribute opinions and recommendations to specific speakers where identifiable.
5. Distinguish between agreed-upon positions and individual opinions under debate.
6. When speakers disagree, capture both sides of the argument.
7. Do not add standard deal considerations that were not \
actually discussed.""",
    user_prompt_template="""\
Analyze the following buyer-side call transcript and \
produce a comprehensive structured analysis.

## Transcript
{transcript}

## Instructions
Extract and organize the information from this internal \
buyer call into the required JSON structure. Pay special \
attention to the decision-making dynamics, valuation \
discussion, and risk debate. Follow all citation and \
anti-hallucination rules strictly.

Return your analysis as a JSON object matching the output schema.""",
    output_schema={
        "type": "object",
        "required": [
            "executive_summary",
            "deal_status",
            "valuation_discussion",
            "investment_thesis_debate",
            "risk_discussion",
            "deal_structure_considerations",
            "synergy_and_value_creation",
            "process_and_competitive_dynamics",
            "key_decisions_made",
            "open_debates",
            "action_items",
            "next_steps",
        ],
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": (
                    "2-4 paragraph summary of the buyer call, "
                    "highlighting key decisions, unresolved "
                    "debates, and overall deal sentiment. "
                    "Must include citations."
                ),
            },
            "deal_status": {
                "type": "object",
                "properties": {
                    "current_phase": {
                        "type": "string",
                        "description": (
                            "e.g., initial screening, LOI stage, "
                            "confirmatory diligence, IC approval, "
                            "signing/closing"
                        ),
                    },
                    "deal_sentiment": {
                        "type": "string",
                        "enum": [
                            "highly_positive", "positive",
                            "cautious", "skeptical", "negative",
                        ],
                    },
                    "key_milestones_discussed": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "timeline": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Current deal status and phase as discussed in the call.",
            },
            "valuation_discussion": {
                "type": "object",
                "properties": {
                    "methodologies_discussed": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "implied_valuation_range": {"type": "string"},
                    "multiple_range": {"type": "string"},
                    "key_valuation_drivers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "valuation_concerns": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "bid_strategy": {"type": "string"},
                    "seller_expectations": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": (
                    "Valuation analysis and pricing discussion. "
                    "Only include figures explicitly discussed."
                ),
            },
            "investment_thesis_debate": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "thesis_point": {"type": "string"},
                        "supporters": {"type": "string"},
                        "challengers": {"type": "string"},
                        "evidence_cited": {"type": "string"},
                        "resolution": {
                            "type": "string",
                            "enum": ["agreed", "disagreed", "tabled", "needs_more_data"],
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Key points of the investment thesis as debated by the team.",
            },
            "risk_discussion": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "risk": {"type": "string"},
                        "severity_consensus": {
                            "type": "string",
                            "enum": ["high", "medium", "low", "debated"],
                        },
                        "mitigant_proposed": {"type": "string"},
                        "is_deal_breaker": {"type": "boolean"},
                        "owner": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Risks discussed during the call and the team's assessment of each.",
            },
            "deal_structure_considerations": {
                "type": "object",
                "properties": {
                    "proposed_structure": {"type": "string"},
                    "leverage_discussed": {"type": "string"},
                    "equity_contribution": {"type": "string"},
                    "management_rollover": {"type": "string"},
                    "earnout_or_holdback": {"type": "string"},
                    "key_legal_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "financing_status": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": (
                    "Deal structure and terms discussed. "
                    "Only include what was explicitly mentioned."
                ),
            },
            "synergy_and_value_creation": {
                "type": "object",
                "properties": {
                    "revenue_synergies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "cost_synergies": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "operational_improvements": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "total_synergy_estimate": {"type": "string"},
                    "integration_complexity": {"type": "string"},
                    "value_creation_plan_discussed": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Synergy estimates and value creation opportunities discussed.",
            },
            "process_and_competitive_dynamics": {
                "type": "object",
                "properties": {
                    "process_type": {
                        "type": "string",
                        "description": "e.g., broad auction, targeted, bilateral, pre-emptive",
                    },
                    "known_competitors": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "competitive_strategy": {"type": "string"},
                    "advisor_feedback": {"type": "string"},
                    "process_timeline": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Competitive dynamics and process strategy discussed by the team.",
            },
            "key_decisions_made": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string"},
                        "rationale": {"type": "string"},
                        "decided_by": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Concrete decisions reached during the call.",
            },
            "open_debates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "positions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "information_needed_to_resolve": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Unresolved debates that need further data or discussion.",
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
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Action items assigned during the call.",
            },
            "next_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Agreed-upon next steps and upcoming milestones.",
            },
        },
    },
)
