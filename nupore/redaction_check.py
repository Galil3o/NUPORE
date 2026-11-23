"""Entkernungs-Pruefskript (config/README, docs/ENTKERNUNG-REGISTER).

Scannt einen Ziel-Baum gegen eine private Deny-Liste und schlaegt **fail-closed**
fehl, sobald etwas nicht sicher als sauber nachweisbar ist. Generisch + inhaltsfrei
(enthaelt selbst KEINE Tokens) -- wandert als Engine-Werkzeug mit NUPORE. Die
Deny-Liste selbst ist Kategorie A und bleibt in der privaten DNA-Instanz.

Haertung (Codex-Review Phase 1, Blocker 3 + Re-Review Runde 2):
  - Zielbaum muss existieren und >= 1 Textdatei tatsaechlich geprueft werden
    (nach Pfadausschluessen), sonst Exit 2 ("effektiv leer").
  - Deny-Liste muss existieren und >= min_tokens enthalten (sonst Exit 2).
  - Datei-INHALTE und Datei-NAMEN werden geprueft.
  - Fail-closed: nicht-UTF8/unlesbare Dateien, **Symlinks und Sonderdateien**
    gelten als unpruefbar (Exit 1) statt uebersprungen.
  - **Vollstaendige Redaktion in der Ausgabe:** gemeldet werden nur eine Pfad-
    KENNUNG (sha256, 12 hex) und der Token-INDEX -- nie der Pfad selbst und nie
    der Token-Wert. So gelangt weder die Deny-Liste noch ein sensibler Dateiname
    in Terminal-/Agenten-/CI-Protokolle.
  - Der Deny-Abgleich beweist nur die Abwesenheit BEKANNTER Tokens.

CLI: python -m nupore.redaction_check <target-baum> <deny-liste.txt> [--min-tokens N]
Exit 0 = sauber, 1 = Treffer/unpruefbar, 2 = Nutzungs-/Konfigurationsfehler.
"""
from __future__ import annotations

import hashlib
import sys
import unicodedata
from pathlib import Path

_DEFAULT_MIN_TOKENS = 5
_MIN_FLOOR = 1   # Sicherheitsboden: unter 1 Token ist die Deny-Pruefung wirkungslos


def _norm(s: str) -> str:
    """Unicode-NFKC + casefold: fail-closed-Normalisierung, die Gross-/Kleinschreibung
    UND ss/ß zusammenfuehrt, damit z. B. Deny `STRASSE` den Inhalt `Straße` faengt."""
    return unicodedata.normalize("NFKC", s).casefold()


def _pid(rel: str) -> str:
    """Redigierte Pfad-Kennung (gibt NIE den Pfad selbst preis)."""
    return hashlib.sha256(rel.encode("utf-8")).hexdigest()[:12]


def load_tokens(path: str) -> list[str]:
    """Ein Token je Zeile; Leerzeilen und #-Kommentare werden ignoriert."""
    tokens = []
    for zeile in Path(path).read_text(encoding="utf-8").splitlines():
        s = zeile.strip()
        if s and not s.startswith("#"):
            tokens.append(s)
    return tokens


def scan(target: str, tokens: list[str], deny_path: str | None = None
           ) -> tuple[list[tuple[str, int, int]], list[tuple[str, str]], int]:
    """Gibt (treffer, unpruefbar, geprueft) zurueck.
    treffer:    (pfad_id, zeile, token_index) -- Zeile 0 = Treffer im Dateinamen.
    unpruefbar: (pfad_id, reason) -- fail-closed (symlink/sonderdatei/nicht-utf8).
    geprueft:   Anzahl tatsaechlich inhaltlich gepruefter Dateien (nach Ausschluessen).
    Weder Pfade noch Token-Werte werden zurueckgegeben (Redaktion)."""
    treffer: list[tuple[str, int, int]] = []
    unpruefbar: list[tuple[str, str]] = []
    geprueft = 0
    idx = {_norm(t): i for i, t in enumerate(tokens)}
    lows = list(idx)
    deny_abs = str(Path(deny_path).resolve()) if deny_path else None
    base = Path(target)
    for p in sorted(base.rglob("*")):
        if ".git" in p.parts:
            continue
        rel = str(p.relative_to(base))
        pid = _pid(rel)
        if p.is_symlink():
            unpruefbar.append((pid, "symlink"))
            continue
        if p.is_dir():
            continue
        if not p.is_file():
            unpruefbar.append((pid, "sonderdatei"))
            continue
        if deny_abs and str(p.resolve()) == deny_abs:
            continue
        rl = _norm(rel)
        for low in lows:
            if low in rl:
                treffer.append((pid, 0, idx[low]))          # Dateiname-Treffer
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            unpruefbar.append((pid, "nicht-utf8"))
            continue
        geprueft += 1
        for i, zeile in enumerate(text.splitlines(), 1):
            zl = _norm(zeile)
            for low in lows:
                if low in zl:
                    treffer.append((pid, i, idx[low]))
    return treffer, unpruefbar, geprueft


