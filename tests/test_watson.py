from pathlib import Path

from nupore.graph.node import Node
from nupore.processes.watson import _directly_supported, _main, check, brief_known

FIXT = str(Path(__file__).resolve().parent / "fixtures" / "watson")


def _map():
    return {d.argument_id: d for d in check(FIXT, "S1")}


def test_nur_vorkommende_argumente():
    m = _map()
    assert set(m) == {"A_BELEGT", "A_MITTELBAR", "A_BESTRITTEN", "A_OFFEN"}
    assert "A_GEGNER" not in m  # kein occurrence auf S1 -> nicht im DeadlineReport


def test_direkt_belegt():
    assert _map()["A_BELEGT"].status == "directly_supported"


def test_mittelbar_gestuetzt():
    d = _map()["A_MITTELBAR"]
    assert d.status == "indirectly_supported"
    assert "A_BELEGT" in d.reason


def test_offen():
    assert _map()["A_OFFEN"].status == "offen"


def test_bestritten_ist_overlay_nicht_status():
    d = _map()["A_BESTRITTEN"]
    assert d.status == "directly_supported"   # hat eigene amtliche Quelle
    assert d.contested is True           # UND wird contested
    assert _map()["A_BELEGT"].contested is False


# --- Komplett-Review 2026-11-20: Eingabe-/Formpruefung ---

def test_list_fundstelle_nicht_direkt_belegt():
    n = Node(id="X", type="argument",
             fields={"source_type": "own_brief", "citation": ["a", "b"]},
             edges={}, body="")
    assert _directly_supported(n) is False   # Liste ist kein formgueltiger Locator


def test_unbekannter_schriftsatz_signalisiert(tmp_path):
    (tmp_path / "ss.md").write_text(
        '---\nid: SS1\ntype: brief\nreach: klage\ncase: X\ndate: "2020-01-01"\n---\nbody\n',
        encoding="utf-8")
    assert brief_known(str(tmp_path), "SS1") is True
    assert brief_known(str(tmp_path), "NICHTDA") is False
    assert _main(["prog", str(tmp_path), "NICHTDA"]) == 2   # eigener Status statt leerer DeadlineReport
