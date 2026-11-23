"""Index-Generator + Sync-Check (config/07).

Indizes sind abgeleitete Build-Artefakte, keine handgepflegten Dateien. Sie
werden aus den Knoten erzeugt und bei jedem Merge regeneriert; der Sync-Check
blockiert driftende Indizes im PR.

CLI:
  python -m nupore.graph.build_index --write <root>   schreibt <root>/_index/*.md
  python -m nupore.graph.build_index --check <root>   Exit 0 (synchron) / 1 (Drift)
"""

from __future__ import annotations

import sys
from pathlib import Path

from nupore.graph.node import iter_nodes

# name -> (Knotentyp, Spaltentitel, Feld-Extraktor je Knoten)
_INDEXES = {
    "decisions": ("decision", ["id", "court", "date", "docket_no"]),
    "arguments": ("argument", ["id", "kind", "origin", "citation"]),
    "argument_structures": ("argument_structure", ["id", "concept"]),
}

# Handgepflegte Nicht-Index-Dateien im _index/ (z. B. README) sind kein
# generiertes Artefakt und zaehlen nicht als Drift.
_INDEX_ALLOWED_EXTRA = {"README.md"}


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(nodes, spalten) -> str:
    header = "| " + " | ".join(spalten) + " |"
    separator = "|" + "|".join(["---"] * len(spalten)) + "|"
    rows = [header, separator]
    for n in sorted(nodes, key=lambda x: x.id):
        rows.append("| " + " | ".join(_cell(n.fields.get(s)) for s in spalten) + " |")
    return "\n".join(rows) + "\n"


def build_indexes(root: str) -> dict[str, str]:
    nodes = list(iter_nodes(root))
    result = {}
    for name, (type, spalten) in _INDEXES.items():
        matching = [n for n in nodes if n.type == type]
        result[name] = _table(matching, spalten)
    return result


def write_indexes(root: str) -> list[str]:
    target = Path(root) / "_index"
    target.mkdir(parents=True, exist_ok=True)
    geschrieben = []
    for name, content in build_indexes(root).items():
        p = target / f"{name}.md"
        p.write_text(content, encoding="utf-8")
        geschrieben.append(str(p))
    return geschrieben


def check_index_sync(root: str) -> bool:
    target = Path(root) / "_index"
    indizes = build_indexes(root)
    for name, content in indizes.items():
        p = target / f"{name}.md"
        if not p.exists() or p.read_text(encoding="utf-8") != content:
            return False
    # Extra-Datei-Check: eine verwaiste/umbenannte Index-Datei ist ebenso Drift
    # wie eine fehlende -- sonst ueberlebt ein stale Index die Regeneration
    # unbemerkt. Handgepflegte Zusatzdateien (README) bleiben erlaubt.
    if target.exists():
        erlaubt = {f"{name}.md" for name in indizes} | _INDEX_ALLOWED_EXTRA
        fremd = {p.name for p in target.glob("*.md")} - erlaubt
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
    for name, content in build_indexes(root).items():
        print(f"## {name}\n{content}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
