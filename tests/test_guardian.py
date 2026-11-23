from datetime import date
from pathlib import Path

from nupore.processes.guardian import (
    Deadline, _main, report, reminder_payload, reminder_key, load_register,
)

FIXT = str(Path(__file__).resolve().parent / "fixtures" / "guardian" / "register.yaml")
HEUTE = date(2026, 1, 20)


def _b():
    return report(load_register(FIXT), HEUTE, horizon=7)


def test_ueberfaellig():
    assert [f.deadline_id for f in _b().overdue] == ["F-UEBER"]


def test_nahe_im_horizont():
    assert [f.deadline_id for f in _b().near] == ["F-NAHE"]  # 2026-01-22 <= 2026-01-27


def test_erledigte_werden_ignoriert():
    b = _b()
    alle = {f.deadline_id for f in b.overdue + b.near + b.unconfirmed}
    assert "F-ERLEDIGT" not in alle


def test_unbestaetigte_separat_nicht_als_frist():
    b = _b()
    assert [f.deadline_id for f in b.unconfirmed] == ["F-UNBEST"]
    assert "F-UNBEST" not in {f.deadline_id for f in b.overdue + b.near}


def test_kaputtes_datum_als_problem_statt_crash():
    assert any("F-KAPUTT" in p for p in _b().problems)


def test_idempotenter_schluessel_stabil_und_sensitiv():
    f = Deadline(deadline_id="F-1", due_date="2026-01-20", status="offen")
    k = reminder_key(f, "morning")
    assert reminder_key(f, "morning") == k          # stabil
    assert reminder_key(f, "taeglich") != k         # anderer Typ
    f2 = Deadline(deadline_id="F-1", due_date="2026-01-25", status="offen")
    assert reminder_key(f2, "morning") != k         # anderer Stand


def test_datengrenze_payload_ohne_akteninhalt():
    f = Deadline(deadline_id="F-1", due_date="2026-01-20", status="offen",
              case_ref="FALL-X", source="geheimer Betreff", trigger="Akteninhalt")
    p = reminder_payload(f)
    assert set(p) == {"deadline_id", "case_ref", "due_date"}
    assert "geheimer Betreff" not in str(p) and "Akteninhalt" not in str(p)


# --- Komplett-Review 2026-11-20: strikte Register-Eingangspruefung ---

def _schreibe(tmp_path, text):
    p = tmp_path / "reg.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_bestaetigt_string_false_nicht_als_wahrheit(tmp_path):
    # bool("false") == True -> ein String 'false' darf NICHT als confirmed gelten.
    reg = _schreibe(tmp_path, '- {deadline_id: F-S, due_date: "2026-01-01", '
                              'status: offen, confirmed: "false"}\n')
    b = report(load_register(reg), HEUTE, horizon=7)
    assert any("F-S" in p and "Boolean" in p for p in b.problems)
    assert "F-S" not in {f.deadline_id for f in b.overdue + b.near}


def test_nicht_mapping_eintrag_als_problem(tmp_path):
    b = report(load_register(_schreibe(tmp_path, '- "nur ein String"\n')), HEUTE)
    assert any("kein Mapping" in p for p in b.problems)


def test_null_frist_id_als_problem(tmp_path):
    reg = _schreibe(tmp_path, '- {deadline_id: null, due_date: "2026-01-01", confirmed: true}\n')
    b = report(load_register(reg), HEUTE)
    assert any("deadline_id" in p for p in b.problems)
    assert not b.overdue            # darf nicht als "None"-id auftauchen


def test_doppelte_frist_id_als_problem(tmp_path):
    reg = _schreibe(tmp_path,
                    '- {deadline_id: F-DUP, due_date: "2026-01-01", confirmed: true}\n'
                    '- {deadline_id: F-DUP, due_date: "2026-01-02", confirmed: true}\n')
    assert any("doppelt" in p for p in report(load_register(reg), HEUTE).problems)


def test_exit_code_registerfehler_nonzero_und_getrennt(tmp_path):
    # Registerfehler ohne ueberfaellige Deadline -> Exit 2 (nicht still 0).
    reg = _schreibe(tmp_path, '- {deadline_id: F-X, due_date: "2026-01-01", confirmed: "false"}\n')
    assert _main(["prog", reg, "--today", "2026-01-20"]) == 2
    # saubere, nicht ueberfaellige Deadline -> Exit 0.
    ok = _schreibe(tmp_path, '- {deadline_id: F-OK, due_date: "2099-01-01", status: offen, confirmed: true}\n')
    assert _main(["prog", ok, "--today", "2026-01-20"]) == 0
