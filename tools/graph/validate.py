"""Validator = Merge-Gate-Kern (config/07). Schema-getrieben.

Checks:
- NO_ROOT              : Graph-Wurzel existiert nicht (statt stillem Erfolg)
- LOAD_ERROR           : Knotendatei nicht ladbar (Frontmatter/YAML/Duplikat-Key);
                         der Lauf bricht nicht ab, andere Dateien werden geprueft
- DUP_ID               : id mehrfach vergeben
- EMPTY_ID             : id oder typ leer / kein String
- UNKNOWN_TYP          : typ nicht im Schema
- MISSING_FIELD        : Pflichtfeld laut Schema fehlt
- NULL_FIELD           : Pflichtfeld vorhanden, aber null (Praesenz != Inhalt)
- UNKNOWN_FIELD        : Frontmatter-Key weder Pflicht-/Optionalfeld noch Kante
                         (faengt vertippte/umlautierte Kanten-Keys wie
                          `instanz_zurück` statt `instanz_zurueck`)
- INVALID_ART          : argument.art nicht in argument_arten
- BAD_EDGE_SHAPE       : Kantenwert ist keine Liste (Kante wird uebersprungen,
                         kein Absturz)
- EDGE_SOURCE          : Kante auf unzulaessigem Quell-Knotentyp (edge_constraints)
- EDGE_TARGET          : aufgeloestes Kantenziel hat falschen Knotentyp
- DEAD_EDGE            : Kante zeigt auf nicht existierende id (ausser norm_fassung)
- GERICHT_UNRESOLVED   : entscheidung.gericht loest nicht auf einen Gericht-Knoten auf
- NORM_UNRESOLVED      : norm_fassung zeigt nicht auf einen Norm-Knoten
- NORM_TEMPORAL        : Anker-Datum ausserhalb der Geltung der verankerten Norm.
                         Anker ist `norm_stichtag` (wenn vorhanden), sonst `datum`
                         (massgeblich ist der materielle Stichtag, nicht das
                         Entscheidungsdatum)
- INVALID_AUSGANG      : entscheidung.ausgang nicht in ausgang_werte
- INVALID_QUELLE_TYP   : quelle_typ nicht in quelle_typen (jeder Knotentyp)
- INVALID_AUSSAGE_FUNKTION : aussage_funktion nicht in aussage_funktionen
- MISSING_QUELLE_URL   : quelle_typ ist amtliche_rechtsprechung/amtlicher_normtext,
                         aber quelle_url fehlt/leer (Originaerquelle braucht URL)
- INVALID_VORKOMMEN_STATUS : vorkommen-Eintrag mit status nicht in vorkommen_status_werte
- INVALID_RECHTSKRAFT   : entscheidung.rechtskraft nicht in rechtskraft_werte
- BAD_PRAEZEDENZ_SHAPE  : praezedenz_nutzung ist keine Liste von Objekten
- INVALID_REICHWEITE_STUFE : praezedenz_nutzung.stufe nicht in reichweite_stufen
- PRAEZEDENZ_UNRESOLVED : praezedenz_nutzung.quelle loest nicht auf ein Argument auf
- PRAEZEDENZ_INCOMPLETE : praezedenz_nutzung-Eintrag ohne 'quelle'/'stufe' (leer)
- NO_HERKUNFT          : argument/entscheidung ohne herkunft
- NO_FUNDSTELLE        : atomares Argument ohne zitat/fundstelle
- BAD_DATE             : Datumsfeld nicht exakt YYYY-MM-DD / kein Kalenderdatum
                         (statt Absturz)
- BAD_INTERVAL         : norm.gueltig_ab > gueltig_bis
- NACHFOLGER_TEMPORAL  : nachfolger nicht lueckenlos anschliessend / Zyklus

CLI: python -m tools.graph.validate <root>  -> Exit 0 (sauber) / 1 (Verstoesse)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from tools.graph.node import EDGE_TYPES, load_node, node_files

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "graph-schema.yaml"
_SCHEMA = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
_NODE_TYPES = _SCHEMA["node_types"]
_ARGUMENT_ARTEN = set(_SCHEMA.get("argument_arten", []))
_QUELLE_TYPEN = set(_SCHEMA.get("quelle_typen", []))
_AUSSAGE_FUNKTIONEN = set(_SCHEMA.get("aussage_funktionen", []))
_AUSGANG_WERTE = set(_SCHEMA.get("ausgang_werte", []))
_VORKOMMEN_STATUS = set(_SCHEMA.get("vorkommen_status_werte", []))
_REICHWEITE_STUFEN = set(_SCHEMA.get("reichweite_stufen", []))
_RECHTSKRAFT_WERTE = set(_SCHEMA.get("rechtskraft_werte", []))
# Reservierter, filterbarer Marker fuer "ehrlich unbekannt" (config/05; D35).
_UNBEKANNT = _SCHEMA.get("marker_unbekannt", "unbekannt")
# Veroeffentlichte Originaerquellen + online-native Materialien: quelle_url ist
# Pflicht (config/02 Regel 2; config/05 Quellen-Zweiteilung Klasse A). Druck-native
# Literatur (kommentar/fachaufsatz/monografie) traegt ihren Locator ueber `fundstelle`.
_QUELLE_URL_PFLICHT = {"amtliche_rechtsprechung", "amtlicher_normtext",
                       "bundestagsdrucksache", "gesetzesmaterialien",
                       "enzyklopaedie", "fachnews", "pressemitteilung"}
_EDGE_CONSTRAINTS = _SCHEMA.get("edge_constraints", {})
_RESERVIERT = {"id", "typ", "fixture"}
_DATUMSFELDER = ("gueltig_ab", "gueltig_bis", "datum", "norm_stichtag", "rechtskraft_ab")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Violation:
    code: str
    node_id: str
    detail: str


def _try_date(wert):
    """Strikt: nur exaktes `YYYY-MM-DD`, das ein echtes Kalenderdatum ist.
    `date.fromisoformat` akzeptiert ab Python 3.11 auch Basisformen wie
    `20200101`; unsere Locator-Konvention ist strikt. Nie werfen -> None."""
    if wert is None:
        return None
    s = str(wert)
    if not _ISO_DATE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _is_enum(wert, vokabular) -> bool:
    """True nur, wenn `wert` ein String im Vokabular ist. Verhindert einen
    TypeError beim Mengen-Test, wenn jemand z. B. eine Liste statt eines Strings
    schreibt (R-003 / D36: strukturierte Diagnose statt Absturz)."""
    return isinstance(wert, str) and wert in vokabular


def _present(wert) -> bool:
    """Feld ist inhaltlich vorhanden: nicht None und, bei Strings, nicht leer.
    Der reservierte Marker `unbekannt` gilt als vorhanden (ehrlicher Zustand)."""
    if wert is None:
        return False
    if isinstance(wert, str):
        return wert.strip() != ""
    return True


def _count_unbekannt(root: str) -> int:
    """Zaehlt die filterbaren `unbekannt`-Marker (Leitplanke D35: sichtbar/zaehlbar)."""
    n = 0
    for pfad in node_files(root):
        try:
            node = load_node(pfad)
        except Exception:
            continue
        for wert in node.felder.values():
            if wert == _UNBEKANNT:
                n += 1
            elif isinstance(wert, list):
                for item in wert:
                    if item == _UNBEKANNT:
                        n += 1
                    elif isinstance(item, dict):
                        n += sum(1 for x in item.values() if x == _UNBEKANNT)
    return n


def _nachfolger_temporal(nodes, norm_by_id) -> list[Violation]:
    viol: list[Violation] = []
    for n in nodes:
        for ziel in n.kanten_ziele("nachfolger"):
            nf = norm_by_id.get(ziel)
            if nf is None:
                continue
            bis = _try_date(n.felder.get("gueltig_bis"))
            if bis is None:
                viol.append(Violation("NACHFOLGER_TEMPORAL", n.id,
                                       "nachfolger ohne gueltiges gueltig_bis"))
                continue
            ab = _try_date(nf.felder.get("gueltig_ab"))
            if ab is None:
                viol.append(Violation("NACHFOLGER_TEMPORAL", nf.id,
                                       "Nachfolger ohne gueltiges gueltig_ab"))
                continue
            if ab != bis + timedelta(days=1):
                viol.append(Violation("NACHFOLGER_TEMPORAL", n.id,
                                       f"Luecke/Ueberlappung: {bis} -> {ab}"))
    succ = {n.id: n.kanten_ziele("nachfolger") for n in nodes}
    for start in succ:
        cur, steps = start, 0
        while succ.get(cur):
            cur = succ[cur][0]
            steps += 1
            if steps > len(succ):
                viol.append(Violation("NACHFOLGER_TEMPORAL", start, "Zyklus in nachfolger"))
                break
    return viol


def validate(root: str) -> list[Violation]:
    base = Path(root)
    if not base.exists():
        return [Violation("NO_ROOT", str(root), "Graph-Wurzel existiert nicht")]

    nodes = []
    viol: list[Violation] = []
    for pfad in node_files(root):
        try:
            nodes.append(load_node(pfad))
        except Exception as e:  # Ladefehler brechen den Lauf nicht ab
            viol.append(Violation("LOAD_ERROR", pfad, str(e)))

    zaehler: dict[str, int] = {}
    for n in nodes:
        zaehler[n.id] = zaehler.get(n.id, 0) + 1
    for nid, c in zaehler.items():
        if c > 1:
            viol.append(Violation("DUP_ID", nid, f"{c}x vergeben"))

    ids = set(zaehler)
    typ_by_id = {n.id: n.typ for n in nodes}
    norm_by_id = {n.id: n for n in nodes if n.typ == "norm"}
    norm_ids = set(norm_by_id)

    for n in nodes:
        if not isinstance(n.id, str) or not n.id.strip():
            viol.append(Violation("EMPTY_ID", n.pfad, "id ist leer oder kein String"))
        if not isinstance(n.typ, str) or not n.typ.strip():
            viol.append(Violation("EMPTY_ID", n.pfad, "typ ist leer oder kein String"))
            continue

        spec = _NODE_TYPES.get(n.typ)
        if spec is None:
            viol.append(Violation("UNKNOWN_TYP", n.id, f"typ '{n.typ}' nicht im Schema"))
            continue

        erlaubt = set(spec.get("pflichtfelder", [])) | set(spec.get("optionale_felder", [])) \
            | EDGE_TYPES | _RESERVIERT
        for feld in spec.get("pflichtfelder", []):
            if feld not in n.felder:
                viol.append(Violation("MISSING_FIELD", n.id, f"Pflichtfeld '{feld}' fehlt"))
            elif n.felder.get(feld) is None:
                viol.append(Violation("NULL_FIELD", n.id, f"Pflichtfeld '{feld}' ist null"))
        for key in n.felder:
            if key not in erlaubt:
                viol.append(Violation("UNKNOWN_FIELD", n.id,
                                       f"unbekanntes Feld '{key}' (Tippfehler/Umlaut in einer Kante?)"))

        if n.typ == "argument":
            art = n.felder.get("art")
            if art is not None and not _is_enum(art, _ARGUMENT_ARTEN):
                viol.append(Violation("INVALID_ART", n.id, f"art '{art}' nicht in {sorted(_ARGUMENT_ARTEN)}"))
            if art == "atomar" and (not n.felder.get("zitat") or not n.felder.get("fundstelle")):
                viol.append(Violation("NO_FUNDSTELLE", n.id, "atomares Argument ohne zitat/fundstelle"))

            # praezedenz_nutzung: Reichweite, mit der dieses Argument ein anderes
            # (Praezedenz-)Argument dehnt. Liste von Objekten {quelle, stufe, ...}.
            pn = n.felder.get("praezedenz_nutzung")
            if pn is not None:
                if not isinstance(pn, list):
                    viol.append(Violation("BAD_PRAEZEDENZ_SHAPE", n.id,
                                           f"praezedenz_nutzung ist keine Liste (Wert: {pn!r})"))
                else:
                    for eintrag in pn:
                        if not isinstance(eintrag, dict):
                            viol.append(Violation("BAD_PRAEZEDENZ_SHAPE", n.id,
                                                   f"Eintrag ist kein Mapping: {eintrag!r}"))
                            continue
                        q = eintrag.get("quelle")
                        stufe = eintrag.get("stufe")
                        # Pflicht: quelle UND stufe vorhanden (Wert darf `unbekannt` sein).
                        if not _present(q) or not _present(stufe):
                            viol.append(Violation("PRAEZEDENZ_INCOMPLETE", n.id,
                                                   "praezedenz_nutzung-Eintrag braucht 'quelle' und 'stufe' "
                                                   f"(Wert darf '{_UNBEKANNT}' sein)"))
                            continue
                        if stufe != _UNBEKANNT and not _is_enum(stufe, _REICHWEITE_STUFEN):
                            viol.append(Violation("INVALID_REICHWEITE_STUFE", n.id,
                                                   f"stufe '{stufe!r}' nicht in {sorted(_REICHWEITE_STUFEN)} "
                                                   f"(oder '{_UNBEKANNT}')"))
                        if q != _UNBEKANNT and not (isinstance(q, str) and q in ids
                                                    and typ_by_id.get(q) == "argument"):
                            viol.append(Violation("PRAEZEDENZ_UNRESOLVED", n.id,
                                                   f"praezedenz_nutzung.quelle '{q!r}' ist kein Argument-Knoten "
                                                   f"(oder '{_UNBEKANNT}')"))

        if n.typ in {"argument", "entscheidung"} and not n.felder.get("herkunft"):
            viol.append(Violation("NO_HERKUNFT", n.id, "herkunft fehlt"))

        # Kontrollierte Vokabulare (optionale Felder) ----------------------
        qt = n.felder.get("quelle_typ")
        if qt is not None and not _is_enum(qt, _QUELLE_TYPEN):
            viol.append(Violation("INVALID_QUELLE_TYP", n.id,
                                   f"quelle_typ '{qt!r}' nicht in {sorted(_QUELLE_TYPEN)}"))
        if _is_enum(qt, _QUELLE_URL_PFLICHT):
            url = n.felder.get("quelle_url")
            if not isinstance(url, str) or not url.strip():
                viol.append(Violation("MISSING_QUELLE_URL", n.id,
                                       f"quelle_typ '{qt}' erfordert nicht-leere quelle_url"))

        # wertigkeit v2 (D37/D38) ist rein ABGELEITET (tools/graph/derive.py) — kein
        # Override-Feld mehr. Die Rechtskraft (unten, entscheidung) speist das Gate.

        af = n.felder.get("aussage_funktion")
        if af is not None and not _is_enum(af, _AUSSAGE_FUNKTIONEN):
            viol.append(Violation("INVALID_AUSSAGE_FUNKTION", n.id,
                                   f"aussage_funktion '{af!r}' nicht in {sorted(_AUSSAGE_FUNKTIONEN)}"))

        if n.typ == "entscheidung":
            ausg = n.felder.get("ausgang")
            if ausg is not None and not _is_enum(ausg, _AUSGANG_WERTE):
                viol.append(Violation("INVALID_AUSGANG", n.id,
                                       f"ausgang '{ausg!r}' nicht in {sorted(_AUSGANG_WERTE)}"))
            rk = n.felder.get("rechtskraft")
            if rk is not None and not _is_enum(rk, _RECHTSKRAFT_WERTE):
                viol.append(Violation("INVALID_RECHTSKRAFT", n.id,
                                       f"rechtskraft '{rk!r}' nicht in {sorted(_RECHTSKRAFT_WERTE)}"))

        vork = n.kanten.get("vorkommen")
        if isinstance(vork, list):
            for eintrag in vork:
                if isinstance(eintrag, dict) and "status" in eintrag:
                    st = eintrag.get("status")
                    if not _is_enum(st, _VORKOMMEN_STATUS):
                        viol.append(Violation("INVALID_VORKOMMEN_STATUS", n.id,
                                               f"vorkommen-status '{st!r}' nicht in {sorted(_VORKOMMEN_STATUS)}"))

        if n.typ == "entscheidung":
            g = n.felder.get("gericht")
            if g is not None and (g not in ids or typ_by_id.get(g) != "gericht"):
                viol.append(Violation("GERICHT_UNRESOLVED", n.id,
                                       f"gericht '{g}' ist kein Gericht-Knoten"))

        for feld in _DATUMSFELDER:
            wert = n.felder.get(feld)
            if wert is not None and _try_date(wert) is None:
                viol.append(Violation("BAD_DATE", n.id, f"{feld}='{wert}' ist kein ISO-Datum (YYYY-MM-DD)"))

        if n.typ == "norm":
            ab = _try_date(n.felder.get("gueltig_ab"))
            bis = _try_date(n.felder.get("gueltig_bis"))
            if ab is not None and bis is not None and ab > bis:
                viol.append(Violation("BAD_INTERVAL", n.id,
                                       f"gueltig_ab {ab} > gueltig_bis {bis}"))

        # Kantenwerte muessen Listen sein; Skalare werden gemeldet und uebersprungen.
        bad_shape = set()
        for kante, wert in n.kanten.items():
            if wert is not None and not isinstance(wert, list):
                viol.append(Violation("BAD_EDGE_SHAPE", n.id,
                                       f"Kante '{kante}' ist keine Liste (Wert: {wert!r})"))
                bad_shape.add(kante)

        for kante in n.kanten:
            if kante in bad_shape:
                continue
            constraint = _EDGE_CONSTRAINTS.get(kante)
            if constraint and n.typ not in constraint.get("quelle", []):
                viol.append(Violation("EDGE_SOURCE", n.id,
                                       f"Kante '{kante}' nicht erlaubt auf typ '{n.typ}'"))
            if kante == "norm_fassung":
                continue  # Zielpruefung via NORM_UNRESOLVED/NORM_TEMPORAL unten
            for ziel in n.kanten_ziele(kante):
                if ziel not in ids:
                    viol.append(Violation("DEAD_EDGE", n.id, f"{kante} -> {ziel} fehlt"))
                    continue
                if constraint and typ_by_id.get(ziel) not in constraint.get("ziel", []):
                    viol.append(Violation("EDGE_TARGET", n.id,
                                           f"{kante} -> {ziel} ist typ '{typ_by_id.get(ziel)}', "
                                           f"erwartet {constraint.get('ziel')}"))

        # Anker-Datum fuer die zeitliche Bindung: der materielle Stichtag
        # (norm_stichtag) geht vor; `null`/fehlend faellt auf `datum` zurueck
        # (ein leeres norm_stichtag darf den aF/nF-Waechter nicht heimlich
        # abschalten -> D36/Befund 2).
        stichtag = n.felder.get("norm_stichtag")
        if stichtag is not None:
            anker = _try_date(stichtag)
        else:
            anker = _try_date(n.felder.get("datum"))
        for ziel in n.kanten_ziele("norm_fassung"):
            if ziel not in norm_ids:
                viol.append(Violation("NORM_UNRESOLVED", n.id,
                                       f"norm_fassung -> {ziel} ist kein Norm-Knoten"))
                continue
            if anker is not None:
                nf = norm_by_id[ziel]
                ab = _try_date(nf.felder.get("gueltig_ab"))
                bis = _try_date(nf.felder.get("gueltig_bis"))
                if (ab and anker < ab) or (bis and anker > bis):
                    viol.append(Violation("NORM_TEMPORAL", n.id,
                                           f"Anker {anker} ausserhalb Geltung von {ziel} ({ab}..{bis})"))

    viol += _nachfolger_temporal(nodes, norm_by_id)
    return viol


def _main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "graph"
    verstoesse = validate(root)
    for v in verstoesse:
        print(f"{v.code}\t{v.node_id}\t{v.detail}")
    unbekannt = _count_unbekannt(root)
    if unbekannt:
        print(f"Hinweis: {unbekannt} '{_UNBEKANNT}'-Marker im Graph "
              f"(sichtbar/filterbar via grep '{_UNBEKANNT}').")
    if verstoesse:
        print(f"\n{len(verstoesse)} Verstoss/Verstoesse.", file=sys.stderr)
        return 1
    print("OK: keine Verstoesse.")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
