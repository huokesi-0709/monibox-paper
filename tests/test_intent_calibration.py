from runtime.intent_extractor import IntentExtractor


def test_dev_calibration_terms_route_to_expected_intents():
    extractor = IntentExtractor()
    samples = {
        "手臂被划开了，血一直往外冒。": "severe_bleeding",
        "我只能小口呼吸，胸口压得厉害。": "respiratory_distress",
        "额头被重物压着，我拉不出来。": "trapped_or_crush",
        "我一边听到墙体又在响，一边手机快没电了，很害怕。": "collapse_aftershock",
        "我刚才短暂晕了一下，现在还很迷糊。": "head_or_consciousness",
        "我在冷风里等了很久，现在一直哆嗦。": "hypothermia",
        "我已经很久没喝水了，头有点晕。": "dehydration",
        "我摔倒后小腿肿起来了。": "pain_or_injury",
        "我一直发抖，脑子很乱。": "panic",
        "我怕手机关机，救援还没找到我。": "low_battery",
    }

    for text, expected in samples.items():
        assert extractor.extract(text).primary_intent == expected


def test_hypothetical_advice_does_not_trigger_crush_intent():
    ctx = IntentExtractor().extract("如果被压住了，我是不是应该硬拉出来？")

    assert ctx.primary_intent == "out_of_scope"
    assert ctx.matched_terms
    assert all(item.get("hypothetical") for item in ctx.matched_terms)
