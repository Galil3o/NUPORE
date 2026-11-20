from tools.graph.derive import (
    derive_fein_rang,
    derive_verbindlichkeit,
    ist_schwebend,
)


def test_norm_ist_verbindlich():
    assert derive_verbindlichkeit({"quelle_typ": "amtlicher_normtext"}) == "verbindlich"


def test_apex_rechtskraeftig_ist_verbindlich():
    f = {"quelle_typ": "amtliche_rechtsprechung", "rechtskraft": "rechtskraeftig"}
    assert derive_verbindlichkeit(f, gericht_id="BAG") == "verbindlich"
    assert derive_verbindlichkeit(f, gericht_rang=1) == "verbindlich"  # Rang 1 = Apex


def test_apex_ohne_rechtskraft_schwebend_und_nicht_verbindlich():
    f = {"quelle_typ": "amtliche_rechtsprechung", "rechtskraft": "nicht_rechtskraeftig"}
    assert derive_verbindlichkeit(f, gericht_id="BVerfG") == "nicht_verbindlich"
    assert ist_schwebend(f, gericht_id="BVerfG") is True


def test_apex_unbekannte_rechtskraft_konservativ_schwebend():
    f = {"quelle_typ": "amtliche_rechtsprechung"}  # rechtskraft fehlt -> wie unbekannt
    assert derive_verbindlichkeit(f, gericht_id="BAG") == "nicht_verbindlich"
    assert ist_schwebend(f, gericht_id="BAG") is True


def test_instanzgericht_nicht_verbindlich_mit_fein_rang():
    f = {"quelle_typ": "amtliche_rechtsprechung", "rechtskraft": "rechtskraeftig"}
    # Nicht-Apex (z. B. LAG, rang 2) -> nicht_verbindlich, Fein-Rang Instanz (10).
    assert derive_verbindlichkeit(f, gericht_rang=2) == "nicht_verbindlich"
    assert derive_fein_rang(f, gericht_rang=2) == 10


def test_kommentar_fein_rang_und_nicht_verbindlich():
    f = {"quelle_typ": "kommentar"}
    assert derive_verbindlichkeit(f) == "nicht_verbindlich"
    assert derive_fein_rang(f) == 30


def test_verbindliche_quelle_hat_keinen_fein_rang():
    assert derive_fein_rang({"quelle_typ": "amtlicher_normtext"}) is None
