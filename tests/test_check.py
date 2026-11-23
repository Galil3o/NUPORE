import shutil
import subprocess
from pathlib import Path

from nupore.graph.build_index import write_indexes

REPO = Path(__file__).resolve().parent.parent
VALID = Path(__file__).resolve().parent / "fixtures" / "graph"


def test_check_skript_gruen_auf_synthetischem_graph(tmp_path):
    # Engine-Test: haengt NICHT an Instanz-Inhalt (`graph/`), sondern baut sich einen
    # vollstaendigen Graph aus der synthetischen Fixture + generierten Indizes. So
    # laeuft nupore/check.sh (Validator + Index-Sync) in der Engine (NUPORE) wie in
    # jeder Instanz (DNA) gruen.
    g = tmp_path / "graph"
    shutil.copytree(VALID, g)
    write_indexes(str(g))  # Indizes erzeugen -> Index-Sync gruen
    r = subprocess.run(
        ["bash", "nupore/check.sh", str(g)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"


def test_check_skript_meldet_fehlende_wurzel(tmp_path):
    # Fehlender Graph-Root -> NO_ROOT -> Nicht-Null-Exit (sichtbarer Fehler statt
    # stillem Erfolg). Deckt die frueher court_instance-abhaengige Annahme sauber ab.
    fehlt = tmp_path / "gibt_es_nicht"
    r = subprocess.run(
        ["bash", "nupore/check.sh", str(fehlt)],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert r.returncode != 0
