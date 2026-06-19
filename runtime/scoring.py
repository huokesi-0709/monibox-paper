from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT

DEFAULT_POLICY_PATH = PROJECT_ROOT / "scoring" / "policy_manual.json"

DEFAULT_WEIGHTS: dict[str, float] = {
    "w_vec": 0.32,
    "w_sparse": 0.16,
    "w_quality": 0.12,
    "w_tag": 0.14,
    "w_risk": 0.18,
    "w_unsafe": 0.22,
    "w_redundancy": 0.08,
}

DEFAULT_THRESHOLDS: dict[str, float] = {
    "min_final_score": 0.0,
    "unsafe_soft_penalty": 0.35,
    "redundancy_overlap": 0.72,
}

UNSAFE_PATTERNS: list[tuple[str, str]] = [
    (r"止血带", "tourniquet"),
    (r"注射|静脉注射", "injection"),
    (r"输液|静脉输液|点滴", "iv_infusion"),
    (r"药物剂量|剂量|毫克|毫升|(?<![A-Za-z])mg(?![A-Za-z])|(?<![A-Za-z])ml(?![A-Za-z])", "dosage"),
    (r"准确诊断|一定是|肯定是", "diagnosis_assertion"),
    (r"救援马上到|马上就能获救|保证获救", "rescue_guarantee"),
]

RISK_TERMS: dict[str, list[str]] = {
    "respiratory_distress": ["喘不上气", "喘不过气", "呼吸困难", "窒息", "胸闷"],
    "severe_bleeding": ["流血", "出血", "大出血", "血止不住", "止血"],
    "trapped_or_crush": ["被困", "压住", "埋住", "废墟", "动不了", "挤压"],
    "collapse_aftershock": ["地震", "余震", "倒塌", "塌方", "坍塌"],
    "head_or_consciousness": ["头晕", "昏迷", "意识", "头部", "眼前发黑"],
    "hypothermia": ["好冷", "失温", "发抖", "冻"],
    "dehydration": ["很渴", "口渴", "缺水", "嘴干"],
    "pain_or_injury": ["疼", "痛", "受伤", "骨折", "扭伤"],
    "panic": ["害怕", "恐慌", "紧张", "崩溃"],
    "low_battery": ["没电", "电量", "手机快没电"],
}

BODY_PART_TERMS = [
    "腿",
    "手",
    "胳膊",
    "脚",
    "膝盖",
    "头",
    "胸",
    "胸口",
    "腹",
    "肚子",
    "背",
    "脖子",
]

SCENE_TERMS = [
    "地震",
    "废墟",
    "倒塌",
    "坍塌",
    "洪水",
    "火灾",
    "烟",
    "粉尘",
    "被困",
    "救援",
]


@dataclass
class HscRagPolicy:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_THRESHOLDS)
    )
    version: str = "manual-v1"

    def normalized_weights(self) -> dict[str, float]:
        merged = dict(DEFAULT_WEIGHTS)
        merged.update({k: float(v) for k, v in self.weights.items()})
        return merged


@dataclass
class ChunkScoreBreakdown:
    chunk_id: str
    final_score: float
    sim_vec: float
    sim_sparse: float
    quality: float
    tag_match: float
    risk_match: float
    unsafe: float
    redundancy: float
    explanation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RerankPolicy:
    """Backward-compatible wrapper for the old distance-adjustment API."""

    w_quality: float = DEFAULT_WEIGHTS["w_quality"] * 0.1
    w_enabled: float = 0.005

    @staticmethod
    def load_default() -> RerankPolicy:
        policy = load_policy()
        w = policy.normalized_weights()
        return RerankPolicy(
            w_quality=float(w.get("w_quality", DEFAULT_WEIGHTS["w_quality"])) * 0.1,
            w_enabled=0.005,
        )


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    if math.isnan(value) or math.isinf(value):
        return low
    return max(low, min(high, float(value)))


def _read_text_field(chunk: Any, name: str, default: Any = "") -> Any:
    if isinstance(chunk, Mapping):
        return chunk.get(name, default)
    return getattr(chunk, name, default)


def _chunk_text(chunk: Any) -> str:
    fields = [
        "text",
        "category",
        "sub_category",
        "dimension",
        "risk",
        "scene",
        "tags_flat",
    ]
    return " ".join(str(_read_text_field(chunk, field_name, "") or "") for field_name in fields)


def _tokenize(text: str) -> list[str]:
    raw = re.sub(r"[\s,，。；;、！？!?：:（）()\[\]【】\"']+", " ", text or "").strip()
    terms: set[str] = {item for item in raw.split(" ") if len(item) >= 2}
    compact = raw.replace(" ", "")
    for i in range(max(0, len(compact) - 1)):
        gram = compact[i : i + 2]
        if len(gram) == 2:
            terms.add(gram)
    for i in range(max(0, len(compact) - 2)):
        gram = compact[i : i + 3]
        if len(gram) == 3:
            terms.add(gram)
    return sorted(terms, key=lambda item: (-len(item), item))


