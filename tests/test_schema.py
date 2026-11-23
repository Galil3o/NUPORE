from pathlib import Path

import yaml

SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "graph-schema.yaml"


def _load():
    return yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))


def test_schema_hat_alle_typen():
    schema = _load()

    assert set(schema["node_types"]) == {
        "decision",
        "argument",
        "argument_structure",
        "legal_provision",
        "inconsistency",
        "case_file",
        "fact_check",
        "brief",
        "court",
    }

    erwartete_kanten = {
        "appeal_to",
        "parent_court",
        "constitutional_complaint_against",
        "referral_to",
        "component_of",
        "applies_to",
        "provision_version",
        "successor",
        "occurrence",
    }
    assert erwartete_kanten <= set(schema["edge_types"])


def test_jeder_knotentyp_hat_pflichtfelder():
    schema = _load()
    for type, spec in schema["node_types"].items():
        assert "required_fields" in spec, f"{type} ohne required_fields"
        assert "id" in spec["required_fields"], f"{type}: id muss Pflichtfeld sein"
        assert "type" in spec["required_fields"], f"{type}: type muss Pflichtfeld sein"