def check(target: str, deny_path: str, min_tokens: int = _DEFAULT_MIN_TOKENS
           ) -> tuple[int, list[str]]:
    """Gehaertete Pruefung. Gibt (exit_code, meldungen) zurueck -- Meldungen sind
    vollstaendig redigiert (Pfad-Kennung + Token-Index)."""
    if not Path(target).is_dir():
        return 2, ["Zielbaum fehlt oder ist kein Verzeichnis."]
    if not Path(deny_path).is_file():
        return 2, ["Deny-Liste fehlt."]
    tokens = load_tokens(deny_path)
    # Sicherheitsboden: min_tokens kann die Pruefung nicht unter 1 Token aushebeln
    # (ein --min-tokens 0 + leere Deny-Liste darf nie als "sauber" durchgehen).
    if min_tokens < _MIN_FLOOR:
        min_tokens = _MIN_FLOOR
    # Mindestzahl auf der NORMALISIERT EINDEUTIGEN Regelmenge (NFKC+casefold, nicht
    # Rohzeilen): Duplikate und Gross-/Klein-/ss-ß-Varianten erhoehen die Zeilenzahl,
    # nicht die Abdeckung. Duplikate werden dismissed (Konfigurationsfehler).
    normalisiert = {_norm(t) for t in tokens}
    if len(normalisiert) != len(tokens):
        return 2, [f"Deny-Liste hat Duplikate/Case-Varianten ({len(tokens)} Zeilen, "
                   f"{len(normalisiert)} eindeutig) -- fail-closed."]
    if len(normalisiert) < min_tokens:
        return 2, [f"Deny-Liste zu kurz ({len(normalisiert)} eindeutig < {min_tokens}) -- fail-closed."]
    treffer, unpruefbar, geprueft = scan(target, tokens, deny_path=deny_path)
    if not treffer and not unpruefbar:
        if geprueft < 1:
            return 2, ["Kein einziges Textfile geprueft -- effektiv leer (fail-closed)."]
        return 0, [f"OK: Entkernung sauber ({len(tokens)} Token, {geprueft} Dateien, 0 Treffer)."]
    meldungen = []
    for pid, zeile, ti in treffer:
        ort = "Dateiname" if zeile == 0 else f"Zeile {zeile}"
        meldungen.append(f"TREFFER Datei {pid} ({ort}): Token #{ti} [redigiert]")
    for pid, reason in unpruefbar:
        meldungen.append(f"UNPRUEFBAR (fail-closed) Datei {pid}: {reason}")
    return 1, meldungen


def _main(argv: list[str]) -> int:
    positional: list[str] = []
    min_tokens = _DEFAULT_MIN_TOKENS
    i = 1
    while i < len(argv):
        if argv[i] == "--min-tokens" and i + 1 < len(argv):
            try:
                min_tokens = int(argv[i + 1])
            except ValueError:
                print("--min-tokens braucht eine Zahl", file=sys.stderr)
                return 2
            i += 2
            continue
        positional.append(argv[i])
        i += 1
    if len(positional) < 2:
        print("Nutzung: python -m nupore.redaction_check <target-baum> <deny-liste.txt> "
              "[--min-tokens N]", file=sys.stderr)
        return 2
    code, meldungen = check(positional[0], positional[1], min_tokens)
    strom = sys.stdout if code == 0 else sys.stderr
    for m in meldungen:
        print(m, file=strom)
    return code


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
