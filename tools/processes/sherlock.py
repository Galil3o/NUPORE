"""Sherlock -- proaktive Beweissicherung & Faktencheck (D13, R-013; projektneutral).

Graph-interner Prozess (D48): findet BELEGLUECKEN (factcheck-Knoten mit strittiger,
ungeprüfter/unbelegter Behauptung) und erzeugt pro Luecke einen Rechercheauftrag mit
EXPLIZITEM Suchraum + Abbruchkriterium (R-013). Die Websuche laeuft AUSSERHALB
(externe Fetch-/Such-Schicht, von der konsumierenden Instanz bereitgestellt); Sherlock
plant und nimmt das Ergebnis strukturiert auf -- inklusive
stuetzender UND widersprechender Quellen und ERFOLGLOSER Suchlaeufe (ein erfolgloser
Lauf ist ein Befund, kein Nichts).

v0: Planung + Ergebnis-Schema (kein Live-Fetch, kein Rueckschreiben).

CLI: python -m tools.processes.sherlock <graph-root>
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from tools.graph.node import Node, iter_nodes

_UNBEKANNT = "unbekannt"
# Beispiel-Suchraum (deutsche Rechts-Schicht; bewusste oeffentliche Illustration, kein
# Inhalt) -- ueber plane(suchraum=..., abbruch=...) ersetzbar/konfigurierbar.
_DEFAULT_SUCHRAUM = (
    "amtlich (BAG/NRW-Justiz/gesetze-im-internet) -> "
    "sekundaer (dejure/openJur/ra-kotz) -> tertiaer (Kommentar/Aufsatz)"
)
_DEFAULT_ABBRUCH = "Beleg gefunden ODER Suchraum erschoepft ODER max_quellen(=10) geprueft"


def _vorhanden(wert) -> bool:
    if wert is None:
        return False
    if isinstance(wert, str):
        s = wert.strip()
        return s != "" and s != _UNBEKANNT
    return True


@dataclass
class Rechercheauftrag:
    auftrag_id: str
    factcheck_id: str
    fall: str
    behauptung: str
    suchraum: str = _DEFAULT_SUCHRAUM
    abbruchkriterium: str = _DEFAULT_ABBRUCH
    status: str = "offen"


@dataclass
class Befund:
    """Strukturierte Aufnahme eines Suchlaufs (nach dem Cube-Fetch zu fuellen).
    Gegenquellen und erfolglose Suchlaeufe sind eigene Slots (R-013)."""
    auftrag_id: str
    quellen_gefunden: list = field(default_factory=list)       # stuetzende Belege
    gegenquellen: list = field(default_factory=list)           # widersprechende
    erfolglose_suchlaeufe: list = field(default_factory=list)  # wo nichts kam (Befund!)
    ergebnis: str = "offen"   # belegt | widerlegt | offen


def _braucht_recherche(n: Node) -> bool:
    """Eine strittige Behauptung ohne Bewertung ODER ohne Beleg ist eine Luecke."""
    if not _vorhanden(n.felder.get("behauptung")):
        return False
    bewertet = _vorhanden(n.felder.get("bewertung"))
    belegt = _vorhanden(n.felder.get("beweis_drive"))
    return not (bewertet and belegt)


def plane(graph_root: str, suchraum: str = _DEFAULT_SUCHRAUM,
          abbruch: str = _DEFAULT_ABBRUCH) -> list[Rechercheauftrag]:
    """Plant Rechercheauftraege fuer alle Belegluecken. `suchraum`/`abbruch` sind
    konfigurierbar (die Defaults sind eine Beispiel-Schicht, kein Engine-Zwang)."""
    auftraege = []
    for n in iter_nodes(graph_root):
        if n.typ != "factcheck" or not _braucht_recherche(n):
            continue
        auftraege.append(Rechercheauftrag(
            auftrag_id=f"RA::{n.id}",
            factcheck_id=n.id,
            fall=str(n.felder.get("fall", "")),
            behauptung=str(n.felder.get("behauptung", "")),
            suchraum=suchraum,
            abbruchkriterium=abbruch,
        ))
    return sorted(auftraege, key=lambda a: a.auftrag_id)


def leerer_befund(a: Rechercheauftrag) -> Befund:
    return Befund(auftrag_id=a.auftrag_id)


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Nutzung: python -m tools.processes.sherlock <graph-root>", file=sys.stderr)
        return 2
    auftraege = plane(argv[1])
    print(f"Sherlock-Rechercheplan: {len(auftraege)} offene Belegluecke(n)")
    for a in auftraege:
        print(f"  {a.auftrag_id} [{a.fall}] Behauptung: {a.behauptung}")
        print(f"      Suchraum: {a.suchraum}")
        print(f"      Abbruch:  {a.abbruchkriterium}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
