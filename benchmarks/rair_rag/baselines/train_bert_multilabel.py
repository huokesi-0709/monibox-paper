from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.rair_rag.baselines.bert_multilabel_dataset import (
    LABELS,
    BertMultilabelExample,
    load_bert_multilabel_examples,
    write_label_map,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DEV_DATA = PROJECT_ROOT / "benchmarks" / "rair_rag" / "data" / "dev" / "rair_dev.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "build" / "bert_multilabel"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a real bert-base-chinese multilabel RAIR baseline."
    )
    parser.add_argument("--train-data", type=Path, required=True)
    parser.add_argument("--dev-data", type=Path, default=DEFAULT_DEV_DATA)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model-name", default="bert-base-chinese")
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    summary = train_bert_multilabel(
        train_data=args.train_data,
        dev_data=args.dev_data,
        out_dir=args.out_dir,
        model_name=args.model_name,
        max_length=args.max_length,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        epochs=args.epochs,
        seed=args.seed,
        weight_decay=args.weight_decay,
        threshold=args.threshold,
        device=args.device,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def train_bert_multilabel(
    *,
    train_data: Path,
    dev_data: Path,
    out_dir: Path,
    model_name: str = "bert-base-chinese",
    max_length: int = 128,
    learning_rate: float = 2e-5,
    batch_size: int = 16,
    epochs: int = 5,
    seed: int = 42,
    weight_decay: float = 0.01,
    threshold: float = 0.5,
    device: str = "auto",
) -> dict[str, Any]:
    _validate_paths(train_data=train_data, dev_data=dev_data)
    _set_seed(seed)

    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    resolved_device = _resolve_device(torch, device)
    train_examples = load_bert_multilabel_examples(train_data)
    dev_examples = load_bert_multilabel_examples(dev_data)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(LABELS),
        problem_type="multi_label_classification",
        id2label={index: label for index, label in enumerate(LABELS)},
        label2id={label: index for index, label in enumerate(LABELS)},
    )
    model.to(resolved_device)

    train_dataset = _TorchMultilabelDataset(
        train_examples, tokenizer=tokenizer, max_length=max_length
    )
    dev_dataset = _TorchMultilabelDataset(
        dev_examples, tokenizer=tokenizer, max_length=max_length
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    dev_loader = DataLoader(dev_dataset, batch_size=batch_size, shuffle=False)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    loss_fn = torch.nn.BCEWithLogitsLoss()

    out_dir.mkdir(parents=True, exist_ok=True)
    best_model_dir = out_dir / "best_model"
    config = {
        "model_name": model_name,
        "train_data": str(train_data),
        "dev_data": str(dev_data),
        "max_length": max_length,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "epochs": epochs,
        "seed": seed,
        "weight_decay": weight_decay,
        "threshold": threshold,
        "device": str(resolved_device),
        "loss": "BCEWithLogitsLoss",
        "best_model_selection": "dev_micro_f1",
        "test_set_used_for_tuning": False,
    }
    _write_json(out_dir / "train_config.json", config)
    write_label_map(out_dir / "label_map.json")

    best_metric = -1.0
    best_metrics: dict[str, Any] = {}
    history = []
    for epoch in range(1, epochs + 1):
        train_loss = _train_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            loss_fn=loss_fn,
            torch=torch,
            device=resolved_device,
        )
        dev_metrics = _evaluate(
            model=model,
            loader=dev_loader,
            torch=torch,
            device=resolved_device,
            threshold=threshold,
        )
        dev_metrics["epoch"] = epoch
        dev_metrics["train_loss"] = train_loss
        history.append(dev_metrics)
        if float(dev_metrics["micro_f1"]) > best_metric:
            best_metric = float(dev_metrics["micro_f1"])
            best_metrics = dict(dev_metrics)
            model.save_pretrained(best_model_dir)
            tokenizer.save_pretrained(best_model_dir)
            shutil.copyfile(
                out_dir / "label_map.json", best_model_dir / "label_map.json"
            )

    dev_summary = {
        "data": str(dev_data),
        "model": model_name,
        "num_cases": len(dev_examples),
        "threshold": threshold,
        "best_epoch": best_metrics.get("epoch"),
        "best_metric": "micro_f1",
        "best_model": str(best_model_dir),
        "history": history,
        **best_metrics,
    }
    _write_json(out_dir / "dev_metrics.json", dev_summary)
    return {
        "out_dir": str(out_dir),
        "best_model": str(best_model_dir),
        "dev_metrics": str(out_dir / "dev_metrics.json"),
        "best_micro_f1": best_metrics.get("micro_f1"),
    }


