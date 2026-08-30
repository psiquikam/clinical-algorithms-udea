"""
Algoritmo clínico: Intubación en Secuencia Rápida (RSI)
Basado en: Difficult Airway Society (DAS) Guidelines 2015
y ATLS 10th Edition

Este módulo implementa el algoritmo de RSI como un árbol de decisiones
formal que incluye: evaluación pre-intubación, preparación, inducción,
parálisis, intubación y manejo post-intubación, con planes de rescate
para vía aérea difícil.

Referencias:
    - Frerk C, et al. Difficult Airway Society 2015 guidelines for
      management of unanticipated difficult intubation in adults.
      Br J Anaesth. 2015.
    - ATLS Subcommittee. Advanced Trauma Life Support 10th Edition.
      American College of Surgeons. 2018.
    - Mosier JM, et al. Rapid Sequence Intubation. N Engl J Med. 2022.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum

from models.patient import Paciente, NivelConciencia, ViaAerea


class ClasificacionMallampati(Enum):
    """Clasificación de Mallampati modificada."""
    CLASE_I = "Clase I - Estructuras visibles"
    CLASE_II = "Clase II - Úvula parcialmente visible"
    CLASE_III = "Clase III - Solo base de úvula"
    CLASE_IV = "Clase IV - Solo paladar duro"


class DificultadViaAerea(Enum):
    """Estratificación de dificultad de vía aérea."""
    SIN_DIFICULTAD = "Sin dificultad anticipada"
    DIFICULTAD_POSIBLE = "Dificultad posible"
    DIFICULTAD_ESPERADA = "Dificultad esperada"
    VIA_AEREA_FRUSTRA = "Vía aérea frustra (no intubable, no ventilable)"


class AgenteInduccion(Enum):
    """Agentes de inducción disponibles."""
    ETOMIDATO = "Etomidato 0.3 mg/kg"
    KETAMINA = "Ketamina 1-2 mg/kg"
    PROPOFOL = "Propofol 1.5-2 mg/kg"
    MIDAZOLAM = "Midazolam 0.1-0.3 mg/kg"


class BloqueanteNeuromuscular(Enum):
    """Bloqueantes neuromusculares para RSI."""
    SUCCINILCOLINA = "Succinilcolina 1-1.5 mg/kg"
    ROCURONIO = "Rocuronio 1.2 mg/kg"


class PlanRSI(Enum):
    """Planes DAS para vía aérea difícil."""
    PLAN_A = "Plan A - Intubación estándar"
    PLAN_B = "Plan B - Dispositivo supraglótico"
    PLAN_C = "Plan C - Ventilación con mascarilla"
    PLAN_D = "Plan D - Vía aérea quirúrgica (cricotiroidotomía)"


@dataclass
class EvaluacionViaAerea:
    """Resultado de evaluación de vía aérea."""
    mallampati: Optional[ClasificacionMallampati] = None
    apertura_bucal: Optional[int] = None     # mm (normal ≥30)
    distancia_tiromentoniana: Optional[int] = None  # mm (normal ≥60)
    extension_atlantooccipital: Optional[str] = None
    obesidad: bool = False
    sangrado_anticipated: bool = False
    traumatismo_cervical: bool = False
    score_dificultad: int = 0
    clasificacion: DificultadViaAerea = DificultadViaAerea.SIN_DIFICULTAD


@dataclass
class ResultadoRSI:
    """Resultado completo del algoritmo RSI."""
    evaluacion_via_aerea: EvaluacionViaAerea
    agente_induccion: AgenteInduccion
    bloqueante: BloqueanteNeuromuscular
    pasos_preparacion: List[str]
    pasos_ejecucion: List[str]
    plan_rescate: List[str]
    manejo_post_intubacion: List[str]
    alertas: List[str]
    dosis_calculadas: dict


class AlgoritmoRSI:
    """
    Algoritmo de Intubación en Secuencia Rápida (RSI).
    
    Implementa:
    - Evaluación pre-intubación (MALLAMPATI, LEMON)
    - Preparación (7 P's)
    - Selección de agentes farmacológicos
    - Ejecución de RSI
    - Planes de rescate DAS (A→B→C→D)
    - Manejo post-intubación
    """

    # ─── Umbrales y constantes ────────────────────────────────────
    UMBRALES = {
        "apertura_bucal_minima": 30,        # mm
        "dtm_minima": 60,                    # mm
        "spo2_preoxigenacion": 98,           # %
        "spo2_minima_intubacion": 90,        # %
        "tiempo_apnea_seguro": 8,            # minutos (aproximado)
        "pam_minima": 65,                    # mmHg
        "dosis_sugammadex": 16,              # mg/kg (reversión completa)
    }

    def __init__(self):
        self.historial: List[dict] = []

    # ═══════════════════════════════════════════════════════════════
    # PASO 1: Evaluación de vía aérea
    # ═══════════════════════════════════════════════════════════════
    def evaluar_via_aerea(self, paciente: Paciente) -> EvaluacionViaAerea:
        """
        Evaluación de vía aérea usando criterio LEMON simplificado.
        
        L = Look externally (mirada externa)
        E = Evaluate 3-3-2 rule
        M = Mallampati
        O = Obstruction
        N = Neck mobility
        
        Args:
            paciente: Objeto Paciente.
            
        Returns:
            EvaluacionViaAerea con score de dificultad y clasificación.
        """
        evalua = EvaluacionViaAerea()
        score = 0

        # ── L: Mirada externa ──
        if paciente.peso > 120:
            evalua.obesidad = True
            score += 1
        if paciente.antecedentes and any(
            "tumor" in a.lower() or "masa" in a.lower()
            for a in paciente.antecedentes
        ):
            score += 1

        # ── E: Regla 3-3-2 (simplificada) ──
        if evalua.apertura_bucal is not None and evalua.apertura_bucal < self.UMBRALES["apertura_bucal_minima"]:
            score += 1
        if evalua.distancia_tiromentoniana is not None and evalua.distancia_tiromentoniana < self.UMBRALES["dtm_minima"]:
            score += 1

        # ── M: Mallampati ──
        if evalua.mallampati in (ClasificacionMallampati.CLASE_III, ClasificacionMallampati.CLASE_IV):
            score += 2

        # ── O: Obstrucción ──
        if paciente.via_aerea in (ViaAerea.OBSTRUIDA_PARCIAL, ViaAerea.OBSTRUIDA_TOTAL):
            evalua.sangrado_anticipated = True
            score += 2

        # ── N: Movilidad cervical ──
        if evalua.traumatismo_cervical or any(
            "trauma cervical" in a.lower() or "inmovilización" in a.lower()
            for a in paciente.antecedentes
        ):
            evalua.traumatismo_cervical = True
            score += 1

        evalua.score_dificultad = score

        # Clasificación
        if score >= 5:
            evalua.clasificacion = DificultadViaAerea.DIFICULTAD_ESPERADA
        elif score >= 2:
            evalua.clasificacion = DificultadViaAerea.DIFICULTAD_POSIBLE
        else:
            evalua.clasificacion = DificultadViaAerea.SIN_DIFICULTAD

        return evalua

    # ═══════════════════════════════════════════════════════════════
    # PASO 2: Selección de agentes farmacológicos
    # ═══════════════════════════════════════════════════════════════
    def seleccionar_agente_induccion(self, paciente: Paciente) -> AgenteInduccion:
        """
        Selecciona el agente de inducción según el estado hemodinámico.
        
        Criterios:
        - Etomidato: Inestabilidad hemodinámica (PAM <65)
        - Ketamina: Broncoespasmo, inestabilidad relativa
        - Propofol: Paciente hemodinámicamente estable
        - Midazolam: Última opción, titulable
        
        Args:
            paciente: Objeto Paciente.
            
        Returns:
            AgenteInduccion seleccionado.
        """
        sv = paciente.signos_vitales
        pam = sv.presion_arterial_media or 0

        # Inestabilidad hemodinámica severa
        if pam < self.UMBRALES["pam_minima"]:
            return AgenteInduccion.ETOMIDATO

        # Broncoespasmo o asma
        if paciente.antecedentes and any(
            "asma" in a.lower() or "broncoespasmo" in a.lower()
            for a in paciente.antecedentes
        ):
            return AgenteInduccion.KETAMINA

        # Paciente estable
        if pam >= self.UMBRALES["pam_minima"]:
            return AgenteInduccion.ETOMIDATO  # Opción más segura en general

        return AgenteInduccion.MIDAZOLAM

    def seleccionar_bloqueante(self, paciente: Paciente) -> BloqueanteNeuromuscular:
        """
        Selecciona el bloqueante neuromuscular.
        
        Criterios:
        - Succinilcolina: Primera línea si no hay contraindicaciones
        - Rocuronio: Si hay contraindicaciones para succinilcolina
          o vía aérea difícil (reversible con sugammadex)
        
        Args:
            paciente: Objeto Paciente.
            
        Returns:
            BloqueanteNeuromuscular seleccionado.
        """
        contraindicaciones_sux = [
            "hiperpotasemia", "quemadura", "denervación",
            "miopatía", "antecedente de hipertermia maligna"
        ]

        # Verificar contraindicaciones de succinilcolina
        antecedentes_lower = [a.lower() for a in paciente.antecedentes]
        if any(
            any(c in a for c in contraindicaciones_sux)
            for a in antecedentes_lower
        ):
            return BloqueanteNeuromuscular.ROCURONIO

        # Si hay dificultad de vía aérea, preferir rocuronio (reversible)
        evalua = self.evaluar_via_aerea(paciente)
        if evalua.clasificacion in (DificultadViaAerea.DIFICULTAD_POSIBLE, DificultadViaAerea.DIFICULTAD_ESPERADA):
            return BloqueanteNeuromuscular.ROCURONIO

        return BloqueanteNeuromuscular.SUCCINILCOLINA

    # ═══════════════════════════════════════════════════════════════
    # PASO 3: Preparación (Las 7 P's)
    # ═══════════════════════════════════════════════════════════════
    def preparar_7_ps(self, paciente: Paciente) -> List[str]:
        """
        Preparación para RSI: Las 7 P's.
        
        1. Preparation (Preparación)
        2. Preoxygenation (Preoxigenación)
        3. Pre-treatment (Pretratamiento)
        4. Paralysis with induction (Parálisis con inducción)
        5. Protection and positioning (Protección y posicionamiento)
        6. Placement with proof (Colocación con confirmación)
        7. Post-intubation management (Manejo post-intubación)
        
        Args:
            paciente: Objeto Paciente.
            
        Returns:
            Lista de pasos de preparación.
        """
        pasos = [
            "═══════════════════════════════════════════════════",
            "  PREPARACIÓN RSI — LAS 7 P's",
            "═══════════════════════════════════════════════════",
            "",
            "📋 1. PREPARATION (Preparación)",
            "   • Equipo de intubación verificado:",
            "     - Laringoscopio con hoja curva #3 y #4",
            "     - Tubo endotraqueal 7.0-8.0 mm (con guía)",
            "     - Manguito verificado (sin fugas)",
            "     - Piloto del manguito inflado",
            "   • Aspiración conectada y funcional",
            "   • Dispositivo supraglótico de rescate (LMA/i-gel)",
            "   • BVM (balón bolsa mascarilla) con PEEP valve",
            "   • Cánula orofaríngea #3 y #4",
            "   • Guía de Eschmann (bougie)",
            "   • Cinta de fijación, estetoscopio",
            "   • Capnógrafo (capnografía es ESTÁNDAR)",
            "   • Bisturí #11 para cricotiroidotomía de emergencia",
            "",
            "🫁 2. PREOXYGENATION (Preoxigenación)",
            "   • FiO2 100% por 3-5 minutos (capacidad residual funcional)",
            "   • O usar 8 maniobras de capacidad vital",
            f"   • Meta: SpO2 ≥ {self.UMBRALES['spo2_preoxigenacion']}%",
            f"   • Desaturación esperada: {paciente.peso} kg → "
            f"aprox. {max(1, 8 - (paciente.peso - 70) * 0.05):.1f} min hasta SpO2 <90%",
            "   • EN LERD: Apoyo con ventilación no invasiva (CPAP/BiPAP)",
            "",
            "💊 3. PRE-TREATMENT (Pretratamiento — 3 min antes)",
            "   • Fentanyl 1-3 µg/kg IV (atenua respuesta simpática)",
            "   • Lidocaína 1.5 mg/kg IV (si hipertensión intracraneana)",
            "   • Atropina 0.02 mg/kg (si <1 año o bradicardia)",
            "   • Defasciculante: NO recomendado rutinariamente",
            "",
            "💉 4. PARALYSIS WITH INDUCTION (Parálisis con inducción)",
            "   • Administrar INDUCTOR + BNM en secuencia RÁPIDA",
            "   • NO se ventila entre inducción y parálisis",
            "   • Esperar 45-60 seg para intubación",
            "",
            "🛡️ 5. PROTECTION AND POSITIONING",
            "   • Posición de olfateo (cabeza extendida, cuello flexionado)",
            "   • Alineación manual en línea si trauma cervical",
            "   • Maniobra de Sellick (presión cricoidea) — opcional",
            "",
            "🎯 6. PLACEMENT WITH PROOF (Colocación con confirmación)",
            "   • Confirmar con capnografía (ETCO2) — patrón cuadrado",
            "   • Auscultación bilateral",
            "   • Visualización directa de cuerdas vocales",
            "   • Rx de tórax post-intubación",
            "",
            "🏥 7. POST-INTUBATION MANAGEMENT",
            "   • Fijar tubo endotraqueal",
            "   • Iniciar ventilación mecánica",
            "   • Sedación continua",
        ]

        return pasos

    # ═══════════════════════════════════════════════════════════════
    # PASO 4: Planes de rescate DAS
    # ═══════════════════════════════════════════════════════════════
    def generar_plan_rescate(self, evaluacion: EvaluacionViaAerea) -> List[str]:
        """
        Genera los planes de rescate según DAS Guidelines.
        
        Plan A → Intubación estándar (máximo 2 intentos + 1 por experto)
        Plan B → Dispositivo supraglótico (LMA/i-gel)
        Plan C → Ventilación con mascarilla + despertar
        Plan D → Vía aérea quirúrgica (Cricotiroidotomía)
        
        Args:
            evaluacion: EvaluacionViaAerea del paciente.
            
        Returns:
            Lista de pasos de rescate.
        """
        plan = [
            "",
            "═══════════════════════════════════════════════════",
            "  PLANES DE RESCATE DAS (Vía Aérea Difícil)",
            f"  Clasificación: {evaluacion.clasificacion.value}",
            "═══════════════════════════════════════════════════",
            "",
            "🅰️  PLAN A — Intubación estándar",
            "   • Intento 1: Laringoscopia directa + bougie",
            "   • Intento 2: Cambio de hoja, BURP (Backward-Upward-Rightward Pressure)",
            "   • Intento 3: Solo por operador más experimentado",
            "   • MÁXIMO 3 INTENTOS → Pasar a Plan B",
            "   • Si SpO2 <90% en cualquier momento → Plan B",
            "",
            "🅱️  PLAN B — Dispositivo supraglótico",
            "   • LMA de segunda generación (LMA ProSeal/i-gel)",
            "   • Intento 1: Inserción estándar",
            "   • Intento 2: Cambio de tamaño o técnica",
            "   • Si ventilación exitosa → Intubación a través del LMA",
            "   • Si falla → Plan C",
            "",
            "🅲  PLAN C — Mascarilla + bolsa",
            "   • Ventilación con BVM + cánula orofaríngea",
            "   • Dos operadores si es necesario",
            "   • Si ventilación exitosa → DESPERTAR al paciente",
            "   • Si NO se puede ventilar → Plan D (Vía aérea frustra)",
            "",
            "🅳  PLAN D — Vía aérea quirúrgica de emergencia",
            "   • CRICOTIROIDOTOMÍA",
            "   • Técnica: Bisturí-bougie-tubo (scalpel-bougie-tube)",
            "   • Pasos: Palpar → Incisión vertical → Punción membrana → Bougie → Tubo 6.0",
            "   • ⚠️  NO SE REQUIERE CONSENTIMIENTO — ES EMERGENCIA",
        ]

        if evaluacion.clasificacion == DificultadViaAerea.DIFICULTAD_ESPERADA:
            plan.extend([
                "",
                "🚨 DIFICULTAD ESPERADA — Considerar:",
                "   • Intubación despierto con fibrobroncoscopio",
                "   • Vía aérea frontal (cricotiroidotomía electiva)",
                "   • NO usar bloqueante neuromuscular hasta asegurar vía aérea",
                "   • Equipo de vía aérea quirúrgica en la mesa",
            ])

        return plan

    # ═══════════════════════════════════════════════════════════════
    # PASO 5: Manejo post-intubación
    # ═══════════════════════════════════════════════════════════════
    def manejo_post_intubacion(self, paciente: Paciente) -> List[str]:
        """
        Genera el plan de manejo post-intubación.
        
        Incluye:
        - Confirmación de posición
        - Ventilación mecánica inicial
        - Sedación y analgesia
        - Monitoreo
        - Reversión farmacológica si es necesario
        
        Args:
            paciente: Objeto Paciente.
            
        Returns:
            Lista de pasos post-intubación.
        """
        pasos = [
            "",
            "═══════════════════════════════════════════════════",
            "  MANEJO POST-INTUBACIÓN",
            "═══════════════════════════════════════════════════",
            "",
            "✅ 1. CONFIRMACIÓN INMEDIATA",
            "   • Capnografía (ETCO2) — curva cuadrada sostenida",
            "   • Auscultación: Ruidos bilaterales, ausencia en epigastrio",
            "   • Expansión torácica simétrica",
            "   • Rx de tórax: Confirmar posición, descartar neumotórax",
            "",
            "🫁 2. VENTILACIÓN MECÁNICA INICIAL",
            "   • Modo: Volumen control (VCV) o presión control (PCV)",
            "   • Vt: 6-8 mL/kg peso ideal",
            "   • PEEP: 5-8 cmH2O",
            "   • FR: 14-16 rpm",
            "   • FiO2: 100% → titular al menor nivel con SpO2 ≥94%",
            "   • Meta: PaO2 60-100 mmHg, PaCO2 35-45 mmHg",
            "",
            "💊 3. SEDACIÓN Y ANALGESIA",
            "   • Analgesia: Fentanyl 25-100 µg IV bolus → infusión 1-5 µg/kg/h",
            "   • Sedación: Propofol 5-80 µg/kg/min o Midazolam 0.02-0.1 mg/kg/h",
            "   • Meta: RASS -2 a 0 (ligera sedación a alerta)",
            "",
            "📊 4. MONITOREO CONTINUO",
            "   • ETCO2 continuo (meta: 35-45 mmHg)",
            "   • SpO2, FC, PA invasiva si es posible",
            "   • Diuresis horaria",
            "   • Rx de tórax a las 4-6 horas",
        ]

        return pasos

    # ═══════════════════════════════════════════════════════════════
    # PASO 6: Cálculo de dosis
    # ═══════════════════════════════════════════════════════════════
    def calcular_dosis(self, paciente: Paciente, agente: AgenteInduccion,
                       bloqueante: BloqueanteNeuromuscular) -> dict:
        """
        Calcula las dosis para el paciente según peso.
        
        Args:
            paciente: Objeto Paciente.
            agente: Agente de inducción seleccionado.
            bloqueante: Bloqueante neuromuscular seleccionado.
            
        Returns:
            Diccionario con dosis calculadas.
        """
        peso = paciente.peso
        dosis = {}

        # Agente de inducción
        if agente == AgenteInduccion.ETOMIDATO:
            dosis["etomidato"] = {
                "mg_total": round(peso * 0.3, 1),
                "concentracion": "2 mg/mL",
                "volumen_mL": round(peso * 0.3 / 2, 1),
            }
        elif agente == AgenteInduccion.KETAMINA:
            dosis["ketamina"] = {
                "mg_total": round(peso * 1.5, 1),
                "concentracion": "50 mg/mL",
                "volumen_mL": round(peso * 1.5 / 50, 1),
            }
        elif agente == AgenteInduccion.PROPOFOL:
            dosis["propofol"] = {
                "mg_total": round(peso * 2.0, 1),
                "concentracion": "10 mg/mL",
                "volumen_mL": round(peso * 2.0 / 10, 1),
            }
        elif agente == AgenteInduccion.MIDAZOLAM:
            dosis["midazolam"] = {
                "mg_total": round(peso * 0.2, 1),
                "concentracion": "5 mg/mL",
                "volumen_mL": round(peso * 0.2 / 5, 1),
            }

        # Bloqueante neuromuscular
        if bloqueante == BloqueanteNeuromuscular.SUCCINILCOLINA:
            dosis["succinilcolina"] = {
                "mg_total": round(peso * 1.5, 1),
                "concentracion": "20 mg/mL",
                "volumen_mL": round(peso * 1.5 / 20, 1),
            }
        elif bloqueante == BloqueanteNeuromuscular.ROCURONIO:
            dosis["rocuronio"] = {
                "mg_total": round(peso * 1.2, 1),
                "concentracion": "10 mg/mL",
                "volumen_mL": round(peso * 1.2 / 10, 1),
            }
            # Sugammadex para reversión
            dosis["sugammadex_rescate"] = {
                "mg_total": round(peso * self.UMBRALES["dosis_sugammadex"], 1),
                "concentracion": "100 mg/mL",
                "volumen_mL": round(peso * self.UMBRALES["dosis_sugammadex"] / 100, 1),
                "nota": "Dosis de rescate: 16 mg/kg (reversión completa inmediata)",
            }

        # Fentanyl pretratamiento
        dosis["fentanyl_pretratamiento"] = {
            "mg_total": round(peso * 0.002, 3),
            "mcg_total": round(peso * 2, 0),
            "concentracion": "50 µg/mL",
            "volumen_mL": round(peso * 2 / 50, 1),
        }

        # Lidocaína (si HIC)
        dosis["lidocaina_pretratamiento"] = {
            "mg_total": round(peso * 1.5, 1),
            "concentracion": "20 mg/mL",
            "volumen_mL": round(peso * 1.5 / 20, 1),
            "nota": "Solo si hipertensión intracraneana o presión intracraneal elevada",
        }

        return dosis

    # ═══════════════════════════════════════════════════════════════
    # Ejecución completa del algoritmo
    # ═══════════════════════════════════════════════════════════════
    def ejecutar(self, paciente: Paciente) -> ResultadoRSI:
        """
        Ejecuta el algoritmo completo de RSI.
        
        Flujo:
            1. Evaluación de vía aérea
            2. Selección de agentes farmacológicos
            3. Preparación (7 P's)
            4. Cálculo de dosis
            5. Planes de rescate DAS
            6. Manejo post-intubación
            
        Args:
            paciente: Paciente a evaluar.
            
        Returns:
            ResultadoRSI completo.
        """
        # 1. Evaluación de vía aérea
        evaluacion = self.evaluar_via_aerea(paciente)

        # 2. Selección de agentes
        agente = self.seleccionar_agente_induccion(paciente)
        bloqueante = self.seleccionar_bloqueante(paciente)

        # 3. Preparación
        pasos_preparacion = self.preparar_7_ps(paciente)

        # 4. Ejecución
        pasos_ejecucion = [
            "",
            "═══════════════════════════════════════════════════",
            "  EJECUCIÓN DE RSI",
            "═══════════════════════════════════════════════════",
            "",
            f"⏱️  T = -3 min: Pretratamiento",
            f"   → Fentanyl {paciente.peso * 2:.0f} µg IV",
            "",
            f"⏱️  T = 0: Inducción + Parálisis",
            f"   → {agente.value} IV",
            f"   → {bloqueante.value} IV (INMEDIATAMENTE después)",
            "",
            f"⏱️  T = +45-60 seg: Intubación",
            f"   → Laringoscopia directa",
            f"   → Visualización de cuerdas vocales",
            f"   → Inserción de tubo endotraqueal",
            f"   → Inflar manguito, conectar ventilación",
            "",
            f"⏱️  T = +2 min: Confirmación",
            f"   → Capnografía (ETCO2)",
            f"   → Auscultación bilateral",
            f"   → Fijar tubo, registrar profundidad",
        ]

        # 5. Plan de rescate
        plan_rescate = self.generar_plan_rescate(evaluacion)

        # 6. Post-intubación
        manejo_post = self.manejo_post_intubacion(paciente)

        # 7. Cálculo de dosis
        dosis = self.calcular_dosis(paciente, agente, bloqueante)

        # 8. Alertas
        alertas = []
        if evaluacion.clasificacion == DificultadViaAerea.DIFICULTAD_ESPERADA:
            alertas.append("🚨 DIFICULTAD ESPERADA — Considerar intubación despierto")
        elif evaluacion.clasificacion == DificultadViaAerea.DIFICULTAD_POSIBLE:
            alertas.append("⚠️  Posible dificultad — Preparar plan de rescate")
        if paciente.alergias:
            alertas.append(f"⚠️  ALERGIAS: {', '.join(paciente.alergias)}")
        if bloqueante == BloqueanteNeuromuscular.ROCURONIO:
            alertas.append("ℹ️  Rocuronio seleccionado — Sugammadex disponible para reversión")
        if bloqueante == BloqueanteNeuromuscular.SUCCINILCOLINA:
            alertas.append("ℹ️  Succinilcolina — Contraindicada en hiperpotasemia, quemaduras >24h, denervación")

        # Registrar
        paciente.registrar_intervencion(
            nombre="Algoritmo RSI",
            detalle=f"Inducción: {agente.value} | BNM: {bloqueante.value} | Dificultad: {evaluacion.clasificacion.value}"
        )

        return ResultadoRSI(
            evaluacion_via_aerea=evaluacion,
            agente_induccion=agente,
            bloqueante=bloqueante,
            pasos_preparacion=pasos_preparacion,
            pasos_ejecucion=pasos_ejecucion,
            plan_rescate=plan_rescate,
            manejo_post_intubacion=manejo_post,
            alertas=alertas,
            dosis_calculadas=dosis
        )