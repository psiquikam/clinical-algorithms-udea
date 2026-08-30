"""
═══════════════════════════════════════════════════════════════════════
  ALGORITMOS CLÍNICOS EN CUIDADO CRÍTICO
  Prototipo funcional — Universidad de Antioquia
  Laboratorio de Simulación — Facultad de Medicina
═══════════════════════════════════════════════════════════════════════

Uso:
    python main.py

Requiere: pip install rich
"""

import sys
import os

# Agregar directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from models.patient import (
    Paciente, SignosVitales, Laboratorio,
    NivelConciencia, ViaAerea
)
from algorithms.septic_shock import AlgoritmoChoqueSeptico
from algorithms.rsi import AlgoritmoRSI, ClasificacionMallampati

console = Console() if RICH_AVAILABLE else None


def print_header():
    """Imprime el encabezado del programa."""
    if console:
        console.print(Panel.fit(
            "[bold cyan]🏥 ALGORITMOS CLÍNICOS EN CUIDADO CRÍTICO[/bold cyan]\n"
            "[dim]Universidad de Antioquia — Laboratorio de Simulación[/dim]\n"
            "[dim]Facultad de Medicina[/dim]",
            border_style="cyan"
        ))
    else:
        print("=" * 60)
        print("  ALGORITMOS CLÍNICOS EN CUIDADO CRÍTICO")
        print("  Universidad de Antioquia — Lab. de Simulación")
        print("=" * 60)


def crear_paciente_sepsis() -> Paciente:
    """Crea un paciente simulado con choque séptico."""
    paciente = Paciente(
        nombre="Caso Simulado — María G.",
        edad=65,
        peso=70,
        alergias=["Penicilina"],
        antecedentes=["Diabetes mellitus tipo 2", "Hipertensión arterial"],
        signos_vitales=SignosVitales(
            frecuencia_cardiaca=125,
            presion_arterial_sistolica=78,
            presion_arterial_diastolica=45,
            presion_arterial_media=56,
            frecuencia_respiratoria=28,
            saturacion_oxigeno=88.0,
            temperatura=39.2,
            glucemia=245
        ),
        laboratorio=Laboratorio(
            lactato=4.8,
            leucocitos=18.5,
            creatinina=2.3,
            bilirrubina=1.8,
            plaquetas=85,
            pafi=180,
            procalcitonina=15.2
        ),
        nivel_conciencia=NivelConciencia.VOZ,
        via_aerea=ViaAerea.PATENTE,
        foco_infeccioso="Abdominal",
        tiempo_hospital=2.5
    )
    return paciente


def crear_paciente_rsi() -> Paciente:
    """Crea un paciente simulado para RSI."""
    paciente = Paciente(
        nombre="Caso Simulado — Carlos R.",
        edad=52,
        peso=80,
        alergias=[],
        antecedentes=["Trauma cerrado de tórax", "TCE"],
        signos_vitales=SignosVitales(
            frecuencia_cardiaca=110,
            presion_arterial_sistolica=90,
            presion_arterial_diastolica=55,
            presion_arterial_media=67,
            frecuencia_respiratoria=8,
            saturacion_oxigeno=82.0,
            temperatura=36.5,
            glucemia=180
        ),
        laboratorio=Laboratorio(),
        nivel_conciencia=NivelConciencia.INCONSCIENTE,
        via_aerea=ViaAerea.PATENTE,
        foco_infeccioso=None,
        tiempo_hospital=0.5
    )
    return paciente


