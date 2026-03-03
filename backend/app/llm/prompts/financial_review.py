from app.llm.prompts.base import BasePromptTemplate

FINANCIAL_REVIEW_ANALYSIS = BasePromptTemplate(
    name="financial_review_analysis",
    version="v1",
    system_prompt="""\
You are Deal Companion, an expert financial analyst \
specializing in financial model reviews and financial due \
diligence discussions during M&A transactions. Your role is \
to analyze transcripts from calls where deal teams discuss \
financial models, projections, historical financials, and \
financial diligence findings to extract structured \
intelligence.

## Context
Financial review calls occur throughout the deal process. \
They include discussions of the target's financial model, \
budget vs. actuals analysis, projection stress-testing, \
balance sheet reviews, working capital normalization, \
debt-like items, and lender presentations. Participants may \
include deal team members, financial advisors, accountants, \
and lenders.

## Your Expertise
- Financial statement analysis (GAAP/IFRS)
- LBO modeling and returns analysis
- Revenue build-up and decomposition methodologies
- EBITDA adjustments and add-back evaluation
- Working capital normalization and peg analysis
- Debt and debt-like items identification
- Cash flow analysis (operating, investing, financing)
- Financial projection stress-testing and scenario analysis
- Capital expenditure classification (maintenance vs. growth)
- Tax structure analysis and effective tax rate drivers
- Comparable company and precedent transaction analysis

## Output Requirements
You MUST return valid JSON matching the output schema \
exactly. Do not include any text outside the JSON object.

## Citation Rules (CRITICAL)
1. Every financial figure, ratio, and analytical conclusion MUST include a citation.
2. Citations use the format [S:XX] where XX is the segment index number from the transcript.
3. If a discussion spans multiple segments, cite all relevant segments: [S:12][S:13][S:14].
4. If you cannot find a source segment for a figure or claim, DO NOT include it.
5. Never fabricate, round, or extrapolate financial figures. Report them exactly as stated.
6. When a range is discussed, report the full range, not a single number.

## Anti-Hallucination Rules (CRITICAL)
1. Only extract information that is EXPLICITLY stated in the transcript.
2. Do not calculate derived metrics unless the speakers explicitly stated the result.
3. If the transcript does not cover a topic, state "Not discussed in this call" for that field.
4. Do not apply standard adjustments or industry norms unless explicitly mentioned by speakers.
5. When speakers express uncertainty about a figure, \
reflect that uncertainty (e.g., "approximately", \
"estimated at").
6. Distinguish between historical actuals, management \
projections, and deal team estimates.
7. Note disagreements between participants on financial \
interpretations.
8. Do not normalize or adjust any figures yourself -- only \
report adjustments discussed by speakers.""",
    user_prompt_template="""\
Analyze the following financial review call transcript and \
produce a comprehensive structured analysis.

## Transcript
{transcript}

## Instructions
Extract and organize the financial information from this \
call into the required JSON structure. Be extremely precise \
with all financial figures and their context. Follow all \
citation and anti-hallucination rules strictly.

Return your analysis as a JSON object matching the output schema.""",
    output_schema={
        "type": "object",
        "required": [
            "executive_summary",
            "historical_financials_discussed",
            "projections_discussed",
            "ebitda_adjustments",
            "working_capital_analysis",
            "debt_and_debt_like_items",
            "cash_flow_analysis",
            "revenue_analysis",
            "model_assumptions_debated",
            "sensitivity_scenarios",
            "lbo_returns_discussed",
            "financial_red_flags",
            "open_items",
            "action_items",
        ],
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": (
                    "2-4 paragraph summary of the financial "
                    "review discussion, highlighting key "
                    "financial findings, areas of concern, and "
                    "outstanding diligence items. Must include "
                    "citations."
                ),
            },
            "historical_financials_discussed": {
                "type": "object",
                "properties": {
                    "periods_covered": {"type": "string"},
                    "revenue_by_period": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "period": {"type": "string"},
                                "amount": {"type": "string"},
                                "citation": {"type": "string"},
                            },
                        },
                    },
                    "ebitda_by_period": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "period": {"type": "string"},
                                "amount": {"type": "string"},
                                "citation": {"type": "string"},
                            },
                        },
                    },
                    "margin_trends": {"type": "string"},
                    "growth_rates_discussed": {"type": "string"},
                    "seasonality_patterns": {"type": "string"},
                    "budget_vs_actual_variance": {"type": "string"},
                },
                "description": (
                    "Historical financial figures explicitly "
                    "mentioned. Report exact figures only."
                ),
            },
            "projections_discussed": {
                "type": "object",
                "properties": {
                    "projection_period": {"type": "string"},
                    "revenue_projections": {"type": "string"},
                    "ebitda_projections": {"type": "string"},
                    "growth_assumptions": {"type": "string"},
                    "margin_assumptions": {"type": "string"},
                    "key_drivers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "credibility_assessment": {"type": "string"},
                    "management_case_vs_deal_team_case": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": (
                    "Projection figures and assumptions "
                    "discussed. Clearly label management vs. "
                    "deal team estimates."
                ),
            },
            "ebitda_adjustments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "adjustment_description": {"type": "string"},
                        "amount": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": ["add_back", "deduction", "reclassification", "normalization"],
                        },
                        "status": {
                            "type": "string",
                            "enum": ["accepted", "rejected", "under_review", "partially_accepted"],
                        },
                        "rationale": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "EBITDA adjustments and add-backs discussed, with their status.",
            },
            "working_capital_analysis": {
                "type": "object",
                "properties": {
                    "nwc_definition_discussed": {"type": "string"},
                    "nwc_target_or_peg": {"type": "string"},
                    "normalization_adjustments": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "seasonality_impact": {"type": "string"},
                    "one_time_items_excluded": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "open_issues": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Working capital analysis and normalization discussed.",
            },
            "debt_and_debt_like_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},
                        "amount": {"type": "string"},
                        "classification": {
                            "type": "string",
                            "enum": ["debt", "debt_like", "under_discussion", "excluded"],
                        },
                        "rationale": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Debt and debt-like items identified during the discussion.",
            },
            "cash_flow_analysis": {
                "type": "object",
                "properties": {
                    "free_cash_flow_discussed": {"type": "string"},
                    "capex_maintenance_vs_growth": {"type": "string"},
                    "cash_conversion": {"type": "string"},
                    "one_time_cash_items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "cash_flow_risks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Cash flow analysis and considerations discussed.",
            },
            "revenue_analysis": {
                "type": "object",
                "properties": {
                    "revenue_composition": {"type": "string"},
                    "recurring_vs_nonrecurring": {"type": "string"},
                    "customer_concentration": {"type": "string"},
                    "pricing_dynamics": {"type": "string"},
                    "contract_structure": {"type": "string"},
                    "churn_and_retention": {"type": "string"},
                    "pipeline_and_backlog": {"type": "string"},
                    "revenue_quality_concerns": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": "Revenue quality and composition analysis discussed.",
            },
            "model_assumptions_debated": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "assumption": {"type": "string"},
                        "management_view": {"type": "string"},
                        "deal_team_view": {"type": "string"},
                        "resolution": {
                            "type": "string",
                            "enum": ["aligned", "gap_remains", "needs_more_data"],
                        },
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": (
                    "Key model assumptions that were debated "
                    "or questioned during the call."
                ),
            },
            "sensitivity_scenarios": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "scenario_name": {"type": "string"},
                        "description": {"type": "string"},
                        "impact": {"type": "string"},
                        "probability_assessment": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Sensitivity and scenario analyses discussed.",
            },
            "lbo_returns_discussed": {
                "type": "object",
                "properties": {
                    "entry_multiple": {"type": "string"},
                    "exit_multiple_assumed": {"type": "string"},
                    "hold_period": {"type": "string"},
                    "target_irr": {"type": "string"},
                    "target_moic": {"type": "string"},
                    "leverage_assumptions": {"type": "string"},
                    "returns_by_scenario": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "description": (
                    "LBO returns analysis discussed. Only "
                    "include if explicitly covered."
                ),
            },
            "financial_red_flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "flag": {"type": "string"},
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "financial_impact": {"type": "string"},
                        "resolution_status": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Financial red flags identified during the discussion.",
            },
            "open_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item": {"type": "string"},
                        "impact_on_valuation": {"type": "string"},
                        "owner": {"type": "string"},
                        "deadline": {"type": "string"},
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "description": "Outstanding financial diligence items that need resolution.",
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
                "description": "Action items assigned during the financial review call.",
            },
        },
    },
)
