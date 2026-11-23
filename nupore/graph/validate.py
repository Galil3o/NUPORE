"""Validator = Merge-Gate-Kern (config/07). Schema-getrieben.

Checks:
- NO_ROOT              : Graph-Wurzel existiert nicht (statt stillem Erfolg)
- LOAD_ERROR           : Knotendatei nicht ladbar (Frontmatter/YAML/Duplikat-Key);
                         der Lauf bricht nicht ab, andere Dateien werden geprueft
- DUP_ID               : id mehrfach vergeben
- EMPTY_ID             : id oder type leer / kein String
- UNKNOWN_TYPE          : type nicht im Schema
- MISSING_FIELD        : Pflichtfeld laut Schema fehlt
- NULL_FIELD           : Pflichtfeld present, aber null (Praesenz != Inhalt)
- UNKNOWN_FIELD        : Frontmatter-Key weder Pflicht-/Optionalfeld noch Kante
                         (faengt vertippte/umlautierte Kanten-Keys wie
                          `instanz_zurück` statt `appeal_from`)
- INVALID_KIND          : argument.kind nicht in argument_kinds
- BAD_EDGE_SHAPE       : Kantenwert ist keine Liste (Kante wird uebersprungen,
                         kein Absturz)
- EDGE_SOURCE          : Kante auf unzulaessigem Quell-Knotentyp (edge_constraints)
- EDGE_TARGET          : aufgeloestes Kantenziel hat falschen Knotentyp
- DEAD_EDGE            : Kante zeigt auf nicht existierende id (ausser provision_version)
- COURT_UNRESOLVED   : decision.court loest nicht auf einen Gericht-Knoten auf
- PROVISION_UNRESOLVED      : provision_version zeigt nicht auf einen Norm-Knoten
- PROVISION_TEMPORAL        : Anker-Datum ausserhalb der Geltung der verankerten Norm.
                         Anker ist `provision_cutoff` (wenn present), sonst `date`
                         (massgeblich ist der materielle Stichtag, nicht das
                         Entscheidungsdatum)
- INVALID_OUTCOME      : decision.outcome nicht in outcome_values
- INVALID_SOURCE_TYPE   : source_type nicht in source_types (jeder Knotentyp)
- INVALID_STATEMENT_FUNCTION : statement_function nicht in statement_functions
- MISSING_SOURCE_URL   : source_type ist official_case_law/official_statute_text,
                         aber source_url fehlt/leer (Originaerquelle braucht URL)
- INVALID_OCCURRENCE_STATUS : occurrence-Eintrag mit status nicht in occurrence_status_values
- OCCURRENCE_INCOMPLETE  : occurrence-Eintrag ohne gueltiges target/status/date (kein Absturz
                         bei `occurrence: [{}]`)
- INVALID_FINALITY   : decision.finality nicht in finality_values
- BAD_PRECEDENT_SHAPE  : precedent_use ist keine Liste von Objekten
- INVALID_REACH : precedent_use.reach nicht in reach_levels
- PRECEDENT_UNRESOLVED : precedent_use.source loest nicht auf ein Argument auf
- PRECEDENT_INCOMPLETE : precedent_use-Eintrag ohne 'source'/'reach' (leer)
- NO_ORIGIN          : argument/decision ohne origin
- INVALID_ORIGIN_PREFIX : origin-Praefix nicht in origin_prefixes (D5)
- NO_CITATION        : atomares Argument ohne quote/citation
- BAD_DATE             : Datumsfeld nicht exakt YYYY-MM-DD / kein Kalenderdatum
                         (statt Absturz)
- BAD_INTERVAL         : legal_provision.valid_from > valid_until
- SUCCESSOR_TEMPORAL  : successor nicht lueckenlos anschliessend / Zyklus

CLI: python -m nupore.graph.validate <root>  -> Exit 0 (sauber) / 1 (Verstoesse)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

from nupore.graph.node import EDGE_TYPES, load_node, node_files

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "graph-schema.yaml"
_SCHEMA = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
_NODE_TYPES = _SCHEMA["node_types"]
_ARGUMENT_KINDS = set(_SCHEMA.get("argument_kinds", []))
_ORIGIN_PREFIXES = set(_SCHEMA.get("origin_prefixes", []))
_SOURCE_TYPES = set(_SCHEMA.get("source_types", []))
_STATEMENT_FUNCTIONS = set(_SCHEMA.get("statement_functions", []))
_OUTCOME_VALUES = set(_SCHEMA.get("outcome_values", []))
_OCCURRENCE_STATUS = set(_SCHEMA.get("occurrence_status_values", []))
_REACH_LEVELS = set(_SCHEMA.get("reach_levels", []))
_FINALITY_VALUES = set(_SCHEMA.get("finality_values", []))
# Reservierter, filterbarer Marker fuer "ehrlich unknown" (config/05; D35).
_UNKNOWN = _SCHEMA.get("marker_unknown", "unknown")
# Veroeffentlichte Originaerquellen + online-native Materialien: source_url ist
# Pflicht (config/02 Regel 2; config/05 Quellen-Zweiteilung Klasse A). Druck-native
# Literatur (commentary/journal_article/monograph) traegt ihren Locator ueber `citation`.
_SOURCE_URL_REQUIRED = {"official_case_law", "official_statute_text",
                       "parliamentary_document", "legislative_materials",
                       "encyclopedia", "professional_news", "press_release"}
_EDGE_CONSTRAINTS = _SCHEMA.get("edge_constraints", {})
_RESERVED = {"id", "type", "fixture"}
_DATE_FIELDS = ("valid_from", "valid_until", "date", "provision_cutoff", "final_since")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Violation:
    code: str
    node_id: str
    detail: str


def _try_date(value):
    """Strikt: nur exaktes `YYYY-MM-DD`, das ein echtes Kalenderdatum ist.
    `date.fromisoformat` akzeptiert ab Python 3.11 auch Basisformen wie
    `20200101`; unsere Locator-Konvention ist strikt. Nie werfen -> None."""
    if value is None:
        return None
    s = str(value)
    if not _ISO_DATE.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _is_enum(value, vokabular) -> bool:
    """True nur, wenn `value` ein String im Vokabular ist. Verhindert einen
    TypeError beim Mengen-Test, wenn jemand z. B. eine Liste statt eines Strings
    schreibt (R-003 / D36: strukturierte Diagnose statt Absturz)."""
    return isinstance(value, str) and value in vokabular


def _present(value) -> bool:
    """Feld ist inhaltlich present: nicht None und, bei Strings, nicht leer.
    Der reservierte Marker `unknown` gilt als present (ehrlicher Zustand)."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _count_unknown(root: str) -> int:
    """Zaehlt die filterbaren `unknown`-Marker (Leitplanke D35: sichtbar/zaehlbar)."""
    n = 0
    for path in node_files(root):
        try:
            node = load_node(path)
        except Exception:
            continue
        for value in node.fields.values():
            if value == _UNKNOWN:
                n += 1
            elif isinstance(value, list):
                for item in value:
                    if item == _UNKNOWN:
                        n += 1
                    elif isinstance(item, dict):
                        n += sum(1 for x in item.values() if x == _UNKNOWN)
    return n


