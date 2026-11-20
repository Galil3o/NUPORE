from pathlib import Path

from tools.processes.sherlock import leerer_befund, plane

FIXT = str(Path(__file__).resolve().parent / "fixtures" / "sherlock")


def test_nur_belegluecken_geplant():
    # FC_OFFEN = Luecke; FC_BELEGT (bewertet+belegt), FC_TATSACHE (keine Behauptung),
    # A_IGNORE (kein factcheck) sind keine.
    assert [a.factcheck_id for a in plane(FIXT)] == ["FC_OFFEN"]


def test_auftrag_traegt_suchraum_und_abbruch():
    a = plane(FIXT)[0]
    assert a.suchraum and a.abbruchkriterium   # R-013: expliziter Umfang + Abbruch
    assert a.status == "offen"
    assert a.fall == "TESTFALL"


def test_befund_haelt_gegenquellen_und_erfolglose():
    b = leerer_befund(plane(FIXT)[0])
    # R-013: stuetzende, widersprechende UND erfolglose Laeufe sind eigene Slots.
    assert b.quellen_gefunden == [] and b.gegenquellen == [] and b.erfolglose_suchlaeufe == []
    assert b.ergebnis == "offen"
