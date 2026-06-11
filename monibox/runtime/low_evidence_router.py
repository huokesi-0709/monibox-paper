"""
Deterministic fallback router for low-evidence queries.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RoutedReply:
    bucket: str
    text: str
    expect_yesno: bool = False


def _has_any(text: str, kws: list[str]) -> bool:
    return any(w and w in text for w in kws)


def _infer_body_part(text: str) -> str:
    body_parts = [
        "腿",
        "膝盖",
        "脚",
        "脚踝",
        "脚趾",
        "手",
        "手腕",
        "手指",
        "胳膊",
        "肩膀",
        "肩",
        "腰",
        "背",
        "脖子",
        "头",
        "胸口",
    ]
    for part in body_parts:
        if part in text:
            return part
    return "疼的地方"


class LowEvidenceRouter:
    def route(self, user_text: str) -> RoutedReply:
        t = (user_text or "").strip()

        if _has_any(
            t,
            ["救我", "求救", "有人吗", "被困", "压住", "堵住", "出不去", "找不到出口"],
        ):
            return RoutedReply(
                bucket="rescue",
                text="先省点力，别一直大声喊。用硬东西敲3下，停5秒再重复。你能听到外面有人或机器声吗？",
                expect_yesno=True,
            )

        if _has_any(
            t, ["冷", "好冷", "发抖", "哆嗦", "冻", "失温", "冻得直抖", "快冻麻了"]
        ):
            return RoutedReply(
                bucket="cold",
                text="先把身体蜷起来，双手抱胸。拿能盖的都裹上，别直接躺冰地上。身边有能盖的吗？",
                expect_yesno=True,
            )

        if _has_any(t, ["渴", "口干", "缺水", "没水", "想喝水"]):
            return RoutedReply(
                bucket="thirst",
                text="先小口慢慢咽，别一口喝太快。尽量少说话。你身边有水或湿布吗？",
                expect_yesno=True,
            )

        if _has_any(t, ["饿", "没吃", "想吃", "肚子饿"]):
            return RoutedReply(
                bucket="hunger",
                text="先少说话，少动，省点体力。别急着乱找东西吃。你多久没吃东西了？",
                expect_yesno=False,
            )

        if _has_any(t, ["累", "很累", "困", "没力气", "撑不住"]):
            return RoutedReply(
                bucket="fatigue",
                text="先放松肩膀，慢慢呼气。别硬撑，也先别睡着。你能动动手指脚趾吗？",
                expect_yesno=True,
            )

        if _has_any(
            t,
            [
                "害怕",
                "好怕",
                "恐慌",
                "紧张",
                "心跳",
                "要失控",
                "焦虑",
                "心慌得不行",
                "慌得不行",
                "要崩了",
            ],
        ):
            return RoutedReply(
                bucket="panic",
                text="先跟我数拍呼吸。鼻子吸3拍，嘴巴呼6拍。你能跟上吗？",
                expect_yesno=True,
            )

        if _has_any(t, ["痛", "疼", "很痛", "剧痛", "刺痛"]):
            part = _infer_body_part(t)
            return RoutedReply(
                bucket="pain",
                text=f"先别硬动{part}。能垫住就先垫住，少用力。{part}有没有发麻、变形，或者一动就更痛？",
                expect_yesno=False,
            )

        if _has_any(
            t, ["好黑", "很黑", "看不见", "看不清", "站着就发黑", "眼前发黑要倒了"]
        ):
            return RoutedReply(
                bucket="vision",
                text="先别乱动，先确认是没光还是看不清。你能看清手指在眼前晃动吗？",
                expect_yesno=True,
            )

        if _has_any(t, ["不太舒服", "人不太行", "难受得不行"]):
            return RoutedReply(
                bucket="generic",
                text="你哪里最不舒服？出血、骨折还是喘不过气？",
                expect_yesno=False,
            )

        return RoutedReply(
            bucket="generic",
            text="你哪里最不舒服？出血、骨折还是喘不过气？",
            expect_yesno=False,
        )

    def followup(self, bucket: str, yes: bool) -> RoutedReply:
        b = bucket or ""

        if b == "cold":
            if yes:
                return RoutedReply(
                    b, "好，把能盖的都裹上，重点护住胸口和肚子。你哪里最冷？"
                )
            return RoutedReply(
                b, "先继续蜷紧身体，双手抱胸。慢慢呼气，别贴着冷地。身下能垫东西吗？"
            )

        if b == "thirst":
            if yes:
                return RoutedReply(b, "好，一小口一小口喝，别着急。喝完告诉我。")
            return RoutedReply(b, "先少说话，含着口水慢慢咽。嘴唇裂了也别一直舔。")

        if b == "rescue":
            if yes:
                return RoutedReply(
                    b, "听到声音时敲3下，停5秒。别一直喊，先省力。你能用硬东西敲吗？"
                )
            return RoutedReply(
                b, "每隔两三分钟敲一组，保持节奏。别着急，先省力。你身边有硬东西吗？"
            )

        if b == "fatigue":
            if yes:
                return RoutedReply(
                    b, "好，每隔几分钟轻轻动一下，别僵住。你现在冷不冷？"
                )
            return RoutedReply(
                b, "先别硬撑。保持现在的姿势，少用力。你有没有发麻或剧痛？"
            )

        if b == "panic":
            if yes:
                return RoutedReply(b, "好，继续做5轮：吸3拍，呼6拍。心跳有没有慢一点？")
            return RoutedReply(b, "先只做慢呼气，数到6再吐。我陪你数。")

        if b == "vision":
            if yes:
                return RoutedReply(
                    b, "可能是周围没光。先用手摸墙或硬东西，确认你的位置。"
                )
            return RoutedReply(b, "先坐下或侧身，别乱动。慢慢呼气。你头晕不晕？")

        return RoutedReply("generic", "你哪里最不舒服？出血、骨折还是呼吸困难？")