def _sequence_from_context(context: Any, name: str) -> list[str]:
    if context is None:
        return []
    value = getattr(context, name, None)
    if value is None and isinstance(context, Mapping):
        value = context.get(name)
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    return [str(item) for item in value if str(item)]


def _intent_names(intent_context: Any) -> list[str]:
    names: list[str] = []
    primary = getattr(intent_context, "primary_intent", None)
    if primary is None and isinstance(intent_context, Mapping):
        primary = intent_context.get("primary_intent")
    if primary and primary != "out_of_scope":
        names.append(str(primary))
    names.extend(_sequence_from_context(intent_context, "secondary_intents"))
    return list(dict.fromkeys(name for name in names if name != "out_of_scope"))


def _terms_for_risks(intent_context: Any, query: str) -> list[str]:
    terms: list[str] = []
    for intent_name in _intent_names(intent_context):
        terms.extend(RISK_TERMS.get(intent_name, []))
    for known_terms in RISK_TERMS.values():
        if any(term in query for term in known_terms):
            terms.extend(known_terms)
    return list(dict.fromkeys(term for term in terms if term))


def load_policy(policy_path: str | Path | None = None) -> HscRagPolicy:
    path = Path(policy_path) if policy_path is not None else DEFAULT_POLICY_PATH
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return HscRagPolicy()

    obj = json.loads(path.read_text(encoding="utf-8"))
    weights = dict(DEFAULT_WEIGHTS)
    weights.update({k: float(v) for k, v in obj.get("weights", {}).items()})
    thresholds = dict(DEFAULT_THRESHOLDS)
    thresholds.update({k: float(v) for k, v in obj.get("thresholds", {}).items()})
    return HscRagPolicy(
        weights=weights,
        thresholds=thresholds,
        version=str(obj.get("version") or "manual-v1"),
    )


def compute_sparse_similarity(query: str, chunk: Any) -> float:
    query_terms = _tokenize(query)
    if not query_terms:
        return 0.0
    haystack = _chunk_text(chunk)
    hits = [term for term in query_terms if term in haystack]
    weighted_hits = sum(min(len(term), 4) for term in hits)
    weighted_total = sum(min(len(term), 4) for term in query_terms)
    return _clip(weighted_hits / max(1, weighted_total))


def compute_tag_match(
    query: str,
    chunk: Any,
    routed_tags: Sequence[str] | None = None,
    intent_context: Any = None,
) -> float:
    haystack = _chunk_text(chunk)
    candidates: list[str] = []
    candidates.extend(routed_tags or [])
    candidates.extend(_sequence_from_context(intent_context, "tags"))
    candidates.extend(_sequence_from_context(intent_context, "body_parts"))
    candidates.extend(_sequence_from_context(intent_context, "scene_terms"))
    candidates.extend(term for term in BODY_PART_TERMS if term in query)
    candidates.extend(term for term in SCENE_TERMS if term in query)
    candidates = list(dict.fromkeys(term for term in candidates if term))
    if not candidates:
        return 0.0
    hits = [term for term in candidates if term in haystack]
    return _clip(len(hits) / len(candidates))


def compute_risk_match(query: str, chunk: Any, intent_context: Any = None) -> float:
    haystack = _chunk_text(chunk)
    terms = _terms_for_risks(intent_context, query)
    if not terms:
        return 0.0
    hits = [term for term in terms if term in haystack]
    risk_field = str(_read_text_field(chunk, "risk", "") or "")
    hits.extend(
        intent_name
        for intent_name in _intent_names(intent_context)
        if intent_name in risk_field
    )
    return _clip(len(set(hits)) / len(set(terms)))


def compute_unsafe_score(chunk: Any) -> float:
    text = _chunk_text(chunk)
    if not text:
        return 0.0
    hits = [
        code
        for pattern, code in UNSAFE_PATTERNS
        if re.search(pattern, text, re.IGNORECASE)
    ]
    if not hits:
        return 0.0
    return _clip(0.35 + 0.15 * (len(set(hits)) - 1))


def compute_redundancy(chunk: Any, selected_chunks: Iterable[Any] | None = None) -> float:
    selected = list(selected_chunks or [])
    if not selected:
        return 0.0
    current_terms = set(_tokenize(str(_read_text_field(chunk, "text", "") or "")))
    if not current_terms:
        return 0.0
    max_overlap = 0.0
    for selected_chunk in selected:
        other_terms = set(_tokenize(str(_read_text_field(selected_chunk, "text", "") or "")))
        if not other_terms:
            continue
        overlap = len(current_terms & other_terms) / len(current_terms | other_terms)
        max_overlap = max(max_overlap, overlap)
    return _clip(max_overlap)


