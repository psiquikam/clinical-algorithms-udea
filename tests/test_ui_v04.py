from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v04_ui_assets_exist():
    assert (ROOT / "web" / "index.html").exists()
    assert (ROOT / "web" / "style.css").exists()
    assert (ROOT / "web" / "app.js").exists()

def test_v04_ui_mentions_simulation():
    text = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "Paciente virtual" in text
    assert "Trayectoria clínica" in text
    assert "Debriefing" in text
