"""Shared schema for RAIR-RAG downstream experiments."""

from benchmarks.rair_rag.downstream.llm_clients import (
    BaseGenerator,
    LocalLlamaCppGenerator,
    ReferenceApiGenerator,
)
from benchmarks.rair_rag.downstream.metrics import (
    compute_case_metrics,
    compute_retrieval_metrics,
)
from benchmarks.rair_rag.downstream.prompt_builders import (
    build_rair_generation_prompt,
    build_vanilla_generation_prompt,
)
from benchmarks.rair_rag.downstream.rubric import evaluate_generation
from benchmarks.rair_rag.downstream.schema import (
    DownstreamCase,
    DownstreamPrediction,
    EvaluationResult,
    GenerationOutput,
    RetrievedEvidence,
)
from benchmarks.rair_rag.downstream.systems import (
    BertRagSystem,
    DownstreamSystem,
    KeywordRagSystem,
    RairRagSystem,
    VanillaRagSystem,
    default_downstream_systems,
)

__all__ = [
    "BaseGenerator",
    "BertRagSystem",
    "DownstreamCase",
    "DownstreamPrediction",
    "DownstreamSystem",
    "EvaluationResult",
    "GenerationOutput",
    "KeywordRagSystem",
    "LocalLlamaCppGenerator",
    "RairRagSystem",
    "ReferenceApiGenerator",
    "RetrievedEvidence",
    "VanillaRagSystem",
    "build_rair_generation_prompt",
    "build_vanilla_generation_prompt",
    "compute_case_metrics",
    "compute_retrieval_metrics",
    "default_downstream_systems",
    "evaluate_generation",
]