def _sim_vec_from_distance(chunk: Any) -> float:
    explicit = _read_text_field(chunk, "sim_vec", None)
    if explicit is not None:
        return _clip(float(explicit))
    distance = float(_read_text_field(chunk, "distance", 1.0) or 0.0)
    return _clip(1.0 / (1.0 + max(0.0, distance)))


def _quality_score(chunk: Any) -> float:
    raw = float(_read_text_field(chunk, "quality_score", 0.0) or 0.0)
    return _clip(raw / 5.0)


def score_chunk(
    query: str,
    chunk: Any,
    policy: HscRagPolicy | None = None,
    routed_tags: Sequence[str] | None = None,
    intent_context: Any = None,
    selected_chunks: Iterable[Any] | None = None,
) -> ChunkScoreBreakdown:
    policy = policy or load_policy()
    weights = policy.normalized_weights()
    chunk_id = str(_read_text_field(chunk, "chunk_id", "") or "")

    sim_vec = _sim_vec_from_distance(chunk)
    sim_sparse = compute_sparse_similarity(query, chunk)
    quality = _quality_score(chunk)
    tag_match = compute_tag_match(query, chunk, routed_tags, intent_context)
    risk_match = compute_risk_match(query, chunk, intent_context)
    unsafe = compute_unsafe_score(chunk)
    redundancy = compute_redundancy(chunk, selected_chunks)

    final_score = (
        weights["w_vec"] * sim_vec
        + weights["w_sparse"] * sim_sparse
        + weights["w_quality"] * quality
        + weights["w_tag"] * tag_match
        + weights["w_risk"] * risk_match
        - weights["w_unsafe"] * unsafe
        - weights["w_redundancy"] * redundancy
    )

    explanation = [
        f"sim_vec={sim_vec:.3f} from distance",
        f"sim_sparse={sim_sparse:.3f} lexical overlap",
        f"quality={quality:.3f}",
    ]
    if tag_match:
        explanation.append(f"tag_match={tag_match:.3f}")
    if risk_match:
        explanation.append(f"risk_match={risk_match:.3f}")
    if unsafe:
        explanation.append(f"unsafe_penalty={unsafe:.3f}")
    if redundancy:
        explanation.append(f"redundancy_penalty={redundancy:.3f}")
    explanation.append(f"policy={policy.version}")

    return ChunkScoreBreakdown(
        chunk_id=chunk_id,
        final_score=float(final_score),
        sim_vec=sim_vec,
        sim_sparse=sim_sparse,
        quality=quality,
        tag_match=tag_match,
        risk_match=risk_match,
        unsafe=unsafe,
        redundancy=redundancy,
        explanation=explanation,
    )


def _with_breakdown(chunk: Any, breakdown: ChunkScoreBreakdown) -> Any:
    if isinstance(chunk, dict):
        chunk["score_breakdown"] = breakdown.to_dict()
        chunk["final_distance"] = 1.0 - breakdown.final_score
        return chunk
    if hasattr(chunk, "score_breakdown"):
        chunk.score_breakdown = breakdown.to_dict()
    if hasattr(chunk, "final_distance"):
        chunk.final_distance = 1.0 - breakdown.final_score
    return chunk


def rerank_chunks(
    query: str,
    chunks: Sequence[Any],
    policy: HscRagPolicy | None = None,
    routed_tags: Sequence[str] | None = None,
    intent_context: Any = None,
    topk: int | None = None,
    max_per_group: int | None = None,
) -> list[Any]:
    policy = policy or load_policy()
    ranked: list[tuple[ChunkScoreBreakdown, Any]] = []
    selected_for_redundancy: list[Any] = []

    for chunk in chunks:
        breakdown = score_chunk(
            query=query,
            chunk=chunk,
            policy=policy,
            routed_tags=routed_tags,
            intent_context=intent_context,
            selected_chunks=selected_for_redundancy,
        )
        ranked.append((breakdown, _with_breakdown(chunk, breakdown)))
        selected_for_redundancy.append(chunk)

    ranked.sort(key=lambda item: item[0].final_score, reverse=True)

    out: list[Any] = []
    group_counts: dict[str, int] = {}
    for _breakdown, chunk in ranked:
        if max_per_group is not None:
            group_id = str(_read_text_field(chunk, "group_id", "") or "")
            if group_id and group_counts.get(group_id, 0) >= max_per_group:
                continue
            if group_id:
                group_counts[group_id] = group_counts.get(group_id, 0) + 1
        out.append(chunk)
        if topk is not None and len(out) >= topk:
            break
    return out


def final_distance(
    distance: float, quality_score: float, status: str, policy: RerankPolicy
) -> float:
    """Compatibility API: distance remains lower-is-better for legacy callers."""

    q = max(0.0, min(5.0, float(quality_score)))
    enabled = 1.0 if status in {"启用", "enabled", "active"} else 0.0
    return float(distance) - policy.w_quality * (q / 5.0) - policy.w_enabled * enabled
