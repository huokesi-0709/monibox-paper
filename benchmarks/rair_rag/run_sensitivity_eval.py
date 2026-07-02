from __future__ import annotations

import argparse
import csv
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.run_routing_eval import evaluate_routing_cases
from runtime.routing_policy import RoutingPolicy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "test" / "rair_test.jsonl"
DEFAULT_POLICY = PROJECT_ROOT / "scoring" / "routing_policy_manual.yaml"
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "rair_eval" / "sensitivity"
NEGATION_PENALTY_VALUES = (0.2, 0.3, 0.45, 0.6, 0.8)
HIGH_RISK_BOOST_VALUES = (0.0, 0.03, 0.05, 0.08, 0.1)
FIELDS = ("Parameter", "Value", "NumCases", "NegRiskF1", "PFTR", "HRR", "RouteAcc")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAIR routing sensitivity checks.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    result = run_sensitivity_eval(
        data_path=args.data,
        policy_path=args.policy,
        out_dir=args.out_dir,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def run_sensitivity_eval(
    *, data_path: Path, policy_path: Path | None, out_dir: Path
) -> dict[str, Any]:
    base_policy = RoutingPolicy.from_file(policy_path) if policy_path else RoutingPolicy()
    rows = []
    for value in NEGATION_PENALTY_VALUES:
        policy = replace(base_policy, negation_penalty=value)
        metrics = _evaluate_with_policy(data_path=data_path, policy=policy)
        rows.append(_row("negation_penalty", value, metrics))
    for value in HIGH_RISK_BOOST_VALUES:
        policy = replace(base_policy, high_risk_boost=value)
        metrics = _evaluate_with_policy(data_path=data_path, policy=policy)
        rows.append(_row("high_risk_boost", value, metrics))

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "routing_sensitivity.md"
    csv_path = out_dir / "routing_sensitivity.csv"
    write_markdown(md_path, rows)
    write_csv(csv_path, rows)
    return {
        "data": str(data_path),
        "policy": str(policy_path) if policy_path else "default RoutingPolicy",
        "num_rows": len(rows),
        "outputs": {"markdown": str(md_path), "csv": str(csv_path)},
    }


def _evaluate_with_policy(*, data_path: Path, policy: RoutingPolicy) -> dict[str, Any]:
    summary = evaluate_routing_cases(
        data_path=data_path,
        method="risk-router",
        policy_path=None,
        policy=policy,
    )
    metrics = summary.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _row(parameter: str, value: float, metrics: dict[str, Any]) -> dict[str, str]:
    return {
        "Parameter": parameter,
        "Value": _format_float(value),
        "NumCases": str(int(metrics.get("num_cases") or 0)),
        "NegRiskF1": _format_float(metrics.get("NegRiskF1")),
        "PFTR": _format_float(metrics.get("PFTR")),
        "HRR": _format_float(metrics.get("HRR")),
        "RouteAcc": _format_float(metrics.get("RouteAcc")),
    }


def write_markdown(path: Path, rows: list[dict[str, str]]) -> None:
    lines = [
        "# RAIR Routing Sensitivity",
        "",
        "For `negation_penalty`, read `NegRiskF1` and `PFTR`. For `high_risk_boost`, read `HRR` and `RouteAcc`.",
        "",
        "| Parameter | Value | NumCases | NegRiskF1 | PFTR | HRR | RouteAcc |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    lines.extend(
        "| {Parameter} | {Value} | {NumCases} | {NegRiskF1} | {PFTR} | {HRR} | {RouteAcc} |".format(
            **row
        )
        for row in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def _format_float(value: Any) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return ""


if __name__ == "__main__":
    main()
