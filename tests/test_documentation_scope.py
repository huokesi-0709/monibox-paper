from __future__ import annotations

from app.config import PROJECT_ROOT

CANONICAL_DOCS = [
    PROJECT_ROOT / "docs" / "RAIR_RAG_routing_reproduction.md",
    PROJECT_ROOT / "docs" / "RAIR_RAG_downstream_reproduction.md",
    PROJECT_ROOT / "models" / "README.md",
    PROJECT_ROOT / "models" / "llm" / "README.md",
]

HISTORICAL_DOCS = [
    PROJECT_ROOT / "docs" / "algorithm-comparison.md",
    PROJECT_ROOT / "docs" / "dataset-guideline-zh.md",
    PROJECT_ROOT / "docs" / "experiment-protocol-zh.md",
    PROJECT_ROOT / "docs" / "final_v2_paper_fill_guide.md",
    PROJECT_ROOT / "docs" / "formal-evaluation-calibration-zh.md",
    PROJECT_ROOT / "docs" / "HSC-RAG-DE_阶段进度教程_论文写作与代码规划.md",
    PROJECT_ROOT / "docs" / "method-design-zh.md",
    PROJECT_ROOT / "docs" / "offline-safe-rag.md",
    PROJECT_ROOT / "docs" / "paper-plan-zh.md",
    PROJECT_ROOT / "docs" / "paper_scope.md",
    PROJECT_ROOT / "docs" / "reproducibility-zh.md",
    PROJECT_ROOT / "paper" / "en" / "manuscript.md",
    *sorted((PROJECT_ROOT / "docs").glob("stage*.md")),
]


def test_canonical_docs_are_not_marked_obsolete() -> None:
    for path in CANONICAL_DOCS:
        text = path.read_text(encoding="utf-8")

        assert "OBSOLETE / HISTORICAL" not in text


def test_historical_docs_are_marked_obsolete() -> None:
    for path in HISTORICAL_DOCS:
        text = path.read_text(encoding="utf-8")

        assert "OBSOLETE / HISTORICAL" in text
        assert "docs/RAIR_RAG_routing_reproduction.md" in text
        assert "docs/RAIR_RAG_downstream_reproduction.md" in text
