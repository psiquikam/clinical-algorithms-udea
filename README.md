
— Documentación del Repositorio
🏥 Algoritmos Clínicos en Cuidado Crítico
Prototipo funcional + simulador ramificado v0.3 que formaliza dos algoritmos representativos del cuidado crítico:Manejo del Choque Séptico e Intubación en Secuencia Rápida (RSI).

Desarrollado como recurso didáctico complementario para el Laboratorio de Simulaciónde la Facultad de Medicina — Universidad de Antioquia.

📋 Tabla de Contenido
Descripción
Algoritmos Implementados
Instalación
Uso
Estructura del Proyecto
Documentación Clínica
Diagramas de Flujo
Pseudocódigo
Testing
Referencias
Licencia
📖 Descripción
Este proyecto codifica algoritmos clínicos como árboles de decisión formales, transformandoguías de práctica clínica en código ejecutable, documentado y verificable. El objetivo es:

Formalizar el conocimiento clínico implícito en estructuras explícitas
Verificar que las decisiones siguen las guías vigentes (SSC 2021, DAS 2015)
Simular escenarios clínicos con pacientes virtuales
Enseñar mediante la interacción con el algoritmo paso a paso
🧬 Algoritmos Implementados
1. Choque Séptico (SSC 2021)
Componente	Descripción
Tamizaje	Criterios SIRS (≥2 de 4)
Estratificación	qSOFA (≥2 puntos = alto riesgo)
Disfunción orgánica	SOFA simplificado (Δ≥2 = sepsis)
Clasificación	Sepsis vs Choque séptico
Bundle 1h	Lactato, hemocultivos, ATB, cristaloides
Bundle 3h	Reevaluación, vasopresores, control foco
Vasopresores	NE → + Vasopresina → + Epinefrina
2. Intubación en Secuencia Rápida (RSI)
Componente	Descripción
Evaluación	LEMON simplificado
Preparación	Las 7 P's
Inducción	Etomidato / Ketamina / Propofol
Parálisis	Succinilcolina / Rocuronio
Rescate DAS	Plan A → B → C → D
Post-intubación	VM, sedación, monitoreo
⚙️ Instalación
```bash
# Clonar el repositorio
git clone https://github.com/usuario/clinical-algorithms-udea.git
cd clinical-algorithms-udea

# Crear entorno virtual (recomendado)
python -m venv venv

# Activar en Linux/Mac
source venv/bin/activate

# Activar en Windows
# venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```
🚀 Uso
Modo interactivo
```bash
python main.py
```
Uso programático
```python
from models.patient import Paciente, SignosVitales, Laboratorio, NivelConciencia
from algorithms.septic_shock import AlgoritmoChoqueSeptico

# Crear paciente
paciente = Paciente(
    nombre="María G.", edad=65, peso=70,
    signos_vitales=SignosVitales(
        frecuencia_cardiaca=125,
        presion_arterial_sistolica=78,
        presion_arterial_media=56,
        frecuencia_respiratoria=28,
        temperatura=39.2,
        saturacion_oxigeno=88.0
    ),
    laboratorio=Laboratorio(lactato=4.8, leucocitos=18.5, creatinina=2.3),
    nivel_conciencia=NivelConciencia.VOZ,
    foco_infeccioso="Abdominal"
)

# Ejecutar algoritmo
algoritmo = AlgoritmoChoqueSeptico()
resultado = algoritmo.ejecutar(paciente)

print(f"Clasificación: {resultado.fase.value}")
print(f"Acciones: {resultado.acciones}")
```
📁 Estructura del Proyecto
```text
clinical-algorithms-udea/
├── README.md                          # Este documento
├── requirements.txt                   # Dependencias
├── main.py                           # Programa principal interactivo
├── algorithms/
│   ├── __init__.py
│   ├── septic_shock.py               # Algoritmo choque séptico
│   └── rsi.py                        # Algoritmo RSI
├── models/
│   ├── __init__.py
│   └── patient.py                    # Modelo de paciente
├── flowcharts/
│   ├── __init__.py
│   └── generate_flowcharts.py        # Generación de diagramas
├── docs/
│   ├── pseudocode_septic_shock.md    # Pseudocódigo sepsis
│   ├── pseudocode_rsi.md             # Pseudocódigo RSI
│   ├── flowchart_septic_shock.md     # Diagrama sepsis
│   └── flowchart_rsi.md              # Diagrama RSI
└── tests/
    ├── __init__.py
    ├── test_septic_shock.py          # Tests sepsis
    └── test_rsi.py                   # Tests RSI
```
📊 Diagramas de Flujo
Los diagramas están en formato Mermaid, compatible con GitHub.

Para generarlos:

```bash
python -c "from flowcharts.generate_flowcharts import guardar_diagramas; guardar_diagramas()"
```
O verlos directamente en GitHub en la carpeta docs/.

📝 Pseudocódigo
Choque Séptico
RSI
✅ Testing
```bash
# Ejecutar todos los tests
pytest tests/ -v

# Solo tests de sepsis
pytest tests/test_septic_shock.py -v

# Solo tests de RSI
pytest tests/test_rsi.py -v
```
📚 Referencias
Evans L, et al. Surviving Sepsis Campaign: International Guidelines for Management of
Sepsis and Septic Shock 2021. Intensive Care Med. 2021;47(11):1181-1247.
Singer M, et al. The Third International Consensus Definitions for Sepsis and Septic
Shock (Sepsis-3). JAMA. 2016;315(8):801-810.
Frerk C, et al. Difficult Airway Society 2015 guidelines for management of unanticipated
difficult intubation in adults. Br J Anaesth. 2015;115(6):827-848.
Mosier JM, et al. Rapid Sequence Intubation. N Engl J Med. 2022;387(6):543-551.
ATLS Subcommittee. Advanced Trauma Life Support 10th Edition. American College of
Surgeons. 2018.
📜 Licencia
MIT License — Libre uso educativo.

💡 Nota: Este prototipo es un recurso didáctico y no reemplaza el juicio clínico
ni las guías de práctica clínica vigentes. Siempre verificar las actualizaciones de las
sociedades científicas correspondientes.

text


---

## 12. Archivos `__init__.py`

