from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from benchmarks.rair_rag.baselines.bert_multilabel_dataset import (
    LABELS,
    OPERATIONAL_LABELS,
)
from benchmarks.rair_rag.routing_schema import RoutingCase
from runtime.risk_router import protocol_for_route, route_for_intent

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BERT_MODEL_DIR = PROJECT_ROOT / "build" / "bert_multilabel" / "best_model"


class BertMultilabelPredictor:
    def __init__(
        self,
        model_dir: Path | None = None,
        *,
        threshold: float | None = None,
        device: str | None = None,
    ) -> None:
        self.model_dir = Path(
            model_dir
            or os.getenv("BERT_MULTILABEL_MODEL_DIR")
            or DEFAULT_BERT_MODEL_DIR
        )
        if not self.model_dir.exists():
            msg = (
                f"BERT multilabel model not found: {self.model_dir}. "
                "Train it first with `uv run python -m "
                "benchmarks.rair_rag.baselines.train_bert_multilabel "
                "--train-data <train.jsonl>`."
            )
            raise FileNotFoundError(msg)
        self.threshold = float(threshold if threshold is not None else 0.5)
        self.labels = _load_labels(self.model_dir)

        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.torch = torch
        self.device = _resolve_device(torch, device)
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
        self.model = AutoModelForSequenceClassification.from_pretrained(
            str(self.model_dir)
        )
        self.model.to(self.device)
        self.model.eval()

    def predict_context(self, text: str) -> dict[str, Any]:
        torch = self.torch
        encoded = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=128,
            return_tensors="pt",
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with torch.no_grad():
            logits = self.model(**encoded).logits[0]
            probabilities = torch.sigmoid(logits).detach().cpu().tolist()
        return context_from_scores(
            text=text,
            labels=self.labels,
            probabilities=[float(value) for value in probabilities],
            threshold=self.threshold,
            model_dir=self.model_dir,
        )

    def predict_case(self, case: RoutingCase) -> dict[str, Any]:
        text = case.raw_input or case.canonical_input
        return self.predict_context(text)


def context_from_scores(
    *,
    text: str,
    labels: list[str],
    probabilities: list[float],
    threshold: float,
    model_dir: Path,
) -> dict[str, Any]:
    scored = [
        (label, float(probabilities[index]))
        for index, label in enumerate(labels)
        if index < len(probabilities)
    ]
    selected = [
        label
        for label, _score in sorted(
            (item for item in scored if item[1] >= threshold),
            key=lambda item: item[1],
            reverse=True,
        )
    ]
    if not selected and scored:
        selected = [max(scored, key=lambda item: item[1])[0]]
    if "out_of_scope" in selected and len(selected) > 1:
        selected = [label for label in selected if label != "out_of_scope"]

    operational = [
        label for label in selected if label in OPERATIONAL_LABELS
    ]
    positive = [
        label
        for label in selected
        if label not in OPERATIONAL_LABELS and label != "out_of_scope"
    ]
    primary = positive[0] if positive else "out_of_scope"
    secondary = positive[1:]
    route = route_for_intent(primary)
    protocol_id = protocol_for_route(route)
    risk_score = max((score for _label, score in scored), default=0.0)
    candidates = [
        {
            "risk": label,
            "trigger": text,
            "term": text,
            "start": 0,
            "end": len(text),
            "span": [0, len(text)],
            "confidence": score,
            "evidence_type": "bert_multilabel",
        }
        for label, score in scored
        if label in selected and label != "out_of_scope"
    ]
    return {
        "primary_intent": primary,
        "secondary_intents": secondary,
        "operational_constraints": operational,
        "positive_risks": positive,
        "negated_risks": [],
        "suppressed_protocols": [],
        "predicted_route": route,
        "protocol_id": protocol_id,
        "risk_score": risk_score,
        "risk_candidates": candidates,
        "risk_mentions": candidates,
        "trace": {
            "baseline": "bert-base-chinese multilabel classifier",
            "route_derivation": {
                "rule": (
                    "select labels with probability >= threshold; if none, use the "
                    "highest-probability label; drop out_of_scope when other labels "
                    "are selected; take the highest-probability non-operational "
                    "label as primary_intent; map primary_intent to route and "
                    "protocol_id with the shared RAIR route table"
                ),
                "primary_intent": primary,
                "predicted_route": route,
                "protocol_id": protocol_id,
                "selected_labels": list(selected),
                "operational_labels": list(operational),
            },
            "model_dir": str(model_dir),
            "threshold": threshold,
            "label_scores": dict(scored),
        },
    }


def _load_labels(model_dir: Path) -> list[str]:
    for path in (model_dir / "label_map.json", model_dir.parent / "label_map.json"):
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        labels = payload.get("labels")
        if isinstance(labels, list) and all(isinstance(item, str) for item in labels):
            return list(labels)
    return list(LABELS)


def _resolve_device(torch: Any, device: str | None) -> Any:
    if device and device != "auto":
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
