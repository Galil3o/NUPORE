"""Abgeleitete Groessen (derive-first; config/01 D8, config/05; Wertigkeit v2 D37/D38).

Wertigkeit wird NICHT von Hand gepflegt (kein Override), sondern pro Knoten abgeleitet:

- `authority` (Kategorie, kategorische Trumpf-Grenze): `binding` =
  Norm (`official_statute_text`) ODER **rechtskraeftige** Apex-Entscheidung; sonst
  `non_binding`. Binding-intern KEINE feste Zahl — der Vorrang ist kontextabhaengig
  (config/04 Vorrang-Fork; EuGH<->BVerfG, BGH<->BAG).
- Rechtskraft-Gate (doppelschneidig, D37): eine Apex-Entscheidung OHNE Rechtskraft ist
  `schwebend` — nutzbar mit Hinweis "noch nicht final", aber kein voller Trumpf
  (und spiegelbildlich Angriffsflaeche). `unknown`/fehlend wird konservativ wie
  nicht-final behandelt.
- `fine_rank`: nur in der Unterklasse (`non_binding`), kleiner = staerker, mit
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
_APEX = set(_SCHEMA.get("apex_courts", []))
_FINE_RANK = dict(_SCHEMA.get("fine_rank_derivation", {}))


def _is_apex(gericht_id, gericht_rang) -> bool:
    """Apex-Gericht: in der Apex-Liste ODER fachgerichtlicher Rang 1 (z. B. BAG)."""
    return (gericht_id in _APEX) or (gericht_rang == 1)


def derive_authority(fields: dict, gericht_id=None, gericht_rang=None) -> str:
    """'binding' oder 'non_binding' (rein abgeleitet, pro Knoten)."""
    qt = fields.get("source_type")
    if qt == "official_statute_text":
        return "binding"
    if qt == "official_case_law" and _is_apex(gericht_id, gericht_rang):
        if fields.get("finality") == "final":
            return "binding"
    return "non_binding"


def is_pending(fields: dict, gericht_id=None, gericht_rang=None) -> bool:
    """Apex-Entscheidung (noch) ohne Rechtskraft -> schwebender Trumpf: nutzbar mit
    Hinweis, kein voller Trumpf (D37). `unknown`/fehlend zaehlt als nicht final."""
    if fields.get("source_type") != "official_case_law":
        return False
    if not _is_apex(gericht_id, gericht_rang):
        return False
    return fields.get("finality") != "final"


def derive_fine_rank(fields: dict, gericht_id=None, gericht_rang=None):
    """Fein-Rang der Unterklasse (kleiner = staerker) oder None fuer verbindliche Quellen."""
    if derive_authority(fields, gericht_id, gericht_rang) == "binding":
        return None
    return _FINE_RANK.get(fields.get("source_type"))
