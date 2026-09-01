from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_static_assets_exist():
    assert (ROOT / "web" / "index.html").exists()
    assert (ROOT / "web" / "style.css").exists()
    assert (ROOT / "web" / "app.js").exists()

def test_server_routes_use_single_web_prefix():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'if path.startswith("/web/")' in app
    assert '(ROOT / "web" / relative).resolve()' in app
