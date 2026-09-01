from pathlib import Path
import json, urllib.request, subprocess, sys, time
ROOT=Path(__file__).resolve().parents[1]

def test_v05_assets_exist():
    assert (ROOT/'web'/'index.html').exists()
    assert (ROOT/'web'/'style.css').exists()
    assert (ROOT/'web'/'app.js').exists()

def test_v05_ui_has_clinical_categories():
    t=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
    for s in ['Observar','Solicitar','Intervenir','Reevaluar','Paciente virtual','MONITOR MULTIPARÁMETRO','Debriefing']:
        assert s in t

def test_v05_action_categories_and_events():
    t=(ROOT/'app.py').read_text(encoding='utf-8')
    for s in ['"observe"','"investigate"','"intervene"','"reassess"','EVENTS','/api/session/action','/api/session/finish']:
        assert s in t
