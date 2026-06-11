from __future__ import annotations

import re

_LOCATION_PAT = re.compile(r"(哪里|哪儿|哪裡|什么部位|哪(里|裡)|哪个部位|哪一处)")
_YESNO_PAT = re.compile(r"(有没有|是否|能不能|可以吗|能吗|行吗|对吗|是不是|有吗|嗎\?)")

_TC_SC_MAP = [
    ("膝蓋", "膝盖"),
    ("腳踝", "脚踝"),
    ("腳趾", "脚趾"),
    ("右腳", "右脚"),
    ("左腳", "左脚"),
    ("沒有", "没有"),
    ("沒", "没"),
    ("嗎", "吗"),
    ("腳", "脚"),
    ("頭", "头"),
    ("頸", "颈"),
]

_BODY_PART_MAP = {
    "脚": ["脚", "脚踝", "脚腕", "脚背", "脚趾", "足", "右脚", "左脚"],
    "腿": ["腿", "小腿", "大腿", "膝盖", "膝", "右腿", "左腿"],
    "手": ["手", "手腕", "手指", "手背", "掌", "右手", "左手"],
    "胳膊": ["胳膊", "手臂", "臂", "前臂", "上臂"],
    "头": ["头", "脑袋", "额头", "后脑", "后脑勺", "头皮"],
    "颈部": ["脖子", "颈部", "颈", "喉咙"],
    "胸口": ["胸", "胸口", "心口"],
    "腹部": ["肚子", "腹部", "胃", "肚脐"],
    "背部": ["背", "背部", "后背", "腰", "腰部"],
}


def _to_simplified_light(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    for k, v in _TC_SC_MAP:
        t = t.replace(k, v)
    return t


def infer_slot_from_text(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None

    if _LOCATION_PAT.search(t):
        return "location"

    # yes/no 触发：含“有没有/是否/能不能” 或者以“吗？”结尾
    if _YESNO_PAT.search(t) or t.endswith(("吗？", "吗?")):
        return "yesno"

    # 对一些典型 yes/no 问句：以问号结尾也视为 yesno
    if t.endswith(("？", "?")):
        return "yesno"

    return None


def parse_location(user_text: str) -> str | None:
    t = _to_simplified_light(user_text)
    t = (t or "").strip()
    if not t:
        return None
    for canon, variants in _BODY_PART_MAP.items():
        for v in variants:
            if v and v in t:
                return canon
    return None


def parse_yesno(user_text: str) -> bool | None:
    """
    支持语义 yes/no：
    True: 是/有/可以/行/好/变少了/少了/好点了/缓解/停了/止住了
    False: 没有/没/不/不行/还是/还在/没变/更多/变多/止不住
    """
    t = _to_simplified_light(user_text)
    t = (t or "").strip()
    if not t:
        return None

    # 强否定优先
    neg_phrases = [
        "没有",
        "没",
        "不行",
        "不能",
        "不会",
        "不可以",
        "还是",
        "还在",
        "没变",
        "没有变",
        "没变少",
        "更多",
        "变多",
        "越来越多",
        "止不住",
        "还在流血",
        "继续流血",
        "还是头晕",
        "还是很晕",
        "还是疼",
        "还是很疼",
        "还是喘",
        "还在晃",
    ]
    for x in neg_phrases:
        if x and x in t:
            return False

    pos_phrases = [
        "有",
        "是",
        "可以",
        "行",
        "好的",
        "变少",
        "少了",
        "减少",
        "好点",
        "缓解",
        "轻了",
        "少了点",
        "有一点",
        "有点好转",
        "停了",
        "止住",
        "止住了",
        "不怎么了",
        "好多了",
    ]
    for x in pos_phrases:
        if x and x in t:
            return True

    # 超短口语
    yes = {
        "可",
        "可以",
        "行",
        "好",
        "好的",
        "有的",
        "嗯",
        "对",
        "是",
        "能",
        "会",
        "行的",
        "有",
    }
    no = {"不", "无"}
    if t in yes:
        return True
    if t in no:
        return False

    return None
