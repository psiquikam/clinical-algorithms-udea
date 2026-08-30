"""
Modelo de paciente para simulación clínica.
Representa el estado fisiológico y las intervenciones realizadas.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class NivelConciencia(Enum):
    """Escala simplificada de nivel de conciencia."""
    ALERTA = "Alerta"
    VOZ = "Responde a la voz"
    DOLOR = "Responde al dolor"
    INCONSCIENTE = "Inconsciente"
    NO_EVALUABLE = "No evaluable"


class ViaAerea(Enum):
    """Estado de la vía aérea."""
    PATENTE = "Patente"
    OBSTRUIDA_PARCIAL = "Obstruida parcial"
    OBSTRUIDA_TOTAL = "Obstruida total"
    PROTEGIDA = "Protegida (tubo endotraqueal)"


@dataclass
class SignosVitales:
    """Signos vitales del paciente."""
    frecuencia_cardiaca: Optional[int] = None       # lpm
    presion_arterial_sistolica: Optional[int] = None # mmHg
    presion_arterial_diastolica: Optional[int] = None
    presion_arterial_media: Optional[int] = None     # mmHg
    frecuencia_respiratoria: Optional[int] = None    # rpm
    saturacion_oxigeno: Optional[float] = None       # %
    temperatura: Optional[float] = None              # °C
    glucemia: Optional[int] = None                   # mg/dL

    def calcular_pam(self) -> Optional[float]:
        """Calcula la Presión Arterial Media."""
        if self.presion_arterial_sistolica and self.presion_arterial_diastolica:
            self.presion_arterial_media = (
                self.presion_arterial_diastola
                + (self.presion_arterial_sistolica - self.presion_arterial_diastolica) / 3
            )
        return self.presion_arterial_media


@dataclass
class Laboratorio:
    """Valores de laboratorio relevantes."""
    lactato: Optional[float] = None                  # mmol/L
    leucocitos: Optional[float] = None               # x10³/µL
    creatinina: Optional[float] = None               # mg/dL
    bilirrubina: Optional[float] = None              # mg/dL
    plaquetas: Optional[float] = None                # x10³/µL
    pafi: Optional[float] = None                     # PaO2/FiO2
    procalcitonina: Optional[float] = None           # ng/mL


@dataclass
class Paciente:
    """
    Modelo completo de paciente para simulación clínica.
    
    Attributes:
        nombre: Nombre del paciente simulado
        edad: Edad en años
        peso: Peso en kilogramos
        alergias: Lista de alergias conocidas
        antecedentes: Antecedentes patológicos relevantes
        signos_vitales: Objeto SignosVitales
        laboratorio: Objeto Laboratorio
        nivel_conciencia: Nivel de conciencia actual
        via_aerea: Estado de la vía aérea
        foco_infeccioso: Foco infeccioso sospechado (si aplica)
        tiempo_hospital: Horas desde el ingreso
        intervenciones: Lista de intervenciones realizadas con timestamp
    """
    nombre: str
    edad: int
    peso: float
    alergias: List[str] = field(default_factory=list)
    antecedentes: List[str] = field(default_factory=list)
    signos_vitales: SignosVitales = field(default_factory=SignosVitales)
    laboratorio: Laboratorio = field(default_factory=Laboratorio)
    nivel_conciencia: NivelConciencia = NivelConciencia.ALERTA
    via_aerea: ViaAerea = ViaAerea.PATENTE
    foco_infeccioso: Optional[str] = None
    tiempo_hospital: float = 0.0
    intervenciones: List[dict] = field(default_factory=list)

    def registrar_intervencion(self, nombre: str, detalle: str = ""):
        """Registra una intervención con timestamp."""
        self.intervenciones.append({
            "timestamp": datetime.now().isoformat(),
            "nombre": nombre,
            "detalle": detalle
        })

    def resumen(self) -> str:
        """Genera un resumen clínico del paciente."""
        sv = self.signos_vitales
        lab = self.laboratorio
        lineas = [
            f"═══════════════════════════════════════════",
            f"  PACIENTE: {self.nombre} | {self.edad} años | {self.peso} kg",
            f"═══════════════════════════════════════════",
            f"  Nivel de conciencia : {self.nivel_conciencia.value}",
            f"  Vía aérea           : {self.via_aerea.value}",
            f"  FC                  : {sv.frecuencia_cardiaca} lpm",
            f"  PA                  : {sv.presion_arterial_sistolica}/{sv.presion_arterial_diastolica} mmHg",
            f"  PAM                 : {sv.presion_arterial_media} mmHg",
            f"  FR                  : {sv.frecuencia_respiratoria} rpm",
            f"  SpO2                : {sv.saturacion_oxigeno}%",
            f"  Temp                : {sv.temperatura} °C",
            f"  Glucemia            : {sv.glucemia} mg/dL",
            f"  ─── Laboratorio ───",
            f"  Lactato             : {lab.lactato} mmol/L",
            f"  Leucocitos          : {lab.leucocitos} x10³/µL",
            f"  Creatinina          : {lab.creatinina} mg/dL",
            f"  Bilirrubina         : {lab.bilirrubina} mg/dL",
            f"  Plaquetas           : {lab.plaquetas} x10³/µL",
            f"  PaFi                : {lab.pafi}",
            f"  Foco infeccioso     : {self.foco_infeccioso or 'No identificado'}",
            f"  Alergias            : {', '.join(self.alergias) or 'Ninguna'}",
            f"  Antecedentes        : {', '.join(self.antecedentes) or 'Ninguno'}",
            f"═══════════════════════════════════════════",
        ]
        return "\n".join(lineas)