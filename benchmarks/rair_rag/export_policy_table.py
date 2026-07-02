from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from runtime.routing_policy import RoutingPolicy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = PROJECT_ROOT / "scoring" / "routing_policy_manual.yaml"
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "rair_eval" / "tables"
FIELDS = ("Parameter", "Value", "Group", "Description")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export RAIR routing policy table.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result = export_policy_table(policy_path=args.policy, out_dir=args.out_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def export_policy_table(*, policy_path: Path | None, out_dir: Path) -> dict[str, Any]:
    policy = RoutingPolicy.from_file(policy_path) if policy_path else RoutingPolicy()
    rows = rows_from_policy(policy)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "policy_parameters.md"
    csv_path = out_dir / "policy_parameters.csv"
    write_markdown(md_path, rows)
    write_csv(csv_path, rows)
    return {
        "policy": str(policy_path) if policy_path else "default RoutingPolicy",
        "num_rows": len(rows),
        "outputs": {"markdown": str(md_path), "csv": str(csv_path)},
    }


def rows_from_policy(policy: RoutingPolicy) -> list[dict[str, str]]:
    data = policy.to_dict()
    rows = [
        _row("negation_window", data["negation_window"], "negation", "Token/window span used for negation scope resolution."),
        _row("negation_penalty", data["negation_penalty"], "negation", "Confidence penalty applied to risks resolved as negated."),
        _row("confidence_threshold", data["confidence_threshold"], "confidence", "Global minimum confidence for retaining a risk candidate."),
        _row("high_risk_boost", data["high_risk_boost"], "priority", "Priority boost for high-risk intents during route selection."),
        _row("operational_constraint_weight", data["operational_constraint_weight"], "priority", "Weight for operational constraints such as low battery."),
        _row("negation_words", ", ".join(data["negation_words"]), "negation", "Lexical triggers used by the negation resolver."),
        _row("boundary_terms", ", ".join(data["boundary_terms"]), "negation", "Boundary terms that limit negation scope."),
    ]
    for label, value in sorted(data["intent_base_weights"].items()):
        rows.append(
            _row(
                f"intent_base_weights.{label}",
                value,
                "intent_weight",
                "Base priority weight for this intent.",
            )
        )
    for label, value in sorted(data["confidence_thresholds"].items()):
        rows.append(
            _row(
                f"confidence_thresholds.{label}",
                value,
                "confidence",
                "Intent-specific confidence threshold override.",
            )
        )
    return rows


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# RAIR Routing Policy Parameters",
        "",
        "| Parameter | Value | Group | Description |",
        "|---|---:|---|---|",
    ]
    lines.extend(
        "| {Parameter} | {Value} | {Group} | {Description} |".format(**row)
        for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def _row(parameter: str, value: Any, group: str, description: str) -> dict[str, str]:
    return {
        "Parameter": parameter,
        "Value": _format_value(value),
        "Group": group,
        "Description": description,
    }


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


if __name__ == "__main__":
    main()
