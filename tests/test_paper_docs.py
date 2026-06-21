from __future__ import annotations

from app.config import PROJECT_ROOT

ZH_FILES = [
    "00_术语表.md",
    "01_论文定位与贡献.md",
    "02_Introduction.md",
    "03_Related_Work.md",
    "04_Method.md",
    "05_Experimental_Setup.md",
    "06_Results.md",
    "07_Discussion.md",
    "08_Conclusion.md",
]


def test_chinese_paper_directory_and_core_sections_exist():
    paper_dir = PROJECT_ROOT / "paper" / "zh"
    for name in ZH_FILES:
        assert (paper_dir / name).exists()

    glossary = (paper_dir / "00_术语表.md").read_text(encoding="utf-8")
    intro = (paper_dir / "02_Introduction.md").read_text(encoding="utf-8")
    method = (paper_dir / "04_Method.md").read_text(encoding="utf-8")

    assert "离线 RAG" in glossary
    assert "差分进化" in glossary
    assert intro.count("\n\n") >= 6
    assert "安全约束重排" in method
    assert "DE 只使用 dev 集，不使用 test 集" in method


def test_paper_docs_define_protocol_and_safety_boundary():
    protocol = (PROJECT_ROOT / "docs" / "experiment-protocol-zh.md").read_text(
        encoding="utf-8"
    )
    dataset = (PROJECT_ROOT / "docs" / "dataset-guideline-zh.md").read_text(
        encoding="utf-8"
    )
    reproducibility = (PROJECT_ROOT / "docs" / "reproducibility-zh.md").read_text(
        encoding="utf-8"
    )

    assert "dev 集用于开发" in protocol
    assert "test 集只用于最终" in protocol
    assert "DE 不允许在 test 集上优化" in protocol
    assert "R0" in dataset
    assert "R8" in dataset
    assert "不替代专业救援" in protocol
    assert "experiments.export_tables" in reproducibility
