"""Servidor web local para el simulador de decisiones clínicas v0.3.

Sin dependencias web externas: sirve HTML/CSS/JS y expone escenarios y
sesiones educativas. El motor clínico existente se reutiliza como referencia
para el caso base; la simulación ramificada es una capa pedagógica separada.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import json
import mimetypes
import sys
import uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from main import crear_paciente_sepsis  # noqa: E402
from algorithms.septic_shock import AlgoritmoChoqueSeptico  # noqa: E402

SESSIONS = {}

NODES = {
    "recognition": {
        "title": "Reconocimiento inicial",
        "prompt": "¿Cuál es la primera acción que debes priorizar en este escenario?",
        "expected": "Medir lactato sérico",
        "options": [
            "Medir lactato sérico",
            "Obtener hemocultivos antes de antibióticos",
            "Administrar antibióticos de amplio espectro IV",
            "Iniciar resucitación con cristaloides",
            "Reevaluar y escalar según respuesta",
        ],
        "next": "cultures",
        "feedback": "El prototipo sitúa la medición de lactato como primera acción del bundle inicial.",
    },
    "cultures": {
        "title": "Microbiología antes del antibiótico",
        "prompt": "El lactato ya fue medido. ¿Qué acción sigue en la secuencia educativa?",
        "expected": "Obtener hemocultivos antes de antibióticos",
        "options": [
            "Obtener hemocultivos antes de antibióticos",
            "Administrar antibióticos de amplio espectro IV",
            "Repetir el lactato inmediatamente",
            "Iniciar vasopresor antes de tomar cultivos",
        ],
        "next": "antibiotics",
        "feedback": "La secuencia del prototipo coloca los hemocultivos antes de la administración antibiótica.",
    },
    "antibiotics": {
        "title": "Tratamiento antimicrobiano",
        "prompt": "Con las muestras obtenidas, ¿qué intervención corresponde ahora?",
        "expected": "Administrar antibióticos de amplio espectro IV",
        "options": [
            "Administrar antibióticos de amplio espectro IV",
            "Esperar el resultado de los cultivos",
            "Suspender toda intervención hasta repetir el SOFA",
            "Pasar directamente a vía aérea quirúrgica",
        ],
        "next": "fluids",
        "feedback": "El escenario enseña la administración temprana de antibióticos empíricos según el foco.",
    },
    "fluids": {
        "title": "Reanimación inicial",
        "prompt": "Persiste la hipotensión. ¿Qué haces en el siguiente nodo?",
        "expected": "Iniciar resucitación con cristaloides",
        "options": [
            "Iniciar resucitación con cristaloides",
            "No administrar volumen y esperar",
            "Administrar solo diurético",
            "Finalizar la simulación",
        ],
        "next": "reassessment",
        "feedback": "El caso base del prototipo propone 30 mL/kg de cristaloides como parte de su secuencia educativa.",
    },
    "reassessment": {
        "title": "Reevaluación dinámica",
        "prompt": "Tras la reanimación inicial, ¿qué decisión corresponde?",
        "expected": "Reevaluar y escalar según respuesta",
        "options": [
            "Reevaluar y escalar según respuesta",
            "Continuar bolos indefinidamente sin reevaluación",
            "Suspender monitorización",
            "Dar de alta al paciente",
        ],
        "next": "vasopressor",
        "feedback": "La simulación ahora cambia el estado fisiológico y obliga a decidir según la respuesta.",
    },
    "vasopressor": {
        "title": "Hipotensión persistente",
        "prompt": "La PAM sigue por debajo del objetivo. ¿Qué intervención escalas?",
        "expected": "Iniciar norepinefrina",
        "options": [
            "Iniciar norepinefrina",
            "Iniciar vasopresina como primera línea",
            "Administrar epinefrina como primera opción",
            "No hacer nada y esperar",
        ],
        "next": "source_control",
        "feedback": "El algoritmo suministrado define la norepinefrina como vasopresor de primera línea.",
    },
    "source_control": {
        "title": "Control del foco",
        "prompt": "La hemodinamia está siendo sostenida. ¿Qué acción completa el escenario?",
        "expected": "Controlar el foco infeccioso",
        "options": [
            "Controlar el foco infeccioso",
            "Esperar a que el lactato normalice antes de buscar el foco",
            "Suspender antimicrobianos",
            "Cerrar la simulación sin reevaluar",
        ],
        "next": None,
        "feedback": "El caso base incluye control del foco como componente esencial de la respuesta al choque séptico.",
    },
}


def scenario_data():
    patient = crear_paciente_sepsis()
    result = AlgoritmoChoqueSeptico().ejecutar(patient)
    return {
        "patient": {
            "edad": patient.edad, "peso": patient.peso,
            "pa": f"{patient.signos_vitales.presion_arterial_sistolica}/{patient.signos_vitales.presion_arterial_diastolica}",
            "pam": patient.signos_vitales.presion_arterial_media,
            "fc": patient.signos_vitales.frecuencia_cardiaca,
            "fr": patient.signos_vitales.frecuencia_respiratoria,
            "spo2": patient.signos_vitales.saturacion_oxigeno,
            "temp": patient.signos_vitales.temperatura,
            "lactato": patient.laboratorio.lactato,
            "leucocitos": patient.laboratorio.leucocitos,
            "creatinina": patient.laboratorio.creatinina,
            "plaquetas": patient.laboratorio.plaquetas,
            "pafi": patient.laboratorio.pafi,
            "foco": patient.foco_infeccioso,
            "alergias": ", ".join(patient.alergias) or "Ninguna",
        },
        "phase": result.fase.value,
        "start_node": "recognition",
        "expected_first_action": NODES["recognition"]["expected"],
        "nodes": NODES,
        "clinical_basis": "Este escenario conserva las reglas del prototipo suministrado; la capa de simulación es educativa.",
    }


def apply_consequence(state, node_id, chosen, elapsed):
    correct = chosen == NODES[node_id]["expected"]
    state["elapsed_seconds"] += elapsed
    if not correct:
        state["score"] -= 1
        state["delay_minutes"] += 5
        state["physiology"]["pam"] = max(40, state["physiology"]["pam"] - 4)
        state["physiology"]["lactato"] = round(state["physiology"]["lactato"] + 0.4, 1)
        return {
            "correct": False,
            "consequence": "Retraso educativo simulado: el tiempo avanza, la PAM desciende y el lactato aumenta.",
            "next_node": node_id,
            "physiology": state["physiology"],
        }

    state["score"] += 2
    if node_id == "fluids":
        state["physiology"]["pam"] = 60
        state["physiology"]["lactato"] = round(state["physiology"]["lactato"] - 0.5, 1)
    elif node_id == "vasopressor":
        state["physiology"]["pam"] = 68
        state["physiology"]["lactato"] = round(state["physiology"]["lactato"] - 0.4, 1)
    elif node_id == "source_control":
        state["physiology"]["pam"] = 72
        state["physiology"]["lactato"] = round(max(1.5, state["physiology"]["lactato"] - 0.6), 1)
    next_node = NODES[node_id]["next"]
    return {
        "correct": True,
        "consequence": "La decisión fue aplicada en el escenario. El estado fisiológico simulado se actualiza.",
        "next_node": next_node,
        "physiology": state["physiology"],
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, content, content_type):
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/scenario/septic-shock":
            self._send(200, json.dumps(scenario_data(), ensure_ascii=False), "application/json; charset=utf-8")
            return
        if path == "/api/health":
            self._send(200, '{"status":"ok","version":"0.3"}', "application/json; charset=utf-8")
            return
        if path == "/" or path == "/index.html":
            self._send(200, (ROOT / "web" / "index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
            return
        relative = path.lstrip("/")
        target = (ROOT / "web" / relative).resolve()
        web_root = (ROOT / "web").resolve()
        if web_root not in target.parents:
            self._send(403, "Forbidden", "text/plain; charset=utf-8")
            return
        if target.is_file():
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if mime.startswith("text/") or mime in {"application/javascript", "application/json"}:
                mime += "; charset=utf-8"
            self._send(200, target.read_bytes(), mime)
            return
        self._send(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._json_body()
            if path == "/api/session/start":
                sid = str(uuid.uuid4())
                scenario = scenario_data()
                SESSIONS[sid] = {
                    "id": sid, "score": 0, "delay_minutes": 0, "elapsed_seconds": 0,
                    "node": scenario["start_node"],
                    "started_at": __import__("datetime").datetime.now().isoformat(),
                    "decisions": [],
                    "physiology": {"pam": scenario["patient"]["pam"], "lactato": scenario["patient"]["lactato"]},
                }
                self._send(200, json.dumps({"session_id": sid, "state": SESSIONS[sid]}, ensure_ascii=False), "application/json; charset=utf-8")
                return
            if path == "/api/session/decision":
                sid = body.get("session_id")
                state = SESSIONS.get(sid)
                if not state:
                    self._send(404, '{"error":"Sesión no encontrada"}', "application/json; charset=utf-8")
                    return
                node_id = body.get("node_id")
                chosen = body.get("choice", "")
                elapsed = float(body.get("elapsed_seconds", 0))
                result = apply_consequence(state, node_id, chosen, elapsed)
                state["decisions"].append({
                    "node": node_id, "choice": chosen, "expected": NODES[node_id]["expected"],
                    "correct": result["correct"], "elapsed_seconds": elapsed,
                    "consequence": result["consequence"],
                })
                state["node"] = result["next_node"]
                if state["node"] is None:
                    state["completed"] = True
                self._send(200, json.dumps({"result": result, "state": state}, ensure_ascii=False), "application/json; charset=utf-8")
                return
            self._send(404, '{"error":"Ruta no encontrada"}', "application/json; charset=utf-8")
        except Exception as exc:
            self._send(400, json.dumps({"error": str(exc)}, ensure_ascii=False), "application/json; charset=utf-8")

    def log_message(self, fmt, *args):
        print(fmt % args)


def main():
    host, port = "127.0.0.1", 8000
    server = ThreadingHTTPServer((host, port), Handler)
    print("\n🏥 Algoritmos Clínicos en Cuidado Crítico — Simulador v0.3")
    print(f"Abre en el navegador: http://{host}:{port}")
    print("Presiona Ctrl+C para detener el servidor.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
