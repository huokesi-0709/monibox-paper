from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.routing_schema import RoutingCase, load_routing_cases

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data"
DEFAULT_GOLD = DATA_DIR / "gold" / "rair_gold_all.jsonl"
DEFAULT_DEV = DATA_DIR / "dev" / "rair_dev.jsonl"
DEFAULT_TEST = DATA_DIR / "test" / "rair_test.jsonl"
DEFAULT_TEST_NEGATION = DATA_DIR / "test" / "rair_test_negation.jsonl"
DEFAULT_TEST_MULTI = DATA_DIR / "test" / "rair_test_multi_intent.jsonl"
DEFAULT_MANIFEST = DATA_DIR / "split_manifest.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split RAIR-RAG gold cases into leakage-safe dev/test files."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--dev-out", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--test-out", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--test-negation-out", type=Path, default=DEFAULT_TEST_NEGATION)
    parser.add_argument("--test-multi-out", type=Path, default=DEFAULT_TEST_MULTI)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dev-ratio", type=float, default=0.4)
    parser.add_argument("--test-ratio", type=float, default=0.6)
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summary = split_dev_test(
        input_path=args.input,
        dev_out=args.dev_out,
        test_out=args.test_out,
        test_negation_out=args.test_negation_out,
        test_multi_out=args.test_multi_out,
        manifest_path=args.manifest,
        dev_ratio=args.dev_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def split_dev_test(
    *,
    input_path: Path,
    dev_out: Path,
    test_out: Path,
    test_negation_out: Path,
    test_multi_out: Path,
    manifest_path: Path,
    dev_ratio: float,
    test_ratio: float,
    seed: int,
    overwrite: bool,
) -> dict[str, Any]:
    validate_ratios(dev_ratio, test_ratio)
    ensure_outputs_available(
        [dev_out, test_out, test_negation_out, test_multi_out, manifest_path],
        overwrite=overwrite,
    )

    cases = load_routing_cases(input_path)
    if not cases:
        raise ValueError(f"{input_path}: no cases found")

    groups = group_by_canonical_id(cases)
    dev_group_ids, test_group_ids = choose_dev_groups(
        groups=groups,
        dev_ratio=dev_ratio,
        test_ratio=test_ratio,
        seed=seed,
    )
    dev_cases = flatten_groups(groups, dev_group_ids)
    test_cases = flatten_groups(groups, test_group_ids)
    verify_no_canonical_leakage(dev_cases, test_cases)

    test_negation_cases = filter_by_perturbation(test_cases, "negation_conflict")
    test_multi_cases = filter_by_perturbation(test_cases, "multi_intent")

    write_jsonl(dev_out, dev_cases)
    write_jsonl(test_out, test_cases)
    write_jsonl(test_negation_out, test_negation_cases)
    write_jsonl(test_multi_out, test_multi_cases)

    manifest = build_manifest(
        input_path=input_path,
        seed=seed,
        dev_ratio=dev_ratio,
        test_ratio=test_ratio,
        dev_cases=dev_cases,
        test_cases=test_cases,
        test_negation_cases=test_negation_cases,
        test_multi_cases=test_multi_cases,
        dev_group_ids=dev_group_ids,
        test_group_ids=test_group_ids,
    )
    write_json(manifest_path, manifest)
    return {
        "dev_cases": len(dev_cases),
        "test_cases": len(test_cases),
        "test_negation_cases": len(test_negation_cases),
        "test_multi_intent_cases": len(test_multi_cases),
        "dev_canonical_ids": len(dev_group_ids),
        "test_canonical_ids": len(test_group_ids),
    }


def validate_ratios(dev_ratio: float, test_ratio: float) -> None:
    if dev_ratio <= 0 or test_ratio <= 0:
        raise ValueError("dev_ratio and test_ratio must be positive")
    total = dev_ratio + test_ratio
    if total <= 0:
        raise ValueError("dev_ratio + test_ratio must be positive")


def ensure_outputs_available(paths: list[Path], *, overwrite: bool) -> None:
    if overwrite:
        return
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = ", ".join(existing)
        raise FileExistsError(f"output already exists; pass --overwrite: {joined}")


def group_by_canonical_id(cases: list[RoutingCase]) -> dict[str, list[RoutingCase]]:
    groups: dict[str, list[RoutingCase]] = defaultdict(list)
    for case in cases:
        groups[case.canonical_id].append(case)
    return dict(groups)


def choose_dev_groups(
    *,
    groups: dict[str, list[RoutingCase]],
    dev_ratio: float,
    test_ratio: float,
    seed: int,
) -> tuple[list[str], list[str]]:
    group_ids = sorted(groups)
    random.Random(seed).shuffle(group_ids)  # noqa: S311
    total_cases = sum(len(items) for items in groups.values())
    target_dev_cases = round(total_cases * dev_ratio / (dev_ratio + test_ratio))

    dev_group_ids: list[str] = []
    dev_case_count = 0
    for group_id in group_ids:
        if dev_case_count >= target_dev_cases and dev_group_ids:
            break
        dev_group_ids.append(group_id)
        dev_case_count += len(groups[group_id])

    if len(dev_group_ids) == len(group_ids) and len(group_ids) > 1:
        dev_group_ids.pop()
    dev_group_set = set(dev_group_ids)
    test_group_ids = [group_id for group_id in group_ids if group_id not in dev_group_set]
    return sorted(dev_group_ids), sorted(test_group_ids)


def flatten_groups(
    groups: dict[str, list[RoutingCase]], group_ids: list[str]
) -> list[RoutingCase]:
    selected: list[RoutingCase] = []
    for group_id in group_ids:
        selected.extend(groups[group_id])
    return sorted(selected, key=lambda case: case.id)


def verify_no_canonical_leakage(
    dev_cases: list[RoutingCase], test_cases: list[RoutingCase]
) -> None:
    dev_ids = {case.canonical_id for case in dev_cases}
    test_ids = {case.canonical_id for case in test_cases}
    leaked = sorted(dev_ids & test_ids)
    if leaked:
        sample = ", ".join(leaked[:5])
        raise ValueError(f"canonical_id leakage between dev/test: {sample}")


def filter_by_perturbation(
    cases: list[RoutingCase], perturbation_type: str
) -> list[RoutingCase]:
    return [
        case for case in cases if perturbation_type in set(case.perturbation_types)
    ]


def build_manifest(
    *,
    input_path: Path,
    seed: int,
    dev_ratio: float,
    test_ratio: float,
    dev_cases: list[RoutingCase],
    test_cases: list[RoutingCase],
    test_negation_cases: list[RoutingCase],
    test_multi_cases: list[RoutingCase],
    dev_group_ids: list[str],
    test_group_ids: list[str],
) -> dict[str, Any]:
    return {
        "input": str(input_path),
        "seed": seed,
        "dev_ratio": dev_ratio,
        "test_ratio": test_ratio,
        "leakage_rule": "all cases with the same canonical_id stay in one split",
        "usage_note": "DE and any parameter tuning may use dev only; test files are held out.",
        "splits": {
            "dev": split_summary(dev_cases, dev_group_ids),
            "test": split_summary(test_cases, test_group_ids),
            "test_negation": split_summary(
                test_negation_cases,
                sorted({case.canonical_id for case in test_negation_cases}),
            ),
            "test_multi_intent": split_summary(
                test_multi_cases,
                sorted({case.canonical_id for case in test_multi_cases}),
            ),
        },
    }


def split_summary(
    cases: list[RoutingCase], canonical_ids: list[str]
) -> dict[str, Any]:
    return {
        "num_cases": len(cases),
        "num_canonical_ids": len(canonical_ids),
        "canonical_ids": canonical_ids,
        "label_distribution": {
            "perturbation_type": count_list_values(
                case.perturbation_types for case in cases
            ),
            "primary_intent": count_values(case.primary_intent for case in cases),
            "risk_level": count_values(case.risk_level for case in cases),
            "source_type": count_values(case.source_type for case in cases),
            "label_status": count_values(case.label_status for case in cases),
        },
    }


def count_values(values: Any) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def count_list_values(values: Any) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for items in values:
        counter.update(items)
    return dict(sorted(counter.items()))


def write_jsonl(path: Path, cases: list[RoutingCase]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(case.to_dict(), ensure_ascii=False, sort_keys=True)
        for case in cases
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
