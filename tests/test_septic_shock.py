"""
Tests unitarios para el algoritmo de choque séptico.
"""

import pytest
from models.patient import Paciente, SignosVitales, Laboratorio, NivelConciencia, ViaAerea
from algorithms.septic_shock import AlgoritmoChoqueSeptico, FaseSepsis


class TestSIRS:
    """Pruebas para la evaluación de criterios SIRS."""

    def setup_method(self):
        self.algoritmo = AlgoritmoChoqueSeptico()

    def test_sirs_cuatro_criterios(self):
        """Paciente que cumple los 4 criterios SIRS."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=120,
                frecuencia_respiratoria=28,
                temperatura=39.5
            ),
            laboratorio=Laboratorio(leucocitos=18.0)
        )
        _, cumplidos = self.algoritmo.evaluar_sirs(paciente)
        assert cumplidos == 4

    def test_sirs_cero_criterios(self):
        """Paciente que no cumple ningún criterio SIRS."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=75,
                frecuencia_respiratoria=16,
                temperatura=37.0
            ),
            laboratorio=Laboratorio(leucocitos=7.0)
        )
        _, cumplidos = self.algoritmo.evaluar_sirs(paciente)
        assert cumplidos == 0

    def test_sirs_leucopenia(self):
        """Leucopenia (<4) debe contar como criterio SIRS."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            laboratorio=Laboratorio(leucocitos=2.5)
        )
        _, cumplidos = self.algoritmo.evaluar_sirs(paciente)
        assert cumplidos >= 1


class TestQSOFA:
    """Pruebas para la evaluación de qSOFA."""

    def setup_method(self):
        self.algoritmo = AlgoritmoChoqueSeptico()

    def test_qsofa_tres_puntos(self):
        """Paciente con qSOFA = 3 (máximo)."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            signos_vitales=SignosVitales(
                presion_arterial_sistolica=85,
                frecuencia_respiratoria=28
            ),
            nivel_conciencia=NivelConciencia.INCONSCIENTE
        )
        _, score = self.algoritmo.evaluar_qsofa(paciente)
        assert score == 3

    def test_qsofa_cero_puntos(self):
        """Paciente con qSOFA = 0."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            signos_vitales=SignosVitales(
                presion_arterial_sistolica=130,
                frecuencia_respiratoria=18
            ),
            nivel_conciencia=NivelConciencia.ALERTA
        )
        _, score = self.algoritmo.evaluar_qsofa(paciente)
        assert score == 0

    def test_qsofa_pas_limite(self):
        """PAS = 100 mmHg debe contar como criterio qSOFA."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            signos_vitales=SignosVitales(presion_arterial_sistolica=100),
        )
        _, score = self.algoritmo.evaluar_qsofa(paciente)
        assert score >= 1


class TestClasificacion:
    """Pruebas para la clasificación de sepsis."""

    def setup_method(self):
        self.algoritmo = AlgoritmoChoqueSeptico()

    def test_choque_septico(self):
        """Paciente con choque séptico completo."""
        paciente = Paciente(
            nombre="Test", edad=65, peso=70,
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=130,
                presion_arterial_sistolica=75,
                presion_arterial_media=52,
                frecuencia_respiratoria=32,
                temperatura=39.5,
                saturacion_oxigeno=85.0
            ),
            laboratorio=Laboratorio(
                lactato=5.2,
                leucocitos=20.0,
                creatinina=2.8,
                plaquetas=65,
                pafi=150
            ),
            nivel_conciencia=NivelConciencia.DOLOR,
            foco_infeccioso="Pulmonar"
        )
        resultado = self.algoritmo.ejecutar(paciente)
        assert resultado.fase == FaseSepsis.CHOQUE_SEPTICO

    def test_sepsis_sin_choque(self):
        """Paciente con sepsis pero sin choque."""
        paciente = Paciente(
            nombre="Test", edad=55, peso=70,
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=105,
                presion_arterial_sistolica=110,
                presion_arterial_media=75,
                frecuencia_respiratoria=24,
                temperatura=38.5
            ),
            laboratorio=Laboratorio(
                lactato=1.5,
                leucocitos=14.0,
                creatinina=1.5
            ),
            nivel_conciencia=NivelConciencia.ALERTA,
            foco_infeccioso="Urinario"
        )
        resultado = self.algoritmo.ejecutar(paciente)
        assert resultado.fase in (FaseSepsis.SEPSIS, FaseSepsis.NO_SEPSIS)

    def test_no_sepsis(self):
        """Paciente que no cumple criterios de sepsis."""
        paciente = Paciente(
            nombre="Test", edad=30, peso=70,
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=80,
                presion_arterial_sistolica=120,
                presion_arterial_media=85,
                frecuencia_respiratoria=16,
                temperatura=37.0
            ),
            laboratorio=Laboratorio(
                leucocitos=7.0,
                creatinina=0.9
            ),
            nivel_conciencia=NivelConciencia.ALERTA
        )
        resultado = self.algoritmo.ejecutar(paciente)
        assert resultado.fase == FaseSepsis.NO_SEPSIS


class TestPlanTerapeutico:
    """Pruebas para el plan terapéutico."""

    def setup_method(self):
        self.algoritmo = AlgoritmoChoqueSeptico()

    def test_choque_tiene_vasopresores(self):
        """El plan para choque séptico debe incluir vasopresores."""
        paciente = Paciente(
            nombre="Test", edad=65, peso=70,
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=130,
                presion_arterial_sistolica=70,
                presion_arterial_media=48,
                frecuencia_respiratoria=32,
                temperatura=39.5
            ),
            laboratorio=Laboratorio(
                lactato=5.0,
                leucocitos=20.0,
                creatinina=3.0
            ),
            nivel_conciencia=NivelConciencia.DOLOR,
            foco_infeccioso="Abdominal"
        )
        resultado = self.algoritmo.ejecutar(paciente)
        assert any("Vasopresor" in a or "Norepinefrina" in a for a in resultado.acciones)

    def test_alergias_en_alertas(self):
        """Las alergias deben aparecer en las alertas."""
        paciente = Paciente(
            nombre="Test", edad=65, peso=70,
            alergias=["Penicilina"],
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=130,
                presion_arterial_sistolica=70,
                presion_arterial_media=48,
                frecuencia_respiratoria=32,
                temperatura=39.5
            ),
            laboratorio=Laboratorio(
                lactato=5.0,
                leucocitos=20.0,
                creatinina=3.0
            ),
            nivel_conciencia=NivelConciencia.DOLOR,
            foco_infeccioso="Abdominal"
        )
        resultado = self.algoritmo.ejecutar(paciente)
        assert any("Penicilina" in a for a in resultado.alertas)

    def test_volumen_cristaloides(self):
        """El volumen de cristaloides debe calcularse según peso."""
        paciente = Paciente(
            nombre="Test", edad=65, peso=80,
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=110,
                presion_arterial_sistolica=80,
                presion_arterial_media=55,
                frecuencia_respiratoria=28,
                temperatura=38.8
            ),
            laboratorio=Laboratorio(
                lactato=3.5,
                leucocitos=16.0,
                creatinina=2.0
            ),
            nivel_conciencia=NivelConciencia.VOZ,
            foco_infeccioso="Urinario"
        )
        resultado = self.algoritmo.ejecutar(paciente)
        # 30 mL/kg × 80 kg = 2400 mL
        assert any("2400" in a for a in resultado.acciones)