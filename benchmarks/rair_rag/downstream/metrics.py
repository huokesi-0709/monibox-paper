from __future__ import annotations

from collections import defaultdict
from typing import Any

from benchmarks.rair_rag.downstream.schema import DownstreamCase

HIGH_RISK_LEVELS = {"high", "critical"}
HIGH_RISK_PROTOCOLS = {
    "prot_respiratory_distress",
    "prot_bleeding_control",
    "prot_crush_injury",
    "prot_head_injury",
    "prot_entrapment",
    "prot_aftershock_collapse",
}


def compute_case_metrics(
    case: DownstreamCase, prediction: dict[str, Any]
) -> dict[str, float]:
    evidence = _retrieved_evidence(prediction)
    return {
        "ProtocolAcc": protocol_acc(case, prediction),
        "EvidenceHit@1": evidence_hit_at(case, evidence, k=1),
        "EvidenceHit@3": evidence_hit_at(case, evidence, k=3),
        "PFTR": pftr(case, prediction),
        "HRR": hrr_hit(case, prediction),
        "AvgRetrieved": float(len(evidence)),
    }


def compute_retrieval_metrics(
    cases: list[DownstreamCase], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    _ensure_same_length(cases, predictions)
    overall = _compute_group(cases, predictions)
    grouped: dict[str, list[tuple[DownstreamCase, dict[str, Any]]]] = defaultdict(list)
    for case, prediction in zip(cases, predictions, strict=True):
        keys = case.perturbation_types or ["<none>"]
        for key in keys:
            grouped[key].append((case, prediction))

    by_perturbation_type: dict[str, dict[str, Any]] = {}
    for key, pairs in sorted(grouped.items()):
        group_cases = [case for case, _prediction in pairs]
        group_predictions = [prediction for _case, prediction in pairs]
        by_perturbation_type[key] = _compute_group(group_cases, group_predictions)

    return {**overall, "by_perturbation_type": by_perturbation_type}


def protocol_acc(case: DownstreamCase, prediction: dict[str, Any]) -> float:
    expected = case.expected_protocol_id
    predicted = _optional_str(prediction.get("predicted_protocol_id"))
    return _hit(expected and predicted and expected == predicted)


def evidence_hit_at(
    case: DownstreamCase, evidence: list[dict[str, Any]], *, k: int
) -> float:
    for item in evidence[:k]:
        if _evidence_matches_gold(case, item):
            return 1.0
    return 0.0


def pftr(case: DownstreamCase, prediction: dict[str, Any]) -> float:
    blocked = set(case.should_not_trigger or case.suppressed_protocols)
    if not blocked:
        return 0.0
    protocols = set(_triggered_protocols(prediction))
    return _hit(bool(protocols & blocked))


def hrr_hit(case: DownstreamCase, prediction: dict[str, Any]) -> float:
    if not _is_high_risk_case(case):
        return 0.0
    expected = case.expected_protocol_id
    if expected and expected in _triggered_protocols(prediction):
        return 1.0
    if any(
        _evidence_matches_gold(case, item) for item in _retrieved_evidence(prediction)
    ):
        return 1.0
    return 0.0


def _compute_group(
    cases: list[DownstreamCase], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    high_pairs = [
        (case, prediction)
        for case, prediction in zip(cases, predictions, strict=True)
        if _is_high_risk_case(case)
    ]
    return {
        "num_cases": len(cases),
        "ProtocolAcc": _mean(
            protocol_acc(case, prediction)
            for case, prediction in zip(cases, predictions, strict=True)
        ),
        "EvidenceHit@1": _mean(
            evidence_hit_at(case, _retrieved_evidence(prediction), k=1)
            for case, prediction in zip(cases, predictions, strict=True)
        ),
        "EvidenceHit@3": _mean(
            evidence_hit_at(case, _retrieved_evidence(prediction), k=3)
            for case, prediction in zip(cases, predictions, strict=True)
        ),
        "PFTR": _mean(
            pftr(case, prediction)
            for case, prediction in zip(cases, predictions, strict=True)
        ),
        "HRR": _mean(hrr_hit(case, prediction) for case, prediction in high_pairs),
        "AvgRetrieved": _mean(
            len(_retrieved_evidence(prediction)) for prediction in predictions
        ),
        "num_high_risk_cases": len(high_pairs),
    }


def _evidence_matches_gold(case: DownstreamCase, evidence: dict[str, Any]) -> bool:
    if evidence.get("matched_gold_protocol") or evidence.get("matched_guideline_ref"):
        return True

    expected = case.expected_protocol_id
    if expected and evidence.get("protocol_id") == expected:
        return True

    source_id = str(evidence.get("source_id") or "")
    if source_id:
        for ref in case.guideline_refs:
            if source_id == str(ref.get("source_id") or ""):
                return True
    return False


def _triggered_protocols(prediction: dict[str, Any]) -> list[str]:
    protocols: list[str] = []
    predicted = _optional_str(prediction.get("predicted_protocol_id"))
    if predicted:
        protocols.append(predicted)
    for item in _retrieved_evidence(prediction):
        protocol_id = _optional_str(item.get("protocol_id"))
        if protocol_id:
            protocols.append(protocol_id)
    return _dedupe(protocols)


def _retrieved_evidence(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    value = prediction.get("retrieved_evidence")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _is_high_risk_case(case: DownstreamCase) -> bool:
    if case.risk_level in HIGH_RISK_LEVELS:
        return True
    return bool(case.expected_protocol_id in HIGH_RISK_PROTOCOLS)


def _ensure_same_length(
    cases: list[DownstreamCase], predictions: list[dict[str, Any]]
) -> None:
    if len(cases) != len(predictions):
        msg = (
            "cases/predictions length mismatch: "
            f"{len(cases)} cases vs {len(predictions)} predictions"
        )
        raise ValueError(msg)


def _mean(values: Any) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return float(sum(items) / len(items))


def _hit(value: Any) -> float:
    return 1.0 if value else 0.0


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output
