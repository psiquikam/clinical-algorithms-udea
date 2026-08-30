import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from app import Handler, NODES


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


def test_scenario_contains_branching_nodes():
    assert len(NODES) == 7
    assert NODES["recognition"]["next"] == "cultures"
    assert NODES["source_control"]["next"] is None


def test_api_session_and_correct_decision_branch():
    server, _ = run_server()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        scenario = request_json(base + "/api/scenario/septic-shock")
        assert scenario["start_node"] == "recognition"
        session = request_json(base + "/api/session/start", "POST", {})
        sid = session["session_id"]
        result = request_json(base + "/api/session/decision", "POST", {
            "session_id": sid, "node_id": "recognition",
            "choice": NODES["recognition"]["expected"], "elapsed_seconds": 3
        })
        assert result["result"]["correct"] is True
        assert result["result"]["next_node"] == "cultures"
        assert len(result["state"]["decisions"]) == 1
    finally:
        server.shutdown()
        server.server_close()


def test_wrong_decision_changes_simulated_physiology():
    server, _ = run_server()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        session = request_json(base + "/api/session/start", "POST", {})
        sid = session["session_id"]
        before = session["state"]["physiology"]
        wrong = next(x for x in NODES["recognition"]["options"] if x != NODES["recognition"]["expected"])
        result = request_json(base + "/api/session/decision", "POST", {
            "session_id": sid, "node_id": "recognition", "choice": wrong, "elapsed_seconds": 5
        })
        assert result["result"]["correct"] is False
        assert result["state"]["physiology"]["pam"] < before["pam"]
        assert result["state"]["physiology"]["lactato"] > before["lactato"]
        assert result["state"]["delay_minutes"] == 5
    finally:
        server.shutdown()
        server.server_close()
