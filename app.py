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
        ("iv","Obtener acceso IV","Requisito previo a fármacos y líquidos"),
        ("antibiotic","Administrar antibiótico empírico","Requiere IV; idealmente después de hemocultivos"),
        ("fluids","Iniciar cristaloides","Requiere IV; bolo de 500 mL, meta ≈30 mL/kg"),
        ("vasopressor","Iniciar norepinefrina","Requiere IV y al menos un bolo de cristaloides previo"),
        ("source_control","Activar control del foco","Requiere hemocultivos y antibiótico ya administrados"),
    ],
    "reassess": [
        ("reassess","Reevaluar respuesta","Integra tendencia fisiológica y clínica"),
        ("recheck_lactate","Revisar tendencia de lactato","Comprueba respuesta metabólica"),
        ("recheck_map","Revisar PAM","Determina si persiste inestabilidad"),
    ],
    "emergency": [
        ("cpr","Iniciar RCP","Compresiones torácicas de alta calidad · solo durante el paro"),
        ("epinephrine","Adrenalina IV","Cada ciclo de RCP · solo durante el paro"),
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
        # ── Prerrequisitos del bundle (dependencias clínicas reales) ──
        "iv_access": False,
        "cultures_done": False,
        "antibiotic_given": False,
        "fluids_count": 0,
        "vasopressor_started": False,
        "source_control_done": False,
        "deviations_log": [],
        "action_counts": {},
        "last_action_time": {},
        "last_coach_at": -999,
        # ── Desenlace real ──
        "critical_seconds": 0.0,
        "arrest": False,
        "arrest_started_at": None,
        "cpr_active": False,
        "epinephrine_count": 0,
        "rosc": False,
        "rosc_achieved_at": None,
        "outcome_locked": None,
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


def generate_coach_message(state):
    """Narración proactiva del preceptor virtual: no depende de que el
    usuario haga clic en algo. Se sondea periódicamente desde el frontend y
    ofrece orientación o refuerzo positivo según el progreso real del
    bundle, con un tono de estímulo (no solo correctivo)."""
    now = state["elapsed_seconds"]
    last = state.get("last_coach_at", -999)
    if now - last < 22:
        return None
    phys = state["physiology"]
    candidates = []
    if not state["iv_access"]:
        candidates.append(("Antes de cualquier fármaco o líquido, asegura un acceso vascular: es la puerta de entrada al resto del bundle.", "Enfermería"))
    elif state["iv_access"] and not state["cultures_done"] and not state["antibiotic_given"]:
        candidates.append(("Buen paso con el acceso IV. Ahora toma los hemocultivos antes del antibiótico, si el tiempo lo permite.", "Equipo"))
    elif state["cultures_done"] and not state["antibiotic_given"]:
        candidates.append(("Cultivos en camino: es un buen momento para iniciar el antibiótico de amplio espectro.", "Laboratorio"))
    elif state["antibiotic_given"] and not state["cultures_done"]:
        candidates.append(("El antibiótico ya está en marcha; en un caso real, documenta que los cultivos no se alcanzaron a tomar antes.", "Equipo"))
    elif state["antibiotic_given"] and phys["map"] < 65 and state["fluids_count"] == 0:
        candidates.append(("La presión arterial sigue baja: valora iniciar cristaloides ahora.", "Monitor"))
    elif state["fluids_count"] > 0 and phys["map"] < 65 and not state["vasopressor_started"]:
        candidates.append(("A pesar del volumen administrado, la PAM continúa baja: considera iniciar soporte vasoactivo.", "Enfermería"))
    elif state["antibiotic_given"] and state["cultures_done"] and not state["source_control_done"]:
        candidates.append(("Con cultivos y antibiótico ya en marcha, evalúa si es momento de activar el control definitivo del foco.", "Equipo"))
    elif phys["map"] >= 65 and state["source_control_done"]:
        candidates.append(("Buen manejo: los parámetros se estabilizan y el foco está controlado. Sigue reevaluando la tendencia.", "Equipo"))
    elif phys["map"] >= 65 and phys["lactate"] > 3:
        candidates.append(("La presión ya responde; sigue de cerca la tendencia del lactato antes de dar el caso por resuelto.", "Laboratorio"))
    if not candidates:
        return None
    text, source = candidates[0]
    state["last_coach_at"] = now
    return {"text": text, "voice_source": source}


def evaluate_case(state):
    """Determina si el caso simulado cumple criterios (educativos) de cierre
    o si, por el contrario, la inestabilidad exige escalamiento.

    El cierre favorable exige el bundle completo (hemocultivos, antibiótico
    y control del foco), no solo metas hemodinámicas: en la práctica real,
    la PAM puede normalizarse transitoriamente sin que la fuente de la
    infección esté resuelta ni el tratamiento antimicrobiano adecuado se
    haya iniciado correctamente.

    Devuelve (status, mensaje) donde status es uno de:
      - "en_curso": el caso continúa sin un hito relevante.
      - "listo_para_cierre": parámetros estables y bundle completo.
      - "escalamiento_requerido": inestabilidad persistente y prolongada.
      - "paro_cardiorrespiratorio": la paciente está en paro (sin pulso).
      - "desenlace_adverso": paro sostenido sin retorno de circulación.
    """
    if state.get("outcome_locked"):
        return "desenlace_adverso", "El caso se cierra con desenlace adverso tras paro cardiorrespiratorio sin retorno de circulación espontánea."
    if state.get("arrest"):
        return "paro_cardiorrespiratorio", "La paciente está en paro cardiorrespiratorio: prioriza RCP y adrenalina."
    phys = state["physiology"]
    hemodinamica_estable = phys.get("map", 0) >= 65 and phys.get("lactate", 99) <= 3.0
    bundle_completo = (
        state.get("cultures_done", False)
        and state.get("antibiotic_given", False)
        and state.get("source_control_done", False)
    )
    prolonged_instability = phys.get("map", 999) < 55 and state["elapsed_seconds"] > 240
    if hemodinamica_estable and bundle_completo:
        return "listo_para_cierre", "Parámetros estables, bundle completo (cultivos, antibiótico y control del foco): el caso cumple criterios educativos para cierre."
    if prolonged_instability:
        return "escalamiento_requerido", "Persiste la inestabilidad y el equipo debe escalar."
    return "en_curso", ""


FLUID_BOLUS_ML = 500          # mL por cada bolo de cristaloides en la simulación
TARGET_ML_KG = 30             # meta orientativa de 30 mL/kg (SSC 2021)
REASSESS_MIN_INTERVAL_S = 20  # evita puntuar reevaluaciones repetidas sin datos nuevos

# ── Desenlace real: paro cardiorrespiratorio / ROSC / estabilización ──
CRITICAL_MAP = 40                 # PAM por debajo de la cual se acumula "tiempo crítico"
ARREST_TRIGGER_SECONDS = 90       # tiempo crítico acumulado (simulado) antes del paro
ARREST_SURVIVABLE_SECONDS = 180   # ventana para lograr RCE antes del desenlace adverso
ROSC_EPI_DOSES_NEEDED = 2         # dosis de adrenalina (con RCP en curso) para intentar RCE


def _peso_paciente():
    return (SCENARIO.get("patient") or {}).get("peso") or 70


def trigger_arrest(state):
    """Dispara el paro cardiorrespiratorio simulado: la paciente deja de
    responder y pierde el pulso. Devuelve la secuencia de alertas/voz que
    dramatiza el evento (enfermería que llama, equipo que confirma ausencia
    de pulso, monitor que registra asistolia)."""
    state["arrest"] = True
    state["arrest_started_at"] = state["elapsed_seconds"]
    state["cpr_active"] = False
    phys = state["physiology"]
    phys["map"] = 0
    phys["bpSys"] = 0
    phys["bpDia"] = 0
    phys["fc"] = 0
    phys["spo2"] = max(0, phys["spo2"] - 20)
    return [
        {"type": "arrest", "title": "Sin respuesta", "text": "¡No responde! ¡No responde! Enfermería llama al equipo.", "voice_source": "Enfermería"},
        {"type": "arrest", "title": "Sin pulso", "text": "No se palpa pulso. Inicien compresiones torácicas de inmediato.", "voice_source": "Equipo"},
        {"type": "arrest", "title": "Asistolia", "text": "El monitor registra asistolia: línea plana, sin actividad eléctrica organizada.", "voice_source": "Monitor"},
    ]


def achieve_rosc(state):
    """Retorno de circulación espontánea tras RCP + adrenalina oportunas."""
    state["arrest"] = False
    state["rosc"] = True
    state["rosc_achieved_at"] = state["elapsed_seconds"]
    state["cpr_active"] = False
    state["critical_seconds"] = 0.0
    phys = state["physiology"]
    phys["map"] = 55
    phys["bpSys"] = 88
    phys["bpDia"] = 52
    phys["fc"] = 108
    phys["spo2"] = 90
    phys["lactate"] = round(phys["lactate"] + 1.2, 1)  # el paro empeora la perfusión tisular
    return [
        {"type": "rosc", "title": "Retorno de circulación", "text": "Recupera pulso palpable. Retorno de circulación espontánea.", "voice_source": "Monitor"},
        {"type": "rosc", "title": "RCE lograda", "text": "Buen trabajo del equipo: la paciente recupera pulso, aunque queda muy inestable y requiere vigilancia estrecha.", "voice_source": "Equipo"},
    ]


def advance_critical_clock(state, elapsed):
    """Avanza el 'reloj crítico' de forma independiente a que el usuario
    actúe: si la paciente permanece inestable, el cuadro empeora
    gradualmente con el tiempo (no se congela) — igual que en la vida real,
    el abandono terapéutico tiene consecuencias. Si la PAM permanece
    crítica el tiempo suficiente, el paro puede ocurrir aunque nadie haga
    clic en nada. Se invoca tanto tras cada acción como desde el sondeo
    periódico del coach."""
    if state.get("arrest") or state.get("outcome_locked"):
        return []
    phys = state["physiology"]
    if phys["map"] < 65:
        # Cuanto más grave la hipotensión, más rápido se deteriora si no se
        # corrige — sin piso artificial que impida llegar al paro.
        severity = max(0.0, 65 - phys["map"]) / 65
        drift = elapsed * (0.04 + severity * 0.12)
        phys["map"] = max(0.0, phys["map"] - drift)
        phys["lactate"] = round(min(12.0, phys["lactate"] + elapsed * 0.01 * (1 + severity)), 1)
        if phys["spo2"] < 92:
            phys["spo2"] = max(50.0, phys["spo2"] - elapsed * 0.02)
    if phys["map"] < CRITICAL_MAP:
        state["critical_seconds"] = state.get("critical_seconds", 0.0) + elapsed
    else:
        state["critical_seconds"] = max(0.0, state.get("critical_seconds", 0.0) - elapsed * 0.5)
    if state["critical_seconds"] >= ARREST_TRIGGER_SECONDS:
        return trigger_arrest(state)
    return []


def check_arrest_outcome(state):
    """Si el paro se sostiene más allá de la ventana simulada sin lograr
    RCE, se declara el desenlace adverso y se cierra el caso."""
    if not state.get("arrest") or state.get("outcome_locked"):
        return []
    since_arrest = state["elapsed_seconds"] - (state.get("arrest_started_at") or 0)
    if since_arrest >= ARREST_SURVIVABLE_SECONDS:
        state["outcome_locked"] = "paro_sin_rce"
        state["case_status"] = "desenlace_adverso"
        state["completed"] = True
        return [{"type": "case_end", "title": "Desenlace",
                  "text": "A pesar de las maniobras, no se logra retorno de circulación espontánea. Se declara el desenlace adverso de este caso simulado.",
                  "voice_source": "Equipo"}]
    return []


def apply_action(state, action_id, elapsed):
    elapsed = max(0, float(elapsed))
    state["elapsed_seconds"] += elapsed
    before = dict(state["physiology"])
    good = True
    score = 0
    feedback = ""
    observation = ""
    deviation = None
    special_alerts = []
    is_request = action_id.startswith("request_")

    counts = state.setdefault("action_counts", {})
    prev_count = counts.get(action_id, 0)
    counts[action_id] = prev_count + 1
    peso = _peso_paciente()

    if state.get("arrest") and action_id not in ("cpr", "epinephrine"):
        good = False; score = 0
        feedback = "La paciente está en paro cardiorrespiratorio: ninguna otra intervención es válida ahora."
        observation = "Prioriza RCP de alta calidad y adrenalina antes que cualquier otra acción del bundle."

    elif is_request:
        key = action_id.replace("request_", "")
        if key in SCENARIO["available_tests"]:
            info = SCENARIO["available_tests"][key]
            already = key in state["requested_information"]
            if not already:
                state["requested_information"].append(key)
                score = 1
                feedback = f"Información obtenida: {info['result']}."
            else:
                feedback = f"Ya cuentas con este resultado: {info['result']}."
            observation = info["detail"]
            if key == "cultures":
                state["cultures_done"] = True
        else:
            good = False
            feedback = "Solicitud no reconocida."

    elif action_id == "oxygen":
        if state["physiology"]["spo2"] >= 94:
            feedback = "La saturación ya es adecuada; el oxígeno adicional no aporta más en este momento."
            observation = "Evita intervenciones sin indicación clara; prioriza otra acción del algoritmo."
        else:
            gain = max(1, 6 - prev_count * 2)
            state["physiology"]["spo2"] = min(97, state["physiology"]["spo2"] + gain)
            score = 1
            feedback = "La oxigenación mejora con soporte suplementario."
            observation = "La SpO₂ asciende, pero la inestabilidad hemodinámica persiste."

    elif action_id == "iv":
        if state["iv_access"]:
            feedback = "El acceso vascular ya estaba disponible."
        else:
            state["iv_access"] = True
            score = 1
            feedback = "Acceso vascular conseguido."
        observation = "El acceso IV es prerrequisito real para administrar antibióticos, cristaloides y vasopresores."

    elif action_id == "antibiotic":
        if not state["iv_access"]:
            good = False; score = -2
            feedback = "No es correcto: no se puede administrar el antibiótico sin acceso vascular."
            observation = "Obtén un acceso IV antes de iniciar cualquier tratamiento endovenoso."
            deviation = "Se intentó administrar antibiótico sin acceso IV disponible."
        elif state["antibiotic_given"]:
            feedback = "Ya se había iniciado el antimicrobiano; no se repite dosis en la simulación."
            observation = "Prioriza otra acción del bundle."
        else:
            if not state["cultures_done"]:
                good = False; score = -1
                # Beneficio reducido: al no tener cultivos previos se pierde
                # rendimiento diagnóstico y no puede considerarse una decisión
                # oportuna, aunque el fármaco sí se administre.
                state["physiology"]["lactate"] = round(max(4.2, state["physiology"]["lactate"] - 0.1), 1)
                state["physiology"]["fc"] -= 1
                feedback = "No es correcto todavía: se administró antibiótico SIN hemocultivos previos (desviación del bundle de 1 hora)."
                observation = "El bundle SSC exige tomar hemocultivos ANTES de iniciar antibióticos, cuando no retrasa la terapia. El efecto terapéutico es menor sin diagnóstico microbiológico."
                deviation = "Antibiótico administrado sin hemocultivos previos."
            else:
                score = 2
                state["physiology"]["lactate"] = round(max(3.8, state["physiology"]["lactate"] - 0.25), 1)
                state["physiology"]["fc"] -= 4
                feedback = "Antibiótico de amplio espectro administrado en el momento oportuno del bundle."
                observation = "La respuesta es gradual; todavía requiere soporte y reevaluación."
            state["antibiotic_given"] = True

    elif action_id == "fluids":
        if not state["iv_access"]:
            good = False; score = -2
            feedback = "No es correcto: no se pueden iniciar cristaloides sin acceso vascular."
            observation = "Obtén un acceso IV antes de iniciar líquidos."
            deviation = "Se intentaron cristaloides sin acceso IV disponible."
        else:
            ml_previo = state["fluids_count"] * FLUID_BOLUS_ML
            mlkg_previo = ml_previo / peso
            if mlkg_previo >= TARGET_ML_KG and state["physiology"]["map"] >= 65:
                good = False; score = -2
                state["physiology"]["spo2"] = max(85, state["physiology"]["spo2"] - 2)
                state["physiology"]["rr"] += 2
                state["physiology"]["fc"] += 4
                feedback = "No es correcto: volumen adicional sin indicación, con la PAM ya en meta."
                observation = f"Ya se administraron ≈{ml_previo} mL (≈{mlkg_previo:.0f} mL/kg) y la PAM está en meta: riesgo real de sobrecarga hídrica."
                deviation = "Cristaloides administrados más allá de la meta de 30 mL/kg sin indicación (riesgo de sobrecarga)."
            else:
                state["fluids_count"] += 1
                gain = max(2, 6 - (state["fluids_count"] - 1))  # respuesta decreciente a boluses repetidos
                state["physiology"]["map"] += gain
                state["physiology"]["bpSys"] += round(gain * 1.3)
                state["physiology"]["bpDia"] += round(gain * 0.7)
                state["physiology"]["lactate"] = round(max(3.6, state["physiology"]["lactate"] - 0.3), 1)
                score = 2
                ml_total = state["fluids_count"] * FLUID_BOLUS_ML
                feedback = f"Bolo de cristaloides administrado (≈{ml_total} mL acumulados, ≈{ml_total/peso:.0f} mL/kg)."
                observation = "La respuesta es incompleta: continúa la necesidad de reevaluación."

    elif action_id == "vasopressor":
        if not state["iv_access"]:
            good = False; score = -2
            feedback = "No es correcto: no se puede iniciar vasopresor sin acceso vascular."
            observation = "Obtén un acceso IV antes de iniciar soporte vasoactivo."
            deviation = "Se intentó iniciar vasopresor sin acceso IV disponible."
        else:
            hipotension_critica = state["physiology"]["map"] < 50
            if state["fluids_count"] == 0 and not hipotension_critica:
                good = False; score = -2
                # Sin beneficio hemodinámico: vasoconstricción sobre un lecho
                # vascular no repletado no mejora la PAM de forma fiable y
                # añade riesgo de taquiarritmia. No puede llamarse "correcta".
                state["physiology"]["fc"] += 6
                state["vasopressor_started"] = True
                feedback = "No es correcto todavía: vasopresor iniciado sin ningún bolo de cristaloides previo (intervención prematura, no oportuna)."
                observation = "La SSC 2021 recomienda iniciar/continuar cristaloides antes o junto con vasopresores, salvo hipotensión crítica refractaria. Sin volumen previo, la respuesta presora es poco fiable y aumenta el riesgo de arritmia."
                deviation = "Vasopresor iniciado antes de cualquier bolo de cristaloides (sin hipotensión crítica que lo justifique)."
            else:
                if state["physiology"]["map"] < 65:
                    state["physiology"]["map"] += 12
                    state["physiology"]["bpSys"] += 12
                    state["physiology"]["bpDia"] += 5
                    score = 3
                    feedback = "Norepinefrina iniciada en el momento oportuno: la PAM mejora con soporte vasoactivo."
                else:
                    feedback = "Soporte vasoactivo aplicado con la PAM ya en meta; no aporta beneficio adicional."
                    observation = "Evita escalar vasopresores sin indicación hemodinámica."
                state["vasopressor_started"] = True
                observation = observation or "La perfusión mejora, pero el foco y la tendencia del lactato deben seguirse."

    elif action_id == "source_control":
        if not state["iv_access"]:
            good = False; score = -2
            feedback = "No es correcto controlar el foco todavía: no hay acceso vascular ni tratamiento en marcha."
            observation = "El control del foco requiere primero acceso IV, hemocultivos y antibiótico administrados."
            deviation = "Se intentó el control del foco sin acceso IV (ningún paso previo del bundle se había completado)."
        elif not (state["cultures_done"] and state["antibiotic_given"]):
            good = False; score = -1
            faltan = []
            if not state["cultures_done"]:
                faltan.append("hemocultivos")
            if not state["antibiotic_given"]:
                faltan.append("antibiótico")
            feedback = f"No es correcto todavía: falta completar {', '.join(faltan)} antes del control del foco."
            observation = "Reconoce y trata primero la infección (cultivos + antibiótico) antes de un control definitivo del foco."
            deviation = "Se intentó el control del foco antes de completar el reconocimiento diagnóstico/terapéutico inicial."
        elif state["source_control_done"]:
            feedback = "El control del foco ya se había activado."
        else:
            state["physiology"]["lactate"] = round(max(2.8, state["physiology"]["lactate"] - 0.5), 1)
            score = 3
            state["source_control_done"] = True
            feedback = "Control del foco activado en el momento oportuno del bundle."
            observation = "La trayectoria simulada mejora gradualmente si se mantiene la reanimación."

    elif action_id in ("reassess", "recheck_lactate", "recheck_map"):
        last_t = state["last_action_time"].get(action_id)
        now_t = state["elapsed_seconds"]
        if last_t is not None and (now_t - last_t) < REASSESS_MIN_INTERVAL_S:
            feedback = "Reevaluación repetida en un intervalo muy corto; todavía no hay información nueva."
            observation = "Espera a que la situación cambie antes de reevaluar de nuevo."
        else:
            score = 2
            if action_id == "recheck_lactate":
                feedback = f"Lactato actual: {state['physiology']['lactate']:.1f} mmol/L."
            elif action_id == "recheck_map":
                feedback = f"PAM actual: {state['physiology']['map']} mmHg."
            else:
                feedback = "Reevaluación realizada: integra tendencia fisiológica y clínica."
            observation = "Compara con la evaluación previa antes de decidir la siguiente acción."
        state["last_action_time"][action_id] = now_t

    elif action_id in ("assess_airway", "assess_breathing", "assess_perfusion"):
        labels = {
            "assess_airway": ("Vía aérea evaluada.", "La vía aérea está patente en este escenario, pero la paciente presenta alteración del estado mental."),
            "assess_breathing": ("Respiración evaluada.", "Taquipnea e hipoxemia requieren soporte y reevaluación."),
            "assess_perfusion": ("Perfusión evaluada.", "La hipotensión y la alteración del estado mental sugieren hipoperfusión."),
        }
        fb, obs = labels[action_id]
        if prev_count == 0:
            score = 2 if action_id == "assess_perfusion" else 1
            feedback = fb
        else:
            feedback = "Ya evaluado recientemente; prioriza otra acción del algoritmo."
        observation = obs

    elif action_id == "vitals":
        if prev_count == 0:
            score = 1
            feedback = "Signos vitales actualizados."
        else:
            feedback = "Ya revisaste el monitor recientemente; prioriza otra acción."
        observation = "Observa la tendencia, no solo un valor puntual."

    elif action_id == "cpr":
        if not state.get("arrest"):
            good = False; score = 0
            feedback = "No hay indicación de RCP: la paciente tiene pulso."
            observation = "Reserva las compresiones torácicas para un paro cardiorrespiratorio real."
        else:
            state["cpr_active"] = True
            score = 2
            feedback = "Compresiones torácicas de alta calidad en curso."
            observation = "Mantén el RCP casi sin interrupciones; permite una dosis de adrenalina cada ciclo."

    elif action_id == "epinephrine":
        if not state.get("arrest"):
            good = False; score = 0
            feedback = "No hay indicación de adrenalina: la paciente tiene pulso."
            observation = "La adrenalina se reserva para el paro cardiorrespiratorio."
        elif not state.get("cpr_active"):
            good = False; score = -1
            feedback = "Antes de la adrenalina, inicia compresiones torácicas de alta calidad."
            observation = "El RCP sostiene una perfusión mínima mientras actúa el fármaco."
        else:
            state["epinephrine_count"] += 1
            score = 2
            feedback = f"Adrenalina IV administrada (dosis {state['epinephrine_count']})."
            observation = "Continúa el RCP; en un paro real se repite cada 3–5 minutos."
            if state["epinephrine_count"] >= ROSC_EPI_DOSES_NEEDED:
                special_alerts += achieve_rosc(state)
                feedback += " Se logra retorno de circulación espontánea."

    else:
        good = False; score = -1; state["delay_minutes"] += 2
        feedback = "La acción no aporta a la prioridad actual."
        observation = "El tiempo continúa y debes reevaluar."

    if deviation:
        state.setdefault("deviations_log", []).append(deviation)

    state["score"] += score
    # Deterioro temporal educativo si se acumula retraso sin soporte hemodinámico.
    if not state.get("arrest") and elapsed >= 30 and action_id not in {"reassess","recheck_lactate","recheck_map","vasopressor","fluids","antibiotic","iv"}:
        state["physiology"]["map"] = max(0, state["physiology"]["map"]-3)
        state["physiology"]["lactate"] = round(state["physiology"]["lactate"]+0.2,1)
        state["delay_minutes"] += 1
        observation += " El tiempo acumulado introduce un pequeño deterioro educativo simulado."
    if state.get("arrest"):
        state["phase"] = "Paro cardiorrespiratorio"
    elif state["physiology"]["map"] >= 65:
        state["phase"] = "Respuesta hemodinámica parcial"
    else:
        state["phase"] = "Inestabilidad persistente"

    # Retroalimentación de ritmo: premia decisiones oportunas, señala demoras.
    tag = speed_tag(elapsed)
    feedback = f"{feedback} {tag}.".strip()

    alerts = []
    alerts += special_alerts

    # Avanza el reloj crítico (puede disparar el paro) y revisa si el paro
    # sostenido sin RCE debe cerrar el caso con desenlace adverso.
    alerts += advance_critical_clock(state, elapsed)
    alerts += check_arrest_outcome(state)

    # Racha de decisiones productivas: refuerzo positivo cada 3 aciertos seguidos.
    if score > 0 and good:
        state["streak"] = state.get("streak", 0) + 1
    else:
        state["streak"] = 0
    if state["streak"] > 0 and state["streak"] % 3 == 0:
        alerts.append({"type": "encouragement", "title": "Buen manejo",
                        "text": "La secuencia de decisiones sigue el bundle recomendado.",
                        "voice_source": "Equipo"})

    # Anuncia en voz alta las desviaciones del protocolo (refuerzo educativo).
    if deviation:
        alerts.append({"type": "deviation", "title": "Desviación del protocolo",
                        "text": deviation, "voice_source": "Equipo"})

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
    if new_status != previous_status and new_status not in ("en_curso", "paro_cardiorrespiratorio", "desenlace_adverso"):
        if new_status == "escalamiento_requerido":
            alerts.append({"type": "deterioration", "title": "Deterioro", "text": status_message, "voice_source": "Enfermería"})
        elif new_status == "listo_para_cierre":
            alerts.append({"type": "closure", "title": "Cierre sugerido", "text": status_message, "voice_source": "Equipo"})

    return {
        "before": before, "after": state["physiology"], "good": good, "score": score,
        "feedback": feedback, "observation": observation, "alerts": alerts,
        "consciousness": state["consciousness"], "deviation": deviation,
        "arrest": state.get("arrest", False), "rosc": state.get("rosc", False),
        "cpr_active": state.get("cpr_active", False),
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
                        "alerts":r["alerts"],"arrest":r["arrest"],"rosc":r["rosc"],"cpr_active":r["cpr_active"]}
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
            if path=="/api/session/coach":
                sid=body.get("session_id"); state=SESSIONS.get(sid)
                if not state: self.send_data(404,json.dumps({"error":"Sesión no encontrada"})); return
                elapsed=max(0.0, float(body.get("elapsed_seconds",15)))
                state["elapsed_seconds"] += elapsed
                alerts=advance_critical_clock(state, elapsed) + check_arrest_outcome(state)
                msg=generate_coach_message(state) if not state.get("arrest") else None
                self.send_data(200,json.dumps({"message":msg,"alerts":alerts,"arrest":state.get("arrest",False),
                                                "rosc":state.get("rosc",False),"case_status":state.get("case_status"),
                                                "physiology":state["physiology"]},ensure_ascii=False)); return
            self.send_data(404,json.dumps({"error":"Ruta no encontrada"}))
        except Exception as exc: self.send_data(400,json.dumps({"error":str(exc)},ensure_ascii=False))
    def log_message(self, fmt,*args): print(fmt%args)


def build_debrief(state):
    decisions=state["decisions"]; bad=sum(1 for d in decisions if d["score"]<0); good=sum(1 for d in decisions if d["score"]>0)
    status, message = evaluate_case(state)
    state["case_status"] = status
    deviations_log = state.get("deviations_log", [])
    arrest_occurred = state.get("arrest", False) or state.get("rosc", False) or bool(state.get("outcome_locked"))
    rosc_achieved = state.get("rosc", False)
    if status == "desenlace_adverso":
        outcome = "Adverso"
        narrative = message or "El caso se cierra con desenlace adverso: paro cardiorrespiratorio sostenido sin retorno de circulación espontánea, a pesar de las maniobras de reanimación."
    elif status == "paro_cardiorrespiratorio":
        outcome = "Crítico"
        narrative = "El caso se cierra con la paciente aún en paro cardiorrespiratorio: continúa el RCP y la adrenalina, o deja que la simulación avance para ver el desenlace."
    elif status == "listo_para_cierre":
        outcome = "Favorable"
        narrative = message or "El caso se cierra con respuesta hemodinámica sostenida y control del foco infeccioso."
        if rosc_achieved:
            narrative += " La paciente logró retorno de circulación espontánea tras el paro y, aun así, alcanzó estabilización — un desenlace favorable poco frecuente que refleja un manejo de emergencia oportuno."
    elif status == "escalamiento_requerido":
        outcome = "Adverso"
        narrative = "El caso se cierra con inestabilidad persistente; en un entorno real correspondería activar escalamiento y soporte avanzado."
    else:
        outcome = "Incompleto"
        faltantes = []
        if not state.get("cultures_done"): faltantes.append("hemocultivos")
        if not state.get("antibiotic_given"): faltantes.append("antibiótico de amplio espectro")
        if not state.get("source_control_done"): faltantes.append("control del foco")
        if faltantes:
            narrative = f"El caso se cierra sin completar el bundle: falta {', '.join(faltantes)}. Revisa la secuencia y los tiempos del protocolo."
        else:
            narrative = "El caso se cierra sin alcanzar criterios claros de estabilización; conviene revisar tiempos del bundle y la secuencia de reevaluación."
        if rosc_achieved:
            narrative += " La paciente logró retorno de circulación espontánea tras un paro cardiorrespiratorio, pero el caso no alcanzó una estabilización completa."
    if deviations_log:
        narrative += f" Se registraron {len(deviations_log)} desviación(es) del protocolo durante el caso."
    return {
        "total_decisions":len(decisions),"productive":good,"deviations":bad,"score":state["score"],
        "delay_minutes":state["delay_minutes"],"elapsed_seconds":round(state["elapsed_seconds"],1),
        "physiology":state["physiology"],"events":state["events_seen"],
        "case_status":status,"outcome":outcome,"closure_narrative":narrative,
        "protocol_deviations":deviations_log,
        "arrest_occurred":arrest_occurred,"rosc_achieved":rosc_achieved,
        "epinephrine_doses":state.get("epinephrine_count",0),
        "bundle_status":{
            "iv_access":state.get("iv_access",False),
            "cultures_done":state.get("cultures_done",False),
            "antibiotic_given":state.get("antibiotic_given",False),
            "fluids_ml":state.get("fluids_count",0)*FLUID_BOLUS_ML,
            "vasopressor_started":state.get("vasopressor_started",False),
            "source_control_done":state.get("source_control_done",False),
        },
    }


def main():
    server=ThreadingHTTPServer(("127.0.0.1",8000),Handler); print("\n🏥 Algoritmos Clínicos en Cuidado Crítico — Simulador v0.6\nAbre en el navegador: http://127.0.0.1:8000\nPresiona Ctrl+C para detener.\n")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nServidor detenido.")
    finally: server.server_close()
if __name__=="__main__": main()
