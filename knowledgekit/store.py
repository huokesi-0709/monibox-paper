"""
db_sqlitevec.py（写入 display_id / group_id 版）

- 启用 sqlite-vec 扩展加载
- 写 chunks 元数据（包含 display_id/group_id）
- 写 vec_chunks 向量（float32 BLOB）
"""

import json
import sqlite3
import struct
from pathlib import Path
from typing import Any

from app.config import SQL_DIR

try:
    import sqlite_vec  # type: ignore
except ImportError:
    sqlite_vec = None  # type: ignore


def flat_pipe(items: list[str]) -> str:
    items = [x.strip() for x in items if x and x.strip()]
    return "|" + "|".join(items) + "|"


def json_text(value: Any) -> str:
    if value is None:
        value = []
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def vec_to_f32_blob(vec: list[float]) -> sqlite3.Binary:
    floats = [float(x) for x in vec]
    blob = struct.pack(f"<{len(floats)}f", *floats)
    return sqlite3.Binary(blob)


class RagDB:
    def __init__(self, db_path: str, schema_path: Path | None = None):
        self.db_path = db_path
        self.schema_path = schema_path or (SQL_DIR / "schema.sql")

    def connect(self) -> sqlite3.Connection:
        if sqlite_vec is None:
            raise RuntimeError(
                "缺少 sqlite-vec 依赖，无法创建或写入向量库。"
                "请先执行 `pip install -r requirements.txt`。"
            )

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        conn.enable_load_extension(True)
        try:
            sqlite_vec.load(conn)
        finally:
            conn.enable_load_extension(False)

        return conn

    def create_tables(self):
        sql = Path(self.schema_path).read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(sql)

    def insert_chunks(self, records: list[dict[str, Any]], vectors: list[list[float]]):
        assert len(records) == len(vectors), "records 与 vectors 数量必须一致"

        with self.connect() as conn:
            cur = conn.cursor()

            for r, v in zip(records, vectors, strict=False):
                # 注意：display_id / group_id 可能缺失，允许为 None
                cur.execute(
                    """
                    INSERT INTO chunks(
                      chunk_id, display_id, group_id,
                      text, category, sub_category, dimension, topic, risk,
                      scene, emotion_fit_json, population_json,
                      source_id, status, quality_score, priority, fingerprint,
                      tts_ok, tts_style, hardware_action_hint, contraindications_json, eval_cases_json,
                      tags_flat, populations_flat
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.get("chunk_id") or r["片段ID"],
                        r.get("display_id") or r.get("显示ID"),
                        r.get("group_id") or r.get("片段组ID"),
                        r.get("text") or r["文本"],
                        r.get("知识类别") or r.get("category") or "evaluation_case",
                        r.get("二级子类") or r.get("sub_category") or "unclassified",
                        r.get("dimension") or r["维度"],
                        r.get("子主题"),
                        r.get("risk") or r["风险等级"],
                        r.get("scene") or "general",
                        json_text(r.get("emotion_fit") or []),
                        json_text(r.get("population") or r.get("适用人群") or []),
                        r.get("source_id") or r["来源ID"],
                        r.get("review_status") or r["状态"],
                        float(r.get("quality_score", r.get("人工评分", 0))),
                        int(r.get("priority") or 0),
                        r["内容指纹"],
                        1 if r.get("tts_ok", r.get("可直接播报", True)) else 0,
                        r.get("tts_style") or r.get("播报风格"),
                        r.get("hardware_action_hint") or r.get("硬件动作提示"),
                        json_text(r.get("contraindications") or r.get("禁忌") or []),
                        json_text(r.get("eval_cases") or r.get("评测用例") or []),
                        flat_pipe(r.get("tags") or r.get("标签", [])),
                        flat_pipe(r.get("population") or r.get("适用人群", [])),
                    ),
                )

                rowid = int(cur.lastrowid)
                blob = vec_to_f32_blob(v)

                cur.execute(
                    "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                    (rowid, blob),
                )

            conn.commit()
