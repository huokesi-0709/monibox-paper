"""
monibox/runtime/variants.py

用途
-----
VariantBank：变体库
- key -> [variant1, variant2, ...]
- 支持轮换（round-robin）与简单随机
- 用于减少“同一句不连播”的机械感，但仍保持可控文本（不依赖 LLM）

约定
----
key 建议采用：
- protocol:<protocol_id>:main
- protocol:<protocol_id>:followup
- protocol:<protocol_id>:qa_location_ack
- protocol:<protocol_id>:qa_yesno_ack
- low:<bucket>:main
- generic:reask
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class VariantBank:
    variants: dict[str, list[str]] = field(default_factory=dict)
    rr_index: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, items: list[str]):
        xs = [x.strip() for x in (items or []) if x and x.strip()]
        if not xs:
            return
        self.variants.setdefault(key, [])
        for x in xs:
            if x not in self.variants[key]:
                self.variants[key].append(x)

    def pick(self, key: str, default: str = "", mode: str = "rr") -> str:
        xs = self.variants.get(key) or []
        if not xs:
            return default
        if mode == "rand":
            return random.choice(xs)
        # round-robin
        i = self.rr_index.get(key, 0) % len(xs)
        self.rr_index[key] = i + 1
        return xs[i]


def build_default_variant_bank() -> VariantBank:
    vb = VariantBank()

    # 通用：重问/没听清
    vb.add(
        "generic:reask",
        ["我没听清。", "刚才那句我没听明白。", "再说一遍也可以，我在听。"],
    )

    # 通用：噪声引导
    # NOTE: 不再用"我在"开头的万能句，而是给出具体伤情排查引导
    vb.add(
        "protocol:prot_noise_ignore:main",
        [
            "我听到了。先说哪里不舒服。",
            "我听到了。你有出血、疼痛或喘不过气吗？",
            "我在听。先说最难受的地方。",
        ],
    )

    # 出血：主话术（只做前缀变化，不改关键动作）
    vb.add(
        "protocol:prot_bleeding_control:main",
        ["先压住伤口别松手。", "先用布压住伤口，别松手。", "先稳住，用衣物压住伤口。"],
    )
    vb.add(
        "protocol:prot_bleeding_control:qa_location_ack",
        ["好，是你的{location}。", "明白，在{location}。", "收到，{location}在流血。"],
    )
    vb.add(
        "protocol:prot_bleeding_control:qa_yesno_ack_yes", ["好。", "明白。", "收到。"]
    )
    vb.add(
        "protocol:prot_bleeding_control:qa_yesno_ack_no", ["明白。", "好。", "收到。"]
    )

    # 骨折：主话术前缀
    vb.add(
        "protocol:prot_injury_fracture:main",
        ["先别动受伤部位。", "先停下来，别移动伤处。", "先别挣扎，保持不动。"],
    )

    # 恐慌：主话术前缀
    vb.add(
        "protocol:prot_panic_breathing:main",
        ["先跟我数拍呼吸。", "先把呼吸稳住，跟我一起数。", "别急，先按节奏呼吸。"],
    )

    # 低证据 generic
    # NOTE: 三个变体从不同角度提问，避免重复感
    vb.add(
        "low:generic:main",
        [
            "你哪里最不舒服？出血的话先告诉我。",
            "你最难受的是哪里？疼痛、出血还是喘不过气？",
            "你先说最急的情况。身上有伤的话先说。",
        ],
    )

    return vb