```python
# algorithms/__init__.py
from algorithms.septic_shock import AlgoritmoChoqueSeptico
from algorithms.rsi import AlgoritmoRSI
python

# models/__init__.py
from models.patient import Paciente, SignosVitales, Laboratorio, NivelConciencia, ViaAerea
python

# flowcharts/__init__.py
from flowcharts.generate_flowcharts import generar_mermaid_septic_shock, generar_mermaid_rsi
python

# tests/__init__.py
Salida de ejemplo del programa
Al ejecutar python main.py y seleccionar el algoritmo de choque séptico, se produce:

text

╭──────────────────────────────────────────────────────────────╮
│  🏥 ALGORITMOS CLÍNICOS EN CUIDADO CRÍTICO                  │
│  Universidad de Antioquia — Laboratorio de Simulación        │
│  Facultad de Medicina                                        │
╰──────────────────────────────────────────────────────────────╯

╭─────────── 📋 DATOS DEL PACIENTE ───────────╮
│  PACIENTE: Caso Simulado — María G.         │
│  FC: 125 lpm  PA: 78/45  PAM: 56 mmHg       │
│  FR: 28 rpm  SpO2: 88%  Temp: 39.2°C        │
│  Lactato: 4.8  Leucocitos: 18.5             │
│  Foco: Abdominal                             │
╰──────────────────────────────────────────────╯

┌──────────────── Evaluaciones Clínicas ────────────────┐
│ Criterio               │ Cumple │ Valor │ Umbral      │
│ SIRS - Taquicardia     │ ✅ Sí  │ 125   │ 90          │
│ SIRS - Taquipnea       │ ✅ Sí  │ 28    │ 20          │
│ SIRS - Temperatura     │ ✅ Sí  │ 39.2  │ 38.0        │
│ SIRS - Leucocitos      │ ✅ Sí  │ 18.5  │ 12.0        │
│ qSOFA - Conciencia     │ ✅ Sí  │ 1     │ 1           │
│ qSOFA - Hipotensión    │ ✅ Sí  │ 78    │ 100         │
│ qSOFA - Taquipnea      │ ✅ Sí  │ 28    │ 22          │
│ SOFA - Respiratorio    │ ✅ Sí  │ 180   │ 300         │
│ SOFA - Coagulación     │ ✅ Sí  │ 85    │ 100         │
│ SOFA - Renal           │ ✅ Sí  │ 2.3   │ 2.0         │
│ SOFA - Neurológico     │ ✅ Sí  │ 2     │ 2           │
└──────────────────────────────────────────────────────┘

🔍 CLASIFICACIÓN: 🚨 CHOQUE SÉPTICO
⏱️  Tiempo límite: 1 hora (bundle inmediato)

╭────────── 📋 PLAN TERAPÉUTICO ──────────╮
│ ⏱️  BUNDLE 1 HORA — Iniciar INMEDIATAMENTE:
│ 1. Medir lactato sérico (actual: 4.8 mmol/L)
│ 2. Obtener hemocultivos ANTES de antibióticos
│ 3. Administrar antibióticos de amplio espectro IV
│ 4. Cristaloides: 30 mL/kg = 2100 mL
│ 5. ATB empírico: Meropenem 1g IV + Metronidazol
│ 6. Ringer lactato preferido
│
│ ⏱️  BUNDLE 3 HORAS:
│ 7. Re-medir lactato
│ 8. Volumen adicional si PAM <65
│ 9. Control de foco infeccioso
│
│ 🚨 CHOQUE SÉPTICO:
│ 10. Norepinefrina 0.1-0.5 µg/kg/min
│ 11. + Vasopresina 0.03 U/min si NE >0.5
│ 12. + Epinefrina como tercer agente
│ 13. Lactato >4 → Resucitación dirigida
│ 14. Control foco <6-12 horas
╰──────────────────────────────────────────╯

╭────────── ⚠️  ALERTAS ──────────╮
│ ⚠️  PACIENTE EN CHOQUE SÉPTICO — Mortalidad >40%
│ ⚠️  Cada hora de retraso en ATB ↑ mortalidad 7.6%
│ ⚠️  Lactato >4 → Resucitación agresiva inmediata
│ ⚠️  ALERGIAS: Penicilina — Verificar antes de ATB
╰──────────────────────────────────────────╯
Resumen de lo entregado
Componente
Estado
Algoritmo Choque Séptico — SIRS, qSOFA, SOFA, clasificación, bundle 1h/3h, vasopresores	✅ Completo
Algoritmo RSI — LEMON, 7 P's, agentes farmacológicos, dosis, rescate DAS A→D	✅ Completo
Modelo de paciente — Signos vitales, laboratorio, conciencia, vía aérea, intervenciones	✅ Completo
Pseudocódigo — Ambos algoritmos con notación formal	✅ Completo
Diagramas de flujo — Mermaid (renderiza en GitHub)	✅ Completo
Cálculo de dosis — Peso-dependiente con volúmenes y concentraciones	✅ Completo
Tests unitarios — 15+ pruebas con pytest	✅ Completo
README — Documentación completa con referencias	✅ Completo
Programa interactivo — Menú con Rich (colores, tablas)	✅ Completo

Para subir a GitHub, simplemente crea el repositorio, copia la estructura de archivos y ejecuta git push. Los diagramas Mermaid se renderizarán automáticamente en el visor de GitHub.
## 🧑‍⚕️ Simulador de decisiones clínicas

La versión web añade una capa de simulación educativa sobre el motor clínico existente.

### Ejecutar la interfaz web

```bash
pip install -r requirements.txt
python app.py
```

Luego abrir en el navegador:

```text
http://127.0.0.1:5000
```

La actividad registra en el navegador la decisión, el tiempo empleado, si coincide con la decisión esperada del escenario y una consecuencia educativa. Esta primera versión implementa un escenario de choque séptico y está preparada para ampliar el mismo patrón a RSI y a nuevos escenarios.

> Nota: esta interfaz es un prototipo didáctico. La decisión esperada se deriva del algoritmo implementado en este repositorio y, en esta versión, conserva la referencia clínica declarada por el prototipo (SSC 2021). Debe verificarse contra guías vigentes y protocolos institucionales antes de usarla en enseñanza clínica formal.

## 🌐 Interfaz web de simulación

La versión web convierte el prototipo CLI en una actividad de decisión clínica ejecutable desde el navegador, sin requerir Flask ni un framework adicional.

### Ejecutar

```bash
python app.py
```

Abrir:

```text
http://127.0.0.1:8000
```

La primera actividad implementada es un escenario de choque séptico. El estudiante selecciona una decisión, el sistema mide el tiempo empleado, compara la opción con la decisión esperada configurada para el escenario, muestra la consecuencia educativa y deja un registro visible de la sesión.

## Release v0.2 — Simulador web

- Interfaz web local sin framework adicional.
- Escenario inicial: choque séptico.
- Decisión del estudiante.
- Temporizador de decisión.
- Comparación con decisión esperada del prototipo.
- Consecuencia y retroalimentación educativa.
- Registro visible de la sesión.
- 24 pruebas automatizadas pasan.

## Simulador ramificado v0.3

La versión 0.3 transforma el motor CLI en una experiencia educativa local basada en nodos de decisión. El estudiante selecciona una intervención, el sistema registra la decisión y el tiempo, aplica una consecuencia educativa y actualiza un estado fisiológico simulado antes de avanzar al siguiente nodo.

### Ejecutar

```bash
python app.py
```

Abrir: `http://127.0.0.1:8000`

La sesión queda registrada mientras el servidor está activo. El escenario de choque séptico utiliza los datos del caso simulado existente y conserva la base clínica declarada por el prototipo; la capa de ramificación es didáctica y no pretende predecir la evolución de un paciente real.

