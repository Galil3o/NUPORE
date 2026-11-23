from pathlib import Path

from nupore.graph.validate import validate

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID = str(FIXTURES / "graph")


def _codes(unterordner):
    return {v.code for v in validate(str(FIXTURES / "invalid" / unterordner))}


def test_valide_fixtures_ohne_verstoss():
    assert validate(VALID) == []


def test_findet_doppelte_id():
    assert "DUP_ID" in _codes("dup_id")


def test_findet_tote_kante():
    assert "DEAD_EDGE" in _codes("dead_edge")


def test_atomares_argument_ohne_fundstelle():
    assert "NO_CITATION" in _codes("no_fundstelle")


def test_fehlende_herkunft():
    assert "NO_ORIGIN" in _codes("no_herkunft")


def test_norm_nicht_aufloesbar():
    assert "PROVISION_UNRESOLVED" in _codes("norm_unresolved")


def test_nachfolger_mit_luecke():
    assert "SUCCESSOR_TEMPORAL" in _codes("nachfolger_luecke")


def test_fehlendes_pflichtfeld():
    assert "MISSING_FIELD" in _codes("missing_field")


def test_unbekannter_typ():
    assert "UNKNOWN_TYPE" in _codes("unknown_typ")


def test_ungueltiger_art_wert():
    assert "INVALID_KIND" in _codes("invalid_art")


def test_unbekanntes_feld_umlaut_kante():
    assert "UNKNOWN_FIELD" in _codes("unknown_field")


def test_norm_fassung_ausserhalb_geltungszeitraum():
    assert "PROVISION_TEMPORAL" in _codes("norm_temporal")


def test_kaputtes_datum_meldet_statt_crash():
    # darf nicht werfen
    assert "BAD_DATE" in _codes("bad_date")


# --- R-002: Domaenen-Constraints der Kanten -------------------------------

def test_kante_auf_falschem_quelltyp():
    assert "EDGE_SOURCE" in _codes("edge_source")


def test_kante_auf_falschen_zieltyp():
    assert "EDGE_TARGET" in _codes("edge_target")


def test_gericht_feld_nicht_aufloesbar():
    assert "COURT_UNRESOLVED" in _codes("gericht_unresolved")


# --- R-003: Praesenz != gueltiger Inhalt ----------------------------------

def test_pflichtfeld_null():
    assert "NULL_FIELD" in _codes("null_field")


def test_leere_id():
    assert "EMPTY_ID" in _codes("empty_id")


def test_kante_kein_list_meldet_statt_crash():
    # darf nicht werfen, Skalar-Kante -> BAD_EDGE_SHAPE
    assert "BAD_EDGE_SHAPE" in _codes("bad_edge_shape")


def test_ladefehler_bricht_lauf_nicht_ab():
    codes = _codes("load_error")
    assert "LOAD_ERROR" in codes  # doppelter YAML-Key erkannt
    # Der gueltige Nachbar wurde trotzdem geladen (kein Abbruch) -> keine
    # Folgefehler aus ihm.


# --- Datum / Intervall ----------------------------------------------------

def test_basisdatum_ist_bad_date():
    # 20200101 waere ab Python 3.11 ein gueltiges date.fromisoformat
    assert "BAD_DATE" in _codes("bad_date_basic")


def test_invertiertes_geltungsintervall():
    assert "BAD_INTERVAL" in _codes("bad_interval")


# --- R-004: Wurzel-Handhabung + Ausschlussregel ---------------------------

def test_fehlende_wurzel_meldet_no_root():
    verstoesse = validate(str(FIXTURES / "gibt_es_nicht"))
    assert [v.code for v in verstoesse] == ["NO_ROOT"]


def test_leere_aber_existierende_wurzel_ist_ok(tmp_path):
    assert validate(str(tmp_path)) == []


def test_unterstrich_datei_wird_ignoriert():
    # _malformed.md wird komplett uebersprungen -> kein LOAD_ERROR, sauber.
    assert validate(str(FIXTURES / "underscore_ok")) == []


# --- Kontrollierte Vokabulare + Originaerquellen --------------------------

def test_ungueltiger_ausgang():
    assert "INVALID_OUTCOME" in _codes("invalid_ausgang")


def test_ungueltiger_quelle_typ():
    assert "INVALID_SOURCE_TYPE" in _codes("invalid_quelle_typ")


def test_ungueltige_aussage_funktion():
    assert "INVALID_STATEMENT_FUNCTION" in _codes("invalid_aussage_funktion")


def test_amtliche_quelle_ohne_url():
    assert "MISSING_SOURCE_URL" in _codes("missing_quelle_url")


def test_ungueltiger_vorkommen_status():
    assert "INVALID_OCCURRENCE_STATUS" in _codes("invalid_vorkommen_status")


