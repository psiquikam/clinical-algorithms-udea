"""Pruebas para las mejoras v0.10: la simulación deja de aceptar cualquier
acción como acertada. Ahora existen dependencias clínicas reales entre
acciones (acceso IV, hemocultivos antes de antibiótico, cristaloides antes
de vasopresores salvo hipotensión crítica, control del foco solo tras
completar el reconocimiento, rendimientos decrecientes y sobrecarga de
volumen)."""
from app import start_session, apply_action, evaluate_case


def test_antibiotic_without_iv_is_blocked():
    state = start_session()
    r = apply_action(state, "antibiotic", 5)
    assert r["good"] is False
    assert state["antibiotic_given"] is False
    assert "acceso" in r["feedback"].lower() or "iv" in r["feedback"].lower()


def test_antibiotic_without_cultures_is_a_deviation():
    state = start_session()
    apply_action(state, "iv", 3)
    r = apply_action(state, "antibiotic", 5)
    assert r["good"] is False
    assert state["antibiotic_given"] is True  # sí se administra, pero mal secuenciado
    assert r["deviation"] is not None
    assert "hemocultivo" in r["deviation"].lower()


def test_antibiotic_after_cultures_and_iv_is_correct():
    state = start_session()
    apply_action(state, "iv", 3)
    apply_action(state, "request_cultures", 3)
    r = apply_action(state, "antibiotic", 5)
    assert r["good"] is True
    assert r["score"] > 0
    assert r["deviation"] is None


def test_vasopressor_without_any_fluids_is_premature():
    state = start_session()
    apply_action(state, "iv", 3)
    map_before = state["physiology"]["map"]
    r = apply_action(state, "vasopressor", 5)
    assert r["good"] is False
    assert r["score"] < 0  # nunca 0: una acción prematura se penaliza, no queda neutra
    # Sin beneficio hemodinámico propio de la vasopresina: la PAM no puede
    # subir por esta acción (la ligera deriva pasiva del reloj crítico solo
    # puede bajarla un poco en estos 5s, nunca subirla).
    assert state["physiology"]["map"] <= map_before
    assert state["vasopressor_started"] is True  # se inicia, pero mal indicado
    assert r["deviation"] is not None


def test_vasopressor_after_fluid_bolus_is_appropriate():
    state = start_session()
    apply_action(state, "iv", 3)
    apply_action(state, "fluids", 3)
    r = apply_action(state, "vasopressor", 5)
    assert r["good"] is True
    assert r["score"] > 0


def test_vasopressor_allowed_without_fluids_if_critically_hypotensive():
    state = start_session()
    apply_action(state, "iv", 3)
    state["physiology"]["map"] = 42  # hipotensión crítica
    r = apply_action(state, "vasopressor", 5)
    assert r["good"] is True


def test_fluids_without_iv_is_blocked_and_not_counted():
    state = start_session()
    r = apply_action(state, "fluids", 3)
    assert r["good"] is False
    assert state["fluids_count"] == 0


def test_excess_fluids_after_target_and_stable_map_is_flagged():
    state = start_session()
    apply_action(state, "iv", 3)
    state["physiology"]["map"] = 70  # ya en meta
    state["fluids_count"] = 5  # ≈2500 mL / 70kg ≈ 35 mL/kg, ya por encima de la meta
    r = apply_action(state, "fluids", 3)
    assert r["good"] is False
    assert "sobrecarga" in (r["deviation"] or "").lower()


def test_source_control_requires_iv_first_even_before_cultures_or_antibiotic():
    """Reproduce exactamente el reporte del usuario: intentar el control del
    foco como primera acción, sin acceso IV, debe quedar bloqueado de forma
    directa (no solo transitiva) y nunca marcar el paso como completado."""
    state = start_session()
    r = apply_action(state, "source_control", 5)
    assert r["good"] is False
    assert r["score"] < 0
    assert state["source_control_done"] is False
    assert state["iv_access"] is False
    assert "IV" in r["feedback"] or "vascular" in r["feedback"].lower()


def test_source_control_requires_cultures_and_antibiotic_first():
    state = start_session()
    apply_action(state, "iv", 3)
    r = apply_action(state, "source_control", 5)
    assert r["good"] is False
    assert state["source_control_done"] is False
    assert r["deviation"] is not None


def test_source_control_after_bundle_steps_succeeds():
    state = start_session()
    apply_action(state, "iv", 3)
    apply_action(state, "request_cultures", 3)
    apply_action(state, "antibiotic", 3)
    r = apply_action(state, "source_control", 5)
    assert r["good"] is True
    assert state["source_control_done"] is True


def test_repeating_vitals_gives_no_extra_score():
    state = start_session()
    r1 = apply_action(state, "vitals", 3)
    r2 = apply_action(state, "vitals", 3)
    assert r1["score"] > 0
    assert r2["score"] == 0


def test_reassess_spam_within_short_interval_scores_zero():
    state = start_session()
    r1 = apply_action(state, "reassess", 3)
    r2 = apply_action(state, "reassess", 3)  # segundos después, sin datos nuevos
    assert r1["score"] > 0
    assert r2["score"] == 0


def test_unrealistic_button_mashing_does_not_close_the_case():
    """Simula a alguien apretando botones al azar sin seguir el bundle: el
    caso no debe quedar 'listo para cierre' solo por buena fisiología."""
    state = start_session()
    for _ in range(3):
        apply_action(state, "vasopressor", 2)  # sin IV, sin fluidos: siempre mal indicado
        apply_action(state, "source_control", 2)  # sin cultivos/antibiótico: bloqueado
        apply_action(state, "vitals", 2)
    status, _ = evaluate_case(state)
    assert status != "listo_para_cierre"
    assert state["source_control_done"] is False


def test_coach_message_prompts_iv_access_when_nothing_done_yet():
    from app import generate_coach_message
    state = start_session()
    state["elapsed_seconds"] = 30  # supera el cooldown inicial
    msg = generate_coach_message(state)
    assert msg is not None
    assert "vascular" in msg["text"].lower() or "iv" in msg["text"].lower()


def test_coach_message_respects_cooldown():
    from app import generate_coach_message
    state = start_session()
    state["elapsed_seconds"] = 30
    first = generate_coach_message(state)
    assert first is not None
    second = generate_coach_message(state)  # sin avanzar el tiempo
    assert second is None


def test_coach_message_is_encouraging_once_bundle_progresses():
    from app import generate_coach_message
    state = start_session()
    apply_action(state, "iv", 3)
    apply_action(state, "request_cultures", 3)
    apply_action(state, "antibiotic", 3)
    apply_action(state, "source_control", 3)
    state["physiology"]["map"] = 70
    state["elapsed_seconds"] += 30
    msg = generate_coach_message(state)
    assert msg is not None
    assert "buen manejo" in msg["text"].lower() or "estabilizan" in msg["text"].lower()
