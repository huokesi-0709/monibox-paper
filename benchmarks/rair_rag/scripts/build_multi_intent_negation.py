from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.routing_schema import load_routing_cases
from runtime.risk_router import PROTOCOL_BY_ROUTE, route_for_intent, suppressed_protocols_for_negated_risks

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUTS = (
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test_v2.jsonl",
    PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "gold" / "rair_gold_all_v2.jsonl",
)
DEFAULT_OUT = (
    PROJECT_ROOT
    / "benchmarks"
    / "rair_rag"
    / "data"
    / "test"
    / "rair_test_multi_intent_negation.jsonl"
)

RISK_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build RAIR-RAG multi-intent-negation subset from existing cases."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--inputs",
        nargs="*",
        type=Path,
        default=list(DEFAULT_INPUTS),
        help="Input JSONL files to mine from.",
    )
    parser.add_argument("--target", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summary = build_multi_intent_negation(
        inputs=[Path(item) for item in args.inputs],
        out_path=args.out,
        target=args.target,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def build_multi_intent_negation(
    *,
    inputs: list[Path],
    out_path: Path,
    target: int,
    seed: int,
    overwrite: bool,
) -> dict[str, Any]:
    if out_path.exists() and not overwrite:
        raise FileExistsError(f"output already exists; pass --overwrite: {out_path}")

    cases = _load_cases(inputs)
    multi_pool = [case for case in cases if _is_multi_intent(case)]
    neg_pool = [case for case in cases if _is_negation(case)]
    if not multi_pool or not neg_pool:
        raise ValueError(
            "need both multi-intent and negation source cases: "
            f"multi={len(multi_pool)} neg={len(neg_pool)}"
        )

    pool: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    rng = random.Random(seed)

    # 先保留任何现成同时满足双条件的样本。
    for case in cases:
        if _is_multi_intent(case) and _is_negation(case):
            row = case.to_dict()
            row["perturbation_types"] = sorted(
                set(row.get("perturbation_types") or [])
                | {"multi_intent", "negation_conflict", "multi_intent_negation"}
            )
            key = _row_key(row)
            if key in seen:
                continue
            seen.add(key)
            pool.append(row)

    # 再从多意图样本与否定样本中合成复合样本，保证能补足目标数量。
    multi_items = list(multi_pool)
    neg_items = list(neg_pool)
    rng.shuffle(multi_items)
    rng.shuffle(neg_items)
    mi_index = 0
    ng_index = 0
    while len(pool) < target:
        multi_case = multi_items[mi_index % len(multi_items)].to_dict()
        neg_case = neg_items[ng_index % len(neg_items)].to_dict()
        mi_index += 1
        ng_index += 1
        row = compose_multi_intent_negation_case(
            multi_case=multi_case,
            neg_case=neg_case,
            composite_index=len(pool) + 1,
            seed=seed,
        )
        key = _row_key(row)
        if key in seen:
            continue
        seen.add(key)
        pool.append(row)

    rng.shuffle(pool)
    selected = pool[:target]
    selected.sort(key=lambda item: _row_key(item))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) for row in selected
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "inputs": [str(path) for path in inputs],
        "out": str(out_path),
        "num_existing_overlap": sum(1 for case in cases if _is_multi_intent(case) and _is_negation(case)),
        "num_multi_pool": len(multi_pool),
        "num_neg_pool": len(neg_pool),
        "num_pool": len(pool),
        "num_selected": len(selected),
        "target": target,
    }


