from app.llm.prompts.base import BasePromptTemplate

MANAGEMENT_PRESENTATION_ANALYSIS = BasePromptTemplate(
    name="management_presentation_analysis",
    version="v1",
    system_prompt="""You are Deal Companion, an expert private equity analyst specializing in the evaluation of management presentations during M&A processes. Your role is to analyze transcripts from management presentations (also known as management meetings or fireside chats) and extract structured intelligence for the deal team.

## Context
Management presentations are formal meetings where the target company's leadership team presents their business to potential buyers or investors. These sessions typically cover the company's story, market opportunity, financial performance, growth strategy, and competitive advantages. Your analysis should help the deal team evaluate the investment thesis and management credibility.

## Your Expertise
- Evaluating management team credibility, preparedness, and depth of knowledge
- Assessing narrative consistency and identifying rehearsed versus authentic responses
- Analyzing the strength of the company's strategic positioning and competitive moat
- Identifying gaps between presented narrative and underlying fundamentals
- Evaluating the quality of growth plans and their supporting evidence
- Detecting overstatements, omissions, and spin in management presentations
- Assessing organizational depth and key-person dependency risks

## Output Requirements
You MUST return valid JSON matching the output schema exactly. Do not include any text outside the JSON object.

## Citation Rules (CRITICAL)
1. Every factual claim, financial figure, and qualitative assessment MUST include a citation.
2. Citations use the format [S:XX] where XX is the segment index number from the transcript.
3. If a finding spans multiple segments, cite all relevant segments: [S:12][S:13][S:14].
4. If you cannot find a source segment for a claim, DO NOT include that claim.
5. Never fabricate or extrapolate financial figures. Only report numbers explicitly stated in the transcript.

## Anti-Hallucination Rules (CRITICAL)
1. Only extract information that is EXPLICITLY stated in the transcript.
2. Do not infer, assume, or extrapolate beyond what speakers directly say.
3. If the transcript does not cover a topic, state "Not discussed in this presentation" for that field.
4. Do not fill in industry benchmarks or typical ranges unless a speaker explicitly mentions them.
5. When management makes forward-looking statements, clearly label them as such.
6. Distinguish between verified claims (backed by data shown) and unverified assertions.
7. Note when management deflects, avoids, or gives vague answers to specific questions.""",
    user_prompt_template="""Analyze the following management presentation transcript and produce a comprehensive structured analysis.

## Transcript
{transcript}

## Instructions
Extract and organize the information from this management presentation into the required JSON structure. Pay special attention to the quality and credibility of management's narrative. Follow all citation and anti-hallucination rules strictly.

Return your analysis as a JSON object matching the output schema.""",
    output_schema={
        "type": "object",
        "required": [
            "executive_summary",
            "company_narrative",
            "management_team_assessment",
            "investment_thesis_components",
            "growth_strategy",
            "financial_highlights",
            "competitive_positioning",
            "risk_factors",
            "narrative_red_flags",
            "information_gaps",
            "follow_up_questions",
        ],
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "2-4 paragraph summary of the management presentation, highlighting the key investment thesis, management credibility assessment, and critical areas for further diligence. Must include citations.",
            },
            "company_narrative": {
                "type": "object",
                "properties": {
                    "founding_story": {"type": "string"},
                    "mission_and_vision": {"type": "string"},
                    "value_proposition": {"type": "string"},
                    "target_market": {"type": "string"},
                    "market_size_tam": {"type": "string"},
                    "market_position": {"type": "string"},
                    "key_differentiators": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "The company story as presented by management. Note what is substantiated versus asserted.",
            },
            "management_team_assessment": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "background_presented": {"type": "string"},
                        "domain_expertise_demonstrated": {
                            "type": "string",
                            "enum": ["strong", "adequate", "weak", "not_assessed"],
                        },
                        "communication_quality": {
                            "type": "string",
                            "enum": ["excellent", "good", "fair", "poor"],
                        },
                        "credibility_notes": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Assessment of each management team member who participated in the presentation.",
            },
            "investment_thesis_components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "thesis_point": {"type": "string"},
                        "evidence_quality": {
                            "type": "string",
                            "enum": ["strong", "moderate", "weak", "unsubstantiated"],
                        },
                        "supporting_data": {"type": "string"},
                        "counterarguments": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "The key components of the investment thesis as presented, with an assessment of how well each is supported.",
            },
            "growth_strategy": {
                "type": "object",
                "properties": {
                    "organic_growth_drivers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "inorganic_growth_plans": {"type": "string"},
                    "new_market_expansion": {"type": "string"},
                    "product_roadmap": {"type": "string"},
                    "growth_investment_required": {"type": "string"},
                    "timeline_and_milestones": {"type": "string"},
                    "credibility_assessment": {
                        "type": "string",
                        "description": "Assessment of how realistic and achievable the growth plans appear.",
                    },
                },
                "description": "Growth strategy as presented by management.",
            },
            "financial_highlights": {
                "type": "object",
                "properties": {
                    "revenue": {"type": "string"},
                    "revenue_growth_rate": {"type": "string"},
                    "recurring_revenue_mix": {"type": "string"},
                    "gross_margin": {"type": "string"},
                    "ebitda_margin": {"type": "string"},
                    "revenue_retention": {"type": "string"},
                    "unit_economics": {"type": "string"},
                    "capital_efficiency": {"type": "string"},
                    "projections_presented": {"type": "string"},
                    "projection_credibility": {"type": "string"},
                },
                "description": "Financial metrics explicitly presented. Use 'Not discussed' for metrics not covered. Include citations.",
            },
            "competitive_positioning": {
                "type": "object",
                "properties": {
                    "competitors_mentioned": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "claimed_advantages": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "barriers_to_entry": {"type": "string"},
                    "switching_costs": {"type": "string"},
                    "market_share_claims": {"type": "string"},
                    "competitive_threats_acknowledged": {"type": "string"},
                },
                "description": "How management positioned the company versus competitors.",
            },
            "risk_factors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "risk": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "category": {"type": "string"},
                        "acknowledged_by_management": {"type": "boolean"},
                        "mitigation_discussed": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Risks identified from the presentation, including both those acknowledged and those not addressed by management.",
            },
            "narrative_red_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "observation": {"type": "string"},
                        "concern": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Red flags in management's narrative: evasive answers, inconsistencies, overstatements, lack of depth, or deflections.",
            },
            "information_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Important topics that were not addressed or insufficiently covered in the presentation.",
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
                "description": "Questions for follow-up sessions based on gaps, inconsistencies, or areas requiring deeper exploration.",
            },
        },
    },
)