def ejecutar_sepsis():
    """Ejecuta el algoritmo de choque séptico."""
    if console:
        console.print("\n[bold yellow]═══════════════════════════════════════════[/bold yellow]")
        console.print("[bold yellow]  ALGORITMO: CHOQUE SÉPTICO (SSC 2021)[/bold yellow]")
        console.print("[bold yellow]═══════════════════════════════════════════[/bold yellow]\n")

    # Crear paciente
    paciente = crear_paciente_sepsis()

    # Mostrar datos del paciente
    if console:
        console.print(Panel(paciente.resumen(), title="📋 DATOS DEL PACIENTE", border_style="blue"))
    else:
        print(paciente.resumen())

    # Ejecutar algoritmo
    algoritmo = AlgoritmoChoqueSeptico()
    resultado = algoritmo.ejecutar(paciente)

    # Mostrar evaluaciones
    if console:
        table = Table(title="Evaluaciones Clínicas", box=box.ROUNDED)
        table.add_column("Criterio", style="cyan")
        table.add_column("¿Cumple?", style="bold")
        table.add_column("Valor", style="yellow")
        table.add_column("Umbral", style="green")
        table.add_column("Detalle", style="dim")

        for ev in resultado.evaluaciones:
            cumple_str = "✅ Sí" if ev.cumple else "❌ No"
            valor_str = str(ev.valor) if ev.valor is not None else "N/A"
            umbral_str = str(ev.umbral) if ev.umbral is not None else "N/A"
            style = "green" if ev.cumple else "red"
            table.add_row(ev.criterio, cumple_str, valor_str, umbral_str, ev.detalle, style=style)

        console.print(table)

        # Fase
        fase_color = "red" if resultado.fase.value == "Choque séptico" else "yellow"
        console.print(f"\n[bold {fase_color}]🔍 CLASIFICACIÓN: {resultado.fase.value}[/bold {fase_color}]")
        console.print(f"[bold]⏱️  Tiempo límite: {resultado.tiempo_limite}[/bold]")

        # Acciones
        console.print(Panel("\n".join(resultado.acciones), title="📋 PLAN TERAPÉUTICO", border_style="green"))

        # Metas
        if resultado.metas:
            console.print(Panel("\n".join(f"• {m}" for m in resultado.metas), title="🎯 METAS", border_style="cyan"))

        # Alertas
        if resultado.alertas:
            console.print(Panel("\n".join(resultado.alertas), title="⚠️  ALERTAS", border_style="red"))
    else:
        print("\n--- Evaluaciones ---")
        for ev in resultado.evaluaciones:
            print(f"  {ev.criterio}: {'✅' if ev.cumple else '❌'} | Valor: {ev.valor} | Umbral: {ev.umbral}")
        print(f"\nClasificación: {resultado.fase.value}")
        print(f"Tiempo límite: {resultado.tiempo_limite}")
        print("\n--- Acciones ---")
        for a in resultado.acciones:
            print(f"  {a}")
        print("\n--- Alertas ---")
        for a in resultado.alertas:
            print(f"  {a}")


