from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v07_audio_controls_and_room_elements():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "audioPanel" in html
    assert "monitorSound" in html
    assert "ambientSound" in html
    assert "alarmSound" in html
    assert "voiceSound" in html
    assert "ventilatorHotspot" in html
    assert "ecgWave" in html

def test_v07_audio_engine_and_visual_feedback():
    js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "AudioContext" in js
    assert "startHeartLoop" in js
    assert "startAmbient" in js
    assert "alarmPulse" in js
    assert "speechSynthesis" in js

def test_v07_room_styles_present():
    css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")
    for token in ("room-scene", "monitor-panel", "ventilator", "voice-bubble", "alarm-light"):
        assert token in css
