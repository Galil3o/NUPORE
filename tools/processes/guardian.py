"""Guardian -- Fristen-/Terminwaechter (D21, PROCESS_GUARDIAN; projektneutral).

PROCESS_, kein Datenmodell (D20): der Prozess liest ein schlankes Fristen-Register
(YAML, im Git), bestimmt faellige/anstehende Fristen und meldet sie. Er ERINNERT,
handelt aber nicht riskant allein (Erledigung bleibt beim Menschen).

Leitplanken (R-016/R-018):
  - Interne To-dos (typ: intern) und rechtlich relevante Fristen (typ: rechtlich)
    bleiben unterscheidbar.
  - Aus E-Mail/Datei ABGELEITETE Fristen gelten erst nach menschlicher Bestaetigung
    als `bestaetigt: true`; unbestaetigte werden SEPARAT ausgewiesen, nie als
    gesicherte Frist gezaehlt.
  - Idempotenz: dieselbe Erinnerung fuer denselben Friststand wird wiedererkannt
    (frist_id + Stand + Erinnerungstyp).
  - Datengrenze: eine Erinnerung traegt NUR frist_id + fallreferenz + faelligkeit,
    keinen Akteninhalt/Originalbetreff.

CLI: python -m tools.processes.guardian <register.yaml> [--heute YYYY-MM-DD] [--horizont N]
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import yaml

_ERLEDIGT = "erfuellt"
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Frist:
    frist_id: str
    faelligkeit: str            # roh; strikt YYYY-MM-DD
    status: str = "offen"       # offen | erfuellt
    typ: str = "unbekannt"      # intern | rechtlich
    bestaetigt: bool = False
    fallreferenz: str = ""
    quelle: str = ""
    verantwortlicher: str = ""
    ausloeser: str = ""

    def datum(self) -> date | None:
        s = str(self.faelligkeit)
        if not _ISO.match(s):
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None


@dataclass
class Bericht:
    ueberfaellig: list[Frist]
    nahe: list[Frist]
    unbestaetigt: list[Frist]
    probleme: list[str]


def lade_register(pfad: str) -> list[Frist]:
    roh = yaml.safe_load(Path(pfad).read_text(encoding="utf-8")) or []
    if not isinstance(roh, list):
        raise ValueError(f"{pfad}: Register ist keine Liste von Fristen")
    fristen = []
    for e in roh:
        if not isinstance(e, dict):
            continue
        fristen.append(Frist(
            frist_id=str(e.get("frist_id", "")),
            faelligkeit=str(e.get("faelligkeit", "")),
            status=str(e.get("status", "offen")),
            typ=str(e.get("typ", "unbekannt")),
            bestaetigt=bool(e.get("bestaetigt", False)),
            fallreferenz=str(e.get("fallreferenz", "")),
            quelle=str(e.get("quelle", "")),
            verantwortlicher=str(e.get("verantwortlicher", "")),
            ausloeser=str(e.get("ausloeser", "")),
        ))
    return fristen


def bericht(fristen: list[Frist], heute: date, horizont: int = 7) -> Bericht:
    ueberfaellig: list[Frist] = []
    nahe: list[Frist] = []
    unbestaetigt: list[Frist] = []
    probleme: list[str] = []
    grenze = heute + timedelta(days=horizont)
    for f in fristen:
        if not f.frist_id:
            probleme.append(f"Eintrag ohne frist_id (faelligkeit={f.faelligkeit!r})")
            continue
        if f.status == _ERLEDIGT:
            continue
        d = f.datum()
        if d is None:
            probleme.append(f"{f.frist_id}: kaputtes/fehlendes faelligkeit {f.faelligkeit!r}")
            continue
        if not f.bestaetigt:
            unbestaetigt.append(f)      # abgeleitet, noch nicht menschlich bestaetigt
            continue
        if d < heute:
            ueberfaellig.append(f)
        elif d <= grenze:
            nahe.append(f)
    key = lambda f: (f.datum() or date.max, f.frist_id)
    return Bericht(sorted(ueberfaellig, key=key), sorted(nahe, key=key),
                   sorted(unbestaetigt, key=lambda f: f.frist_id), probleme)


def erinnerung_schluessel(f: Frist, erinnerungstyp: str) -> str:
    """Idempotent: gleicher Friststand -> gleicher Schluessel -> dieselbe
    Erinnerung wird wiedererkannt (nicht erneut zugestellt)."""
    return f"{f.frist_id}|{f.faelligkeit}|{f.status}|{erinnerungstyp}"


def erinnerung_payload(f: Frist) -> dict:
    """Datengrenze (R-018): NUR neutrale Kennung + Fallreferenz + Faelligkeit.
    KEIN Akteninhalt/Originalbetreff/Ausloesertext."""
    return {"frist_id": f.frist_id, "fallreferenz": f.fallreferenz, "faelligkeit": f.faelligkeit}


def _format(b: Bericht, heute: date) -> str:
    zeilen = [f"Guardian-Fristenbericht (Stichtag {heute.isoformat()})"]

    def block(titel: str, fristen: list[Frist]) -> None:
        zeilen.append(f"{titel} ({len(fristen)}):")
        for f in fristen:
            zeilen.append(f"  {f.frist_id} @ {f.faelligkeit} [{f.typ}] -> {f.fallreferenz}")

    block("UEBERFAELLIG", b.ueberfaellig)
    block("NAHE (<= Horizont)", b.nahe)
    block("UNBESTAETIGT (brauchen menschliche Bestaetigung)", b.unbestaetigt)
    if b.probleme:
        zeilen.append(f"PROBLEME ({len(b.probleme)}):")
        for p in b.probleme:
            zeilen.append(f"  {p}")
    return "\n".join(zeilen)


def _main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or args[0].startswith("--"):
        print("Nutzung: python -m tools.processes.guardian <register.yaml> "
              "[--heute YYYY-MM-DD] [--horizont N]", file=sys.stderr)
        return 2
    pfad = args[0]
    heute = date.today()
    horizont = 7
    i = 1
    while i < len(args):
        if args[i] == "--heute" and i + 1 < len(args):
            heute = date.fromisoformat(args[i + 1]); i += 2
        elif args[i] == "--horizont" and i + 1 < len(args):
            horizont = int(args[i + 1]); i += 2
        else:
            i += 1
    b = bericht(lade_register(pfad), heute, horizont)
    print(_format(b, heute))
    return 1 if b.ueberfaellig else 0   # ueberfaellig = sichtbares Alarmsignal


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
