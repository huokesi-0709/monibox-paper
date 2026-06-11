from app.config import KNOWLEDGE_SRC, PROJECT_ROOT
from runtime.protocol_matcher import ProtocolEngine


def test_asr_corrections_file_uses_current_knowledge_directory():
    assert KNOWLEDGE_SRC == PROJECT_ROOT / "knowledge"
    assert (KNOWLEDGE_SRC / "asr_corrections.json").exists()


def test_protocol_engine_uses_current_knowledge_directory():
    engine = ProtocolEngine()

    assert engine.protocols_path == KNOWLEDGE_SRC / "protocols.json"
    assert engine.protocols_path.exists()


def test_no_python_modules_left_at_project_root():
    root_modules = sorted(PROJECT_ROOT.glob("*.py"))

    assert root_modules == []


def test_top_level_code_directories_do_not_use_underscores():
    code_dirs = [
        "app",
        "core",
        "devices",
        "devtools",
        "knowledgekit",
        "language",
        "runtime",
        "speech",
    ]

    assert all("_" not in name for name in code_dirs)
    assert all((PROJECT_ROOT / name).is_dir() for name in code_dirs)