def ejecutar_rsi():
    """Ejecuta el algoritmo de RSI."""
    if console:
        console.print("\n[bold magenta]═══════════════════════════════════════════[/bold magenta]")
        console.print("[bold magenta]  ALGORITMO: INTUBACIÓN SECUENCIA RÁPIDA[/bold magenta]")
        console.print("[bold magenta]═══════════════════════════════════════════[/bold magenta]\n")

    # Crear paciente
    paciente = crear_paciente_rsi()

    # Mostrar datos
    if console:
        console.print(Panel(paciente.resumen(), title="📋 DATOS DEL PACIENTE", border_style="blue"))
    else:
        print(paciente.resumen())

    # Ejecutar algoritmo
    algoritmo = AlgoritmoRSI()
    resultado = algoritmo.ejecutar(paciente)

    # Resultados
    if console:
        # Evaluación de vía aérea
        ev = resultado.evaluacion_via_aerea
        console.print(Panel(
            f"Clasificación: [bold]{ev.clasificacion.value}[/bold]\n"
            f"Score de dificultad: {ev.score_dificultad}",
            title="🫁 EVALUACIÓN DE VÍA AÉREA",
            border_style="magenta"
        ))

        # Agentes seleccionados
        console.print(Panel(
            f"Inducción: [bold cyan]{resultado.agente_induccion.value}[/bold cyan]\n"
            f"Bloqueante: [bold cyan]{resultado.bloqueante.value}[/bold cyan]",
            title="💊 AGENTES FARMACOLÓGICOS",
            border_style="cyan"
        ))

        # Dosis calculadas
        dosis_text = []
        for nombre, datos in resultado.dosis_calculadas.items():
            dosis_text.append(f"\n[bold]{nombre.upper()}[/bold]")
            for k, v in datos.items():
                dosis_text.append(f"  {k}: {v}")
        console.print(Panel("\n".join(dosis_text), title="💉 DOSIS CALCULADAS", border_style="green"))

        # Preparación
        console.print(Panel("\n".join(resultado.pasos_preparacion), title="📋 PREPARACIÓN (7 P's)", border_style="yellow"))

        # Ejecución
        console.print(Panel("\n".join(resultado.pasos_ejecucion), title="⚡ EJECUCIÓN DE RSI", border_style="red"))

        # Plan de rescate
        console.print(Panel("\n".join(resultado.plan_rescate), title="🆘 PLANES DE RESCATE DAS", border_style="magenta"))

        # Post-intubación
        console.print(Panel("\n".join(resultado.manejo_post_intubacion), title="🏥 POST-INTUBACIÓN", border_style="cyan"))

        # Alertas
        if resultado.alertas:
            console.print(Panel("\n".join(resultado.alertas), title="⚠️  ALERTAS", border_style="red"))
    else:
        print(f"\nEvaluación vía aérea: {resultado.evaluacion_via_aerea.clasificacion.value}")
        print(f"Inducción: {resultado.agente_induccion.value}")
        print(f"Bloqueante: {resultado.bloqueante.value}")
        print("\n--- Dosis ---")
        for nombre, datos in resultado.dosis_calculadas.items():
            print(f"  {nombre}: {datos}")
        print("\n--- Preparación ---")
        for p in resultado.pasos_preparacion:
            print(p)
        print("\n--- Ejecución ---")
        for p in resultado.pasos_ejecucion:
            print(p)
        print("\n--- Plan Rescate ---")
        for p in resultado.plan_rescate:
            print(p)
        print("\n--- Post-Intubación ---")
        for p in resultado.manejo_post_intubacion:
            print(p)
        print("\n--- Alertas ---")
        for a in resultado.alertas:
            print(f"  {a}")


def ejecutar_ambos():
    """Ejecuta ambos algoritmos secuencialmente."""
    ejecutar_sepsis()
    print("\n\n")
    ejecutar_rsi()


def menu():
    """Menú principal del programa."""
    print_header()

    while True:
        if console:
            console.print("\n[bold]Seleccione un algoritmo:[/bold]")
            console.print("  [cyan]1[/cyan] — 🦠 Choque Séptico (SSC 2021)")
            console.print("  [cyan]2[/cyan] — 🫁 Intubación Secuencia Rápida (RSI)")
            console.print("  [cyan]3[/cyan] — 📋 Ambos algoritmos")
            console.print("  [cyan]4[/cyan] — 📊 Generar diagramas de flujo")
            console.print("  [cyan]0[/cyan] — 🚪 Salir")
        else:
            print("\nSeleccione un algoritmo:")
            print("  1 — Choque Séptico (SSC 2021)")
            print("  2 — Intubación Secuencia Rápida (RSI)")
            print("  3 — Ambos algoritmos")
            print("  4 — Generar diagramas de flujo")
            print("  0 — Salir")

        opcion = input("\nOpción: ").strip()

        if opcion == "1":
            ejecutar_sepsis()
        elif opcion == "2":
            ejecutar_rsi()
        elif opcion == "3":
            ejecutar_ambos()
        elif opcion == "4":
            from flowcharts.generate_flowcharts import guardar_diagramas
            guardar_diagramas()
        elif opcion == "0":
            if console:
                console.print("[bold green]¡Hasta pronto! 👋[/bold green]")
            else:
                print("¡Hasta pronto!")
            break
        else:
            if console:
                console.print("[red]Opción no válida[/red]")
            else:
                print("Opción no válida")

        input("\nPresione Enter para continuar...")


if __name__ == "__main__":
    menu()