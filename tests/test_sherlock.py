from pathlib import Path

from nupore.processes.sherlock import _main, empty_finding, plan, root_present

FIXT = str(Path(__file__).resolve().parent / "fixtures" / "sherlock")


def test_nur_belegluecken_geplant():
    # FC_OFFEN = Luecke; FC_BELEGT (bewertet+belegt), FC_TATSACHE (keine Behauptung),
    # A_IGNORE (kein fact_check) sind keine.
    assert [a.fact_check_id for a in plan(FIXT)] == ["FC_OFFEN"]


def test_auftrag_traegt_suchraum_und_abbruch():
    a = plan(FIXT)[0]
    assert a.search_scope and a.stop_condition   # R-013: expliziter Umfang + Abbruch
    assert a.status == "offen"
    assert a.case == "TESTFALL"


def test_befund_haelt_gegenquellen_und_erfolglose():
    b = empty_finding(plan(FIXT)[0])
    # R-013: stuetzende, widersprechende UND erfolglose Laeufe sind eigene Slots.
    assert b.sources_found == [] and b.counter_sources == [] and b.empty_searches == []
    assert b.result == "offen"


def test_fehlende_wurzel_signalisiert(tmp_path):
    # Fehlende Wurzel ergab still 0 Auftraege (wie 'keine Luecken') -> jetzt Exit 2.
    fehlt = tmp_path / "gibtesnicht"
    assert root_present(str(fehlt)) is False
    assert _main(["prog", str(fehlt)]) == 2
