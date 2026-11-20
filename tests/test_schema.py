from pathlib import Path

import yaml

SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "graph-schema.yaml"


def _load():
    return yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))


def test_schema_hat_alle_typen():
    schema = _load()

    assert set(schema["node_types"]) == {
        "entscheidung",
        "argument",
        "argumentstruktur",
        "norm",
        "inkonsistenz",
        "handakte",
        "factcheck",
        "schriftsatz",
        "gericht",
    }

    erwartete_kanten = {
        "instanz_weiter",
        "instanz_ueber",
        "verfassungsbeschwerde_gegen",
        "vorlage_nach",
        "komponente_von",
        "uebertraegt_auf",
        "norm_fassung",
        "nachfolger",
        "vorkommen",
    }
    assert erwartete_kanten <= set(schema["edge_types"])


def test_jeder_knotentyp_hat_pflichtfelder():
    schema = _load()
    for typ, spec in schema["node_types"].items():
        assert "pflichtfelder" in spec, f"{typ} ohne pflichtfelder"
        assert "id" in spec["pflichtfelder"], f"{typ}: id muss Pflichtfeld sein"
        assert "typ" in spec["pflichtfelder"], f"{typ}: typ muss Pflichtfeld sein"
