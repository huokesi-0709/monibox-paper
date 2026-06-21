from __future__ import annotations

# ruff: noqa: S608
import re
import sqlite3
import struct
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from runtime.scoring import RerankPolicy, final_distance, load_policy, rerank_chunks
from runtime.topic_router import AutoRouter

try:
    import sqlite_vec  # type: ignore
except ImportError:
    sqlite_vec = None  # type: ignore


def vec_to_f32_blob(vec: list[float]) -> sqlite3.Binary:
    floats = [float(x) for x in vec]
    blob = struct.pack(f"<{len(floats)}f", *floats)
    return sqlite3.Binary(blob)


@dataclass
class SearchResult:
    chunk_id: str
    display_id: str | None
    group_id: str | None
    text: str
    category: str
    sub_category: str
    dimension: str
    risk: str
    scene: str
    source_id: str
    status: str
    quality_score: float
    priority: int
    hardware_action_hint: str | None
    distance: float
    final_distance: float
    tags_flat: str = ""
    score_breakdown: dict[str, Any] | None = None


class RagEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.policy = RerankPolicy.load_default()
        self.hsc_policy = load_policy()
        self.router = AutoRouter()

    def _open_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        if sqlite_vec is None:
            raise RuntimeError("sqlite-vec 不可用")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        return conn

    def _iter_fallback_terms(self, query: str) -> Iterable[str]:
        q = re.sub(r"[，。！？、,.!?\s]+", " ", query or "").strip()
        if not q:
            return []

        terms = set()
        for item in q.split():
            if len(item) >= 2:
                terms.add(item)

        raw = q.replace(" ", "")
        for i in range(max(0, len(raw) - 1)):
            gram = raw[i : i + 2]
            if len(gram) == 2:
                terms.add(gram)

        return sorted(terms, key=len, reverse=True)

    def _is_vague_query(self, query: str) -> bool:
        q = (query or "").strip()
        vague_phrases = {
            "不好",
            "不太好",
            "难受",
            "难受得不行",
            "不舒服",
            "我不太舒服",
            "不行了",
            "我人不太行",
            "不对劲",
            "有点难受",
            "有点不好",
        }
        return q in vague_phrases

    def is_vague_query(self, query: str) -> bool:
        return self._is_vague_query(query)

    def _fallback_score(self, query: str, row: sqlite3.Row) -> float:
        text = str(row["text"] or "")
        tags = str(row["tags_flat"] or "")
        haystack = f"{text} {tags}"
        score = 0.0

        for term in self._iter_fallback_terms(query):
            if term in haystack:
                score += 1.0 + min(len(term), 6) * 0.12

        if query and query in text:
            score += 2.5

        uniq_q = {ch for ch in query if not ch.isspace()}
        uniq_t = {ch for ch in text if not ch.isspace()}
        if uniq_q and uniq_t:
            overlap = len(uniq_q & uniq_t) / len(uniq_q)
            score += overlap

        return score

    def _query_term_adjustment(
        self, query: str, text: str, tags_flat: str = ""
    ) -> float:
        """
        基于 query 与 chunk 文本的白名单/黑名单轻量调权。
        返回值直接加到 final_distance 上：
        - 负数：更优先
        - 正数：更靠后
        """
        q = (query or "").strip()
        body = f"{text or ''} {tags_flat or ''}"
        adjust = 0.0

        if any(term in q for term in ("洪水求救", "水里求救", "泡水求救", "求救")):
            if any(
                term in body for term in ("求救信号", "信号", "哨子", "手电", "敲金属")
            ):
                adjust -= 0.10
            if any(
                term in body
                for term in ("冲洗伤口", "清洗伤口", "伤口清洁", "清洁干燥")
            ):
                adjust += 0.18

        if any(
            term in q
            for term in ("被压住了", "压住了", "腿被压住", "手被压住", "压着动不了")
        ):
            if any(term in body for term in ("压了多久", "说话", "呼吸", "别动")):
                adjust -= 0.06
            if any(term in body for term in ("布条", "扎紧", "近心端")):
                adjust += 0.22

        if any(term in q for term in ("灰很大", "灰太大", "粉尘很大", "一直咳嗽")):
            if any(term in body for term in ("口鼻", "扬灰", "慢呼吸", "小口慢呼吸")):
                adjust -= 0.05
            if any(term in body for term in ("眼睛", "闭上", "往干净的地方挪")):
                adjust += 0.04

        if any(
            term in q for term in ("我很渴", "特别渴", "口特别干", "嘴里发干")
        ) and any(term in body for term in ("小口", "别大口", "省水", "少说话")):
            adjust -= 0.05

        return adjust

    def _query_blacklist(self, query: str) -> set[str]:
        q = (query or "").strip()
        blocked: set[str] = set()

        if any(
            term in q for term in ("洪水求救", "水里求救", "泡水求救", "被水围困求救")
        ):
            blocked.add("k_qa_00053_3c4753f7be_00_287c673a")

        if any(
            term in q
            for term in ("被压住了", "压住了", "腿被压住", "手被压住", "压着动不了")
        ):
            blocked.add("k_qa_00010_767a838612_01_5fc465dc")

        return blocked

    def _query_whitelist(self, query: str) -> set[str] | None:
        q = (query or "").strip()

        if any(
            term in q for term in ("洪水求救", "水里求救", "泡水求救", "被水围困求救")
        ):
            return {
                "k_qa_00054_c52d3cb306_00_691d613e",
                "k_qa_00052_062edd73f8_00_2eb0e23d",
            }

        if any(
            term in q
            for term in ("被压住了", "压住了", "腿被压住", "手被压住", "压着动不了")
        ):
            return {
                "k_qa_00022_7832d82c23_00_400fdd9b",
                "k_qa_00010_767a838612_00_9df64882",
                "k_qa_00034_6591b01571_00_9f365ae0",
                "k_qa_00039_1c76365fef_00_4c9db65a",
            }

        if any(term in q for term in ("灰很大", "灰太大", "粉尘很大", "一直咳嗽")):
            return {
                "k_qa_00019_e83ba81f42_00_940855a8",
                "k_qa_00031_a5cecd0ea0_00_60f374e4",
            }

        if any(
            term in q for term in ("我很渴", "特别渴", "口特别干", "嘴里发干", "缺水")
        ):
            return {
                "k_qa_00017_fc8e9b9921_00_bdafbfa0",
                "k_qa_00005_748d19828b_01_386e1440",
                "k_qa_00029_9c0f602694_00_bbd7120e",
                "k_qa_00005_748d19828b_00_e307bde1",
            }

        return None

    def _query_whitelist_adjustment(self, query: str, chunk_id: str) -> float:
        whitelist = self._query_whitelist(query)
        if not whitelist:
            return 0.0
        return 0.0 if chunk_id in whitelist else 0.08

    def _hsc_rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        topk: int,
        tags: list[str] | None = None,
        max_per_group: int = 1,
        intent_context: Any = None,
    ) -> list[SearchResult]:
        return rerank_chunks(
            query=query,
            chunks=candidates,
            policy=self.hsc_policy,
            routed_tags=tags,
            intent_context=intent_context,
            topk=topk,
            max_per_group=max_per_group,
        )

    def _fallback_search(
        self,
        query: str,
        topk: int = 5,
        dimension: str | None = None,
        tags: list[str] | None = None,
        status_exclude: str = "停用",
        max_per_group: int = 1,
        intent_context: Any = None,
    ) -> list[SearchResult]:

        if self._is_vague_query(query):
            return []

        blocked_ids = self._query_blacklist(query)

        where = ["status <> :ex_status"]
        params: dict[str, Any] = {"ex_status": status_exclude}

        if dimension:
            where.append("dimension = :dimension")
            params["dimension"] = dimension

        if tags:
            ors = []
            for i, t in enumerate(tags):
                k = f"t{i}"
                params[k] = f"%|{t}|%"
                ors.append(f"tags_flat LIKE :{k}")
            where.append("(" + " OR ".join(ors) + ")")

        where_sql = " WHERE " + " AND ".join(where)

        sql = (
            f"""
        SELECT
          chunk_id, display_id, group_id, text, category, sub_category, dimension,
          risk, scene, source_id, status, quality_score, priority, hardware_action_hint, tags_flat
        FROM chunks
        {where_sql}
        LIMIT 800;
        """
        )

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        scored = []
        for r in rows:
            if str(r["chunk_id"] or "") in blocked_ids:
                continue
            score = self._fallback_score(query, r)
            if score <= 0:
                continue

            # 将“分数越高越好”映射成与原接口兼容的“距离越低越好”
            d = max(0.05, 1.0 / (1.0 + score))
            q = float(r["quality_score"])
            st = r["status"]
            d_final = (
                final_distance(d, q, st, self.policy)
                + self._query_term_adjustment(
                    query=query,
                    text=str(r["text"] or ""),
                    tags_flat=str(r["tags_flat"] or ""),
                )
                + self._query_whitelist_adjustment(
                    query=query, chunk_id=str(r["chunk_id"] or "")
                )
            )
            scored.append((d_final, d, r))

        out: list[SearchResult] = []
        for d_final, d, r in scored:
            out.append(
                SearchResult(
                    chunk_id=r["chunk_id"],
                    display_id=r["display_id"],
                    group_id=r["group_id"],
                    text=r["text"],
                    category=r["category"],
                    sub_category=r["sub_category"],
                    dimension=r["dimension"],
                    risk=r["risk"],
                    scene=r["scene"],
                    source_id=r["source_id"],
                    status=r["status"],
                    quality_score=float(r["quality_score"]),
                    priority=int(r["priority"] or 0),
                    hardware_action_hint=r["hardware_action_hint"],
                    distance=float(d),
                    final_distance=float(d_final),
                    tags_flat=str(r["tags_flat"] or ""),
                )
            )
        return self._hsc_rerank(
            query=query,
            candidates=out,
            topk=topk,
            tags=tags,
            max_per_group=max_per_group,
            intent_context=intent_context,
        )

    def search(
        self,
        query: str,
        topk: int = 5,
        pool_mult: int = 8,
        dimension: str | None = None,
        tags: list[str] | None = None,
        status_exclude: str = "停用",
        max_per_group: int = 1,
        intent_context: Any = None,
    ) -> list[SearchResult]:

        try:
            from knowledgekit.embedder import embed_texts
        except Exception:
            embed_texts = None  # type: ignore

        if sqlite_vec is None or embed_texts is None:
            return self._fallback_search(
                query=query,
                topk=topk,
                dimension=dimension,
                tags=tags,
                status_exclude=status_exclude,
                max_per_group=max_per_group,
                intent_context=intent_context,
            )

        try:
            qvec = embed_texts([query])[0]
            qblob = vec_to_f32_blob(qvec)
        except Exception:
            return self._fallback_search(
                query=query,
                topk=topk,
                dimension=dimension,
                tags=tags,
                status_exclude=status_exclude,
                max_per_group=max_per_group,
                intent_context=intent_context,
            )

        where = ["c.status <> :ex_status"]
        params: dict[str, Any] = {"ex_status": status_exclude}

        if dimension:
            where.append("c.dimension = :dimension")
            params["dimension"] = dimension

        if tags:
            ors = []
            for i, t in enumerate(tags):
                k = f"t{i}"
                params[k] = f"%|{t}|%"
                ors.append(f"c.tags_flat LIKE :{k}")
            where.append("(" + " OR ".join(ors) + ")")

        where_sql = " WHERE " + " AND ".join(where)

        k_pool = min(max(topk, topk * pool_mult), 300)

        sql = (
            f"""
        WITH knn AS (
          SELECT rowid, distance
          FROM vec_chunks
          WHERE embedding MATCH :qvec
            AND k = :kpool
        )
        SELECT
          c.chunk_id, c.display_id, c.group_id,
          c.text, c.category, c.sub_category, c.dimension, c.risk, c.scene,
          c.source_id, c.status, c.quality_score, c.priority, c.hardware_action_hint,
          c.tags_flat,
          knn.distance
        FROM knn
        JOIN chunks c ON c.id = knn.rowid
        {where_sql}
        ORDER BY knn.distance
        LIMIT :kpool;
        """
        )

        params["qvec"] = qblob
        params["kpool"] = int(k_pool)

        try:
            conn = self._open_db()
            rows = conn.execute(sql, params).fetchall()
            conn.close()
        except Exception:
            return self._fallback_search(
                query=query,
                topk=topk,
                dimension=dimension,
                tags=tags,
                status_exclude=status_exclude,
                max_per_group=max_per_group,
                intent_context=intent_context,
            )

        if not rows:
            return self._fallback_search(
                query=query,
                topk=topk,
                dimension=dimension,
                tags=tags,
                status_exclude=status_exclude,
                max_per_group=max_per_group,
                intent_context=intent_context,
            )

        scored = []
        blocked_ids = self._query_blacklist(query)
        for r in rows:
            if str(r["chunk_id"] or "") in blocked_ids:
                continue
            d = float(r["distance"])
            q = float(r["quality_score"])
            st = r["status"]
            d_final = (
                final_distance(d, q, st, self.policy)
                + self._query_term_adjustment(query=query, text=str(r["text"] or ""))
                + self._query_whitelist_adjustment(
                    query=query, chunk_id=str(r["chunk_id"] or "")
                )
            )
            scored.append((d_final, r))

        if not scored:
            return self._fallback_search(
                query=query,
                topk=topk,
                dimension=dimension,
                tags=tags,
                status_exclude=status_exclude,
                max_per_group=max_per_group,
                intent_context=intent_context,
            )
        out: list[SearchResult] = []
        for d_final, r in scored:
            out.append(
                SearchResult(
                    chunk_id=r["chunk_id"],
                    display_id=r["display_id"],
                    group_id=r["group_id"],
                    text=r["text"],
                    category=r["category"],
                    sub_category=r["sub_category"],
                    dimension=r["dimension"],
                    risk=r["risk"],
                    scene=r["scene"],
                    source_id=r["source_id"],
                    status=r["status"],
                    quality_score=float(r["quality_score"]),
                    priority=int(r["priority"] or 0),
                    hardware_action_hint=r["hardware_action_hint"],
                    distance=float(r["distance"]),
                    final_distance=float(d_final),
                    tags_flat=str(r["tags_flat"] or ""),
                )
            )
        return self._hsc_rerank(
            query=query,
            candidates=out,
            topk=topk,
            tags=tags,
            max_per_group=max_per_group,
            intent_context=intent_context,
        )

    def auto_search(
        self, query: str, topk: int = 5, auto_top_tags: int = 2
    ) -> list[SearchResult]:
        rr = self.router.route(query, top_tags=auto_top_tags)
        # 跨维度：不锁 dimension，只用 tags
        dim = None if rr.cross_dimension else rr.dimension
        return self.search(query, topk=topk, dimension=dim, tags=rr.tags)
