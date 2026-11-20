"""Index-Generator + Sync-Check (config/07).

Indizes sind abgeleitete Build-Artefakte, keine handgepflegten Dateien. Sie
werden aus den Knoten erzeugt und bei jedem Merge regeneriert; der Sync-Check
blockiert driftende Indizes im PR.

CLI:
  python -m tools.graph.build_index --write <root>   schreibt <root>/_index/*.md
  python -m tools.graph.build_index --check <root>   Exit 0 (synchron) / 1 (Drift)
"""

from __future__ import annotations

import sys
from pathlib import Path

from tools.graph.node import iter_nodes

# name -> (Knotentyp, Spaltentitel, Feld-Extraktor je Knoten)
_INDizes = {
    "urteile": ("entscheidung", ["id", "gericht", "datum", "az"]),
    "argumente": ("argument", ["id", "art", "herkunft", "fundstelle"]),
    "argumentstrukturen": ("argumentstruktur", ["id", "konzept"]),
}

# Handgepflegte Nicht-Index-Dateien im _index/ (z. B. README) sind kein
# generiertes Artefakt und zaehlen nicht als Drift.
_INDEX_ERLAUBTE_ZUSATZ = {"README.md"}


def _zelle(wert) -> str:
    if wert is None:
        return ""
    return str(wert).replace("|", "\\|").replace("\n", " ")


def _tabelle(nodes, spalten) -> str:
    kopf = "| " + " | ".join(spalten) + " |"
    trenner = "|" + "|".join(["---"] * len(spalten)) + "|"
    zeilen = [kopf, trenner]
    for n in sorted(nodes, key=lambda x: x.id):
        zeilen.append("| " + " | ".join(_zelle(n.felder.get(s)) for s in spalten) + " |")
    return "\n".join(zeilen) + "\n"


def build_indexes(root: str) -> dict[str, str]:
    nodes = list(iter_nodes(root))
    ergebnis = {}
    for name, (typ, spalten) in _INDizes.items():
        passende = [n for n in nodes if n.typ == typ]
        ergebnis[name] = _tabelle(passende, spalten)
    return ergebnis


def write_indexes(root: str) -> list[str]:
    ziel = Path(root) / "_index"
    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for name, inhalt in build_indexes(root).items():
        p = ziel / f"{name}.md"
        p.write_text(inhalt, encoding="utf-8")
        geschrieben.append(str(p))
    return geschrieben


def check_index_sync(root: str) -> bool:
    ziel = Path(root) / "_index"
    indizes = build_indexes(root)
    for name, inhalt in indizes.items():
        p = ziel / f"{name}.md"
        if not p.exists() or p.read_text(encoding="utf-8") != inhalt:
            return False
    # Extra-Datei-Check: eine verwaiste/umbenannte Index-Datei ist ebenso Drift
    # wie eine fehlende -- sonst ueberlebt ein stale Index die Regeneration
    # unbemerkt. Handgepflegte Zusatzdateien (README) bleiben erlaubt.
    if ziel.exists():
        erlaubt = {f"{name}.md" for name in indizes} | _INDEX_ERLAUBTE_ZUSATZ
        fremd = {p.name for p in ziel.glob("*.md")} - erlaubt
        if fremd:
            return False
    return True


def _main(argv: list[str]) -> int:
    flags = [a for a in argv[1:] if a.startswith("--")]
    roots = [a for a in argv[1:] if not a.startswith("--")]
    root = roots[0] if roots else "graph"
    if "--write" in flags:
        for p in write_indexes(root):
            print(f"geschrieben: {p}")
        return 0
    if "--check" in flags:
        if check_index_sync(root):
            print("OK: Indizes synchron.")
            return 0
        print("Index-Drift: regeneriere mit --write.", file=sys.stderr)
        return 1
    for name, inhalt in build_indexes(root).items():
        print(f"## {name}\n{inhalt}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