def _successor_temporal(nodes, norm_by_id) -> list[Violation]:
    viol: list[Violation] = []
    for n in nodes:
        for target in n.edge_targets("successor"):
            nf = norm_by_id.get(target) if isinstance(target, str) else None
            if nf is None:
                continue
            bis = _try_date(n.fields.get("valid_until"))
            if bis is None:
                viol.append(Violation("SUCCESSOR_TEMPORAL", n.id,
                                       "successor ohne gueltiges valid_until"))
                continue
            ab = _try_date(nf.fields.get("valid_from"))
            if ab is None:
                viol.append(Violation("SUCCESSOR_TEMPORAL", nf.id,
                                       "Nachfolger ohne gueltiges valid_from"))
                continue
            if ab != bis + timedelta(days=1):
                viol.append(Violation("SUCCESSOR_TEMPORAL", n.id,
                                       f"Luecke/Ueberlappung: {bis} -> {ab}"))
    succ = {n.id: [z for z in n.edge_targets("successor") if isinstance(z, str)]
            for n in nodes if isinstance(n.id, str)}
    for start in succ:
        cur, steps = start, 0
        while succ.get(cur):
            cur = succ[cur][0]
            steps += 1
            if steps > len(succ):
                viol.append(Violation("SUCCESSOR_TEMPORAL", start, "Zyklus in successor"))
                break
    return viol


