"""Pruebas para las mejoras v0.8: eventos estructurados, alertas por voz,
manejo del caso hasta su cierre (favorable, adverso o incompleto)."""
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
import urllib.request

from app import Handler, EVENTS, evaluate_case, start_session, apply_action, build_debrief

ROOT = Path(__file__).resolve().parents[1]


def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def request_json(url, method="GET", payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, method=method, data=data, headers=headers), timeout=3) as r:
        return json.loads(r.read().decode())


def test_events_are_structured_with_title_and_type():
    assert len(EVENTS) >= 5
    titles = {e["title"] for e in EVENTS}
    assert "Aviso de enfermería" in titles
    assert "Resultados disponibles" in titles
    assert "Evento clínico" in titles
    texts = {e["text"] for e in EVENTS}
    assert "La paciente está más fría y responde más lentamente." in texts
    assert "Se liberan nuevos datos de laboratorio." in texts
    for e in EVENTS:
        assert {"at", "type", "title", "text", "voice_source"} <= set(e.keys())


def test_evaluate_case_stable_and_source_controlled_is_ready_for_closure():
    state = start_session()
    state["physiology"]["map"] = 70
    state["physiology"]["lactate"] = 2.0
    state["cultures_done"] = True
    state["antibiotic_given"] = True
    state["source_control_done"] = True
    status, message = evaluate_case(state)
    assert status == "listo_para_cierre"
    assert message


def test_evaluate_case_stable_without_full_bundle_is_not_ready_for_closure():
    """La PAM y el lactato en meta NO bastan: si falta un paso real del bundle
    (cultivos, antibiótico o control del foco) el caso no puede cerrarse como
    favorable — así se evita que 'apretar cualquier botón' cierre el caso."""
    state = start_session()
    state["physiology"]["map"] = 70
    state["physiology"]["lactate"] = 2.0
    state["source_control_done"] = True
    # cultures_done y antibiotic_given quedan en False (valor por defecto)
    status, message = evaluate_case(state)
    assert status != "listo_para_cierre"


def test_evaluate_case_prolonged_instability_requires_escalation():
    state = start_session()
    state["physiology"]["map"] = 50
    state["elapsed_seconds"] = 500
    status, message = evaluate_case(state)
    assert status == "escalamiento_requerido"
    assert "escalar" in message.lower()


def test_evaluate_case_default_in_progress():
    state = start_session()
    status, message = evaluate_case(state)
    assert status == "en_curso"
    assert message == ""


def test_apply_action_emits_closure_alert_once():
    state = start_session()
    state["physiology"]["map"] = 66
    state["physiology"]["lactate"] = 2.0
    state["iv_access"] = True
    state["cultures_done"] = True
    state["antibiotic_given"] = True
    r = apply_action(state, "source_control", 5)
    assert any(a["type"] == "closure" for a in r["alerts"])
    assert state["case_status"] == "listo_para_cierre"
    # Una segunda acción sin cambio de estado no debe repetir la alerta de cierre.
    r2 = apply_action(state, "reassess", 5)
    assert not any(a["type"] == "closure" for a in r2["alerts"])


def test_build_debrief_reports_outcome_and_narrative():
    state = start_session()
    state["physiology"]["map"] = 70
    state["physiology"]["lactate"] = 2.0
    state["cultures_done"] = True
    state["antibiotic_given"] = True
    state["source_control_done"] = True
    debrief = build_debrief(state)
    assert debrief["outcome"] == "Favorable"
    assert debrief["case_status"] == "listo_para_cierre"
    assert debrief["closure_narrative"]


def test_build_debrief_incomplete_lists_missing_bundle_steps():
    state = start_session()
    state["physiology"]["map"] = 70
    state["physiology"]["lactate"] = 2.0
    # No se completan cultivos, antibiótico ni control del foco.
    debrief = build_debrief(state)
    assert debrief["outcome"] == "Incompleto"
    assert "hemocultivos" in debrief["closure_narrative"]


def test_build_debrief_adverse_outcome():
    state = start_session()
    state["physiology"]["map"] = 45
    state["elapsed_seconds"] = 500
    debrief = build_debrief(state)
    assert debrief["outcome"] == "Adverso"


def test_api_event_endpoint_returns_title_and_voice_source():
    server, _ = run_server()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        session = request_json(base + "/api/session/start", "POST", {})
        sid = session["session_id"]
        result = request_json(base + "/api/session/event", "POST", {"session_id": sid, "event": 90})
        assert result["title"] == "Aviso de enfermería"
        assert result["voice_source"] == "Enfermería"
        assert "más fría" in result["text"]
    finally:
        server.shutdown()
        server.server_close()


def test_api_action_response_includes_case_status():
    server, _ = run_server()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        session = request_json(base + "/api/session/start", "POST", {})
        sid = session["session_id"]
        result = request_json(base + "/api/session/action", "POST", {
            "session_id": sid, "action_id": "vitals", "elapsed_seconds": 3
        })
        assert "case_status" in result["result"]
    finally:
        server.shutdown()
        server.server_close()


def test_frontend_uses_structured_events_and_case_status():
    js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "event_schedule" in js
    assert "updateCaseStatus" in js
    assert "case_status" in js
    assert "alert" in js

    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "caseStatusTag" in html
