"""Watson -- Nachweis-Deckungspruefung bei Nutzung (D16, R-013; projektneutral).

Graph-interner Read-Prozess (D48): prueft je NUTZUNG (Schriftsatz) fuer jedes dort
`occurrence`de Argument den Deckungsstatus:

  - directly_supported      : eigene zitierfaehige Quelle (source_type + Locator)
  - indirectly_supported: keine eigene Quelle, aber von einem direkt belegten
                         Argument via supports/specifies getragen
  - offen              : benutzt, aber unbelegt

plus Overlay `contested` (eine `contradicts`-Kante zeigt auf das Argument).

Das ist eine Deckungs-SICHT fuers Retrieval, keine Fachlogik-Entscheidung. v0
schreibt NICHT zurueck (reiner Report); die schreibende Anreicherung ist ein
spaeterer Schritt. Die Quellen-LIVENESS (tatsaechlicher Abruf) bleibt ausserhalb
(externe Fetch-Schicht der Instanz) -- hier zaehlt nur Praesenz + Locator-Form.

CLI: python -m nupore.processes.watson <graph-root> <brief-id>
Exit 0 immer (Report, kein Gate).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from nupore.graph.node import Node, iter_nodes

_UNKNOWN = "unknown"
_SUPPORT_EDGES = ("supports", "specifies")
# source_types, deren Locator eine URL ist (sonst `citation`, druck-nativ).
_URL_LOCATOR_TYPES = {
    "official_case_law", "official_statute_text", "parliamentary_document",
    "legislative_materials", "encyclopedia", "professional_news", "press_release",
}


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        s = value.strip()
        return s != "" and s != _UNKNOWN
    return True


def _directly_supported(n: Node) -> bool:
    qt = n.fields.get("source_type")
    if not isinstance(qt, str) or not _present(qt):
        return False
    locator = n.fields.get("source_url") if qt in _URL_LOCATOR_TYPES else n.fields.get("citation")
    # Nur ein String ist ein formgueltiger Locator -- eine Liste als citation
    # darf NICHT als directly_supported zaehlen (Komplett-Review 2026-11-20).
    return isinstance(locator, str) and _present(locator)


def _targets(n: Node, edge: str) -> list[str]:
    try:
        return n.edge_targets(edge)
    except ValueError:
        return []  # malformte Kante bricht den Prozess nicht ab (Validator meldet sie)


@dataclass
class Coverage:
    argument_id: str
    core_statement: str
    status: str          # directly_supported | indirectly_supported | offen
    contested: bool
    reason: str


def check(graph_root: str, brief_id: str) -> list[Coverage]:
    """Deckungsbericht fuer alle Argumente, die in `brief_id` occurrence."""
    args = [n for n in iter_nodes(graph_root) if n.type == "argument"]
    belegt = {n.id for n in args if _directly_supported(n)}

    getragen_von: dict[str, set[str]] = {}
    bestritten_ids: set[str] = set()
    for n in args:
        for edge in _SUPPORT_EDGES:
            for target in _targets(n, edge):
                getragen_von.setdefault(target, set()).add(n.id)
        for target in _targets(n, "contradicts"):
            bestritten_ids.add(target)

    result: list[Coverage] = []
    for n in args:
        if brief_id not in _targets(n, "occurrence"):
            continue
        if n.id in belegt:
            status, reason = "directly_supported", "eigene zitierfaehige Quelle (source_type + Locator)"
        elif belegt & getragen_von.get(n.id, set()):
            traeger = sorted(belegt & getragen_von[n.id])
            status, reason = "indirectly_supported", "getragen von " + ", ".join(traeger)
        else:
            status, reason = "offen", "benutzt, aber keine eigene/mittelbare Quelle"
        result.append(Coverage(n.id, str(n.fields.get("core_statement", "")),
                                status, n.id in bestritten_ids, reason))
    return sorted(result, key=lambda d: d.argument_id)


def _format(deckungen: list[Coverage], brief_id: str) -> str:
    rows = [f"Watson-Deckungsbericht: {brief_id}"]
    if not deckungen:
        rows.append("  (keine vorkommenden Argumente gefunden)")
    for d in deckungen:
        flag = " [BESTRITTEN]" if d.contested else ""
        rows.append(f"  {d.argument_id}: {d.status}{flag} -- {d.reason}")
    offen = sum(1 for d in deckungen if d.status == "offen")
    contested = sum(1 for d in deckungen if d.contested)
    rows.append(f"Summe: {len(deckungen)} benutzt, {offen} offen, {contested} contested.")
    return "\n".join(rows)


def brief_known(graph_root: str, brief_id: str) -> bool:
    """True, wenn `brief_id` ueberhaupt als brief-Knoten existiert.
    Trennt einen UNBEKANNTEN Schriftsatz von einem bekannten, aber leeren -- beide
    ergaeben sonst denselben leeren DeadlineReport (Komplett-Review 2026-11-20)."""
    return any(n.id == brief_id and n.type == "brief"
               for n in iter_nodes(graph_root))


def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Nutzung: python -m nupore.processes.watson <graph-root> <brief-id>",
              file=sys.stderr)
        return 2
    graph_root, brief_id = argv[1], argv[2]
    if not brief_known(graph_root, brief_id):
        print(f"Unbekannter Schriftsatz: {brief_id!r} (kein brief-Knoten gefunden)",
              file=sys.stderr)
        return 2
    print(_format(check(graph_root, brief_id), brief_id))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