def compose_multi_intent_negation_case(
    *,
    multi_case: dict[str, Any],
    neg_case: dict[str, Any],
    composite_index: int,
    seed: int,
) -> dict[str, Any]:
    raw_input = f"{multi_case['raw_input']}，{neg_case['raw_input']}"
    canonical_input = raw_input
    offset = len(str(multi_case["raw_input"])) + 1

    positive_risks = _dedupe_strs(
        [
            *multi_case.get("positive_risks", []),
            *neg_case.get("positive_risks", []),
        ]
    )
    negated_risks = _dedupe_strs(neg_case.get("negated_risks", []))
    secondary_intents = _dedupe_strs(
        [
            *multi_case.get("secondary_intents", []),
            *([neg_case.get("primary_intent")] if neg_case.get("primary_intent") else []),
        ]
    )
    operational_constraints = _dedupe_strs(
        [
            *multi_case.get("operational_constraints", []),
            *neg_case.get("operational_constraints", []),
        ]
    )
    should_not_trigger = _dedupe_strs(
        [
            *multi_case.get("should_not_trigger", []),
            *neg_case.get("should_not_trigger", []),
        ]
    )
    suppressed_protocols = _dedupe_strs(
        [
            *multi_case.get("suppressed_protocols", []),
            *neg_case.get("suppressed_protocols", []),
            *suppressed_protocols_for_negated_risks(negated_risks),
        ]
    )
    risk_candidates = _shift_risk_candidates(
        multi_case.get("risk_candidates", []), 0
    ) + _shift_risk_candidates(neg_case.get("risk_candidates", []), offset)
    risk_mentions = [
        f"{item.get('risk')}:{item.get('trigger')}"
        for item in risk_candidates
        if item.get("risk") and item.get("trigger")
    ]

    primary_intent = str(multi_case.get("primary_intent") or "")
    expected_route = route_for_intent(primary_intent) or str(
        multi_case.get("expected_route") or ""
    )
    expected_protocol_id = PROTOCOL_BY_ROUTE.get(expected_route)
    risk_level = _max_risk_level(
        str(multi_case.get("risk_level") or "medium"),
        str(neg_case.get("risk_level") or "medium"),
    )
    guideline_refs = _merge_dicts(
        [
            *multi_case.get("guideline_refs", []),
            *neg_case.get("guideline_refs", []),
        ]
    )
    expected_tags = _dedupe_strs(
        [
            *multi_case.get("expected_tags", []),
            *neg_case.get("expected_tags", []),
        ]
    )

    return {
        "id": f"multi_neg_{composite_index:04d}",
        "canonical_id": f"{multi_case.get('canonical_id', 'case_multi')}_x_{neg_case.get('canonical_id', 'case_neg')}_{composite_index:04d}",
        "raw_input": raw_input,
        "canonical_input": canonical_input,
        "language": multi_case.get("language") or neg_case.get("language") or "zh-CN",
        "source_type": "template_composed_multi_intent_negation",
        "perturbation_types": sorted(
            {
                *multi_case.get("perturbation_types", []),
                *neg_case.get("perturbation_types", []),
                "multi_intent",
                "negation_conflict",
                "multi_intent_negation",
            }
        ),
        "positive_risks": positive_risks,
        "negated_risks": negated_risks,
        "operational_constraints": operational_constraints,
        "primary_intent": primary_intent,
        "secondary_intents": secondary_intents,
        "risk_candidates": risk_candidates,
        "risk_mentions": risk_mentions,
        "should_not_trigger": should_not_trigger,
        "suppressed_protocols": suppressed_protocols or should_not_trigger,
        "expected_route": expected_route,
        "expected_protocol_id": expected_protocol_id,
        "risk_level": risk_level,
        "expected_tags": expected_tags,
        "guideline_refs": guideline_refs,
        "safety_boundaries": _dedupe_strs(
            [
                *multi_case.get("safety_boundaries", []),
                *neg_case.get("safety_boundaries", []),
            ]
        ),
        "label_status": "template_composed",
        "safety_note": None,
        "reference_reply": None,
    }


def _load_cases(inputs: list[Path]) -> list[Any]:
    cases: list[Any] = []
    seen: set[tuple[str, str]] = set()
    for path in inputs:
        for case in load_routing_cases(path):
            key = (str(case.canonical_id or ""), str(case.raw_input or ""))
            if key in seen:
                continue
            seen.add(key)
            cases.append(case)
    return cases


def _is_multi_intent(case: Any) -> bool:
    perturbations = set(case.perturbation_types or [])
    return "multi_intent" in perturbations or len(case.secondary_intents or []) > 0


def _is_negation(case: Any) -> bool:
    perturbations = set(case.perturbation_types or [])
    return "negation_conflict" in perturbations or len(case.negated_risks or []) > 0


def _shift_risk_candidates(
    candidates: list[dict[str, Any]], offset: int
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        span = row.get("span")
        if isinstance(span, list) and len(span) == 2:
            try:
                row["span"] = [int(span[0]) + offset, int(span[1]) + offset]
            except (TypeError, ValueError):
                pass
        output.append(row)
    return output


def _merge_dicts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        output.append(dict(item))
    return output


def _dedupe_strs(items: list[Any]) -> list[str]:
    output: list[str] = []
    for item in items:
        value = str(item or "")
        if value and value not in output:
            output.append(value)
    return output


def _max_risk_level(a: str, b: str) -> str:
    return max((a, b), key=lambda item: RISK_LEVEL_ORDER.get(item, 1))


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("canonical_id") or ""), str(row.get("id") or ""))


if __name__ == "__main__":
    main()
