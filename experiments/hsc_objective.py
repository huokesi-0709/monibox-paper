from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.config import PROJECT_ROOT


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


@dataclass(frozen=True)
class SearchVariable:
    name: str
    low: float
    high: float


@dataclass(frozen=True)
class SearchSpace:
    version: str
    variables: tuple[SearchVariable, ...]

    @classmethod
    def load(cls, path: str | Path = "scoring/search_space.json") -> SearchSpace:
        obj = json.loads(_resolve(path).read_text(encoding="utf-8"))
        weights = obj.get("weights") or {}
        variables: list[SearchVariable] = []
        for name, bounds in weights.items():
            low = float(bounds["low"])
            high = float(bounds["high"])
            if high < low:
                raise ValueError(f"invalid search bounds for {name}: high < low")
            variables.append(SearchVariable(name=name, low=low, high=high))
        if not variables:
            raise ValueError("search space has no weight variables")
        return cls(version=str(obj.get("version") or ""), variables=tuple(variables))

    @property
    def names(self) -> list[str]:
        return [item.name for item in self.variables]

    @property
    def xl(self) -> np.ndarray:
        return np.asarray([item.low for item in self.variables], dtype=float)

    @property
    def xu(self) -> np.ndarray:
        return np.asarray([item.high for item in self.variables], dtype=float)

    def vector_to_weights(self, x: Any) -> dict[str, float]:
        values = np.asarray(x, dtype=float).reshape(-1)
        if len(values) != len(self.variables):
            raise ValueError(
                f"expected {len(self.variables)} weights, got {len(values)}"
            )
        clipped = np.clip(values, self.xl, self.xu)
        return {
            variable.name: float(value)
            for variable, value in zip(self.variables, clipped, strict=True)
        }

    def vector_to_policy(
        self,
        x: Any,
        template: dict[str, Any],
        version: str = "hsc-rag-de-candidate",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        policy = dict(template)
        policy["version"] = version
        policy["weights"] = self.vector_to_weights(x)
        if metadata:
            policy["metadata"] = dict(metadata)
        return policy


def _metric(metrics: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = metrics.get(key, default)
    if value is None:
        return default
    return float(value)


def compute_fitness(metrics: dict[str, Any]) -> float:
    route_clean = _metric(metrics, "route_accuracy_clean", _metric(metrics, "route_accuracy"))
    route_robust = _metric(metrics, "route_accuracy_robust", _metric(metrics, "route_accuracy"))
    evidence = _metric(
        metrics,
        "evidence_hit_at_5",
        _metric(metrics, "evidence_hit_at_3"),
    )
    safety = _metric(
        metrics,
        "safety_compliance",
        1.0 - _metric(metrics, "unsafe_response_rate"),
    )
    robust_consistency = _metric(metrics, "robust_consistency")
    clarification = _metric(
        metrics,
        "clarification_appropriateness",
        1.0 - _metric(metrics, "protocol_false_trigger_rate"),
    )
    action_correctness = _metric(
        metrics,
        "action_correctness",
        _metric(metrics, "protocol_hit_rate"),
    )
    high_risk_miss = _metric(metrics, "high_risk_miss_rate")
    unsafe = _metric(metrics, "unsafe_response_rate")
    unsupported = _metric(metrics, "unsupported_claim_rate")
    latency_penalty = _metric(metrics, "latency_penalty")

    return float(
        0.20 * route_clean
        + 0.20 * route_robust
        + 0.15 * evidence
        + 0.20 * safety
        + 0.10 * robust_consistency
        + 0.10 * clarification
        + 0.05 * action_correctness
        - 0.25 * high_risk_miss
        - 0.20 * unsafe
        - 0.15 * unsupported
        - 0.05 * latency_penalty
    )
