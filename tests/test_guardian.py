from datetime import date
from pathlib import Path

from tools.processes.guardian import (
    Frist, bericht, erinnerung_payload, erinnerung_schluessel, lade_register,
)

FIXT = str(Path(__file__).resolve().parent / "fixtures" / "guardian" / "register.yaml")
HEUTE = date(2026, 1, 20)


def _b():
    return bericht(lade_register(FIXT), HEUTE, horizont=7)


def test_ueberfaellig():
    assert [f.frist_id for f in _b().ueberfaellig] == ["F-UEBER"]


def test_nahe_im_horizont():
    assert [f.frist_id for f in _b().nahe] == ["F-NAHE"]  # 2026-01-22 <= 2026-01-27


def test_erledigte_werden_ignoriert():
    b = _b()
    alle = {f.frist_id for f in b.ueberfaellig + b.nahe + b.unbestaetigt}
    assert "F-ERLEDIGT" not in alle


def test_unbestaetigte_separat_nicht_als_frist():
    b = _b()
    assert [f.frist_id for f in b.unbestaetigt] == ["F-UNBEST"]
    assert "F-UNBEST" not in {f.frist_id for f in b.ueberfaellig + b.nahe}


def test_kaputtes_datum_als_problem_statt_crash():
    assert any("F-KAPUTT" in p for p in _b().probleme)


def test_idempotenter_schluessel_stabil_und_sensitiv():
    f = Frist(frist_id="F-1", faelligkeit="2026-01-20", status="offen")
    k = erinnerung_schluessel(f, "morning")
    assert erinnerung_schluessel(f, "morning") == k          # stabil
    assert erinnerung_schluessel(f, "taeglich") != k         # anderer Typ
    f2 = Frist(frist_id="F-1", faelligkeit="2026-01-25", status="offen")
    assert erinnerung_schluessel(f2, "morning") != k         # anderer Stand


def test_datengrenze_payload_ohne_akteninhalt():
    f = Frist(frist_id="F-1", faelligkeit="2026-01-20", status="offen",
              fallreferenz="FALL-X", quelle="geheimer Betreff", ausloeser="Akteninhalt")
    p = erinnerung_payload(f)
    assert set(p) == {"frist_id", "fallreferenz", "faelligkeit"}
    assert "geheimer Betreff" not in str(p) and "Akteninhalt" not in str(p)
