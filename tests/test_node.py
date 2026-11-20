from pathlib import Path

import pytest
import yaml

from tools.graph.node import Node, iter_nodes, load_node

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "graph"
SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "graph-schema.yaml"


def test_laedt_frontmatter_und_body():
    n = load_node(str(FIXTURES / "SUB4_NORMS" / "SGB-IX_164_nF.md"))
    assert isinstance(n, Node)
    assert n.id == "SGB-IX_164_nF"
    assert n.typ == "norm"
    assert n.felder["fassung"] == "nF"
    assert "nachfolger" not in n.kanten  # nF ist Nachfolger, zeigt nicht zurueck


def test_kante_wird_aus_frontmatter_erkannt():
    n = load_node(str(FIXTURES / "SUB4_NORMS" / "SGB-IX_81_aF.md"))
    assert n.kanten_ziele("nachfolger") == ["SGB-IX_164_nF"]


def test_vorkommen_kante_mit_attributen():
    n = load_node(str(FIXTURES / "SUB2_CASE_ARGUMENTS" / "ARG_KENNTNIS_ZUGANG.md"))
    assert "SS_ANSPRUCH" in n.kanten_ziele("vorkommen")


def test_malformed_frontmatter_wirft():
    with pytest.raises(ValueError):
        load_node(str(FIXTURES / "_malformed.md"))


def test_iter_nodes_ueberspringt_readme_und_unterstrich():
    ids = {n.id for n in iter_nodes(str(FIXTURES))}
    assert "SGB-IX_164_nF" in ids
    assert "ARG_EINLADUNG_GESAMT" in ids
    # _malformed.md beginnt mit "_" und darf nicht als Knoten auftauchen
    assert all("malformed" not in i.lower() for i in ids)


def test_alle_fixtures_haben_pflichtfelder():
    schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    for n in iter_nodes(str(FIXTURES)):
        pflicht = schema["node_types"][n.typ]["pflichtfelder"]
        fehlend = [f for f in pflicht if f not in n.felder]
        assert not fehlend, f"{n.id} ({n.typ}) fehlen Pflichtfelder: {fehlend}"
