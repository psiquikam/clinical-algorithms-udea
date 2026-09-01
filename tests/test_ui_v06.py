from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_v06_visual_and_audio_ui_assets():
    html=(ROOT/"web"/"index.html").read_text(encoding="utf-8")
    js=(ROOT/"web"/"app.js").read_text(encoding="utf-8")
    css=(ROOT/"web"/"style.css").read_text(encoding="utf-8")
    assert "SALA DE REANIMACIÓN 1" in html
    assert "MONITOR MULTIPARÁMETRO" in html
    assert "AudioContext" in js
    assert "patientHotspot" in html and "monitorHotspot" in html
    assert "room-scene" in css and "feedback-floating" in css

def test_v06_app_version():
    text=(ROOT/"app.py").read_text(encoding="utf-8")
    assert '"version":"0.6"' in text or 'Simulador v0.6' in text
