from pathlib import Path

from tools.processes.watson import pruefe

FIXT = str(Path(__file__).resolve().parent / "fixtures" / "watson")


def _map():
    return {d.argument_id: d for d in pruefe(FIXT, "S1")}


def test_nur_vorkommende_argumente():
    m = _map()
    assert set(m) == {"A_BELEGT", "A_MITTELBAR", "A_BESTRITTEN", "A_OFFEN"}
    assert "A_GEGNER" not in m  # kein vorkommen auf S1 -> nicht im Bericht


def test_direkt_belegt():
    assert _map()["A_BELEGT"].status == "direkt_belegt"


def test_mittelbar_gestuetzt():
    d = _map()["A_MITTELBAR"]
    assert d.status == "mittelbar_gestuetzt"
    assert "A_BELEGT" in d.grund


def test_offen():
    assert _map()["A_OFFEN"].status == "offen"


def test_bestritten_ist_overlay_nicht_status():
    d = _map()["A_BESTRITTEN"]
    assert d.status == "direkt_belegt"   # hat eigene amtliche Quelle
    assert d.bestritten is True           # UND wird bestritten
    assert _map()["A_BELEGT"].bestritten is False
