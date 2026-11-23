"""Guardian -- Fristen-/Terminwaechter (D21, PROCESS_GUARDIAN; projektneutral).

PROCESS_, kein Datenmodell (D20): der Prozess liest ein schlankes Fristen-Register
(YAML, im Git), bestimmt faellige/anstehende Fristen und meldet sie. Er ERINNERT,
handelt aber nicht riskant allein (Erledigung bleibt beim Menschen).

Leitplanken (R-016/R-018):
  - Interne To-dos (type: intern) und rechtlich relevante Fristen (type: rechtlich)
    bleiben unterscheidbar.
  - Aus E-Mail/Datei ABGELEITETE Fristen gelten erst nach menschlicher Bestaetigung
    als `confirmed: true`; unbestaetigte werden SEPARAT ausgewiesen, nie als
    gesicherte Deadline gezaehlt.
  - Idempotenz: dieselbe Erinnerung fuer denselben Friststand wird wiedererkannt
    (deadline_id + Stand + Erinnerungstyp).
  - Datengrenze: eine Erinnerung traegt NUR deadline_id + case_ref + due_date,
    keinen Akteninhalt/Originalbetreff.

Strikte Register-Eingangspruefung (Komplett-Review 2026-11-20):
  - `confirmed` MUSS ein echtes YAML-Boolean sein. Ein String wie `"false"` wird
    NICHT als Wahrheit gedeutet (bool("false") == True), sondern als Registerfehler
    gemeldet und konservativ als unconfirmed behandelt.
  - Nicht-Mappings, fehlende/leere/doppelte `deadline_id` und falsch typisierte Felder
    verschwinden nicht still, sondern erscheinen unter PROBLEME.
  - Exit-Codes getrennt: 2 = Registerfehler (Konfig/Datenproblem), 1 = fachlicher
    Alarm (overdue), 0 = sauber. Ein Scheduler sieht einen kaputten Lauf also
    NICHT als Erfolg, auch wenn gerade keine Deadline overdue ist.

CLI: python -m nupore.processes.guardian <register.yaml> [--today YYYY-MM-DD] [--horizon N]
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

_FULFILLED = "fulfilled"
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Deadline:
    deadline_id: str
    due_date: str            # roh; strikt YYYY-MM-DD
    status: str = "offen"       # offen | fulfilled
    type: str = "unknown"      # intern | rechtlich
    confirmed: bool = False
    case_ref: str = ""
    source: str = ""
    responsible: str = ""
    trigger: str = ""
    load_error: str = ""       # strukturierter Ladefehler (nie still verschluckt)

    def date(self) -> date | None:
        s = str(self.due_date)
        if not _ISO.match(s):
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None


@dataclass
class DeadlineReport:
    overdue: list[Deadline]
    near: list[Deadline]
    unconfirmed: list[Deadline]
    problems: list[str]


def _as_text(value) -> str:
    """None -> '' (statt 'None'), sonst str. Verhindert, dass ein explizites
    YAML-`null` ueber str(...) zu einem scheinbar vorhandenen Wert wird."""
    return "" if value is None else str(value)


def load_register(path: str) -> list[Deadline]:
    """Laedt das Register und validiert jeden Eintrag strikt. Fehlerhafte Eintraege
    werden NICHT verworfen, sondern als Deadline mit `load_error` zurueckgegeben, damit
    `report` sie sichtbar unter PROBLEME fuehrt."""
    roh = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    if not isinstance(roh, list):
        raise ValueError(f"{path}: Register ist keine Liste von Fristen")
    deadlines: list[Deadline] = []
    gesehen: set[str] = set()
    for idx, e in enumerate(roh):
        if not isinstance(e, dict):
            deadlines.append(Deadline(deadline_id="", due_date="",
                                 load_error=f"Eintrag #{idx} ist kein Mapping ({type(e).__name__})"))
            continue
        errors: list[str] = []

        # deadline_id: Pflicht, nicht-leerer String, eindeutig.
        fid_raw = e.get("deadline_id")
        if fid_raw is None or (isinstance(fid_raw, str) and not fid_raw.strip()):
            fid = ""
            errors.append("deadline_id fehlt oder ist leer")
        elif not isinstance(fid_raw, str):
            fid = ""
            errors.append(f"deadline_id ist kein String ({fid_raw!r})")
        else:
            fid = fid_raw
            if fid in gesehen:
                errors.append(f"deadline_id '{fid}' doppelt vergeben")
            gesehen.add(fid)

        # confirmed: strikt Boolean. String 'false'/'true' NICHT als Wahrheit deuten.
        best_raw = e.get("confirmed", False)
        if isinstance(best_raw, bool):
            best = best_raw
        else:
            best = False
            errors.append(f"confirmed ist kein Boolean ({best_raw!r})")

        # status/type: Strings.
        status_raw = e.get("status", "offen")
        if not isinstance(status_raw, str):
            errors.append(f"status ist kein String ({status_raw!r})")
            status_raw = "offen"
        typ_raw = e.get("type", "unknown")
        if not isinstance(typ_raw, str):
            errors.append(f"type ist kein String ({typ_raw!r})")
            typ_raw = "unknown"

        deadlines.append(Deadline(
            deadline_id=fid,
            due_date=_as_text(e.get("due_date")),
            status=status_raw,
            type=typ_raw,
            confirmed=best,
            case_ref=_as_text(e.get("case_ref")),
            source=_as_text(e.get("source")),
            responsible=_as_text(e.get("responsible")),
            trigger=_as_text(e.get("trigger")),
            load_error="; ".join(errors),
        ))
    return deadlines


def report(deadlines: list[Deadline], today: date, horizon: int = 7) -> DeadlineReport:
    overdue: list[Deadline] = []
    near: list[Deadline] = []
    unconfirmed: list[Deadline] = []
    problems: list[str] = []
    grenze = today + timedelta(days=horizon)
    for f in deadlines:
        if f.load_error:
            problems.append(f"{f.deadline_id or '?'}: {f.load_error}")
            continue
        if not f.deadline_id:
            problems.append(f"Eintrag ohne deadline_id (due_date={f.due_date!r})")
            continue
        if f.status == _FULFILLED:
            continue
        d = f.date()
        if d is None:
            problems.append(f"{f.deadline_id}: kaputtes/fehlendes due_date {f.due_date!r}")
            continue
        if not f.confirmed:
            unconfirmed.append(f)      # abgeleitet, noch nicht menschlich confirmed
            continue
        if d < today:
            overdue.append(f)
        elif d <= grenze:
            near.append(f)
    key = lambda f: (f.date() or date.max, f.deadline_id)
    return DeadlineReport(sorted(overdue, key=key), sorted(near, key=key),
                   sorted(unconfirmed, key=lambda f: f.deadline_id), problems)


def reminder_key(f: Deadline, erinnerungstyp: str) -> str:
    """Idempotent: gleicher Friststand -> gleicher Schluessel -> dieselbe
    Erinnerung wird wiedererkannt (nicht erneut zugestellt)."""
    return f"{f.deadline_id}|{f.due_date}|{f.status}|{erinnerungstyp}"


def reminder_payload(f: Deadline) -> dict:
    """Datengrenze (R-018): NUR neutrale Kennung + Fallreferenz + Faelligkeit.
    KEIN Akteninhalt/Originalbetreff/Ausloesertext."""
    return {"deadline_id": f.deadline_id, "case_ref": f.case_ref, "due_date": f.due_date}


def _format(b: DeadlineReport, today: date) -> str:
    rows = [f"Guardian-Fristenbericht (Stichtag {today.isoformat()})"]

    def block(titel: str, deadlines: list[Deadline]) -> None:
        rows.append(f"{titel} ({len(deadlines)}):")
        for f in deadlines:
            rows.append(f"  {f.deadline_id} @ {f.due_date} [{f.type}] -> {f.case_ref}")

    block("UEBERFAELLIG", b.overdue)
    block("NAHE (<= Horizont)", b.near)
    block("UNBESTAETIGT (brauchen menschliche Bestaetigung)", b.unconfirmed)
    if b.problems:
        rows.append(f"PROBLEME ({len(b.problems)}):")
        for p in b.problems:
            rows.append(f"  {p}")
    return "\n".join(rows)


def _main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0].startswith("--"):
        print("Nutzung: python -m nupore.processes.guardian <register.yaml> "
              "[--today YYYY-MM-DD] [--horizon N]", file=sys.stderr)
        return 2
    path = args[0]
    today = date.today()
    horizon = 7
    i = 1
    while i < len(args):
        if args[i] == "--today" and i + 1 < len(args):
            today = date.fromisoformat(args[i + 1]); i += 2
        elif args[i] == "--horizon" and i + 1 < len(args):
            horizon = int(args[i + 1]); i += 2
        else:
            i += 1
    b = report(load_register(path), today, horizon)
    print(_format(b, today))
    # Exit-Codes getrennt: Registerfehler (2) wiegen schwerer als der fachliche
    # Ueberfaellig-Alarm (1); ein Scheduler darf einen kaputten Lauf nie als Erfolg sehen.
    if b.problems:
        return 2
    return 1 if b.overdue else 0   # overdue = sichtbares Alarmsignal


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
