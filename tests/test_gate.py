from patterns.rolling_risk_gate import AMBER, GREEN, RED, make_gate


def ans(pay=0.0, imp=0.0, sec=0.1, pressure=0.0, conf=0.8):
    """Fake Decider answers. pay = probability of a dangerous payment choice, imp = probability of any identity."""
    return {
        "payment_ask": {"probabilities": {"none": 1 - pay, "gift_cards_crypto_or_wire": pay}, "confidence": conf},
        "impersonation": {"probabilities": {"none": 1 - imp, "relative_in_trouble": imp}, "confidence": conf},
        "secrecy": {"noul": sec},
        "pressure": {"score": pressure, "confidence": conf},
    }


CALM = ans()


def test_calm_call_stays_green():
    g = make_gate()
    for _ in range(20):
        assert g.update(CALM).state == GREEN


def test_one_weak_sentence_stays_green():
    g = make_gate()
    s = g.update(ans(pay=0.25, conf=0.3))
    assert s.state == GREEN


def test_one_strong_signal_is_amber_not_red():
    g = make_gate()
    s = g.update(ans(pay=0.95))
    assert s.state == AMBER and s.active == ["payment_ask"]


def test_two_independent_signals_go_red():
    g = make_gate()
    g.update(ans(sec=0.95))
    s = g.update(ans(pay=0.95))
    assert s.state == RED and s.changed and s.red_at_step == 2


def test_two_signals_in_the_same_group_do_not_go_red():
    g = make_gate()
    g.update(ans(sec=0.95))
    s = g.update(ans(sec=0.95, pressure=1.0))  # secrecy and pressure are both "manipulation"
    assert s.state == AMBER


def test_signal_fades_so_far_apart_signals_do_not_add_up():
    g = make_gate()
    g.update(ans(sec=0.95))
    for _ in range(25):
        g.update(CALM)
    assert g.update(ans(pay=0.95)).state == AMBER


def test_red_is_latched_until_a_human_clears_it():
    g = make_gate()
    g.update(ans(sec=0.95)); g.update(ans(pay=0.95))
    for _ in range(40):
        assert g.update(CALM).state == RED
    g.clear()
    assert g.state == GREEN and g.snapshot().risk == 0.0
    assert g.update(CALM).state == GREEN


def test_amber_returns_to_green_when_calm():
    g = make_gate()
    assert g.update(ans(pay=0.95)).state == AMBER
    states = [g.update(CALM).state for _ in range(30)]
    assert states[-1] == GREEN
