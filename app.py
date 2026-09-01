"""Servidor local para el simulador clínico v0.9.

La capa de simulación es educativa y separada del motor clínico heredado.
No pretende modelar con fidelidad fisiológica un paciente real.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
import json, mimetypes, sys, uuid

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from main import crear_paciente_sepsis
from algorithms.septic_shock import AlgoritmoChoqueSeptico

SESSIONS = {}

SCENARIO = {
    "id": "septic-shock-room",
    "title": "Sala de reanimación — infección abdominal con hipoperfusión",
    "patient": None,
    "initial_physiology": {"fc":125,"bpSys":78,"bpDia":45,"spo2":88,"rr":28,"temp":39.2,"map":56,"lactate":4.8},
    "available_tests": {
        "lactate": {"label":"Lactato", "result":"4.8 mmol/L", "detail":"Marcador de hipoperfusión; interpretar junto al contexto y tendencia."},
        "cbc": {"label":"Hemograma", "result":"Leucocitos 18.500/µL · Plaquetas 85.000/µL", "detail":"Alteraciones compatibles con respuesta inflamatoria y disfunción orgánica en el caso simulado."},
        "gas": {"label":"Gasometría", "result":"PaFi 180", "detail":"Hipoxemia significativa en el caso simulado."},
        "renal": {"label":"Función renal", "result":"Creatinina 2.3 mg/dL", "detail":"Dato usado por el motor heredado de SOFA simplificado."},
        "cultures": {"label":"Hemocultivos", "result":"Muestras obtenidas; resultado diferido", "detail":"La simulación no resuelve microbiología en tiempo real."},
    },
}


# Compatibilidad con la API v0.3: conserva nodos y ruta de decisión heredados.
NODES = {
    "recognition": {"expected": "Medir lactato sérico", "options": ["Medir lactato sérico", "Obtener hemocultivos antes de antibióticos", "Administrar antibióticos de amplio espectro IV", "Iniciar resucitación con cristaloides", "Reevaluar y escalar según respuesta"], "next": "cultures"},
    "cultures": {"expected": "Obtener hemocultivos antes de antibióticos", "options": ["Obtener hemocultivos antes de antibióticos"], "next": "antibiotics"},
    "antibiotics": {"expected": "Administrar antibióticos de amplio espectro IV", "options": ["Administrar antibióticos de amplio espectro IV"], "next": "fluids"},
    "fluids": {"expected": "Iniciar resucitación con cristaloides", "options": ["Iniciar resucitación con cristaloides"], "next": "reassessment"},
    "reassessment": {"expected": "Reevaluar y escalar según respuesta", "options": ["Reevaluar y escalar según respuesta"], "next": "vasopressor"},
    "vasopressor": {"expected": "Iniciar norepinefrina", "options": ["Iniciar norepinefrina"], "next": "source_control"},
    "source_control": {"expected": "Controlar el foco infeccioso", "options": ["Controlar el foco infeccioso"], "next": None},
}

ACTIONS = {
    "observe": [
        ("assess_airway","Evaluar vía aérea","Observación dirigida"),
        ("assess_breathing","Evaluar respiración","Frecuencia, esfuerzo y oxigenación"),
        ("assess_perfusion","Evaluar perfusión","Estado mental, piel, pulsos y PAM"),
        ("vitals","Revisar signos vitales","Actualización del monitor"),
    ],
    "investigate": [
        ("request_lactate","Solicitar lactato","Obtienes un resultado de laboratorio"),
        ("request_cbc","Solicitar hemograma","Obtienes hemograma y plaquetas"),
        ("request_gas","Solicitar gasometría","Obtienes PaFi"),
        ("request_renal","Solicitar función renal","Obtienes creatinina"),
        ("request_cultures","Obtener hemocultivos","Tomas muestras antes del antibiótico cuando es factible"),
    ],
    "intervene": [
        ("oxygen","Administrar oxígeno","Soporte de oxigenación"),
        ("iv","Obtener acceso IV","Permite muestras y tratamiento"),
        ("antibiotic","Administrar antibiótico empírico","Tratamiento antimicrobiano temprano"),
        ("fluids","Iniciar cristaloides","Reanimación con reevaluación"),
        ("vasopressor","Iniciar norepinefrina","Escalamiento hemodinámico"),
        ("source_control","Activar control del foco","Buscar y tratar la fuente"),
    ],
    "reassess": [
        ("reassess","Reevaluar respuesta","Integra tendencia fisiológica y clínica"),
        ("recheck_lactate","Revisar tendencia de lactato","Comprueba respuesta metabólica"),
        ("recheck_map","Revisar PAM","Determina si persiste inestabilidad"),
    ],
}

# Cada evento tiene un tipo (nursing/labs/clinical/deterioration/monitor), un título
# visible y un texto. "voice_source" define quién "habla" el evento por síntesis de
# voz. "patient_voice", cuando existe, agrega una segunda línea hablada por la propia
# paciente inmediatamente después del anuncio del equipo — refuerza la inmersión sin
# convertir el evento en dos alertas separadas en el registro.
EVENTS = [
    {"at": 0, "type": "clinical", "title": "Evento clínico",
     "text": "La paciente está somnolienta, responde a la voz y tiene respiración rápida.",
     "voice_source": "Equipo"},
    {"at": 45, "type": "labs", "title": "Resultados disponibles",
     "text": "Se liberan nuevos datos de laboratorio.",
     "voice_source": "Laboratorio"},
    {"at": 90, "type": "nursing", "title": "Aviso de enfermería",
     "text": "La paciente está más fría y responde más lentamente.",
     "voice_source": "Enfermería"},
    {"at": 150, "type": "clinical", "title": "Evento clínico",
     "text": "Aparece dolor abdominal intenso. El foco infeccioso requiere evaluación y control.",
     "voice_source": "Equipo",
     "patient_voice": "Me duele mucho el abdomen... por favor, ayúdenme."},
    {"at": 210, "type": "nursing", "title": "Aviso de enfermería",
     "text": "El estado mental parece peor y la perfusión periférica está fría.",
     "voice_source": "Enfermería"},
    {"at": 270, "type": "monitor", "title": "Alarma del monitor",
     "text": "El monitor registra taquicardia sostenida; vigila el ritmo y la perfusión.",
     "voice_source": "Monitor"},
    {"at": 330, "type": "labs", "title": "Resultados disponibles",
     "text": "Llega un nuevo control de lactato desde el laboratorio.",
     "voice_source": "Laboratorio"},
    {"at": 390, "type": "nursing", "title": "Aviso de enfermería",
     "text": "La familia pregunta por el estado de la paciente; el equipo continúa concentrado en la reanimación.",
     "voice_source": "Enfermería"},
]
EVENTS_BY_TIME = {e["at"]: e for e in EVENTS}


ROOM_CONFIG = {
    "name": "Sala de Reanimación 1",
    "simulation_speed": 2,
    "equipment": ["Monitor multiparámetro", "Carro de paro", "Oxígeno", "Aspiración", "Bomba de infusión", "Acceso vascular"],
    "visual_note": "Escenografía 2D educativa; no representa una instalación clínica específica.",
}


def scenario_data():
    p = crear_paciente_sepsis()
    result = AlgoritmoChoqueSeptico().ejecutar(p)
    patient = {
        "edad": p.edad, "peso": p.peso,
        "pa": f"{p.signos_vitales.presion_arterial_sistolica}/{p.signos_vitales.presion_arterial_diastolica}",
        "pam": p.signos_vitales.presion_arterial_media,
        "fc": p.signos_vitales.frecuencia_cardiaca,
        "fr": p.signos_vitales.frecuencia_respiratoria,
        "spo2": p.signos_vitales.saturacion_oxigeno,
        "temp": p.signos_vitales.temperatura,
        "lactato": p.laboratorio.lactato,
        "leucocitos": p.laboratorio.leucocitos,
        "creatinina": p.laboratorio.creatinina,
        "plaquetas": p.laboratorio.plaquetas,
        "pafi": p.laboratorio.pafi,
        "foco": p.foco_infeccioso,
        "alergias": ", ".join(p.alergias) or "Ninguna",
    }
    SCENARIO["patient"] = patient
    return {
        "id": SCENARIO["id"], "title": SCENARIO["title"], "patient": patient,
        "initial_physiology": SCENARIO["initial_physiology"],
        "actions": ACTIONS, "available_tests": SCENARIO["available_tests"],
        "event_schedule": EVENTS,
        "phase": result.fase.value,
        "start_node": "recognition",
        "expected_first_action": NODES["recognition"]["expected"],
        "nodes": NODES,
        "clinical_basis": "La simulación conserva el motor clínico heredado; los cambios fisiológicos son pedagógicos y no predictivos.",
        "room": ROOM_CONFIG,
    }


def start_session():
    sid = str(uuid.uuid4())
    scenario_data()
    now = datetime.now().isoformat()
    SESSIONS[sid] = {
        "id": sid,
        "started_at": now,
        "score": 0,
        "delay_minutes": 0,
        "elapsed_seconds": 0,
        "decisions": [],
        "requested_information": [],
        "events_seen": [],
        "physiology": {**SCENARIO["initial_physiology"], "pam": SCENARIO["initial_physiology"]["map"], "lactato": SCENARIO["initial_physiology"]["lactate"]},
        "phase": "Establecimiento inicial",
        "completed": False,
        "case_status": "en_curso",
        "source_control_done": False,
        "consciousness": consciousness_level(SCENARIO["initial_physiology"]["map"]),
        "streak": 0,
    }
    return SESSIONS[sid]


def consciousness_level(map_value):
    """Nivel de conciencia simulado, derivado de la PAM en este motor educativo.
    No es un sustituto de una escala clínica real (p. ej. Glasgow)."""
    if map_value >= 65:
        return "Alerta y orientada"
    if map_value >= 55:
        return "Responde a la voz"
    if map_value >= 45:
        return "Responde solo al dolor"
    return "No responde"


def speed_tag(elapsed):
    if elapsed < 10:
        return "Respuesta rápida"
    if elapsed <= 30:
        return "Respuesta oportuna"
    return "Respuesta tardía"


def evaluate_case(state):
    """Determina si el caso simulado cumple criterios (educativos) de cierre
    o si, por el contrario, la inestabilidad exige escalamiento.

    Devuelve (status, mensaje) donde status es uno de:
      - "en_curso": el caso continúa sin un hito relevante.
      - "listo_para_cierre": parámetros estables y foco controlado.
      - "escalamiento_requerido": inestabilidad persistente y prolongada.
    """
    phys = state["physiology"]
    # 3.0 mmol/L es alcanzable con el piso fisiológico que produce la acción
    # "source_control" (2.8) en este motor educativo; sirve como umbral de
    # tendencia favorable sin exigir un valor inalcanzable dentro del juego.
    stable = phys.get("map", 0) >= 65 and phys.get("lactate", 99) <= 3.0
    source_controlled = state.get("source_control_done", False)
    prolonged_instability = phys.get("map", 999) < 55 and state["elapsed_seconds"] > 240
    if stable and source_controlled:
        return "listo_para_cierre", "Parámetros estables y foco controlado: el caso cumple criterios educativos para cierre."
    if prolonged_instability:
        return "escalamiento_requerido", "Persiste la inestabilidad y el equipo debe escalar."
    return "en_curso", ""


def apply_action(state, action_id, elapsed):
    elapsed = max(0, float(elapsed))
    state["elapsed_seconds"] += elapsed
    before = dict(state["physiology"])
    good = True
    score = 0
    feedback = ""
    observation = ""
    is_request = action_id.startswith("request_")

    if is_request:
        key = action_id.replace("request_", "")
        if key in SCENARIO["available_tests"]:
            info = SCENARIO["available_tests"][key]
            if key not in state["requested_information"]:
                state["requested_information"].append(key)
            state["score"] += 1
            score = 1
            feedback = f"Información obtenida: {info['result']}."
            observation = info["detail"]
        else:
            good = False
            feedback = "Solicitud no reconocida."

    elif action_id == "oxygen":
        state["physiology"]["spo2"] = min(97, state["physiology"]["spo2"] + 6); score=1
        feedback="La oxigenación mejora en la simulación."; observation="La SpO₂ asciende, pero la inestabilidad hemodinámica persiste."
    elif action_id == "iv":
        score=1; feedback="Acceso vascular conseguido."; observation="Ahora puedes obtener muestras y administrar tratamientos."
    elif action_id == "antibiotic":
        state["physiology"]["lactate"] = round(max(3.8, state["physiology"]["lactate"]-0.25),1); state["physiology"]["fc"] -= 4; score=2
        feedback="Tratamiento antimicrobiano administrado en la simulación."; observation="La respuesta es gradual; todavía requiere soporte y reevaluación."
    elif action_id == "fluids":
        state["physiology"]["map"] += 6; state["physiology"]["bpSys"] += 8; state["physiology"]["bpDia"] += 4; state["physiology"]["lactate"] = round(max(4.0, state["physiology"]["lactate"]-0.4),1); score=2
        feedback="La PAM mejora parcialmente con la intervención."; observation="La respuesta es incompleta: continúa la necesidad de reevaluación."
    elif action_id == "vasopressor":
        if state["physiology"]["map"] < 65:
            state["physiology"]["map"] += 12; state["physiology"]["bpSys"] += 12; state["physiology"]["bpDia"] += 5; score=3
            feedback="La PAM mejora con soporte vasoactivo."; observation="La perfusión mejora, pero el foco y la tendencia del lactato deben seguirse."
        else:
            score=1; feedback="Soporte vasoactivo aplicado con PAM ya mejorada."; observation="La simulación recomienda seguir reevaluando el estado global."
    elif action_id == "source_control":
        state["physiology"]["lactate"] = round(max(2.8, state["physiology"]["lactate"]-0.5),1); score=3
        state["source_control_done"] = True
        feedback="Se activa el control del foco."; observation="La trayectoria simulada mejora gradualmente si se mantiene la reanimación."
    elif action_id == "reassess":
        score=2; feedback="Reevaluación realizada."; observation="Compara PAM, SpO₂, estado mental y tendencia del lactato antes de la siguiente acción."
    elif action_id == "recheck_lactate":
        score=2; state["requested_information"].append("lactate_trend") if "lactate_trend" not in state["requested_information"] else None
        feedback=f"Lactato actual: {state['physiology']['lactate']:.1f} mmol/L."; observation="Una tendencia es más útil que un valor aislado para la discusión del caso."
    elif action_id == "recheck_map":
        score=2; feedback=f"PAM actual: {state['physiology']['map']} mmHg."; observation="Valora esta cifra junto con perfusión y respuesta global."
    elif action_id == "assess_airway":
        score=1; feedback="Vía aérea evaluada."; observation="La vía aérea está patente en este escenario, pero la paciente presenta alteración del estado mental."
    elif action_id == "assess_breathing":
        score=1; feedback="Respiración evaluada."; observation="Taquipnea e hipoxemia requieren soporte y reevaluación."
    elif action_id == "assess_perfusion":
        score=2; feedback="Perfusión evaluada."; observation="La hipotensión y la alteración del estado mental sugieren hipoperfusión."
    elif action_id == "vitals":
        score=1; feedback="Signos vitales actualizados."; observation="Observa la tendencia, no solo un valor puntual."
    else:
        good=False; score=-1; state["delay_minutes"] += 2; feedback="La acción no aporta a la prioridad actual."; observation="El tiempo continúa y debes reevaluar."

    state["score"] += score
    # Deterioro temporal educativo si se acumula retraso sin soporte hemodinámico.
    if elapsed >= 30 and action_id not in {"reassess","recheck_lactate","recheck_map","vasopressor"}:
        state["physiology"]["map"] = max(44, state["physiology"]["map"]-3)
        state["physiology"]["lactate"] = round(state["physiology"]["lactate"]+0.2,1)
        state["delay_minutes"] += 1
        observation += " El tiempo acumulado introduce un pequeño deterioro educativo simulado."
    if state["physiology"]["map"] >= 65:
        state["phase"] = "Respuesta hemodinámica parcial"
    else:
        state["phase"] = "Inestabilidad persistente"

    # Retroalimentación de ritmo: premia decisiones oportunas, señala demoras.
    tag = speed_tag(elapsed)
    feedback = f"{feedback} {tag}.".strip()

    alerts = []

    # Racha de decisiones productivas: refuerzo positivo cada 3 aciertos seguidos.
    if score > 0 and good:
        state["streak"] = state.get("streak", 0) + 1
    else:
        state["streak"] = 0
    if state["streak"] > 0 and state["streak"] % 3 == 0:
        alerts.append({"type": "encouragement", "title": "Buen manejo",
                        "text": "La secuencia de decisiones sigue el bundle recomendado.",
                        "voice_source": "Equipo"})

    # Cambio de estado de conciencia: se anuncia solo cuando cambia realmente.
    new_consciousness = consciousness_level(state["physiology"]["map"])
    if new_consciousness != state.get("consciousness"):
        state["consciousness"] = new_consciousness
        alerts.append({"type": "consciousness", "title": "Cambio de estado",
                        "text": f"El estado de conciencia cambia: {new_consciousness.lower()}.",
                        "voice_source": "Enfermería"})

    # Evalúa si el caso alcanza un hito de cierre o de escalamiento y, si el
    # estado cambia respecto al previo, produce una alerta puntual (evita
    # repetir la misma alerta en cada acción posterior).
    previous_status = state.get("case_status", "en_curso")
    new_status, status_message = evaluate_case(state)
    state["case_status"] = new_status
    if new_status != previous_status and new_status != "en_curso":
        if new_status == "escalamiento_requerido":
            alerts.append({"type": "deterioration", "title": "Deterioro", "text": status_message, "voice_source": "Enfermería"})
        elif new_status == "listo_para_cierre":
            alerts.append({"type": "closure", "title": "Cierre sugerido", "text": status_message, "voice_source": "Equipo"})

    return {
        "before": before, "after": state["physiology"], "good": good, "score": score,
        "feedback": feedback, "observation": observation, "alerts": alerts,
        "consciousness": state["consciousness"],
    }



def legacy_decision(state, node_id, chosen, elapsed):
    # Adaptador para la API v0.3: usa la expectativa heredada para validar la decisión.
    node = NODES[node_id]
    correct = chosen == node["expected"]
    state["elapsed_seconds"] += max(0,float(elapsed))
    state["physiology"]["pam"] = state["physiology"].get("pam", state["physiology"].get("map", 0))
    state["physiology"]["lactato"] = state["physiology"].get("lactato", state["physiology"].get("lactate", 0))
    if correct:
        state["score"] += 2
        if node_id == "fluids": state["physiology"]["map"] += 6; state["physiology"]["lactate"] = round(max(4.0,state["physiology"]["lactate"]-.5),1)
        elif node_id == "vasopressor": state["physiology"]["map"] = max(state["physiology"]["map"],68); state["physiology"]["lactate"] = round(max(3.5,state["physiology"]["lactate"]-.4),1)
        elif node_id == "source_control": state["physiology"]["map"] = max(state["physiology"]["map"],72); state["physiology"]["lactate"] = round(max(2.8,state["physiology"]["lactate"]-.5),1)
        state["physiology"]["pam"] = state["physiology"].get("map", state["physiology"]["pam"])
        state["physiology"]["lactato"] = state["physiology"].get("lactate", state["physiology"]["lactato"])
        return {"correct":True,"consequence":"La decisión coincide con la secuencia educativa heredada.","next_node":node["next"],"physiology":state["physiology"]}
    state["score"] -= 1; state["delay_minutes"] += 5; state["physiology"]["map"] = max(40,state["physiology"]["map"]-4); state["physiology"]["lactate"] = round(state["physiology"]["lactate"]+.4,1)
    state["physiology"]["pam"] = state["physiology"]["map"]
    state["physiology"]["lactato"] = state["physiology"]["lactate"]
    return {"correct":False,"consequence":"Retraso educativo simulado: disminuye la PAM y aumenta el lactato.","next_node":node_id,"physiology":state["physiology"]}

class Handler(BaseHTTPRequestHandler):
    def send_data(self, code, payload, content_type="application/json; charset=utf-8"):
        raw = payload.encode("utf-8") if isinstance(payload,str) else payload
        self.send_response(code); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def json_body(self):
        ln=int(self.headers.get("Content-Length","0")); return json.loads(self.rfile.read(ln) or b"{}")
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/scenario/septic-shock": self.send_data(200,json.dumps(scenario_data(),ensure_ascii=False)); return
        if path=="/api/health": self.send_data(200,json.dumps({"status":"ok","version":"0.9"})); return
        if path in {"/","/index.html"}: self.send_data(200,(ROOT/"web"/"index.html").read_text(encoding="utf-8"),"text/html; charset=utf-8"); return
        if path.startswith("/web/"): relative=path[5:]
        else: relative=path.lstrip("/")
        target = (ROOT / "web" / relative).resolve(); webroot=(ROOT/"web").resolve()
        if webroot != target.parent and webroot not in target.parents: self.send_data(403,"Forbidden","text/plain; charset=utf-8"); return
        if target.is_file():
            mime=mimetypes.guess_type(str(target))[0] or "application/octet-stream"; mime += "; charset=utf-8" if mime.startswith("text/") or mime=="application/javascript" else ""; self.send_data(200,target.read_bytes(),mime); return
        self.send_data(404,"Not found","text/plain; charset=utf-8")
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            body=self.json_body()
            if path=="/api/session/start":
                st=start_session(); self.send_data(200,json.dumps({"session_id":st["id"],"state":st},ensure_ascii=False)); return
            if path=="/api/session/decision":
                sid=body.get("session_id"); state=SESSIONS.get(sid)
                if not state: self.send_data(404,json.dumps({"error":"Sesión no encontrada"})); return
                node_id=body.get("node_id"); chosen=body.get("choice",""); elapsed=float(body.get("elapsed_seconds",0))
                res=legacy_decision(state,node_id,chosen,elapsed)
                state["decisions"].append({"node":node_id,"choice":chosen,"expected":NODES[node_id]["expected"],"correct":res["correct"],"elapsed_seconds":elapsed,"consequence":res["consequence"]})
                state["node"]=res["next_node"]
                if state["node"] is None: state["completed"]=True
                self.send_data(200,json.dumps({"result":res,"state":state},ensure_ascii=False)); return
            if path=="/api/session/action":
                sid=body.get("session_id"); state=SESSIONS.get(sid)
                if not state: self.send_data(404,json.dumps({"error":"Sesión no encontrada"})); return
                action_id=body.get("action_id",""); elapsed=float(body.get("elapsed_seconds",0))
                r=apply_action(state,action_id,elapsed)
                decision={"timestamp":datetime.now().isoformat(),"action_id":action_id,"elapsed_seconds":elapsed,"before":r["before"],"after":dict(r["after"]),"score":r["score"],"feedback":r["feedback"]}
                state["decisions"].append(decision)
                result={"good":r["good"],"feedback":r["feedback"],"observation":r["observation"],"physiology":r["after"],
                        "score_delta":r["score"],"case_status":state["case_status"],"consciousness":r["consciousness"],
                        "alerts":r["alerts"]}
                self.send_data(200,json.dumps({"result":result,"state":state},ensure_ascii=False)); return
            if path=="/api/session/event":
                sid=body.get("session_id"); state=SESSIONS.get(sid)
                if not state: self.send_data(404,json.dumps({"error":"Sesión no encontrada"})); return
                event_key=body.get("event")
                ev=EVENTS_BY_TIME.get(int(event_key)) if str(event_key).isdigit() else None
                if event_key is not None and event_key not in state["events_seen"]: state["events_seen"].append(event_key)
                self.send_data(200,json.dumps({
                    "event":event_key,
                    "text":ev["text"] if ev else None,
                    "title":ev["title"] if ev else None,
                    "type":ev["type"] if ev else None,
                    "voice_source":ev["voice_source"] if ev else None,
                    "patient_voice":ev.get("patient_voice") if ev else None,
                    "state":state,
                },ensure_ascii=False)); return
            if path=="/api/session/finish":
                sid=body.get("session_id"); state=SESSIONS.get(sid)
                if not state: self.send_data(404,json.dumps({"error":"Sesión no encontrada"})); return
                state["completed"]=True; state["finished_at"]=datetime.now().isoformat(); self.send_data(200,json.dumps({"state":state,"debrief":build_debrief(state)},ensure_ascii=False)); return
            self.send_data(404,json.dumps({"error":"Ruta no encontrada"}))
        except Exception as exc: self.send_data(400,json.dumps({"error":str(exc)},ensure_ascii=False))
    def log_message(self, fmt,*args): print(fmt%args)


def build_debrief(state):
    decisions=state["decisions"]; bad=sum(1 for d in decisions if d["score"]<0); good=sum(1 for d in decisions if d["score"]>0)
    status, message = evaluate_case(state)
    state["case_status"] = status
    if status == "listo_para_cierre":
        outcome = "Favorable"
        narrative = message or "El caso se cierra con respuesta hemodinámica sostenida y control del foco infeccioso."
    elif status == "escalamiento_requerido":
        outcome = "Adverso"
        narrative = "El caso se cierra con inestabilidad persistente; en un entorno real correspondería activar escalamiento y soporte avanzado."
    else:
        outcome = "Incompleto"
        narrative = "El caso se cierra sin alcanzar criterios claros de estabilización; conviene revisar tiempos del bundle y la secuencia de reevaluación."
    return {
        "total_decisions":len(decisions),"productive":good,"deviations":bad,"score":state["score"],
        "delay_minutes":state["delay_minutes"],"elapsed_seconds":round(state["elapsed_seconds"],1),
        "physiology":state["physiology"],"events":state["events_seen"],
        "case_status":status,"outcome":outcome,"closure_narrative":narrative,
    }


def main():
    server=ThreadingHTTPServer(("127.0.0.1",8000),Handler); print("\n🏥 Algoritmos Clínicos en Cuidado Crítico — Simulador v0.6\nAbre en el navegador: http://127.0.0.1:8000\nPresiona Ctrl+C para detener.\n")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nServidor detenido.")
    finally: server.server_close()
if __name__=="__main__": main()
