"""Abgeleitete Groessen (derive-first; config/01 D8, config/05; Wertigkeit v2 D37/D38).

Wertigkeit wird NICHT von Hand gepflegt (kein Override), sondern pro Knoten abgeleitet:

- `verbindlichkeit` (Kategorie, kategorische Trumpf-Grenze): `verbindlich` =
  Norm (`amtlicher_normtext`) ODER **rechtskraeftige** Apex-Entscheidung; sonst
  `nicht_verbindlich`. Binding-intern KEINE feste Zahl — der Vorrang ist kontextabhaengig
  (config/04 Vorrang-Fork; EuGH<->BVerfG, BGH<->BAG).
- Rechtskraft-Gate (doppelschneidig, D37): eine Apex-Entscheidung OHNE Rechtskraft ist
  `schwebend` — nutzbar mit Hinweis "noch nicht rechtskraeftig", aber kein voller Trumpf
  (und spiegelbildlich Angriffsflaeche). `unbekannt`/fehlend wird konservativ wie
  nicht-rechtskraeftig behandelt.
- `fein_rang`: nur in der Unterklasse (`nicht_verbindlich`), kleiner = staerker, mit
  Headroom; verbindliche Quellen haben KEINEN Fein-Rang (-> None).

Lean (D37): Ableitung PRO KNOTEN. Fuer eine Entscheidung liefert der Aufrufer `gericht_id`/
`gericht_rang` (aus dem aufgeloesten Gericht-Knoten). Eine Mehr-Hop-Aufloesung
Argument->Entscheidung gibt es (noch) nicht, solange kein Konsument sie braucht.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "graph-schema.yaml"
_SCHEMA = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
_APEX = set(_SCHEMA.get("apex_gerichte", []))
_FEIN_RANG = dict(_SCHEMA.get("fein_rang_ableitung", {}))


def _ist_apex(gericht_id, gericht_rang) -> bool:
    """Apex-Gericht: in der Apex-Liste ODER fachgerichtlicher Rang 1 (z. B. BAG)."""
    return (gericht_id in _APEX) or (gericht_rang == 1)


def derive_verbindlichkeit(felder: dict, gericht_id=None, gericht_rang=None) -> str:
    """'verbindlich' oder 'nicht_verbindlich' (rein abgeleitet, pro Knoten)."""
    qt = felder.get("quelle_typ")
    if qt == "amtlicher_normtext":
        return "verbindlich"
    if qt == "amtliche_rechtsprechung" and _ist_apex(gericht_id, gericht_rang):
        if felder.get("rechtskraft") == "rechtskraeftig":
            return "verbindlich"
    return "nicht_verbindlich"


def ist_schwebend(felder: dict, gericht_id=None, gericht_rang=None) -> bool:
    """Apex-Entscheidung (noch) ohne Rechtskraft -> schwebender Trumpf: nutzbar mit
    Hinweis, kein voller Trumpf (D37). `unbekannt`/fehlend zaehlt als nicht rechtskraeftig."""
    if felder.get("quelle_typ") != "amtliche_rechtsprechung":
        return False
    if not _ist_apex(gericht_id, gericht_rang):
        return False
    return felder.get("rechtskraft") != "rechtskraeftig"


def derive_fein_rang(felder: dict, gericht_id=None, gericht_rang=None):
    """Fein-Rang der Unterklasse (kleiner = staerker) oder None fuer verbindliche Quellen."""
    if derive_verbindlichkeit(felder, gericht_id, gericht_rang) == "verbindlich":
        return None
    return _FEIN_RANG.get(felder.get("quelle_typ"))
