"""Sherlock -- proaktive Beweissicherung & Faktencheck (D13, R-013; projektneutral).

Graph-interner Prozess (D48): findet BELEGLUECKEN (fact_check-Knoten mit strittiger,
ungeprüfter/unbelegter Behauptung) und erzeugt pro Luecke einen ResearchRequest mit
EXPLIZITEM Suchraum + Abbruchkriterium (R-013). Die Websuche laeuft AUSSERHALB
(externe Fetch-/Such-Schicht, von der konsumierenden Instanz bereitgestellt); Sherlock
plant und nimmt das Ergebnis strukturiert auf -- inklusive
stuetzender UND widersprechender Quellen und ERFOLGLOSER Suchlaeufe (ein erfolgloser
Lauf ist ein SearchFinding, kein Nichts).

v0: Planung + Ergebnis-Schema (kein Live-Fetch, kein Rueckschreiben).

CLI: python -m nupore.processes.sherlock <graph-root>
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from nupore.graph.node import Node, iter_nodes

_UNKNOWN = "unknown"
# Beispiel-Suchraum (deutsche Rechts-Schicht; bewusste oeffentliche Illustration, kein
# Inhalt) -- ueber plan(search_scope=..., abbruch=...) ersetzbar/konfigurierbar.
_DEFAULT_SEARCH_SCOPE = (
    "amtlich (BAG/NRW-Justiz/gesetze-im-internet) -> "
    "sekundaer (dejure/openJur/ra-kotz) -> tertiaer (Kommentar/Aufsatz)"
)
_DEFAULT_STOP = "Beleg gefunden ODER Suchraum erschoepft ODER max_quellen(=10) geprueft"


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        s = value.strip()
        return s != "" and s != _UNKNOWN
    return True


@dataclass
class ResearchRequest:
    request_id: str
    fact_check_id: str
    case: str
    assertion: str
    search_scope: str = _DEFAULT_SEARCH_SCOPE
    stop_condition: str = _DEFAULT_STOP
    status: str = "offen"


@dataclass
class SearchFinding:
    """Strukturierte Aufnahme eines Suchlaufs (nach dem Cube-Fetch zu fuellen).
    Gegenquellen und erfolglose Suchlaeufe sind eigene Slots (R-013)."""
    request_id: str
    sources_found: list = field(default_factory=list)       # stuetzende Belege
    counter_sources: list = field(default_factory=list)           # widersprechende
    empty_searches: list = field(default_factory=list)  # wo nichts kam (SearchFinding!)
    result: str = "offen"   # belegt | widerlegt | offen


def _needs_research(n: Node) -> bool:
    """Eine strittige Behauptung ohne Bewertung ODER ohne Beleg ist eine Luecke."""
    if not _present(n.fields.get("assertion")):
        return False
    bewertet = _present(n.fields.get("assessment"))
    belegt = _present(n.fields.get("evidence_drive"))
    return not (bewertet and belegt)


def plan(graph_root: str, search_scope: str = _DEFAULT_SEARCH_SCOPE,
          abbruch: str = _DEFAULT_STOP) -> list[ResearchRequest]:
    """Plant Rechercheauftraege fuer alle Belegluecken. `search_scope`/`abbruch` sind
    konfigurierbar (die Defaults sind eine Beispiel-Schicht, kein Engine-Zwang)."""
    auftraege = []
    for n in iter_nodes(graph_root):
        if n.type != "fact_check" or not _needs_research(n):
            continue
        auftraege.append(ResearchRequest(
            request_id=f"RA::{n.id}",
            fact_check_id=n.id,
            case=str(n.fields.get("case", "")),
            assertion=str(n.fields.get("assertion", "")),
            search_scope=search_scope,
            stop_condition=abbruch,
        ))
    return sorted(auftraege, key=lambda a: a.request_id)


def empty_finding(a: ResearchRequest) -> SearchFinding:
    return SearchFinding(request_id=a.request_id)


def root_present(graph_root: str) -> bool:
    """True, wenn die Graph-Wurzel existiert. Eine fehlende Wurzel ergibt sonst
    stillschweigend null Auftraege -- ununterscheidbar von 'keine Luecken'
    (Komplett-Review 2026-11-20)."""
    return Path(graph_root).is_dir()


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Nutzung: python -m nupore.processes.sherlock <graph-root>", file=sys.stderr)
        return 2
    if not root_present(argv[1]):
        print(f"Graph-Wurzel fehlt oder ist kein Verzeichnis: {argv[1]!r}", file=sys.stderr)
        return 2
    auftraege = plan(argv[1])
    print(f"Sherlock-Rechercheplan: {len(auftraege)} offene Belegluecke(n)")
    for a in auftraege:
        print(f"  {a.request_id} [{a.case}] Behauptung: {a.assertion}")
        print(f"      Suchraum: {a.search_scope}")
        print(f"      Abbruch:  {a.stop_condition}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
