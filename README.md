# NUPORE

**Data-Sieve-Engine** fuer quellenverankerte KnowHow-Graphen (Nuclear Pore Complex).
Generischer, inhaltsfreier Bauplan: Schema, Validator (Merge-Gate), Index-Generator,
Wertigkeits-Ableitung und die graph-internen Prozesse (Sherlock/Watson/Guardian).

Private Instanzen konsumieren NUPORE als Engine und halten ihren eigenen Inhalt
(Normen, Faelle, Belege) getrennt.

## Engine-Vertrag (was NUPORE ist -- und nicht ist)
- NUPORE enthaelt **keinen** Inhalt: keine Faelle, keine Normtexte, keine Belege,
  keine instanzspezifische Methodik-Prosa, keine privaten Register/Deny-Listen.
- Fach-/Domaenenbezuege in Code-Kommentaren (z. B. ein Beispiel-Suchraum, Design-
  Kuerzel wie `D13`/`R-013`) sind bewusste **oeffentliche** Illustration der Methode,
  kein Inhalt. Default-Beispiele sind konfigurierbar (siehe `tools/processes/`).
- Externe Schichten -- **Websuche/Fetch** (fuer Sherlock) und **Zustellung** (fuer
  Guardian) -- liegen absichtlich AUSSERHALB der Engine und werden von der
  konsumierenden Instanz bereitgestellt.
- Ein gruener Testlauf ist **keine** Datenschutz- oder Veroeffentlichungsfreigabe der
  konsumierenden Instanz.

## Inhalt (Phase 1 -- Code-Engine)
- `schema/graph-schema.yaml` -- Knoten/Kanten/kontrollierte Vokabulare.
- `tools/graph/` -- Node-Parser, Validator (Merge-Gate), Index-Generator, Wertigkeits-Ableitung.
- `tools/processes/` -- Sherlock (Beweissicherung), Watson (Deckungspruefung), Guardian (Fristen).
- `tools/entkernung_check.py` -- fail-closed-Gate fuer private -> oeffentliche Extraktion.
- `tools/check.sh` -- lokales Merge-Gate (Validator + Index-Sync) gegen einen Graph-Root.
- `tests/` -- Engine-Tests ueber synthetische Fixtures.

## Nutzung
    pip install pyyaml pytest
    python -m pytest                              # Engine-Tests
    python -m tools.graph.validate <graph-root>   # Validator
    bash tools/check.sh <graph-root>              # Merge-Gate

Stand: Phase-1-Export (Code-Engine). Methodik-Prosa und Design-Notizen folgen nach
gesonderter Entkernung (Phase 2).
