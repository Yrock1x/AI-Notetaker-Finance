FINANCIAL_VOCABULARY = [
    "EBITDA", "EBIT", "LBO", "DCF", "IRR", "MOIC", "CoC",
    "revenue", "gross margin", "net income", "free cash flow",
    "enterprise value", "equity value", "debt-to-equity",
    "leverage ratio", "working capital", "capex", "opex",
    "ARR", "MRR", "churn rate", "CAC", "LTV", "NRR",
    "quality of earnings", "QoE", "add-back", "normalization",
    "management presentation", "CIM", "teaser", "LOI",
    "term sheet", "due diligence", "data room", "SPA",
    "representations and warranties", "indemnification",
    "pro forma", "run rate", "synergies", "accretion", "dilution",
]

DEEPGRAM_CONFIG = {
    "model": "nova-2",
    "language": "en",
    "smart_format": True,
    "diarize": True,
    "punctuate": True,
    "paragraphs": True,
    "utterances": True,
    "keywords": FINANCIAL_VOCABULARY,
}