# --- Norm-Temporal-Bindung ueber provision_cutoff ----------------------------

def test_norm_stichtag_rebindet_datum():
    # date liegt ausserhalb, provision_cutoff innerhalb der Geltung:
    # der Stichtag ist massgeblich -> kein PROVISION_TEMPORAL.
    assert "PROVISION_TEMPORAL" not in _codes("norm_stichtag_ok")


def test_norm_stichtag_ausserhalb_meldet_temporal():
    # date liegt innerhalb, provision_cutoff ausserhalb der Geltung:
    # der Stichtag ist massgeblich -> PROVISION_TEMPORAL.
    assert "PROVISION_TEMPORAL" in _codes("norm_stichtag_bad")


# --- Quellen-Zweiteilung, Wertigkeit, Reichweite (Praezedenz-Nutzung) ------

def test_neue_quellentypen_und_praezedenz_valide():
    # commentary (SUB6, druck-nativ, kein url-Zwang) + supports + precedent_use
    # mit gueltiger Reichweite -> sauber.
    assert validate(str(FIXTURES / "valid_erweiterungen")) == []


def test_ungueltige_reichweite_stufe():
    assert "INVALID_REACH" in _codes("invalid_reichweite_stufe")


def test_praezedenz_quelle_unaufloesbar():
    assert "PRECEDENT_UNRESOLVED" in _codes("praezedenz_unresolved")


def test_ungueltige_rechtskraft():
    assert "INVALID_FINALITY" in _codes("invalid_rechtskraft")


# --- Runde 3: Validator-Haertung (D36) ------------------------------------

def test_listwert_in_quelle_typ_kein_absturz():
    # Liste statt String darf NICHT crashen (TypeError), sondern sauber melden.
    assert "INVALID_SOURCE_TYPE" in _codes("quelle_typ_listwert")


def test_praezedenz_eintrag_ohne_pflichtfelder():
    assert "PRECEDENT_INCOMPLETE" in _codes("praezedenz_unvollstaendig")


def test_praezedenz_unbekannt_marker_valide():
    # source/reach = 'unknown' ist ein gueltiger, ehrlicher Zustand (D35).
    assert validate(str(FIXTURES / "valid_unbekannt")) == []


def test_norm_stichtag_null_faellt_auf_datum():
    # null darf die Zeitpruefung nicht abschalten: Rueckfall auf date -> PROVISION_TEMPORAL.
    assert "PROVISION_TEMPORAL" in _codes("norm_stichtag_null_datum")


def test_listwert_in_art_kein_absturz():
    # Liste statt String bei `kind` ist unhashbar -> der Mengen-Test `in
    # _ARGUMENT_KINDS` warf TypeError und brach den GESAMTEN Lauf ab (Watcher-
    # SearchFinding BOFH-SGBIX-VALIDATOR-ART, validate.py:226 -- der letzte ungeguardte
    # Enum). Jetzt per `_is_enum` geguardt. Abnahme (exakt): INVALID_KIND UND die
    # Diagnose des zweiten fehlerhaften Knotens (NO_CITATION) im selben Lauf.
    codes = _codes("art_listwert")
    assert "INVALID_KIND" in codes
    assert "NO_CITATION" in codes


# --- Komplett-Review 2026-11-20: Typsicherheit (R-003-Familie) ---

def test_listwert_in_id_kein_absturz():
    # Listenwert fuer id ist unhashbar -> Map-Bildung warf TypeError und brach den
    # GESAMTEN Lauf ab. Jetzt: EMPTY_ID + der zweite fehlerhafte Knoten (NO_CITATION).
    codes = _codes("id_listwert")
    assert "EMPTY_ID" in codes
    assert "NO_CITATION" in codes


def test_listwert_in_gericht_kein_absturz():
    # Listenwert fuer court -> Mengen-Test warf TypeError. Jetzt COURT_UNRESOLVED.
    assert "COURT_UNRESOLVED" in _codes("gericht_listwert")


def test_vorkommen_leer_kein_absturz_und_incomplete():
    # occurrence: [{}] brach den Lauf ab (edge_targets warf). Jetzt strukturiert gemeldet.
    assert "OCCURRENCE_INCOMPLETE" in _codes("vorkommen_kaputt")


def test_listwert_in_fundstelle_ist_no_fundstelle():
    # Eine Liste als citation galt als "present" -> jetzt NO_CITATION (Formpruefung).
    assert "NO_CITATION" in _codes("fundstelle_listwert")


def test_ungueltiger_herkunft_praefix():
    # D5: der origin-Praefix wurde bisher nicht erzwungen.
    assert "INVALID_ORIGIN_PREFIX" in _codes("herkunft_praefix")
