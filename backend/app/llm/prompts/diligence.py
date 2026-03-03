from app.llm.prompts.base import BasePromptTemplate

DILIGENCE_CALL_ANALYSIS = BasePromptTemplate(
    name="diligence_call_analysis",
    version="v1",
    system_prompt="""\
You are Deal Companion, an expert private equity due \
diligence analyst. Your role is to analyze transcripts from \
due diligence calls conducted during M&A transactions and \
produce structured, actionable intelligence for deal teams.

## Your Expertise
You have deep domain knowledge in:
- Private equity due diligence processes (buy-side and sell-side)
- Financial statement analysis (income statement, balance sheet, cash flow)
- Revenue quality and sustainability assessment
- Customer concentration and churn analysis
- Management team evaluation and red flag detection
- Working capital normalization and adjustments
- EBITDA add-backs and quality of earnings considerations
- Market sizing, competitive positioning, and TAM/SAM/SOM analysis
- Regulatory and compliance risk identification
- Integration planning considerations

## Output Requirements
You MUST return valid JSON matching the output schema \
exactly. Do not include any text outside the JSON object.

## Citation Rules (CRITICAL)
1. Every factual claim, financial figure, and qualitative \
assessment MUST include a citation.
2. Citations use the format [S:XX] where XX is the segment \
index number from the transcript.
3. If a finding spans multiple segments, cite all relevant \
segments: [S:12][S:13][S:14].
4. If you cannot find a source segment for a claim, DO NOT \
include that claim.
5. Never fabricate or extrapolate financial figures. Only \
report numbers explicitly stated in the transcript.
6. If a metric is discussed qualitatively but no specific \
number is given, describe it qualitatively and note that no \
specific figure was provided.

## Anti-Hallucination Rules (CRITICAL)
1. Only extract information that is EXPLICITLY stated in the transcript.
2. Do not infer, assume, or extrapolate beyond what speakers directly say.
3. If the transcript does not cover a topic, state "Not discussed in this call" for that field.
4. Do not fill in industry benchmarks or typical ranges unless a speaker explicitly mentions them.
5. When speakers express uncertainty, reflect that uncertainty in your output.
6. Distinguish clearly between facts stated by management \
and opinions/assessments from the deal team.
7. If financial figures are approximate (e.g., "roughly $10 million"), note the approximation.

## Quality Standards
- Be specific and quantitative wherever possible
- Flag contradictions between different speakers
- Highlight information gaps that need follow-up
- Prioritize risk flags by severity (high, medium, low)
- Note the speaker identity when attributing statements""",
    user_prompt_template="""\
Analyze the following due diligence call transcript and \
produce a comprehensive structured analysis.

## Transcript
{transcript}

## Instructions
Extract and organize the information from this transcript \
into the required JSON structure. Follow all citation and \
anti-hallucination rules strictly. Every claim must be \
traceable to a specific transcript segment.

Return your analysis as a JSON object matching the output schema.""",
    output_schema={
        "type": "object",
        "required": [
            "executive_summary",
            "company_overview",
            "key_findings",
            "risk_flags",
            "financial_metrics_discussed",
            "management_quality_indicators",
            "action_items",
            "follow_up_questions",
        ],
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": (
                    "2-4 paragraph high-level summary of the "
                    "call covering the most important takeaways "
                    "for the deal team. Must include citations."
                ),
            },
            "company_overview": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "industry": {"type": "string"},
                    "description": {"type": "string"},
                    "business_model": {"type": "string"},
                    "key_products_services": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "geographic_presence": {"type": "string"},
                    "employee_count": {"type": "string"},
                    "founding_year": {"type": "string"},
                },
                "description": (
                    "Basic company information extracted from "
                    "the call. Use 'Not discussed' for fields "
                    "not covered."
                ),
            },
            "key_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": [
                                "revenue",
                                "profitability",
                                "growth",
                                "customers",
                                "market",
                                "operations",
                                "technology",
                                "legal",
                                "regulatory",
                                "management",
                                "other",
                            ],
                        },
                        "finding": {"type": "string"},
                        "significance": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "sentiment": {
                            "type": "string",
                            "enum": ["positive", "negative", "neutral"],
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": (
                    "Structured list of key findings from the "
                    "call, each with category, significance, "
                    "and citations."
                ),
            },
            "risk_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "risk": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "category": {
                            "type": "string",
                            "enum": [
                                "financial",
                                "operational",
                                "market",
                                "legal",
                                "management",
                                "customer",
                                "technology",
                                "regulatory",
                            ],
                        },
                        "mitigation_discussed": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Risk flags identified from the call, ordered by severity.",
            },
            "financial_metrics_discussed": {
                "type": "object",
                "properties": {
                    "revenue": {"type": "string"},
                    "revenue_growth": {"type": "string"},
                    "gross_margin": {"type": "string"},
                    "ebitda": {"type": "string"},
                    "ebitda_margin": {"type": "string"},
                    "net_income": {"type": "string"},
                    "cash_flow": {"type": "string"},
                    "debt": {"type": "string"},
                    "capex": {"type": "string"},
                    "working_capital": {"type": "string"},
                    "customer_metrics": {"type": "string"},
                    "other_metrics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                                "citation": {"type": "string"},
                            },
                        },
                    },
                },
                "description": (
                    "Financial metrics explicitly mentioned in "
                    "the call. Use 'Not discussed' for metrics "
                    "not covered. Include citations with every "
                    "figure."
                ),
            },
            "management_quality_indicators": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "indicator": {"type": "string"},
                        "assessment": {
                            "type": "string",
                            "enum": ["strong", "adequate", "concerning", "insufficient_data"],
                        },
                        "evidence": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": (
                    "Indicators of management team quality, "
                    "depth, and credibility based on their "
                    "responses during the call."
                ),
            },
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "owner": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "deadline_mentioned": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": (
                    "Action items explicitly mentioned or "
                    "strongly implied by the discussion."
                ),
            },
            "follow_up_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "rationale": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "target_respondent": {"type": "string"},
                    },
                },
                "description": (
                    "Questions that should be asked in "
                    "subsequent calls or data requests, based "
                    "on gaps or ambiguities identified in the "
                    "transcript."
                ),
            },
        },
    },
)
