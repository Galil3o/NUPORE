"""Watson -- Nachweis-Deckungspruefung bei Nutzung (D16, R-013; projektneutral).

Graph-interner Read-Prozess (D48): prueft je NUTZUNG (Schriftsatz) fuer jedes dort
`vorkommen`de Argument den Deckungsstatus:

  - direkt_belegt      : eigene zitierfaehige Quelle (quelle_typ + Locator)
  - mittelbar_gestuetzt: keine eigene Quelle, aber von einem direkt belegten
                         Argument via stuetzt/konkretisiert getragen
  - offen              : benutzt, aber unbelegt

plus Overlay `bestritten` (eine `widerspricht`-Kante zeigt auf das Argument).

Das ist eine Deckungs-SICHT fuers Retrieval, keine Fachlogik-Entscheidung. v0
schreibt NICHT zurueck (reiner Report); die schreibende Anreicherung ist ein
spaeterer Schritt. Die Quellen-LIVENESS (tatsaechlicher Abruf) bleibt ausserhalb
(externe Fetch-Schicht der Instanz) -- hier zaehlt nur Praesenz + Locator-Form.

CLI: python -m tools.processes.watson <graph-root> <schriftsatz-id>
Exit 0 immer (Report, kein Gate).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from tools.graph.node import Node, iter_nodes

_UNBEKANNT = "unbekannt"
_STUETZ_KANTEN = ("stuetzt", "konkretisiert")
# quelle_typen, deren Locator eine URL ist (sonst `fundstelle`, druck-nativ).
_URL_LOCATOR_TYPEN = {
    "amtliche_rechtsprechung", "amtlicher_normtext", "bundestagsdrucksache",
    "gesetzesmaterialien", "enzyklopaedie", "fachnews", "pressemitteilung",
}


def _vorhanden(wert) -> bool:
    if wert is None:
        return False
    if isinstance(wert, str):
        s = wert.strip()
        return s != "" and s != _UNBEKANNT
    return True


def _direkt_belegt(n: Node) -> bool:
    qt = n.felder.get("quelle_typ")
    if not isinstance(qt, str) or not _vorhanden(qt):
        return False
    locator = n.felder.get("quelle_url") if qt in _URL_LOCATOR_TYPEN else n.felder.get("fundstelle")
    return _vorhanden(locator)


def _ziele(n: Node, kante: str) -> list[str]:
    try:
        return n.kanten_ziele(kante)
    except ValueError:
        return []  # malformte Kante bricht den Prozess nicht ab (Validator meldet sie)


@dataclass
class Deckung:
    argument_id: str
    kernaussage: str
    status: str          # direkt_belegt | mittelbar_gestuetzt | offen
    bestritten: bool
    grund: str


def pruefe(graph_root: str, schriftsatz_id: str) -> list[Deckung]:
    """Deckungsbericht fuer alle Argumente, die in `schriftsatz_id` vorkommen."""
    args = [n for n in iter_nodes(graph_root) if n.typ == "argument"]
    belegt = {n.id for n in args if _direkt_belegt(n)}

    getragen_von: dict[str, set[str]] = {}
    bestritten_ids: set[str] = set()
    for n in args:
        for kante in _STUETZ_KANTEN:
            for ziel in _ziele(n, kante):
                getragen_von.setdefault(ziel, set()).add(n.id)
        for ziel in _ziele(n, "widerspricht"):
            bestritten_ids.add(ziel)

    ergebnis: list[Deckung] = []
    for n in args:
        if schriftsatz_id not in _ziele(n, "vorkommen"):
            continue
        if n.id in belegt:
            status, grund = "direkt_belegt", "eigene zitierfaehige Quelle (quelle_typ + Locator)"
        elif belegt & getragen_von.get(n.id, set()):
            traeger = sorted(belegt & getragen_von[n.id])
            status, grund = "mittelbar_gestuetzt", "getragen von " + ", ".join(traeger)
        else:
            status, grund = "offen", "benutzt, aber keine eigene/mittelbare Quelle"
        ergebnis.append(Deckung(n.id, str(n.felder.get("kernaussage", "")),
                                status, n.id in bestritten_ids, grund))
    return sorted(ergebnis, key=lambda d: d.argument_id)


def _format(deckungen: list[Deckung], schriftsatz_id: str) -> str:
    zeilen = [f"Watson-Deckungsbericht: {schriftsatz_id}"]
    if not deckungen:
        zeilen.append("  (keine vorkommenden Argumente gefunden)")
    for d in deckungen:
        flag = " [BESTRITTEN]" if d.bestritten else ""
        zeilen.append(f"  {d.argument_id}: {d.status}{flag} -- {d.grund}")
    offen = sum(1 for d in deckungen if d.status == "offen")
    bestritten = sum(1 for d in deckungen if d.bestritten)
    zeilen.append(f"Summe: {len(deckungen)} benutzt, {offen} offen, {bestritten} bestritten.")
    return "\n".join(zeilen)


def _main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Nutzung: python -m tools.processes.watson <graph-root> <schriftsatz-id>",
              file=sys.stderr)
        return 2
    print(_format(pruefe(argv[1], argv[2]), argv[2]))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
