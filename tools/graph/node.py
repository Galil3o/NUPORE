"""Node-Parser fuer den Datei-Graphen.

Ein Knoten ist eine Markdown-Datei mit YAML-Frontmatter zwischen zwei `---`-
Zeilen, gefolgt vom Body. Kantenfelder (laut schema/graph-schema.yaml) werden
von gewoehnlichen Feldern getrennt. Quelle der Wahrheit: config/05.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "graph-schema.yaml"
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def _edge_types() -> set[str]:
    schema = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return set(schema["edge_types"])


EDGE_TYPES = _edge_types()


class _DuplicateKeyError(ValueError):
    """Doppelter Key im Frontmatter (yaml.safe_load wuerde still ueberschreiben)."""


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader, der doppelte Mapping-Keys als Fehler meldet statt sie
    stillschweigend zu ueberschreiben."""


def _strict_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise _DuplicateKeyError(f"doppelter YAML-Key '{key}'")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _strict_mapping
)


@dataclass
class Node:
    id: str
    typ: str
    felder: dict
    kanten: dict
    body: str
    pfad: str = field(default="")

    def kanten_ziele(self, kante: str) -> list[str]:
        """Zielknoten-IDs einer Kante, egal ob Liste von IDs oder von
        Objekten mit `ziel` (z. B. `vorkommen` mit status/datum).

        Ist der Kantenwert keine Liste (z. B. ein Skalar), wird `[]`
        zurueckgegeben statt zu werfen; der Validator meldet das als
        BAD_EDGE_SHAPE separat (kein Absturz des ganzen Laufs)."""
        wert = self.kanten.get(kante)
        if not isinstance(wert, list):
            return []
        ziele = []
        for eintrag in wert:
            if isinstance(eintrag, dict):
                if "ziel" not in eintrag:
                    raise ValueError(f"{self.id}: Kante {kante} ohne 'ziel'")
                ziele.append(eintrag["ziel"])
            else:
                ziele.append(eintrag)
        return ziele


def load_node(path: str) -> Node:
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: kein YAML-Frontmatter")
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError(f"{path}: Frontmatter nicht geschlossen")
    try:
        fm = yaml.load(m.group(1), Loader=_StrictLoader)
    except (yaml.YAMLError, _DuplicateKeyError) as e:
        raise ValueError(f"{path}: YAML-Fehler: {e}") from e
    if not isinstance(fm, dict):
        raise ValueError(f"{path}: Frontmatter ist kein Mapping")
    if "id" not in fm or "typ" not in fm:
        raise ValueError(f"{path}: id und typ sind Pflicht")
    kanten = {k: fm[k] for k in EDGE_TYPES if k in fm}
    return Node(id=fm["id"], typ=fm["typ"], felder=fm, kanten=kanten,
                body=m.group(2), pfad=str(path))


def node_files(root: str) -> Iterator[str]:
    """Pfade aller Knotendateien unter `root`. Uebersprungen: README.md und
    jeder Pfad, dessen Komponente mit `_` beginnt (z. B. `_index/`,
    `_malformed.md`). Trennt die Dateiauswahl vom Laden, damit der Validator
    je Datei fangen kann (LOAD_ERROR statt Abbruch)."""
    base = Path(root)
    for p in sorted(base.rglob("*.md")):
        if p.name == "README.md":
            continue
        if any(part.startswith("_") for part in p.relative_to(base).parts):
            continue
        yield str(p)


def iter_nodes(root: str) -> Iterator[Node]:
    """Alle Knoten unter `root` (siehe `node_files` fuer die Auswahlregeln)."""
    for pfad in node_files(root):
        yield load_node(pfad)
