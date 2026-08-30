"""
Tests unitarios para el algoritmo de RSI.
"""

import pytest
from models.patient import Paciente, SignosVitales, Laboratorio, NivelConciencia, ViaAerea
from algorithms.rsi import (
    AlgoritmoRSI, AgenteInduccion, BloqueanteNeuromuscular,
    DificultadViaAerea, ClasificacionMallampati
)


class TestEvaluacionViaAerea:
    """Pruebas para la evaluación de vía aérea."""

    def setup_method(self):
        self.algoritmo = AlgoritmoRSI()

    def test_via_aerea_sin_dificultad(self):
        """Paciente sin factores de dificultad."""
        paciente = Paciente(
            nombre="Test", edad=35, peso=70,
            antecedentes=[]
        )
        evalua = self.algoritmo.evaluar_via_aerea(paciente)
        assert evalua.clasificacion == DificultadViaAerea.SIN_DIFICULTAD
        assert evalua.score_dificultad == 0

    def test_via_aerea_obstruida(self):
        """Vía aérea obstruida debe aumentar dificultad."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            via_aerea=ViaAerea.OBSTRUIDA_PARCIAL
        )
        evalua = self.algoritmo.evaluar_via_aerea(paciente)
        assert evalua.score_dificultad >= 2


class TestSeleccionAgentes:
    """Pruebas para la selección de agentes farmacológicos."""

    def setup_method(self):
        self.algoritmo = AlgoritmoRSI()

    def test_inestabilidad_etomidato(self):
        """PAM <65 debe seleccionar etomidato."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            signos_vitales=SignosVitales(
                presion_arterial_media=55
            )
        )
        agente = self.algoritmo.seleccionar_agente_induccion(paciente)
        assert agente == AgenteInduccion.ETOMIDATO

    def test_asma_ketamina(self):
        """Antecedente de asma debe seleccionar ketamina."""
        paciente = Paciente(
            nombre="Test", edad=50, peso=70,
            antecedentes=["Asma"],
            signos_vitales=SignosVitales(
                presion_arterial_media=75
            )
        )
        agente = self.algoritmo.seleccionar_agente_induccion(paciente)
        assert agente == AgenteInduccion.KETAMINA

    def test_quemadura_rocuronio(self):
        """Quemaduras deben contraindicar succinilcolina."""
        paciente = Paciente(
            nombre="Test", edad=40, peso=70,
            antecedentes=["Quemadura 30% TBS"]
        )
        bloqueante = self.algoritmo.seleccionar_bloqueante(paciente)
        assert bloqueante == BloqueanteNeuromuscular.ROCURONIO


class TestCalculoDosis:
    """Pruebas para el cálculo de dosis."""

    def setup_method(self):
        self.algoritmo = AlgoritmoRSI()

    def test_dosis_etomidato(self):
        """Etomidato 0.3 mg/kg debe calcularse correctamente."""
        paciente = Paciente(nombre="Test", edad=50, peso=70)
        dosis = self.algoritmo.calcular_dosis(paciente, AgenteInduccion.ETOMIDATO, BloqueanteNeuromuscular.SUCCINILCOLINA)
        assert dosis["etomidato"]["mg_total"] == 21.0

    def test_dosis_rocuronio_con_sugammadex(self):
        """Rocuronio debe incluir sugammadex de rescate."""
        paciente = Paciente(nombre="Test", edad=50, peso=70)
        dosis = self.algoritmo.calcular_dosis(paciente, AgenteInduccion.ETOMIDATO, BloqueanteNeuromuscular.ROCURONIO)
        assert "sugammadex_rescate" in dosis
        assert dosis["rocuronio"]["mg_total"] == 84.0

    def test_dosis_sux(self):
        """Succinilcolina 1.5 mg/kg debe calcularse correctamente."""
        paciente = Paciente(nombre="Test", edad=50, peso=80)
        dosis = self.algoritmo.calcular_dosis(paciente, AgenteInduccion.KETAMINA, BloqueanteNeuromuscular.SUCCINILCOLINA)
        assert dosis["succinilcolina"]["mg_total"] == 120.0


class TestEjecucionCompleta:
    """Pruebas para la ejecución completa del algoritmo."""

    def test_rsi_paciente_trauma(self):
        """Ejecución completa con paciente traumatizado."""
        paciente = Paciente(
            nombre="Test", edad=45, peso=75,
            antecedentes=["Trauma cervical"],
            signos_vitales=SignosVitales(
                frecuencia_cardiaca=115,
                presion_arterial_sistolica=95,
                presion_arterial_media=70,
                frecuencia_respiratoria=8,
                saturacion_oxigeno=80.0
            ),
            nivel_conciencia=NivelConciencia.INCONSCIENTE,
            via_aerea=ViaAerea.PATENTE
        )
        algoritmo = AlgoritmoRSI()
        resultado = algoritmo.ejecutar(paciente)

        assert resultado.agente_induccion is not None
        assert resultado.bloqueante is not None
        assert len(resultado.pasos_preparacion) > 0
        assert len(resultado.pasos_ejecucion) > 0
        assert len(resultado.plan_rescate) > 0
        assert len(resultado.manejo_post_intubacion) > 0
        assert len(resultado.dosis_calculadas) > 0

    def test_rsi_paciente_estable(self):
        """Ejecución con paciente hemodinámicamente estable."""
        paciente = Paciente(
            nombre="Test", edad=60, peso=70,
            signos_vitales=SignosVitales(
                presion_arterial_media=85,
                frecuencia_cardiaca=90
            ),
            nivel_conciencia=NivelConciencia.INCONSCIENTE
        )
        algoritmo = AlgoritmoRSI()
        resultado = algoritmo.ejecutar(paciente)
        assert resultado.evaluacion_via_aerea.score_dificultad < 5