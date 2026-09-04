"""Pruebas para el desenlace real (v0.11): la simulación ahora puede
progresar a un paro cardiorrespiratorio genuino si la inestabilidad crítica
se sostiene, y puede resolverse con RCP + adrenalina (retorno de
circulación espontánea) o terminar en un desenlace adverso si no se
rescata a tiempo."""
from app import (
    start_session, apply_action, evaluate_case, build_debrief,
    advance_critical_clock, trigger_arrest, achieve_rosc, check_arrest_outcome,
    ARREST_TRIGGER_SECONDS, ARREST_SURVIVABLE_SECONDS, CRITICAL_MAP,
)


def test_sustained_critical_hypotension_triggers_arrest():
    state = start_session()
    state["physiology"]["map"] = 30  # por debajo de CRITICAL_MAP
    alerts = []
    # Avanza el reloj crítico manualmente en bloques hasta disparar el paro.
    for _ in range(12):
        alerts += advance_critical_clock(state, 10)
        if state["arrest"]:
            break
    assert state["arrest"] is True
    assert state["physiology"]["map"] == 0
    assert state["physiology"]["fc"] == 0
    assert any(a["type"] == "arrest" for a in alerts)
    assert any("no responde" in a["text"].lower() for a in alerts)


def test_brief_hypotension_recovering_does_not_trigger_arrest():
    """Si la PAM se recupera antes del umbral, el reloj crítico retrocede
    (no sigue acumulando) y el paro no debe dispararse."""
    state = start_session()
    state["physiology"]["map"] = 30
    advance_critical_clock(state, ARREST_TRIGGER_SECONDS - 20)
    assert state["arrest"] is False
    peak = state["critical_seconds"]
    state["physiology"]["map"] = 70  # se recupera
    advance_critical_clock(state, 10)
    assert state["arrest"] is False
    assert state["critical_seconds"] < peak  # el reloj retrocede en vez de seguir subiendo


def test_other_actions_are_ineffective_during_arrest():
    state = start_session()
    trigger_arrest(state)
    r = apply_action(state, "fluids", 5)
    assert r["good"] is False
    assert state["fluids_count"] == 0
    assert "paro" in r["feedback"].lower()


def test_cpr_without_arrest_is_rejected():
    state = start_session()
    r = apply_action(state, "cpr", 3)
    assert r["good"] is False
    assert state["cpr_active"] is False


def test_epinephrine_requires_cpr_first():
    state = start_session()
    trigger_arrest(state)
    r = apply_action(state, "epinephrine", 3)
    assert r["good"] is False
    assert state["epinephrine_count"] == 0


def test_cpr_then_two_epinephrine_doses_achieve_rosc():
    state = start_session()
    trigger_arrest(state)
    apply_action(state, "cpr", 3)
    r1 = apply_action(state, "epinephrine", 3)
    assert state["rosc"] is False
    r2 = apply_action(state, "epinephrine", 3)
    assert r2["rosc"] is True
    assert state["arrest"] is False
    assert state["physiology"]["map"] > 0
    assert state["physiology"]["fc"] > 0
    assert any(a["type"] == "rosc" for a in r2["alerts"])


def test_sustained_arrest_without_rescue_locks_adverse_outcome():
    state = start_session()
    trigger_arrest(state)
    state["elapsed_seconds"] = 10
    alerts = check_arrest_outcome(state)
    assert alerts == []  # todavía dentro de la ventana
    state["elapsed_seconds"] = 10 + ARREST_SURVIVABLE_SECONDS + 1
    alerts = check_arrest_outcome(state)
    assert state["outcome_locked"] == "paro_sin_rce"
    assert state["completed"] is True
    assert any(a["type"] == "case_end" for a in alerts)
    status, _ = evaluate_case(state)
    assert status == "desenlace_adverso"


def test_debrief_reports_arrest_and_rosc():
    state = start_session()
    trigger_arrest(state)
    apply_action(state, "cpr", 3)
    apply_action(state, "epinephrine", 3)
    apply_action(state, "epinephrine", 3)
    debrief = build_debrief(state)
    assert debrief["arrest_occurred"] is True
    assert debrief["rosc_achieved"] is True
    assert debrief["epinephrine_doses"] == 2


def test_debrief_reports_adverse_outcome_without_rosc():
    state = start_session()
    trigger_arrest(state)
    state["elapsed_seconds"] = ARREST_SURVIVABLE_SECONDS + 5
    check_arrest_outcome(state)
    debrief = build_debrief(state)
    assert debrief["outcome"] == "Adverso"
    assert debrief["case_status"] == "desenlace_adverso"
    assert "retorno de circulación" in debrief["closure_narrative"].lower()


def test_true_neglect_via_public_api_reaches_arrest():
    """Reproduce exactamente cómo lo viviría un usuario real: nunca se toca
    el estado interno directamente, solo se deja pasar el tiempo (como haría
    el sondeo periódico del coach) sin ninguna intervención útil. Antes de
    esta corrección, un piso artificial de PAM=44 impedía llegar al umbral
    crítico de 40 y el paro era, en la práctica, inalcanzable por abandono."""
    state = start_session()  # PAM inicial 56 (inestable, pero no crítica)
    assert state["physiology"]["map"] == 56
    reached_arrest = False
    for _ in range(40):
        # 'vitals' es una acción neutra (mirar el monitor), no terapéutica.
        r = apply_action(state, "vitals", 10)
        if r["arrest"]:
            reached_arrest = True
            break
    assert reached_arrest, "El abandono prolongado debe poder llevar al paro por sí solo"
    assert state["physiology"]["map"] == 0
    assert state["physiology"]["fc"] == 0
