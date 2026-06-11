"""
monibox/runtime/protocol_fsm.py

用途
-----
协议交互处理器：管理协议的 pending/active 状态机和所有 QA 交互逻辑。
从原 session.py 中剥离以下方法：
- _should_enable_qa, _extract_last_question
- _set_active_protocol, _set_protocol_pending
- _is_noise_like, _maybe_reask_pending_protocol
- _try_protocol_pending_answer, _try_active_protocol_freeform
- _pick_protocol_actions, _extract_tts_texts, _pick_followup_text_for_slot
- _refresh_active_and_pending_from_text
"""

from __future__ import annotations

import re
import time
from typing import Any

from monibox.runtime.emotions import EmotionStrategyBook
from monibox.runtime.slot_parser import (
    infer_slot_from_text,
    parse_location,
    parse_yesno,
)
from monibox.runtime.runtime_config import RuntimeConfig
from monibox.runtime.guard import SafetyGuard
from monibox.runtime.preprocessor import (
    dedup_sentences,
    force_second_person,
    smart_cut,
)


class ProtocolHandler:
    """
    协议上下文状态机：
    - pending_protocol: 协议刚问了一个问题，等待用户回答（location / yesno）
    - active_protocol: 协议仍在"活跃窗口"内，短答会被当作对该协议的追问回应
    - _prot_state: 各协议的冷却时间 + 步骤计数器
    """

    def __init__(
        self,
        guard: SafetyGuard,
        cfg: RuntimeConfig,
        emotion_book: EmotionStrategyBook | None = None,
    ):
        self.guard = guard
        self.cfg = cfg
        self.emotion_book = emotion_book or EmotionStrategyBook()

        # 协议状态
        self.pending_protocol: dict[str, Any] | None = (
            None  # {pid, proto, slot, until, question, reask_count}
        )
        self.active_protocol: dict[str, Any] | None = None  # {pid, proto, until}
        self._prot_state: dict[str, tuple[float, int]] = {}

    # ========== 状态管理 ==========

    def clear_state(self) -> None:
        """抢占时清空所有协议状态"""
        self.pending_protocol = None
        self.active_protocol = None

    def set_active(self, pid: str, proto: dict[str, Any]) -> None:
        """设置活跃协议（若 QA 未启用则不设置）"""
        if not self._should_enable_qa(proto):
            self.active_protocol = None
            return
        self.active_protocol = {
            "pid": pid,
            "proto": proto,
            "until": time.monotonic() + self.cfg.active_protocol_ttl_sec,
        }

    def set_pending(self, pid: str, proto: dict[str, Any], question_text: str) -> None:
        """设置等待回答的协议问题"""
        if not self._should_enable_qa(proto):
            self.pending_protocol = None
            return
        slot = infer_slot_from_text(question_text)
        if slot is None:
            self.pending_protocol = None
            return
        self.pending_protocol = {
            "pid": pid,
            "proto": proto,
            "slot": slot,
            "until": time.monotonic() + self.cfg.protocol_qa_ttl_sec,
            "question": self.extract_last_question(question_text),
            "reask_count": 0,
        }
        if self.cfg.debug_runtime:
            print(f"[PROTOCOL_PENDING] pid={pid} slot={slot}")

    def refresh_active_and_pending_from_text(
        self, pid: str, proto: dict[str, Any], text: str
    ) -> None:
        """
        作用：
        1) 刷新 active_protocol 的 TTL（保持流程不中断）
        2) 如果本轮输出里包含问句（location/yesno），立刻把它写入 pending_protocol
           这样用户下一句"没有/有/变少了/还在"等就会被正确当作回答，而不会掉到 RAG。
        """
        # 1) 刷新 active（延长窗口）
        if self.active_protocol and self.active_protocol.get("pid") == pid:
            self.active_protocol["until"] = (
                time.monotonic() + self.cfg.active_protocol_ttl_sec
            )

        # 2) 提取最后问句并写入 pending
        q = self.extract_last_question(text)
        slot = infer_slot_from_text(q) if q else None
        if slot is None:
            return

        self.pending_protocol = {
            "pid": pid,
            "proto": proto,
            "slot": slot,
            "until": time.monotonic() + self.cfg.protocol_qa_ttl_sec,
            "question": q,
            "reask_count": 0,
        }
        if self.cfg.debug_runtime:
            print(f"[PROTOCOL_PENDING] pid={pid} slot={slot}")

    # ========== QA 交互 ==========

    def try_pending_answer(self, user_text: str) -> tuple[str, str] | None:
        """
        尝试将用户输入解析为对 pending 问题的回答。
        成功则返回 (回复文本, protocol_id)，否则返回 None。
        """
        if not self.pending_protocol:
            return None
        if time.monotonic() > float(self.pending_protocol.get("until", 0.0)):
            self.pending_protocol = None
            return None

        pid = str(self.pending_protocol.get("pid") or "")
        proto = self.pending_protocol.get("proto")
        slot = str(self.pending_protocol.get("slot") or "")
        if not isinstance(proto, dict):
            self.pending_protocol = None
            return None

        val: Any = None
        if slot == "location":
            val = parse_location(user_text)
        elif slot == "yesno":
            val = parse_yesno(user_text)

        if val is None:
            special = self._try_pending_status_followup(
                pid=pid, proto=proto, slot=slot, user_text=user_text
            )
            if special is not None:
                return special, pid

        if val is None:
            return None

        self.pending_protocol = None
        self.set_active(pid, proto)

        follow = self._pick_followup_text_for_slot(proto, slot, val)
        merged = self._merge_pending_followup(slot=slot, val=val, follow=follow)

        if self.cfg.debug_runtime:
            print(f"[PROTOCOL_QA_FOLLOWUP] pid={pid} slot={slot} val={val}")
            print("[FINAL]", merged)

        slot2 = infer_slot_from_text(follow)
        if slot2 is not None:
            self.pending_protocol = {
                "pid": pid,
                "proto": proto,
                "slot": slot2,
                "until": time.monotonic() + self.cfg.protocol_qa_ttl_sec,
                "question": self.extract_last_question(follow),
                "reask_count": 0,
            }
            if self.cfg.debug_runtime:
                print(f"[PROTOCOL_PENDING] pid={pid} slot={slot2}")

        return merged, pid

    def _try_pending_status_followup(
        self, pid: str, proto: dict[str, Any], slot: str, user_text: str
    ) -> str | None:
        """
        某些协议在等待 yes/no 时，用户会直接汇报状态变化，而不是回答“有/没有”。
        这里优先接住这类短答，避免误判成 reask。
        """
        t = (user_text or "").strip()
        if slot != "yesno" or not t:
            return None

        if pid == "prot_syncope_blackout" and any(
            token in t for token in ("不那么晕", "不太晕", "好多了", "好点了", "缓过来")
        ):
            merged = (
                "好，先继续躺着别起来，慢慢呼气。能喝水就小口喝两口。眼前还发黑吗？"
            )
            self.pending_protocol = None
            self.set_active(pid, proto)
            self.refresh_active_and_pending_from_text(pid, proto, merged)
            return merged

        return None

    def handle_pending_noise(self, user_text: str) -> tuple[str, str] | None:
        """
        协议挂起时，对"喂/你好/在吗"这类噪声输入给出更自然的短回应，
        同时把用户拉回当前问题，而不是直接进入机械 reask。
        """
        if not self.pending_protocol:
            return None
        if time.monotonic() > float(self.pending_protocol.get("until", 0.0)):
            self.pending_protocol = None
            return None
        if not self._is_attention_noise(user_text):
            return None

        pid = str(self.pending_protocol.get("pid") or "")
        slot = str(self.pending_protocol.get("slot") or "")
        q = str(self.pending_protocol.get("question") or "").strip()

        if slot == "location":
            text = f"我听到了。先告诉我流血的位置。{q}"
        elif slot == "yesno":
            text = f"我听到了。先回答我有或没有。{q}"
        else:
            text = (
                f"我听到了。先回答我刚才那个问题。{q}"
                if q
                else "我听到了。先回答我刚才那个问题。"
            )

        merged = smart_cut(
            dedup_sentences(force_second_person(text.strip())),
            self.cfg.max_chars_protocol_followup,
        )
        return merged, pid

    def handle_pending_soft_interruption(
        self, user_text: str
    ) -> tuple[str, str] | None:
        """
        协议挂起时，遇到情绪化插话或辱骂，先做一句柔性回拉，
        再把用户带回当前高优问题。
        """
        if not self.pending_protocol:
            return None
        if time.monotonic() > float(self.pending_protocol.get("until", 0.0)):
            self.pending_protocol = None
            return None

        slot = str(self.pending_protocol.get("slot") or "")
        q = str(self.pending_protocol.get("question") or "").strip()
        pid = str(self.pending_protocol.get("pid") or "")
        t = (user_text or "").strip()
        if not t:
            return None

        if slot == "location" and parse_location(t) is not None:
            return None
        if slot == "yesno" and parse_yesno(t) is not None:
            return None

        emotion = self.emotion_book.detect(t, allowed={"panic", "despair", "angry"})
        anger_like = emotion is not None and emotion.emotion == "angry"
        panic_like = emotion is not None and emotion.emotion in {"panic", "despair"}

        if not anger_like and not panic_like:
            return None

        if slot == "location":
            prefix = (
                "先别急，先告诉我流血的位置。"
                if panic_like
                else "先别多说，先告诉我流血的位置。"
            )
        elif slot == "yesno":
            prefix = (
                "先别急，先回答我有或没有。"
                if panic_like
                else "先别多说，先回答我有或没有。"
            )
        else:
            prefix = (
                "先别急，先回答我刚才那个问题。"
                if panic_like
                else "先别多说，先回答我刚才那个问题。"
            )

        text = f"{prefix}{q}" if q else prefix
        merged = smart_cut(
            dedup_sentences(force_second_person(text.strip())),
            self.cfg.max_chars_protocol_followup,
        )
        return merged, pid

    def maybe_reask(self, user_text: str) -> str | None:
        """如果用户没有给出有效回答，重新追问（最多 2 次）"""
        if not self.pending_protocol:
            return None
        if time.monotonic() > float(self.pending_protocol.get("until", 0.0)):
            self.pending_protocol = None
            return None

        slot = str(self.pending_protocol.get("slot") or "")
        q = str(self.pending_protocol.get("question") or "").strip()
        if not q:
            return None

        if slot == "location" and parse_location(user_text) is not None:
            return None
        if slot == "yesno" and parse_yesno(user_text) is not None:
            return None

        cnt = int(self.pending_protocol.get("reask_count", 0) or 0)
        if cnt >= 2:
            self.pending_protocol = None
            return None
        self.pending_protocol["reask_count"] = cnt + 1

        if self._is_noise_like(user_text):
            return f"我没听清。{q}"
        if slot == "location":
            return f"我需要你告诉我流血的部位（比如脚、腿、手）。{q}"
        if slot == "yesno":
            return f"我需要你回答有或没有。{q}"
        return f"我没听清。{q}"

    def try_active_freeform(self, user_text: str) -> tuple[str, str] | None:
        """对活跃协议窗口内的短答（≤6字）做自由应答"""
        if not self.active_protocol:
            return None
        if time.monotonic() > float(self.active_protocol.get("until", 0.0)):
            self.active_protocol = None
            return None

        t = (user_text or "").strip()
        # 只对短答生效
        if len(t) > 6 and "只有" not in t and "就" not in t:
            return None

        pid = str(self.active_protocol.get("pid") or "")
        proto = self.active_protocol.get("proto")
        if not isinstance(proto, dict):
            return None

        yn = parse_yesno(t)
        if yn is not None:
            follow = self._pick_followup_text_for_slot(proto, "yesno", yn)
            merged = smart_cut(
                dedup_sentences(
                    force_second_person(("好。" if yn else "明白。") + " " + follow)
                ),
                self.cfg.max_chars_protocol_followup,
            )
            if self.cfg.debug_runtime:
                print(f"[ACTIVE_PROTOCOL_FOLLOW] pid={pid} slot=yesno val={yn}")
                print("[FINAL]", merged)
            self.refresh_active_and_pending_from_text(pid, proto, merged)
            return merged, pid

        loc = parse_location(t)
        if loc is not None:
            follow = self._pick_followup_text_for_slot(proto, "location", loc)
            merged = smart_cut(
                dedup_sentences(force_second_person(f"好，是你的{loc}。{follow}")),
                self.cfg.max_chars_protocol_followup,
            )
            if self.cfg.debug_runtime:
                print(f"[ACTIVE_PROTOCOL_FOLLOW] pid={pid} slot=location val={loc}")
                print("[FINAL]", merged)
            self.refresh_active_and_pending_from_text(pid, proto, merged)
            return merged, pid

        return None

    def _merge_pending_followup(self, slot: str, val: Any, follow: str) -> str:
        """
        合并 QA 应答与 followup，尽量避免：
        1. “好。好……”
        2. “是你的腿。腿在流血……”
        3. 语义重复但不增加信息的前缀
        """
        f = (follow or "").strip()

        if slot == "location":
            canon = str(val).strip()
            if canon:
                if "{location}" in f:
                    f = f.replace("{location}", canon)

                if f.startswith(
                    ("好，", "好。", "明白，", "明白。", "收到，", "收到。")
                ) or (canon and canon in f):
                    merged = f
                else:
                    merged = f"好，{canon}在流血。{f}" if f else f"好，{canon}在流血。"
            else:
                merged = f
        elif slot == "yesno":
            if f.startswith(("好，", "好。", "明白，", "明白。", "收到，", "收到。")):
                merged = f
            else:
                ack = "好。" if bool(val) else "明白。"
                merged = f"{ack} {f}".strip() if f else ack
        else:
            merged = f

        return smart_cut(
            dedup_sentences(force_second_person(merged.strip())),
            self.cfg.max_chars_protocol_followup,
        )

    # ========== 协议动作选择 ==========

    def pick_actions(
        self, proto: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], bool, int]:
        """根据冷却状态选择主动作或跟进动作"""
        pid = str(proto.get("protocol_id") or "")
        now = time.monotonic()
        cooldown = float(
            proto.get("cooldown_sec", self.cfg.protocol_default_cooldown_sec) or 0.0
        )
        last_ts, step = self._prot_state.get(pid, (0.0, 0))

        in_cooldown = cooldown > 0 and (now - last_ts) < cooldown
        if not in_cooldown:
            self._prot_state[pid] = (now, 0)
            return list(proto.get("actions", []) or []), False, 0

        followups = proto.get("followup_actions")
        if isinstance(followups, list) and followups:
            step2 = step + 1
            self._prot_state[pid] = (now, step2)
            idx = (step2 - 1) % len(followups)
            chosen = followups[idx]
            if isinstance(chosen, dict):
                return [chosen], True, step2

        step2 = step + 1
        self._prot_state[pid] = (now, step2)
        return list(proto.get("actions", []) or []), True, step2

    def extract_tts_texts(self, actions: list[dict[str, Any]]) -> list[str]:
        """从动作列表中提取所有 TTS 文本"""
        out = []
        for a in actions:
            if isinstance(a, dict) and a.get("type") == "tts":
                out.append(str(a.get("text", "") or ""))
        return [x for x in out if x.strip()]

    # ========== 辅助方法 ==========

    def _should_enable_qa(self, proto: dict[str, Any]) -> bool:
        """判断协议是否启用 QA 追问"""
        if proto.get("enable_qa") is False:
            return False
        if proto.get("enable_qa") is True:
            return True
        return int(proto.get("priority", 0) or 0) >= 50

    def extract_last_question(self, text: str) -> str:
        """提取文本中最后一个问句"""
        t = (text or "").strip()
        if not t:
            return ""
        idx = max(t.rfind("？"), t.rfind("?"))
        if idx == -1:
            return t
        start = max(
            t.rfind("。", 0, idx),
            t.rfind("！", 0, idx),
            t.rfind("!", 0, idx),
            t.rfind(".", 0, idx),
        )
        if start == -1:
            return t[: idx + 1].strip()
        return t[start + 1 : idx + 1].strip()

    def _is_noise_like(self, text: str) -> bool:
        """检测是否为噪声/无效输入"""
        t = (text or "").strip()
        if not t:
            return True
        if len(t) <= 2:
            return True
        if re.fullmatch(r"[A-Za-z0-9_\-]+", t):
            return True
        return False

    def _is_attention_noise(self, text: str) -> bool:
        """
        只识别“喂/你好/在吗”这类招呼词。
        不把合法的短答（如“腿”“有”“没有”）误判成噪声。
        """
        t = (text or "").strip()
        if not t:
            return False
        return t in {
            "喂",
            "喂喂",
            "喂？",
            "喂?",
            "你好",
            "您好",
            "在吗",
            "在嘛",
            "有人吗",
            "听到吗",
            "听得到吗",
            "听见吗",
            "嗯",
            "啊",
            "哦",
        }

    def _pick_followup_text_for_slot(
        self, proto: dict[str, Any], slot: str, val: Any
    ) -> str:
        """根据槽位和值选择协议定义的跟进话术"""
        qaf = proto.get("qa_followups")
        if isinstance(qaf, dict):
            if slot == "yesno" and isinstance(val, bool):
                k = "yesno_true" if val else "yesno_false"
                if isinstance(qaf.get(k), str) and str(qaf.get(k)).strip():
                    return str(qaf[k]).strip()
            if isinstance(qaf.get(slot), str) and str(qaf.get(slot)).strip():
                s = str(qaf[slot]).strip()
                if slot == "location":
                    s = s.replace("{location}", str(val))
                return s

        return self.cfg.protocol_generic_followup