### Pruebas

```bash
python -m pytest tests/ -v
```


## v0.4 — Sala de reanimación interactiva

La interfaz web evoluciona hacia una experiencia de simulación clínica: el estudiante observa un
paciente virtual, consulta el monitor, selecciona intervenciones y observa cambios fisiológicos
simulados antes de volver a decidir. La actividad registra la trayectoria de decisiones y ofrece un
debriefing final.

### Ejecutar la interfaz

```bash
python app.py
```

Después abrir:

http://127.0.0.1:8000

### Nota de identidad institucional

La interfaz utiliza una paleta visual inspirada en la identidad de la Universidad de Antioquia.
El logosímbolo oficial no se redistribuye en este prototipo. Su incorporación formal deberá seguir
el Manual de Identidad Institucional y las autorizaciones aplicables.

### Nota de seguridad pedagógica

Los cambios de signos vitales y demás respuestas del paciente son **simulaciones educativas**.
No constituyen recomendaciones para atención de pacientes ni sustituyen guías clínicas, supervisión
docente o juicio profesional.


\n## v0.4.1 — Corrección de recursos estáticos\n\n
Corrección del enrutamiento de `app.py` para servir correctamente `web/style.css` y `web/app.js`.
Incluye una prueba de regresión para evitar que los recursos estáticos vuelvan a resolverse como
`web/web/...`.\n\n


## v0.6 — Sala virtual de reanimación

La interfaz incorpora una escenografía 2D de sala de reanimación, paciente virtual, monitor multiparámetro, equipo interactivo, eventos del escenario, controles de pausa/sonido, trayectoria de decisiones y debriefing. Los sonidos se sintetizan localmente con Web Audio API; no se requieren archivos de audio externos.

**Nota:** la escenografía, animaciones, eventos y respuestas fisiológicas son simulaciones educativas. No representan una sala clínica específica ni predicen la respuesta de un paciente real.


## v0.7 — Sala de reanimación inmersiva

La interfaz incorpora una capa audiovisual sintética para reforzar la inmersión: monitor ECG
animado, sonido cardiaco sincronizado de forma aproximada con la frecuencia simulada, alarmas
sintéticas ante inestabilidad, ambiente de sala opcional y mensajes del equipo con voz del navegador
cuando esté disponible.

### Activar audio

Los navegadores modernos suelen bloquear el audio automático. Abre el botón **Audio**, pulsa
**Activar sonido** y configura volumen, monitor, ambiente, alarmas y voz del equipo.

### Alcance

Los sonidos no son grabaciones clínicas ni pretenden reproducir fielmente un monitor comercial.
Son una representación sonora sintética para simulación educativa. La fisiología mostrada también
es simulada y no predictiva.


## v0.8 — Cierre de caso, eventos estructurados y más alertas de voz

Esta versión perfecciona el manejo del caso desde el evento inicial hasta su cierre, y amplía
las alertas habladas del equipo.

### Eventos del escenario, tipados y con voz

Cada evento del escenario ahora tiene un **tipo** (`nursing`, `labs`, `clinical`, `deterioration`,
`closure`), un **título** visible y un **texto**, en lugar de un texto plano genérico. Esto corrige
la inconsistencia previa entre los tiempos programados en el backend y los que realmente disparaba
la interfaz. Ejemplos incluidos en la línea de tiempo del caso:

- **Aviso de enfermería** — "La paciente está más fría y responde más lentamente."
- **Resultados disponibles** — "Se liberan nuevos datos de laboratorio."
- **Evento clínico** — "Aparece dolor abdominal intenso."
- **Deterioro** — "Persiste la inestabilidad y el equipo debe escalar."

Cada evento se anuncia con voz del navegador (cuando está activada) además de quedar registrado
en el panel de "Eventos y equipo".

### Manejo del caso hasta su cierre

El backend evalúa continuamente el estado del caso (`en_curso`, `listo_para_cierre`,
`escalamiento_requerido`) según la tendencia fisiológica y si se activó el control del foco
infeccioso. El primer cambio de estado dispara una alerta puntual (visual y de voz) para no
repetirse en cada acción posterior. Un indicador de estado del caso se muestra junto a las
etiquetas clínicas de la sala.

Al finalizar la simulación, el debriefing incluye un **desenlace** (`Favorable`, `Adverso` o
`Incompleto`) y una **narrativa de cierre** que explica el motivo, en lugar de solo mostrar
cifras del resumen.

### Nota de seguridad pedagógica

La clasificación de desenlace es una simulación educativa basada en umbrales del propio motor
didáctico. No constituye un criterio clínico de cierre de caso real ni sustituye la valoración
del equipo tratante ni las guías vigentes.
