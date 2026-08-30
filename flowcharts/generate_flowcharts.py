"""Generación de diagramas de flujo para los algoritmos clínicos.
Produce diagramas en formato Mermaid, compatibles con GitHub.
"""
from pathlib import Path

MERMAID_SEPTIC_SHOCK = r'''```mermaid
flowchart TD
    START([🩺 Paciente con sospecha de infección]) --> SIRS
    subgraph SIRS["PASO 1: Tamizaje SIRS"]
        S1{FC > 90 lpm?}
        S2{FR > 20 rpm?}
        S3{Temp >38°C o <36°C?}
        S4{Leuc >12 o <4 x10³/µL?}
    end
    SIRS --> QS[qSOFA]
    QS --> SOFA[SOFA simplificado]
    SOFA --> CLASS[Clasificación]
    CLASS --> SHOCK[🚨 Choque séptico]
    CLASS --> SEPSIS[⚡ Sepsis]
    SHOCK --> B1[Bacteriología / lactato / antibiótico / cristaloide]
    SEPSIS --> B1
    B1 --> VASO{PAM <65 tras fluidos?}
    VASO -->|Sí| NE[Norepinefrina]
    VASO -->|No| REEVAL[Reevaluación continua]
    NE --> ESC{Respuesta insuficiente?}
    ESC -->|Sí| VP[+ Vasopresina / escalamiento]
    ESC -->|No| REEVAL
    VP --> REEVAL
    REEVAL --> END([Fin / nueva evaluación])
```
'''

MERMAID_RSI = r'''```mermaid
flowchart TD
    START([🫁 Paciente con indicación de intubación]) --> AIRWAY[Evaluación de vía aérea]
    AIRWAY --> PREP[Preparación: 7 P's]
    PREP --> INDUCE[Selección de agente de inducción]
    INDUCE --> PARALYZE[Selección de bloqueante neuromuscular]
    PARALYZE --> DOSE[Cálculo de dosis según peso]
    DOSE --> INTUB[Plan A: intubación]
    INTUB --> SUCCESS{¿Intubación exitosa?}
    SUCCESS -->|Sí| POST[Manejo post-intubación]
    SUCCESS -->|No| PLANB[Plan B: dispositivo supraglótico]
    PLANB --> VENT{¿Ventilación adecuada?}
    VENT -->|Sí| POST
    VENT -->|No| PLANC[Plan C: ventilación con mascarilla / despertar]
    PLANC --> OXY{¿Oxigenación adecuada?}
    OXY -->|Sí| POST
    OXY -->|No| PLAND[Plan D: vía aérea quirúrgica]
    POST --> END([Monitoreo y reevaluación])
    PLAND --> END
```
'''

def generar_mermaid_septic_shock() -> str:
    return MERMAID_SEPTIC_SHOCK

def generar_mermaid_rsi() -> str:
    return MERMAID_RSI

def guardar_diagramas(directorio: str = "docs") -> None:
    out = Path(directorio)
    out.mkdir(parents=True, exist_ok=True)
    (out / "flowchart_septic_shock.md").write_text(MERMAID_SEPTIC_SHOCK + "\n", encoding="utf-8")
    (out / "flowchart_rsi.md").write_text(MERMAID_RSI + "\n", encoding="utf-8")
    print(f"Diagramas guardados en: {out.resolve()}")

if __name__ == "__main__":
    guardar_diagramas()