def validate(root: str) -> list[Violation]:
    base = Path(root)
    if not base.exists():
        return [Violation("NO_ROOT", str(root), "Graph-Wurzel existiert nicht")]

    nodes = []
    viol: list[Violation] = []
    for path in node_files(root):
        try:
            nodes.append(load_node(path))
        except Exception as e:  # Ladefehler brechen den Lauf nicht ab
            viol.append(Violation("LOAD_ERROR", path, str(e)))

    # id/type-Typsicherheit ZUERST: ein Listenwert fuer `id` ist unhashbar und
    # wuerde die Map-/Mengenbildung mit TypeError abbrechen (R-003). Nur string-ids
    # fliessen in die Referenz-Maps; fehlerhafte id/type meldet die Hauptschleife.
    zaehler: dict[str, int] = {}
    for n in nodes:
        if isinstance(n.id, str):
            zaehler[n.id] = zaehler.get(n.id, 0) + 1
    for nid, c in zaehler.items():
        if c > 1:
            viol.append(Violation("DUP_ID", nid, f"{c}x vergeben"))

    ids = set(zaehler)
    typ_by_id = {n.id: n.type for n in nodes if isinstance(n.id, str)}
    norm_by_id = {n.id: n for n in nodes if isinstance(n.id, str) and n.type == "legal_provision"}
    norm_ids = set(norm_by_id)

    for n in nodes:
        if not isinstance(n.id, str) or not n.id.strip():
            viol.append(Violation("EMPTY_ID", n.path, "id ist leer oder kein String"))
        if not isinstance(n.type, str) or not n.type.strip():
            viol.append(Violation("EMPTY_ID", n.path, "type ist leer oder kein String"))
            continue

        spec = _NODE_TYPES.get(n.type)
        if spec is None:
            viol.append(Violation("UNKNOWN_TYPE", n.id, f"type '{n.type}' nicht im Schema"))
            continue

        erlaubt = set(spec.get("required_fields", [])) | set(spec.get("optional_fields", [])) \
            | EDGE_TYPES | _RESERVED
        for feld in spec.get("required_fields", []):
            if feld not in n.fields:
                viol.append(Violation("MISSING_FIELD", n.id, f"Pflichtfeld '{feld}' fehlt"))
            elif n.fields.get(feld) is None:
                viol.append(Violation("NULL_FIELD", n.id, f"Pflichtfeld '{feld}' ist null"))
        for key in n.fields:
            if key not in erlaubt:
                viol.append(Violation("UNKNOWN_FIELD", n.id,
                                       f"unbekanntes Feld '{key}' (Tippfehler/Umlaut in einer Kante?)"))

        if n.type == "argument":
            kind = n.fields.get("kind")
            if kind is not None and not _is_enum(kind, _ARGUMENT_KINDS):
                viol.append(Violation("INVALID_KIND", n.id, f"kind '{kind}' nicht in {sorted(_ARGUMENT_KINDS)}"))
            if kind == "atomic":
                quote = n.fields.get("quote")
                citation = n.fields.get("citation")
                # Form zaehlt: ein atomares Argument braucht quote UND citation als
                # nicht-leere Strings. Eine Liste als citation galt sonst als
                # "present" und wurde von Watson als directly_supported gewertet
                # (Komplett-Review 2026-11-20).
                if not (isinstance(quote, str) and quote.strip()) or \
                        not (isinstance(citation, str) and citation.strip()):
                    viol.append(Violation("NO_CITATION", n.id,
                                           "atomares Argument braucht quote UND citation als nicht-leere Strings"))

            # precedent_use: Reichweite, mit der dieses Argument ein anderes
            # (Praezedenz-)Argument dehnt. Liste von Objekten {source, reach, ...}.
            pn = n.fields.get("precedent_use")
            if pn is not None:
                if not isinstance(pn, list):
                    viol.append(Violation("BAD_PRECEDENT_SHAPE", n.id,
                                           f"precedent_use ist keine Liste (Wert: {pn!r})"))
                else:
                    for eintrag in pn:
                        if not isinstance(eintrag, dict):
                            viol.append(Violation("BAD_PRECEDENT_SHAPE", n.id,
                                                   f"Eintrag ist kein Mapping: {eintrag!r}"))
                            continue
                        q = eintrag.get("source")
                        reach = eintrag.get("reach")
                        # Pflicht: source UND reach present (Wert darf `unknown` sein).
                        if not _present(q) or not _present(reach):
                            viol.append(Violation("PRECEDENT_INCOMPLETE", n.id,
                                                   "precedent_use-Eintrag braucht 'source' und 'reach' "
                                                   f"(Wert darf '{_UNKNOWN}' sein)"))
                            continue
                        if reach != _UNKNOWN and not _is_enum(reach, _REACH_LEVELS):
                            viol.append(Violation("INVALID_REACH", n.id,
                                                   f"reach '{reach!r}' nicht in {sorted(_REACH_LEVELS)} "
                                                   f"(oder '{_UNKNOWN}')"))
                        if q != _UNKNOWN and not (isinstance(q, str) and q in ids
                                                    and typ_by_id.get(q) == "argument"):
                            viol.append(Violation("PRECEDENT_UNRESOLVED", n.id,
                                                   f"precedent_use.source '{q!r}' ist kein Argument-Knoten "
                                                   f"(oder '{_UNKNOWN}')"))

        if n.type in {"argument", "decision"}:
            origin = n.fields.get("origin")
            if not origin:
                viol.append(Violation("NO_ORIGIN", n.id, "origin fehlt"))
            elif not isinstance(origin, str):
                viol.append(Violation("INVALID_ORIGIN_PREFIX", n.id,
                                       f"origin ist kein String ({origin!r})"))
            else:
                # origin = `praefix:rest` (config/03); der Praefix muss aus dem
                # Vokabular stammen (D5: bisher gar nicht erzwungen).
                praefix = origin.split(":", 1)[0]
                if praefix != _UNKNOWN and praefix not in _ORIGIN_PREFIXES:
                    viol.append(Violation("INVALID_ORIGIN_PREFIX", n.id,
                                           f"origin-Praefix {praefix!r} nicht in {sorted(_ORIGIN_PREFIXES)}"))

        # Kontrollierte Vokabulare (optionale Felder) ----------------------
        qt = n.fields.get("source_type")
        if qt is not None and not _is_enum(qt, _SOURCE_TYPES):
            viol.append(Violation("INVALID_SOURCE_TYPE", n.id,
                                   f"source_type '{qt!r}' nicht in {sorted(_SOURCE_TYPES)}"))
        if _is_enum(qt, _SOURCE_URL_REQUIRED):
            url = n.fields.get("source_url")
            if not isinstance(url, str) or not url.strip():
                viol.append(Violation("MISSING_SOURCE_URL", n.id,
                                       f"source_type '{qt}' erfordert nicht-leere source_url"))

        # wertigkeit v2 (D37/D38) ist rein ABGELEITET (nupore/graph/derive.py) — kein
        # Override-Feld mehr. Die Rechtskraft (unten, decision) speist das Gate.

        af = n.fields.get("statement_function")
        if af is not None and not _is_enum(af, _STATEMENT_FUNCTIONS):
            viol.append(Violation("INVALID_STATEMENT_FUNCTION", n.id,
                                   f"statement_function '{af!r}' nicht in {sorted(_STATEMENT_FUNCTIONS)}"))

        if n.type == "decision":
            ausg = n.fields.get("outcome")
            if ausg is not None and not _is_enum(ausg, _OUTCOME_VALUES):
                viol.append(Violation("INVALID_OUTCOME", n.id,
                                       f"outcome '{ausg!r}' nicht in {sorted(_OUTCOME_VALUES)}"))
            rk = n.fields.get("finality")
            if rk is not None and not _is_enum(rk, _FINALITY_VALUES):
                viol.append(Violation("INVALID_FINALITY", n.id,
                                       f"finality '{rk!r}' nicht in {sorted(_FINALITY_VALUES)}"))

        vork = n.edges.get("occurrence")
        if isinstance(vork, list):
            for eintrag in vork:
                # Jeder occurrence-Eintrag braucht target + status + date (R-003:
                # ein Eintrag mit nur einem Ziel ohne status/date war bisher
                # stillschweigend akzeptiert).
                if not isinstance(eintrag, dict):
                    viol.append(Violation("OCCURRENCE_INCOMPLETE", n.id,
                                           f"occurrence-Eintrag ist kein Mapping: {eintrag!r}"))
                    continue
                target = eintrag.get("target")
                if not (isinstance(target, str) and target.strip()):
                    viol.append(Violation("OCCURRENCE_INCOMPLETE", n.id,
                                           f"occurrence-Eintrag ohne gueltiges 'target' ({target!r})"))
                st = eintrag.get("status")
                if not _is_enum(st, _OCCURRENCE_STATUS):
                    viol.append(Violation("INVALID_OCCURRENCE_STATUS", n.id,
                                           f"occurrence-status {st!r} nicht in {sorted(_OCCURRENCE_STATUS)}"))
                if not _present(eintrag.get("date")):
                    viol.append(Violation("OCCURRENCE_INCOMPLETE", n.id,
                                           "occurrence-Eintrag ohne 'date'"))

        if n.type == "decision":
            g = n.fields.get("court")
            if g is not None and not (isinstance(g, str) and g in ids
                                      and typ_by_id.get(g) == "court"):
                viol.append(Violation("COURT_UNRESOLVED", n.id,
                                       f"court {g!r} ist kein Gericht-Knoten"))

        for feld in _DATE_FIELDS:
            value = n.fields.get(feld)
            if value is not None and _try_date(value) is None:
                viol.append(Violation("BAD_DATE", n.id, f"{feld}='{value}' ist kein ISO-Datum (YYYY-MM-DD)"))

        if n.type == "legal_provision":
            ab = _try_date(n.fields.get("valid_from"))
            bis = _try_date(n.fields.get("valid_until"))
            if ab is not None and bis is not None and ab > bis:
                viol.append(Violation("BAD_INTERVAL", n.id,
                                       f"valid_from {ab} > valid_until {bis}"))

        # Kantenwerte muessen Listen sein; Skalare werden gemeldet und uebersprungen.
        bad_shape = set()
        for edge, value in n.edges.items():
            if value is not None and not isinstance(value, list):
                viol.append(Violation("BAD_EDGE_SHAPE", n.id,
                                       f"Kante '{edge}' ist keine Liste (Wert: {value!r})"))
                bad_shape.add(edge)

        for edge in n.edges:
            if edge in bad_shape:
                continue
            constraint = _EDGE_CONSTRAINTS.get(edge)
            if constraint and n.type not in constraint.get("source", []):
                viol.append(Violation("EDGE_SOURCE", n.id,
                                       f"Kante '{edge}' nicht erlaubt auf type '{n.type}'"))
            if edge == "provision_version":
                continue  # Zielpruefung via PROVISION_UNRESOLVED/PROVISION_TEMPORAL unten
            for target in n.edge_targets(edge):
                if not isinstance(target, str) or target not in ids:
                    viol.append(Violation("DEAD_EDGE", n.id, f"{edge} -> {target!r} fehlt"))
                    continue
                if constraint and typ_by_id.get(target) not in constraint.get("target", []):
                    viol.append(Violation("EDGE_TARGET", n.id,
                                           f"{edge} -> {target} ist type '{typ_by_id.get(target)}', "
                                           f"erwartet {constraint.get('target')}"))

        # Anker-Datum fuer die zeitliche Bindung: der materielle Stichtag
        # (provision_cutoff) geht vor; `null`/fehlend faellt auf `date` zurueck
        # (ein leeres provision_cutoff darf den aF/nF-Waechter nicht heimlich
        # abschalten -> D36/SearchFinding 2).
        stichtag = n.fields.get("provision_cutoff")
        if stichtag is not None:
            anker = _try_date(stichtag)
        else:
            anker = _try_date(n.fields.get("date"))
        for target in n.edge_targets("provision_version"):
            if not isinstance(target, str) or target not in norm_ids:
                viol.append(Violation("PROVISION_UNRESOLVED", n.id,
                                       f"provision_version -> {target!r} ist kein Norm-Knoten"))
                continue
            if anker is not None:
                nf = norm_by_id[target]
                ab = _try_date(nf.fields.get("valid_from"))
                bis = _try_date(nf.fields.get("valid_until"))
                if (ab and anker < ab) or (bis and anker > bis):
                    viol.append(Violation("PROVISION_TEMPORAL", n.id,
                                           f"Anker {anker} ausserhalb Geltung von {target} ({ab}..{bis})"))

    viol += _successor_temporal(nodes, norm_by_id)
    return viol


def _main(argv: list[str]) -> int:
    root = argv[1] if len(argv) > 1 else "graph"
    verstoesse = validate(root)
    for v in verstoesse:
        print(f"{v.code}\t{v.node_id}\t{v.detail}")
    unknown = _count_unknown(root)
    if unknown:
        print(f"Hinweis: {unknown} '{_UNKNOWN}'-Marker im Graph "
              f"(sichtbar/filterbar via grep '{_UNKNOWN}').")
    if verstoesse:
        print(f"\n{len(verstoesse)} Verstoss/Verstoesse.", file=sys.stderr)
        return 1
    print("OK: keine Verstoesse.")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
