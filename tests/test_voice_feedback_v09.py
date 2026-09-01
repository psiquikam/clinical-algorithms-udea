"""Pruebas para las mejoras v0.9: la voz toma protagonismo (múltiples fuentes,
línea propia de la paciente), retroalimentación de ritmo y racha, y nuevos
cambios de estado (nivel de conciencia) además del cierre del caso."""
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
import urllib.request

from app import (
    Handler, EVENTS, EVENTS_BY_TIME, consciousness_level, speed_tag,
    start_session, apply_action,
)

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


def test_events_expanded_with_variety_of_voices():
    assert len(EVENTS) >= 8
    sources = {e["voice_source"] for e in EVENTS}
    assert {"Enfermería", "Laboratorio", "Equipo", "Monitor"} <= sources
    # El evento de dolor abdominal incluye una línea propia de la paciente.
    pain_event = EVENTS_BY_TIME[150]
    assert "patient_voice" in pain_event
    assert "duele" in pain_event["patient_voice"].lower()


def test_consciousness_level_thresholds():
    assert consciousness_level(70) == "Alerta y orientada"
    assert consciousness_level(60) == "Responde a la voz"
    assert consciousness_level(48) == "Responde solo al dolor"
    assert consciousness_level(30) == "No responde"


def test_speed_tag_thresholds():
    assert speed_tag(5) == "Respuesta rápida"
    assert speed_tag(20) == "Respuesta oportuna"
    assert speed_tag(45) == "Respuesta tardía"


def test_apply_action_includes_speed_feedback():
    state = start_session()
    r = apply_action(state, "vitals", 4)
    assert "Respuesta rápida" in r["feedback"]


def test_apply_action_emits_consciousness_alert_on_change():
    state = start_session()
    state["physiology"]["map"] = 66  # por encima del umbral inicial "Responde a la voz"
    r = apply_action(state, "vitals", 3)
    assert any(a["type"] == "consciousness" for a in r["alerts"])
    assert r["consciousness"] == "Alerta y orientada"


def test_apply_action_emits_encouragement_after_three_good_actions():
    state = start_session()
    alerts_seen = []
    for action in ["vitals", "assess_perfusion", "reassess"]:
        r = apply_action(state, action, 3)
        alerts_seen.extend(r["alerts"])
    assert any(a["type"] == "encouragement" for a in alerts_seen)


def test_api_event_endpoint_returns_patient_voice_when_present():
    server, _ = run_server()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        session = request_json(base + "/api/session/start", "POST", {})
        sid = session["session_id"]
        result = request_json(base + "/api/session/event", "POST", {"session_id": sid, "event": 150})
        assert result["patient_voice"]
        assert "duele" in result["patient_voice"].lower()
    finally:
        server.shutdown()
        server.server_close()


def test_api_action_response_includes_alerts_list_and_consciousness():
    server, _ = run_server()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        session = request_json(base + "/api/session/start", "POST", {})
        sid = session["session_id"]
        result = request_json(base + "/api/session/action", "POST", {
            "session_id": sid, "action_id": "vitals", "elapsed_seconds": 3
        })
        assert "alerts" in result["result"]
        assert isinstance(result["result"]["alerts"], list)
        assert "consciousness" in result["result"]
    finally:
        server.shutdown()
        server.server_close()


def test_frontend_gives_voice_protagonism():
    js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "voiceQueue" in js
    assert "voiceProfile" in js
    assert "patient_voice" in js
    assert "alerts" in js

    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "voiceLog" in html