class _TorchMultilabelDataset:
    def __init__(
        self, examples: list[BertMultilabelExample], *, tokenizer: Any, max_length: int
    ) -> None:
        self.examples = examples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        example = self.examples[index]
        encoded = self.tokenizer(
            example.text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        import torch

        item["labels"] = torch.tensor(example.target, dtype=torch.float32)
        return item


def _train_epoch(
    *,
    model: Any,
    loader: Any,
    optimizer: Any,
    loss_fn: Any,
    torch: Any,
    device: Any,
) -> float:
    model.train()
    losses: list[float] = []
    for batch in loader:
        optimizer.zero_grad()
        labels = batch.pop("labels").to(device)
        inputs = {key: value.to(device) for key, value in batch.items()}
        logits = model(**inputs).logits
        loss = loss_fn(logits, labels)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu().item()))
    return float(sum(losses) / len(losses)) if losses else 0.0


def _evaluate(
    *, model: Any, loader: Any, torch: Any, device: Any, threshold: float
) -> dict[str, Any]:
    model.eval()
    y_true: list[list[float]] = []
    y_score: list[list[float]] = []
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels").to(device)
            inputs = {key: value.to(device) for key, value in batch.items()}
            logits = model(**inputs).logits
            scores = torch.sigmoid(logits)
            y_true.extend(labels.detach().cpu().tolist())
            y_score.extend(scores.detach().cpu().tolist())
    return multilabel_metrics(y_true, y_score, threshold=threshold)


def multilabel_metrics(
    y_true: list[list[float]], y_score: list[list[float]], *, threshold: float
) -> dict[str, Any]:
    true = np.asarray(y_true, dtype=np.int32)
    pred = (np.asarray(y_score, dtype=np.float32) >= threshold).astype(np.int32)
    tp = int(((true == 1) & (pred == 1)).sum())
    fp = int(((true == 0) & (pred == 1)).sum())
    fn = int(((true == 1) & (pred == 0)).sum())
    micro_precision = _ratio(tp, tp + fp)
    micro_recall = _ratio(tp, tp + fn)
    micro_f1 = _f1(micro_precision, micro_recall)
    per_label = {}
    f1_values = []
    for index, label in enumerate(LABELS):
        label_true = true[:, index]
        label_pred = pred[:, index]
        label_tp = int(((label_true == 1) & (label_pred == 1)).sum())
        label_fp = int(((label_true == 0) & (label_pred == 1)).sum())
        label_fn = int(((label_true == 1) & (label_pred == 0)).sum())
        precision = _ratio(label_tp, label_tp + label_fp)
        recall = _ratio(label_tp, label_tp + label_fn)
        f1 = _f1(precision, recall)
        f1_values.append(f1)
        per_label[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(label_true.sum()),
        }
    exact_match = float((true == pred).all(axis=1).mean()) if len(true) else 0.0
    return {
        "threshold": threshold,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "macro_f1": float(sum(f1_values) / len(f1_values)) if f1_values else 0.0,
        "exact_match": exact_match,
        "per_label": per_label,
    }


def _validate_paths(*, train_data: Path, dev_data: Path) -> None:
    if not train_data.exists():
        raise FileNotFoundError(f"training data not found: {train_data}")
    if not dev_data.exists():
        raise FileNotFoundError(f"dev data not found: {dev_data}")
    if "test" in {part.lower() for part in train_data.parts}:
        raise ValueError("test data must not be used for BERT training")
    if "test" in {part.lower() for part in dev_data.parts}:
        raise ValueError("test data must not be used for dev model selection")


def _set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def _resolve_device(torch: Any, device: str) -> Any:
    if device != "auto":
        return torch.device(device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return _ratio(2 * precision * recall, precision + recall)


if __name__ == "__main__":
    main()
