from __future__ import annotations

from app.config import PROJECT_ROOT


def test_stage12_paper_files_exist():
    paths = [
        PROJECT_ROOT / "paper" / "README.md",
        PROJECT_ROOT / "paper" / "manuscript_zh.md",
        PROJECT_ROOT / "paper" / "tables.md",
        PROJECT_ROOT / "paper" / "figures.md",
        PROJECT_ROOT / "paper" / "reproducibility.md",
        PROJECT_ROOT / "docs" / "stage12_paper_draft.md",
    ]

    for path in paths:
        assert path.exists()


def test_stage12_manuscript_contains_required_sections():
    text = (PROJECT_ROOT / "paper" / "manuscript_zh.md").read_text(
        encoding="utf-8"
    )

    assert "## 摘要" in text
    assert "## 3 方法" in text
    assert "## 4 实验设置" in text
    assert "## 7 局限性" in text
    assert "## 8 结论" in text
    assert "不提供医学诊断" in text
    assert "不保证救援结果" in text


def test_stage12_supporting_docs_reference_reproducible_outputs():
    reproducibility = (PROJECT_ROOT / "paper" / "reproducibility.md").read_text(
        encoding="utf-8"
    )
    tables = (PROJECT_ROOT / "paper" / "tables.md").read_text(encoding="utf-8")
    readme = (PROJECT_ROOT / "paper" / "README.md").read_text(encoding="utf-8")

    assert "scripts/export_tables.sh" in reproducibility
    assert "trace_audit_results.csv" in tables
    assert "clean_dev / robustness_dev" in readme
