"""
Algoritmo clínico: Manejo del Choque Séptico
Basado en: Surviving Sepsis Campaign 2021 (SSC)

Este módulo implementa el algoritmo de manejo del choque séptico
como un árbol de decisiones formal, con validación de criterios,
cálculo de scores y recomendaciones terapéuticas escalonadas.

Referencias:
    - Evans L, et al. Surviving Sepsis Campaign: International Guidelines
      for Management of Sepsis and Septic Shock 2021. Intensive Care Med. 2021.
    - Singer M, et al. The Third International Consensus Definitions for
      Sepsis and Septic Shock (Sepsis-3). JAMA. 2016.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum

from models.patient import Paciente, NivelConciencia


class FaseSepsis(Enum):
    """Clasificación de severidad según Sepsis-3."""
    SEPSIS = "Sepsis"
    CHOQUE_SEPTICO = "Choque séptico"
    NO_SEPSIS = "No cumple criterios"


class TipoFluidos(Enum):
    """Tipos de fluidos cristaloides."""
    SS09 = "Solución salina 0.9%"
    RINGER_LACTATO = "Ringer lactato"
    PLASMALYTE = "Plasmalyte"


class Vasopresor(Enum):
    """Vasopresores disponibles."""
    NOREPINEFRINA = "Norepinefrina"
    VASOPRESINA = "Vasopresina"
    EPINEFRINA = "Epinefrina"
    FENILEFRINA = "Fenilefrina"


@dataclass
class ResultadoEvaluacion:
    """Resultado de una evaluación clínica."""
    criterio: str
    cumple: bool
    valor: Optional[float] = None
    umbral: Optional[float] = None
    detalle: str = ""


@dataclass
class PlanTerapeutico:
    """Plan terapéutico generado por el algoritmo."""
    fase: FaseSepsis
    evaluaciones: List[ResultadoEvaluacion]
    acciones: List[str]
    metas: List[str]
    alertas: List[str]
    tiempo_limite: str  # Ventana de tiempo crítica


class AlgoritmoChoqueSeptico:
    """
    Algoritmo de manejo del choque séptico.
    
    Implementa el bundle de 1 hora y 3 horas de la SSC 2021,
    con evaluación secuencial de criterios diagnósticos,
    estratificación de riesgo y plan terapéutico escalonado.
    """

    # ─── Umbrales clínicos según SSC 2021 ───────────────────────
    UMBRALES = {
        "qsofa_alteracion_conciencia": 1,      # Punto qSOFA
        "qsofa_pas": 100,                       # mmHg
        "qsofa_fr": 22,                         # rpm
        "sirs_fc": 90,                          # lpm
        "sirs_fr": 20,                          # rpm
        "sirs_temp_baja": 36.0,                 # °C
        "sirs_temp_alta": 38.0,                 # °C
        "sirs_leucocitos_bajo": 4.0,            # x10³/µL
        "sirs_leucocitos_alto": 12.0,           # x10³/µL
        "pam_umbral": 65,                       # mmHg
        "lactato_elevado": 2.0,                 # mmol/L
        "lactato_criticamente_elevado": 4.0,    # mmol/L
        "volumen_cristaloide": 30,              # mL/kg
        "creatinina_injury": 2.0,               # mg/dL
        "bilirrubina_injury": 2.0,              # mg/dL
        "plaquetas_injury": 100,                # x10³/µL
        "pafi_injury": 300,                     # PaO2/FiO2
    }

    def __init__(self):
        self.historial_evaluaciones: List[ResultadoEvaluacion] = []

    # ═══════════════════════════════════════════════════════════════
    # PASO 1: Tamizaje — Criterios SIRS
    # ═══════════════════════════════════════════════════════════════
    def evaluar_sirs(self, paciente: Paciente) -> Tuple[List[ResultadoEvaluacion], int]:
        """
        Evalúa los criterios SIRS (Systemic Inflammatory Response Syndrome).
        Se requieren ≥2 de 4 criterios para sospecha de sepsis.
        
        Args:
            paciente: Objeto Paciente con signos vitales y laboratorio.
            
        Returns:
            Tupla con (lista de evaluaciones, número de criterios cumplidos).
        """
        u = self.UMBRALES
        sv = paciente.signos_vitales
        lab = paciente.laboratorio
        evaluaciones = []

        # Criterio 1: Frecuencia cardíaca
        evaluaciones.append(ResultadoEvaluacion(
            criterio="SIRS - Taquicardia",
            cumple=sv.frecuencia_cardiaca is not None and sv.frecuencia_cardiaca > u["sirs_fc"],
            valor=sv.frecuencia_cardiaca,
            umbral=u["sirs_fc"],
            detalle=f"FC > {u['sirs_fc']} lpm"
        ))

        # Criterio 2: Frecuencia respiratoria
        evaluaciones.append(ResultadoEvaluacion(
            criterio="SIRS - Taquipnea",
            cumple=sv.frecuencia_respiratoria is not None and sv.frecuencia_respiratoria > u["sirs_fr"],
            valor=sv.frecuencia_respiratoria,
            umbral=u["sirs_fr"],
            detalle=f"FR > {u['sirs_fr']} rpm"
        ))

        # Criterio 3: Temperatura
        temp_alterada = (
            sv.temperatura is not None and
            (sv.temperatura > u["sirs_temp_alta"] or sv.temperatura < u["sirs_temp_baja"])
        )
        evaluaciones.append(ResultadoEvaluacion(
            criterio="SIRS - Temperatura alterada",
            cumple=temp_alterada,
            valor=sv.temperatura,
            umbral=u["sirs_temp_alta"],
            detalle=f"Temp > {u['sirs_temp_alta']}°C o < {u['sirs_temp_baja']}°C"
        ))

        # Criterio 4: Leucocitos
        leuc_alterados = (
            lab.leucocitos is not None and
            (lab.leucocitos > u["sirs_leucocitos_alto"] or lab.leucocitos < u["sirs_leucocitos_bajo"])
        )
        evaluaciones.append(ResultadoEvaluacion(
            criterio="SIRS - Leucocitos alterados",
            cumple=leuc_alterados,
            valor=lab.leucocitos,
            umbral=u["sirs_leucocitos_alto"],
            detalle=f"Leuc > {u['sirs_leucocitos_alto']} o < {u['sirs_leucocitos_bajo']} x10³/µL"
        ))

        cumplidos = sum(1 for e in evaluaciones if e.cumple)
        self.historial_evaluaciones.extend(evaluaciones)
        return evaluaciones, cumplidos

    # ═══════════════════════════════════════════════════════════════
    # PASO 2: qSOFA — Score rápido de disfunción orgánica
    # ═══════════════════════════════════════════════════════════════
    def evaluar_qsofa(self, paciente: Paciente) -> Tuple[List[ResultadoEvaluacion], int]:
        """
        Evalúa el quickSOFA (qSOFA).
        Score ≥2 sugiere disfunción orgánica y mayor mortalidad.
        
        Args:
            paciente: Objeto Paciente.
            
        Returns:
            Tupla con (lista de evaluaciones, score qSOFA).
        """
        u = self.UMBRALES
        sv = paciente.signos_vitales
        evaluaciones = []

        # Criterio 1: Alteración del nivel de conciencia
        alteracion_conciencia = paciente.nivel_conciencia in (
            NivelConciencia.VOZ,
            NivelConciencia.DOLOR,
            NivelConciencia.INCONSCIENTE
        )
        evaluaciones.append(ResultadoEvaluacion(
            criterio="qSOFA - Alteración conciencia",
            cumple=alteracion_conciencia,
            valor=1 if alteracion_conciencia else 0,
            umbral=1,
            detalle="GCS < 15 o equivalente"
        ))

        # Criterio 2: Hipotensión
        evaluaciones.append(ResultadoEvaluacion(
            criterio="qSOFA - Hipotensión (PAS ≤100)",
            cumple=sv.presion_arterial_sistolica is not None and sv.presion_arterial_sistolica <= u["qsofa_pas"],
            valor=sv.presion_arterial_sistolica,
            umbral=u["qsofa_pas"],
            detalle=f"PAS ≤ {u['qsofa_pas']} mmHg"
        ))

        # Criterio 3: Taquipnea
        evaluaciones.append(ResultadoEvaluacion(
            criterio="qSOFA - Taquipnea (FR ≥22)",
            cumple=sv.frecuencia_respiratoria is not None and sv.frecuencia_respiratoria >= u["qsofa_fr"],
            valor=sv.frecuencia_respiratoria,
            umbral=u["qsofa_fr"],
            detalle=f"FR ≥ {u['qsofa_fr']} rpm"
        ))

        score = sum(1 for e in evaluaciones if e.cumple)
        self.historial_evaluaciones.extend(evaluaciones)
        return evaluaciones, score

    # ═══════════════════════════════════════════════════════════════
    # PASO 3: SOFA — Disfunción orgánica
    # ═══════════════════════════════════════════════════════════════
    def evaluar_sofa_simplificado(self, paciente: Paciente) -> Tuple[List[ResultadoEvaluacion], int]:
        """
        Evaluación simplificada de SOFA (Sequential Organ Failure Assessment).
        Un incremento ≥2 puntos respecto al basal define sepsis (Sepsis-3).
        
        Se asume basal = 0 (paciente previamente sano).
        
        Args:
            paciente: Objeto Paciente.
            
        Returns:
            Tupla con (lista de evaluaciones, score SOFA).
        """
        u = self.UMBRALES
        sv = paciente.signos_vitales
        lab = paciente.laboratorio
        evaluaciones = []
        score_total = 0

        # ── Respiratorio: PaFi ──
        if lab.pafi is not None:
            if lab.pafi < 100:
                pafi_score = 4
            elif lab.pafi < 200:
                pafi_score = 3
            elif lab.pafi < 300:
                pafi_score = 2
            elif lab.pafi < 400:
                pafi_score = 1
            else:
                pafi_score = 0
            evaluaciones.append(ResultadoEvaluacion(
                criterio="SOFA - Respiratorio (PaFi)",
                cumple=pafi_score >= 2,
                valor=lab.pafi,
                umbral=u["pafi_injury"],
                detalle=f"PaFi = {lab.pafi} → SOFA respiratorio = {pafi_score}"
            ))
            score_total += pafi_score

        # ── Coagulación: Plaquetas ──
        if lab.plaquetas is not None:
            if lab.plaquetas < 20:
                plat_score = 4
            elif lab.plaquetas < 50:
                plat_score = 3
            elif lab.plaquetas < 100:
                plat_score = 2
            elif lab.plaquetas < 150:
                plat_score = 1
            else:
                plat_score = 0
            evaluaciones.append(ResultadoEvaluacion(
                criterio="SOFA - Coagulación (Plaquetas)",
                cumple=plat_score >= 2,
                valor=lab.plaquetas,
                umbral=u["plaquetas_injury"],
                detalle=f"Plaquetas = {lab.plaquetas} → SOFA coagulación = {plat_score}"
            ))
            score_total += plat_score

        # ── Hepático: Bilirrubina ──
        if lab.bilirrubina is not None:
            if lab.bilirrubina >= 12.0:
                bil_score = 4
            elif lab.bilirrubina >= 6.0:
                bil_score = 3
            elif lab.bilirrubina >= 2.0:
                bil_score = 2
            elif lab.bilirrubina >= 1.2:
                bil_score = 1
            else:
                bil_score = 0
            evaluaciones.append(ResultadoEvaluacion(
                criterio="SOFA - Hepático (Bilirrubina)",
                cumple=bil_score >= 2,
                valor=lab.bilirrubina,
                umbral=u["bilirrubina_injury"],
                detalle=f"Bilirrubina = {lab.bilirrubina} → SOFA hepático = {bil_score}"
            ))
            score_total += bil_score

        # ── Cardiovascular: PAM y vasopresores ──
        if sv.presion_arterial_media is not None:
            if sv.presion_arterial_media < 70:
                cv_score = 1
            else:
                cv_score = 0
            evaluaciones.append(ResultadoEvaluacion(
                criterio="SOFA - Cardiovascular (PAM)",
                cumple=cv_score >= 1,
                valor=sv.presion_arterial_media,
                umbral=u["pam_umbral"],
                detalle=f"PAM = {sv.presion_arterial_media} → SOFA cardiovascular = {cv_score}"
            ))
            score_total += cv_score

        # ── Renal: Creatinina ──
        if lab.creatinina is not None:
            if lab.creatinina >= 5.0:
                ren_score = 4
            elif lab.creatinina >= 3.5:
                ren_score = 3
            elif lab.creatinina >= 2.0:
                ren_score = 2
            elif lab.creatinina >= 1.2:
                ren_score = 1
            else:
                ren_score = 0
            evaluaciones.append(ResultadoEvaluacion(
                criterio="SOFA - Renal (Creatinina)",
                cumple=ren_score >= 2,
                valor=lab.creatinina,
                umbral=u["creatinina_injury"],
                detalle=f"Creatinina = {lab.creatinina} → SOFA renal = {ren_score}"
            ))
            score_total += ren_score

        # ── Neurológico: Nivel de conciencia (simplificado) ──
        if paciente.nivel_conciencia == NivelConciencia.INCONSCIENTE:
            neuro_score = 4
        elif paciente.nivel_conciencia == NivelConciencia.DOLOR:
            neuro_score = 3
        elif paciente.nivel_conciencia == NivelConciencia.VOZ:
            neuro_score = 2
        else:
            neuro_score = 0
        evaluaciones.append(ResultadoEvaluacion(
            criterio="SOFA - Neurológico (Conciencia)",
            cumple=neuro_score >= 2,
            valor=neuro_score,
            umbral=2,
            detalle=f"Nivel conciencia = {paciente.nivel_conciencia.value} → SOFA neurológico = {neuro_score}"
        ))
        score_total += neuro_score

        self.historial_evaluaciones.extend(evaluaciones)
        return evaluaciones, score_total

    # ═══════════════════════════════════════════════════════════════
    # PASO 4: Clasificación — Sepsis vs Choque Séptico
    # ═══════════════════════════════════════════════════════════════
    def clasificar_sepsis(self, paciente: Paciente, sofa_score: int) -> FaseSepsis:
        """
        Clasifica la fase de sepsis según Sepsis-3:
        
        - Sepsis: Infección + SOFA ≥2
        - Choque séptico: Sepsis + necesidad de vasopresores para PAM ≥65
          Y lactato >2 mmol/L a pesar de resucitación con fluidos.
        
        Args:
            paciente: Objeto Paciente.
            sofa_score: Score SOFA calculado.
            
        Returns:
            FaseSepsis: Clasificación de severidad.
        """
        sv = paciente.signos_vitales
        lab = paciente.laboratorio

        if sofa_score < 2:
            return FaseSepsis.NO_SEPSIS

        # ¿Requiere vasopresores o PAM <65?
        requiere_vasopresores = (
            sv.presion_arterial_media is not None and
            sv.presion_arterial_media < self.UMBRALES["pam_umbral"]
        )

        # ¿Lactato elevado?
        lactato_elevado = (
            lab.lactato is not None and
            lab.lactato > self.UMBRALES["lactato_elevado"]
        )

        if requiere_vasopresores and lactato_elevado:
            return FaseSepsis.CHOQUE_SEPTICO
        else:
            return FaseSepsis.SEPSIS

    # ═══════════════════════════════════════════════════════════════
    # PASO 5: Plan terapéutico — Bundle SSC 2021
    # ═══════════════════════════════════════════════════════════════
    def generar_plan_terapeutico(self, paciente: Paciente) -> PlanTerapeutico:
        """
        Genera el plan terapéutico completo según la fase de sepsis.
        
        Implementa los bundles de la SSC 2021:
        - Bundle de 1 hora: Medidas inmediatas
        - Bundle de 3 horas: Resucitación y reevaluación
        
        Args:
            paciente: Objeto Paciente con todos los datos.
            
        Returns:
            PlanTerapeutico con acciones, metas y alertas.
        """
        # Evaluaciones
        eval_sirs, sirs_count = self.evaluar_sirs(paciente)
        eval_qsofa, qsofa_score = self.evaluar_qsofa(paciente)
        eval_sofa, sofa_score = self.evaluar_sofa_simplificado(paciente)

        todas_evaluaciones = eval_sirs + eval_qsofa + eval_sofa

        # Clasificación
        fase = self.clasificar_sepsis(paciente, sofa_score)

        # ── Acciones según fase ──
        acciones = []
        metas = []
        alertas = []

        # Acciones comunes para sepsis y choque séptico
        if fase in (FaseSepsis.SEPSIS, FaseSepsis.CHOQUE_SEPTICO):

            # ── BUNDLE 1 HORA ──
            acciones.extend([
                "⏱️  BUNDLE 1 HORA — Iniciar INMEDIATAMENTE:",
                f"   1. Medir lactato sérico (actual: {paciente.laboratorio.lactato or 'NO MEDIDO'} mmol/L)",
                f"   2. Obtener hemocultivos ANTES de antibióticos",
                f"   3. Administrar antibióticos de amplio espectro IV",
                f"   4. Iniciar resucitación con cristaloides: {self.UMBRALES['volumen_cristaloide']} mL/kg "
                f"= {int(self.UMBRALES['volumen_cristaloide'] * paciente.peso)} mL para este paciente",
            ])

            metas.extend([
                "Antibióticos en <1 hora desde el reconocimiento",
                "Hemocultivos antes de antibióticos (2 sets)",
                "Lactato medido en <1 hora",
            ])

            # ── Antibióticos empíricos según foco ──
            foco = paciente.foco_infeccioso or "No identificado"
            acciones.append(f"   5. Antibiótico empírico según foco: {foco}")
            if foco and foco.lower() in ("abdominal", "peritonitis"):
                acciones.append("      → Meropenem 1g IV + Metronidazol 500mg IV")
            elif foco and foco.lower() in ("neumonía", "respiratorio"):
                acciones.append("      → Piperacilina/Tazobactam 4.5g IV o Cefepime 2g IV + Azitromicina")
            elif foco and foco.lower() in ("urinario", "ITU"):
                acciones.append("      → Ceftriaxona 2g IV o Piperacilina/Tazobactam 4.5g IV")
            else:
                acciones.append("      → Piperacilina/Tazobactam 4.5g IV (cobertura amplia)")

            # ── Tipo de cristaloide ──
            acciones.append(
                f"   6. Cristaloide de elección: Ringer lactato "
                f"(preferido sobre SS 0.9% por menor riesgo de AKI)"
            )

            # ── BUNDLE 3 HORAS ──
            acciones.extend([
                "",
                "⏱️  BUNDLE 3 HORAS — Reevaluación:",
                f"   7. Re-medir lactato si inicial > {self.UMBRALES['lactato_elevado']} mmol/L",
                f"   8. Administrar volumen adicional si PAM < {self.UMBRALES['pam_umbral']} mmHg",
                f"   9. Reevaluar volumen si lactato no disminuye",
            ])

        # ── Acciones específicas para CHOQUE SÉPTICO ──
        if fase == FaseSepsis.CHOQUE_SEPTICO:

            acciones.extend([
                "",
                "🚨 CHOQUE SÉPTICO — Medidas adicionales:",
                f"   10. INICIAR VASOPRESORES si PAM < {self.UMBRALES['pam_umbral']} mmHg "
                f"después de {self.UMBRALES['volumen_cristaloide']} mL/kg cristaloides:",
                "       → Primera línea: Norepinefrina 0.1-0.5 µg/kg/min",
                f"       → Meta: PAM ≥ {self.UMBRALES['pam_umbral']} mmHg",
                "",
                "   11. Si Norepinefrina > 0.5 µg/kg/min:",
                "       → Agregar Vasopresina 0.03 U/min (dosis fija)",
                "",
                "   12. Si requiere > 0.5 µg/kg/min de NE + Vasopresina:",
                "       → Agregar Epinefrina como tercer agente",
                "",
                f"   13. Lactato > {self.UMBRALES['lactato_criticamente_elevado']} mmol/L → "
                f"Resucitación dirigida por lactato:",
                f"       → Repetir bolos de cristaloides hasta normalizar lactato < {self.UMBRALES['lactato_elevado']}",
                "",
                "   14. Control del foco infeccioso:",
                "       → Drenaje de abscesos, remoción de dispositivos, etc.",
                "       → Dentro de las primeras 6-12 horas",
            ])

            metas.extend([
                f"PAM ≥ {self.UMBRALES['pam_umbral']} mmHg",
                f"Lactato < {self.UMBRALES['lactato_elevado']} mmol/L",
                "Diuresis ≥ 0.5 mL/kg/h",
                "ScvO2 ≥ 70% (si catéter venoso central disponible)",
            ])

            alertas.extend([
                f"⚠️  PACIENTE EN CHOQUE SÉPTICO — Mortalidad >40%",
                "⚠️  Cada hora de retraso en antibióticos aumenta mortalidad 7.6%",
                "⚠️  Lactato >4 mmol/L → Resucitación agresiva inmediata",
                "⚠️  Evaluar control de foco en <6 horas",
            ])

            # Alerta por alergias
            if paciente.alergias:
                alertas.append(
                    f"⚠️  ALERGIAS: {', '.join(paciente.alergias)} — "
                    f"Verificar antes de administrar antibióticos"
                )

        elif fase == FaseSepsis.SEPSIS:
            alertas.extend([
                "⚡ Sepsis sin choque — Vigilar deterioro hemodinámico",
                "⚡ Reevaluar cada 2-4 horas",
                "⚡ Si PAM <65 o lactato >2 → Escalar a choque séptico",
            ])

        else:
            acciones.append("✅ No cumple criterios de sepsis. Reevaluar si hay cambios clínicos.")
            alertas.append("ℹ️  Considerar diagnósticos alternativos")

        # Determinar tiempo límite
        if fase == FaseSepsis.CHOQUE_SEPTICO:
            tiempo_limite = "1 hora (bundle inmediato)"
        elif fase == FaseSepsis.SEPSIS:
            tiempo_limite = "3 horas (bundle de resucitación)"
        else:
            tiempo_limite = "No aplica"

        # Registrar evaluación en el paciente
        paciente.registrar_intervencion(
            nombre="Algoritmo Choque Séptico",
            detalle=f"Fase: {fase.value} | SOFA: {sofa_score} | qSOFA: {qsofa_score} | SIRS: {sirs_count}"
        )

        return PlanTerapeutico(
            fase=fase,
            evaluaciones=todas_evaluaciones,
            acciones=acciones,
            metas=metas,
            alertas=alertas,
            tiempo_limite=tiempo_limite
        )

    # ═══════════════════════════════════════════════════════════════
    # Ejecución completa del algoritmo
    # ═══════════════════════════════════════════════════════════════
    def ejecutar(self, paciente: Paciente) -> PlanTerapeutico:
        """
        Ejecuta el algoritmo completo de choque séptico.
        
        Flujo:
            1. Tamizaje (SIRS)
            2. Estratificación (qSOFA)
            3. Disfunción orgánica (SOFA)
            4. Clasificación
            5. Plan terapéutico
            
        Args:
            paciente: Paciente a evaluar.
            
        Returns:
            PlanTerapeutico completo.
        """
        return self.generar_plan_terapeutico(paciente)