from nupore.graph.derive import (
    derive_fine_rank,
    derive_authority,
    is_pending,
)


def test_norm_ist_verbindlich():
    assert derive_authority({"source_type": "official_statute_text"}) == "binding"


def test_apex_rechtskraeftig_ist_verbindlich():
    f = {"source_type": "official_case_law", "finality": "final"}
    assert derive_authority(f, gericht_id="BAG") == "binding"
    assert derive_authority(f, gericht_rang=1) == "binding"  # Rang 1 = Apex


def test_apex_ohne_rechtskraft_schwebend_und_nicht_verbindlich():
    f = {"source_type": "official_case_law", "finality": "not_final"}
    assert derive_authority(f, gericht_id="BVerfG") == "non_binding"
    assert is_pending(f, gericht_id="BVerfG") is True


def test_apex_unbekannte_rechtskraft_konservativ_schwebend():
    f = {"source_type": "official_case_law"}  # finality fehlt -> wie unknown
    assert derive_authority(f, gericht_id="BAG") == "non_binding"
    assert is_pending(f, gericht_id="BAG") is True


def test_instanzgericht_nicht_verbindlich_mit_fein_rang():
    f = {"source_type": "official_case_law", "finality": "final"}
    # Nicht-Apex (z. B. LAG, rank 2) -> non_binding, Fein-Rang Instanz (10).
    assert derive_authority(f, gericht_rang=2) == "non_binding"
    assert derive_fine_rank(f, gericht_rang=2) == 10


def test_kommentar_fein_rang_und_nicht_verbindlich():
    f = {"source_type": "commentary"}
    assert derive_authority(f) == "non_binding"
    assert derive_fine_rank(f) == 30


def test_verbindliche_quelle_hat_keinen_fein_rang():
    assert derive_fine_rank({"source_type": "official_statute_text"}) is None
