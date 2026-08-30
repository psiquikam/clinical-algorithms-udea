from app import scenario_data
from pathlib import Path


def test_scenario_data():
    data = scenario_data()
    assert data['expected_first_action'] == 'Medir lactato sérico'
    assert data['phase'] == 'Choque séptico'
    assert data['patient']['edad'] == 65


def test_web_assets_exist():
    web = Path(__file__).resolve().parents[1] / 'web'
    assert (web / 'index.html').is_file()
    assert (web / 'app.js').is_file()
    assert (web / 'style.css').is_file()
