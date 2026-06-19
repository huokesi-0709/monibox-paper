from __future__ import annotations

ABLATION_METHODS = {
    "hsc-rag-no-risk": {"risk_match": False},
    "hsc-rag-no-unsafe": {"unsafe_penalty": False},
    "hsc-rag-no-protocol": {"protocol": False},
}


def get_ablation_config(method: str) -> dict:
    return dict(ABLATION_METHODS.get(method, {}))
