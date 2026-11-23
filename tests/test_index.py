import shutil
from pathlib import Path

from nupore.graph.build_index import build_indexes, check_index_sync, write_indexes
from nupore.graph.node import iter_nodes

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID = str(FIXTURES / "graph")


def test_index_hat_drei_tabellen():
    assert set(build_indexes(VALID)) == {"decisions", "arguments", "argument_structures"}


def test_index_enthaelt_jede_entscheidung():
    idx = build_indexes(VALID)["decisions"]
    entscheidungen = [n.id for n in iter_nodes(VALID) if n.type == "decision"]
    assert entscheidungen
    for eid in entscheidungen:
        assert eid in idx


def test_sync_true_nach_write(tmp_path):
    dst = tmp_path / "graph"
    shutil.copytree(VALID, dst)
    write_indexes(str(dst))
    assert check_index_sync(str(dst)) is True


def test_sync_false_bei_drift(tmp_path):
    dst = tmp_path / "graph"
    shutil.copytree(VALID, dst)
    write_indexes(str(dst))
    new = dst / "SUB1_CASE_LAW" / "entscheidungen" / "ArbG-X__2099-01-01__9-Ca-9-99.md"
    new.write_text(
        '---\nid: ArbG-X__2099-01-01__9-Ca-9-99\ntype: decision\n'
        'origin: own_case:X\ncourt: ArbG-X\ndate: "2099-01-01"\n---\n',
        encoding="utf-8",
    )
    assert check_index_sync(str(dst)) is False


def test_sync_false_bei_extra_index_datei(tmp_path):
    # Eine verwaiste/umbenannte Index-Datei im _index/ ist Drift, auch wenn alle
    # generierten Indizes synchron sind (Extra-Datei-Check).
    dst = tmp_path / "graph"
    shutil.copytree(VALID, dst)
    write_indexes(str(dst))
    (dst / "_index" / "zombie.md").write_text("| x |\n", encoding="utf-8")
    assert check_index_sync(str(dst)) is False


def test_readme_im_index_ist_kein_drift(tmp_path):
    # Handgepflegte README im _index/ ist kein generiertes Artefakt -> kein Drift
    # (sonst wuerde der echte graph/_index/README.md das Merge-Gate brechen).
    dst = tmp_path / "graph"
    shutil.copytree(VALID, dst)
    write_indexes(str(dst))
    (dst / "_index" / "README.md").write_text("# Indizes\n", encoding="utf-8")
    assert check_index_sync(str(dst)) is True
