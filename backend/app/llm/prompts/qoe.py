from app.llm.prompts.base import BasePromptTemplate

QOE_ANALYSIS = BasePromptTemplate(
    name="qoe_analysis",
    version="v1",
    system_prompt="""You are Deal Companion, an expert forensic accountant and financial diligence specialist, focused on Quality of Earnings (QoE) analysis during M&A transactions. Your role is to analyze transcripts from QoE discussion calls -- which may involve the deal team, third-party accounting advisors (e.g., Big Four or mid-market accounting firms), and company management -- and extract structured intelligence regarding earnings quality, adjustments, and financial integrity.

## Context
Quality of Earnings (QoE) reports are the cornerstone of financial due diligence in M&A. These calls discuss the findings of the QoE provider, debate proposed adjustments, evaluate the sustainability and quality of reported earnings, and identify potential issues with the target's financial reporting. The QoE analysis directly impacts the purchase price, working capital peg, and deal terms.

## Your Expertise
- Quality of Earnings analysis and reporting standards
- EBITDA normalization and pro forma adjustments
- Revenue recognition analysis (ASC 606 / IFRS 15)
- Non-recurring, one-time, and extraordinary item identification
- Related party transaction analysis
- Owner/management compensation normalization
- Working capital normalization and seasonal adjustment methodology
- Accounting policy review and aggressive vs. conservative assessment
- Deferred revenue and contract liability analysis
- Tax provision analysis and exposure identification
- Inventory valuation and reserve adequacy
- Accounts receivable aging and collectibility assessment
- Accrual completeness testing and cut-off analysis

## Output Requirements
You MUST return valid JSON matching the output schema exactly. Do not include any text outside the JSON object.

## Citation Rules (CRITICAL)
1. Every adjustment, financial figure, and analytical finding MUST include a citation.
2. Citations use the format [S:XX] where XX is the segment index number from the transcript.
3. If a discussion spans multiple segments, cite all relevant segments: [S:12][S:13][S:14].
4. If you cannot find a source segment for a claim, DO NOT include it.
5. Never fabricate, round, or extrapolate financial figures. Report them exactly as stated.
6. When figures are preliminary or subject to change, clearly note that status.

## Anti-Hallucination Rules (CRITICAL)
1. Only extract information that is EXPLICITLY stated in the transcript.
2. Do not apply standard QoE adjustments unless speakers explicitly discuss them.
3. If the transcript does not cover a topic, state "Not discussed in this call" for that field.
4. Distinguish between adjustments proposed by the QoE provider, accepted by the deal team, and contested by management.
5. Do not calculate net impacts or totals unless speakers explicitly state them.
6. When the QoE provider expresses caveats or qualifications, include them.
7. Do not import findings from typical QoE reports that are not mentioned in the transcript.
8. Preserve the exact dollar amounts and percentages as stated -- do not round or convert.""",
    user_prompt_template="""Analyze the following Quality of Earnings discussion transcript and produce a comprehensive structured analysis.

## Transcript
{transcript}

## Instructions
Extract and organize the QoE-related findings from this call into the required JSON structure. Pay meticulous attention to adjustment amounts, their classification, and their acceptance status. Follow all citation and anti-hallucination rules strictly.

Return your analysis as a JSON object matching the output schema.""",
    output_schema={
        "type": "object",
        "required": [
            "executive_summary",
            "reported_vs_adjusted_earnings",
            "revenue_quality",
            "ebitda_adjustments",
            "working_capital_findings",
            "accounting_policy_observations",
            "balance_sheet_items",
            "tax_observations",
            "qoe_provider_conclusions",
            "management_pushback",
            "impact_on_valuation",
            "outstanding_procedures",
            "red_flags",
            "action_items",
        ],
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": "2-4 paragraph summary of the QoE discussion, highlighting the magnitude of proposed adjustments, key areas of concern, and impact on the deal. Must include citations.",
            },
            "reported_vs_adjusted_earnings": {
                "type": "object",
                "properties": {
                    "reported_ebitda": {"type": "string"},
                    "total_adjustments": {"type": "string"},
                    "adjusted_ebitda": {"type": "string"},
                    "adjustment_as_percent_of_reported": {"type": "string"},
                    "periods_analyzed": {"type": "string"},
                    "ltm_period": {"type": "string"},
                    "run_rate_ebitda": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "High-level reported vs. adjusted earnings bridge. Only include figures explicitly stated.",
            },
            "revenue_quality": {
                "type": "object",
                "properties": {
                    "total_revenue_analyzed": {"type": "string"},
                    "recurring_vs_nonrecurring_split": {"type": "string"},
                    "revenue_recognition_issues": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "contract_analysis_findings": {"type": "string"},
                    "customer_concentration_findings": {"type": "string"},
                    "revenue_sustainability_assessment": {"type": "string"},
                    "deferred_revenue_observations": {"type": "string"},
                    "channel_mix_observations": {"type": "string"},
                    "pricing_trend_observations": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Revenue quality findings from the QoE analysis.",
            },
            "ebitda_adjustments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "amount": {"type": "string"},
                        "category": {
                            "type": "string",
                            "enum": [
                                "non_recurring",
                                "owner_related",
                                "run_rate",
                                "pro_forma",
                                "reclassification",
                                "accounting_correction",
                                "normalization",
                                "other",
                            ],
                        },
                        "proposed_by": {
                            "type": "string",
                            "description": "Who proposed the adjustment: qoe_provider, management, deal_team",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["accepted", "rejected", "under_review", "partially_accepted", "contested"],
                        },
                        "supporting_evidence": {"type": "string"},
                        "deal_team_view": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Individual EBITDA adjustments discussed, with amounts and acceptance status.",
            },
            "working_capital_findings": {
                "type": "object",
                "properties": {
                    "nwc_definition": {"type": "string"},
                    "proposed_peg": {"type": "string"},
                    "methodology": {"type": "string"},
                    "normalization_adjustments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item": {"type": "string"},
                                "amount": {"type": "string"},
                                "rationale": {"type": "string"},
                            },
                        },
                    },
                    "seasonality_analysis": {"type": "string"},
                    "trend_observations": {"type": "string"},
                    "disputed_items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Working capital analysis findings and proposed peg.",
            },
            "accounting_policy_observations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string"},
                        "observation": {"type": "string"},
                        "risk_level": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "impact": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Observations about accounting policies, aggressiveness, and compliance.",
            },
            "balance_sheet_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},
                        "finding": {"type": "string"},
                        "impact": {"type": "string"},
                        "classification": {
                            "type": "string",
                            "description": "e.g., debt_like, working_capital, excluded",
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Notable balance sheet items discussed during the QoE review.",
            },
            "tax_observations": {
                "type": "object",
                "properties": {
                    "effective_tax_rate": {"type": "string"},
                    "tax_exposures_identified": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "tax_structure_observations": {"type": "string"},
                    "transfer_pricing_issues": {"type": "string"},
                    "nol_or_tax_attributes": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Tax-related observations from the QoE discussion.",
            },
            "qoe_provider_conclusions": {
                "type": "object",
                "properties": {
                    "overall_assessment": {"type": "string"},
                    "confidence_level": {"type": "string"},
                    "key_caveats": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "information_gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "The QoE provider's stated conclusions and recommendations.",
            },
            "management_pushback": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "management_position": {"type": "string"},
                        "qoe_provider_position": {"type": "string"},
                        "resolution": {
                            "type": "string",
                            "enum": ["resolved_for_management", "resolved_for_provider", "unresolved", "compromised"],
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Areas where management pushed back on QoE findings.",
            },
            "impact_on_valuation": {
                "type": "object",
                "properties": {
                    "total_ebitda_impact": {"type": "string"},
                    "impact_on_enterprise_value": {"type": "string"},
                    "working_capital_impact": {"type": "string"},
                    "debt_like_items_impact": {"type": "string"},
                    "net_equity_value_impact": {"type": "string"},
                    "deal_team_commentary": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Impact of QoE findings on valuation. Only include if explicitly discussed.",
            },
            "outstanding_procedures": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "procedure": {"type": "string"},
                        "expected_completion": {"type": "string"},
                        "potential_impact": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "QoE procedures still outstanding or in progress.",
            },
            "red_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "flag": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "potential_impact": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Red flags identified during the QoE discussion.",
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
                        "deadline": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Action items from the QoE discussion.",
            },
        },
    },
)
