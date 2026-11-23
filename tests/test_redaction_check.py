from pathlib import Path

from nupore.redaction_check import _main, load_tokens, check, scan

FIXT = Path(__file__).resolve().parent / "fixtures" / "entkernung"
DENY = str(FIXT / "deny.txt")


def test_sauberer_baum_exit0():
    code, _ = check(str(FIXT / "clean"), DENY)
    assert code == 0


def test_leck_exit1_vollstaendig_redigiert():
    code, meldungen = check(str(FIXT / "dirty"), DENY)
    text = "\n".join(meldungen)
    assert code == 1
    assert "Token #" in text and "Datei " in text          # redigierte Kennung
    # Weder Token-Wert NOCH Rohpfad in der Ausgabe.
    assert "GEHEIMNAME" not in text and "docket_no-12345" not in text.lower()
    assert "leak.md" not in text and "dirty" not in text


def test_leere_deny_exit2(tmp_path):
    (tmp_path / "g").mkdir()
    (tmp_path / "g" / "a.md").write_text("harmlos", encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("# nur Kommentar\n", encoding="utf-8")
    assert check(str(tmp_path / "g"), str(deny))[0] == 2


def test_zu_kurze_deny_exit2(tmp_path):
    (tmp_path / "g").mkdir()
    (tmp_path / "g" / "a.md").write_text("harmlos", encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("EINS\nZWEI\n", encoding="utf-8")
    assert check(str(tmp_path / "g"), str(deny))[0] == 2


def test_fehlender_zielbaum_exit2():
    assert check(str(FIXT / "gibt_es_nicht"), DENY)[0] == 2


def test_deny_duplikate_case_variante_exit2(tmp_path):
    # Normalisiert eindeutige Mindestzahl: "Foo"/"FOO" sind EINE wirksame Regel ->
    # Duplikat/Case-Variante wird als Konfigurationsfehler fail-closed dismissed.
    (tmp_path / "g").mkdir()
    (tmp_path / "g" / "a.md").write_text("harmlos", encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("Foo\nFOO\nBar\nBaz\nQux\n", encoding="utf-8")   # 5 Zeilen, 4 eindeutig
    assert check(str(tmp_path / "g"), str(deny), min_tokens=3)[0] == 2


def test_leerer_zielbaum_exit2(tmp_path):
    (tmp_path / "leer").mkdir()
    assert check(str(tmp_path / "leer"), DENY)[0] == 2   # geprueft < 1 -> fail-closed


def test_nur_ausgeschlossene_dateien_exit2(tmp_path):
    # Verzeichnis mit nur .git-Inhalt -> nichts geprueft -> effektiv leer.
    g = tmp_path / "g"
    (g / ".git").mkdir(parents=True)
    (g / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert check(str(g), DENY)[0] == 2


def test_binaerdatei_fail_closed_exit1(tmp_path):
    g = tmp_path / "g"
    g.mkdir()
    (g / "ok.md").write_text("harmlos", encoding="utf-8")
    (g / "blob.bin").write_bytes(b"\xff\xfe\x00\x01\x80")
    code, meldungen = check(str(g), DENY)
    assert code == 1 and any("nicht-utf8" in m for m in meldungen)


def test_symlink_fail_closed_exit1(tmp_path):
    g = tmp_path / "g"
    g.mkdir()
    (g / "ok.md").write_text("harmlos", encoding="utf-8")
    (g / "link").symlink_to(g / "ok.md")
    code, meldungen = check(str(g), DENY)
    assert code == 1 and any("symlink" in m for m in meldungen)


def test_token_im_dateinamen_ohne_pfad_in_ausgabe(tmp_path, capsys):
    g = tmp_path / "g"
    g.mkdir()
    (g / "GEHEIMNAME_akte.md").write_text("inhaltlich harmlos", encoding="utf-8")
    code = _main(["prog", str(g), DENY])
    erfasst = capsys.readouterr()
    gesamt = erfasst.out + erfasst.err
    assert code == 1
    assert "Dateiname" in gesamt                     # Treffer-Art gemeldet
    # Der sensible Dateiname/Marker erscheint in KEINER Ausgabe (stdout+stderr).
    assert "GEHEIMNAME" not in gesamt


def test_scanne_gibt_keine_pfade_oder_werte_zurueck():
    treffer, unpruefbar, geprueft = scan(str(FIXT / "dirty"), load_tokens(DENY))
    assert geprueft >= 1
    for pid, zeile, ti in treffer:
        assert isinstance(ti, int) and len(pid) == 12 and "/" not in pid


# --- Komplett-Review 2026-11-20: Fail-open-Pfade geschlossen ---

def test_min_tokens_null_hebelt_pruefung_nicht_aus(tmp_path):
    # --min-tokens 0 + leere Deny-Liste darf NIE als "sauber" (Exit 0) durchgehen.
    g = tmp_path / "g"; g.mkdir()
    (g / "a.md").write_text("harmlos", encoding="utf-8")
    deny = tmp_path / "deny.txt"; deny.write_text("", encoding="utf-8")
    assert check(str(g), str(deny), min_tokens=0)[0] == 2


def test_unicode_casefold_strasse_matcht(tmp_path):
    # Deny `HAUPTSTRASSE` muss den Inhalt `Hauptstraße` fangen (ß == ss, NFKC+casefold).
    g = tmp_path / "g"; g.mkdir()
    (g / "a.md").write_text("Adresse: Hauptstraße 1", encoding="utf-8")
    deny = tmp_path / "deny.txt"
    deny.write_text("HAUPTSTRASSE\nEINS\nZWEI\nDREI\nVIER\n", encoding="utf-8")
    code, meld = check(str(g), str(deny))
    assert code == 1 and any("TREFFER" in m for m in meld)
