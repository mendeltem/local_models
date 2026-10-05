"""Unit-Tests fuer frag.py. Ohne Laya-Dienst und ohne Agenten."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import frag
import pruef
from test_pruef import Attrappe, choice, noul


class TestZiel(unittest.TestCase):
    def test_sicher_geht_direkt(self):
        self.assertEqual(frag.ziel_fuer("coding", 0.95), ("opencode", False))
        self.assertEqual(frag.ziel_fuer("trivial", 0.9), ("hermes", False))

    def test_unsicher_wird_markiert(self):
        self.assertEqual(frag.ziel_fuer("coding", 0.6), ("opencode", True))

    def test_schwer_immer_claude(self):
        self.assertEqual(frag.ziel_fuer("schwer", 0.3), ("claude", False))


class TestBesteFassung(unittest.TestCase):
    def test_ohne_datei_grundfassung(self):
        route, nach = frag.beste_fassung("/gibt/es/nicht.json")
        self.assertEqual(route, pruef.REIHEN["route"][1])
        self.assertEqual(nach, pruef.REIHEN["nachpruefung"][1])

    def test_liest_optimierte_fassung(self):
        cfg = dict(pruef.REIHEN["route"][1], schwelle=0.6, coding=1)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"route": {"cfg": cfg}}, f)
        route, _ = frag.beste_fassung(f.name)
        Path(f.name).unlink()
        self.assertEqual(route["coding"], 1)
        # die Frage, die frag damit stellt, nutzt die zweite Formulierung
        q = pruef.route_fragen(route)
        self.assertEqual(q["route"]["criteria"]["coding"], pruef.ROUTE_POOL["coding"][1])


class TestEntscheidung(unittest.TestCase):
    def test_entscheide_liest_antwort(self):
        a = Attrappe(lambda t, q: {"route": dict(choice("coding", 0.93), probabilities={"coding": 0.93})})
        label, p, probs, _ = frag.entscheide(pruef.Laya(senden=a), "fix den bug", pruef.REIHEN["route"][1])
        self.assertEqual((label, p), ("coding", 0.93))

    def test_nachpruefen_kuerzt_auf_das_ende(self):
        gesehen = []

        def antwort(text, q):
            gesehen.append(text)
            return {"ohne_beleg": noul(0.81), "rueckfrage": noul(0.1)}
        h = frag.nachpruefen(pruef.Laya(senden=Attrappe(antwort)), "x" * 10000 + "ENDE",
                             pruef.REIHEN["nachpruefung"][1])
        self.assertEqual(h, {"ohne_beleg": 0.81, "rueckfrage": 0.1})
        self.assertEqual(len(gesehen[0]), frag.REST)
        self.assertTrue(gesehen[0].endswith("ENDE"))


class TestGit(unittest.TestCase):
    def test_nur_neue_aenderungen(self):
        vorher = {" M tools/lok.py", "?? alt/"}
        nachher = {" M tools/lok.py", "?? alt/", "?? tools/test_lok.py", " M tools/detect.py"}
        self.assertEqual(frag.neu_geaendert(vorher, nachher), ["tools/detect.py", "tools/test_lok.py"])

    def test_ohne_repo_none(self):
        self.assertIsNone(frag.neu_geaendert(None, set()))
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(frag.git_stand(d))

    def test_echtes_repo(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q", d], check=True)
            vorher = frag.git_stand(d)
            Path(d, "neu.py").write_text("x = 1\n")
            self.assertEqual(frag.neu_geaendert(vorher, frag.git_stand(d)), ["neu.py"])


class TestBericht(unittest.TestCase):
    def test_behauptung_ohne_aenderung_ist_laut(self):
        b = frag.bericht(0, [], {"ohne_beleg": 0.9, "rueckfrage": 0.1})
        self.assertIn("keine Datei geaendert", b)
        self.assertIn("ohne Beleg", b)
        self.assertIn("und keine Datei geaendert!", b)

    def test_unauffaellig_bleibt_kurz(self):
        b = frag.bericht(0, ["a.py"], {"ohne_beleg": 0.2, "rueckfrage": 0.1})
        self.assertNotIn("Laya", b)
        self.assertIn("1 Datei(en) geaendert: a.py", b)

    def test_rueckfrage(self):
        self.assertIn("Rueckfrage", frag.bericht(0, ["a"], {"ohne_beleg": 0.1, "rueckfrage": 0.7}))


class TestAusfuehren(unittest.TestCase):
    def test_ausgabe_und_code(self):
        code, rest = frag.ausfuehren([sys.executable, "-c", "print('hallo'); raise SystemExit(3)"])
        self.assertEqual(code, 3)
        self.assertIn("hallo", rest)

    def test_stdin_ist_zu(self):
        # opencode haengt bei offenem stdin; read() muss sofort leer zurueckkommen
        code, rest = frag.ausfuehren([sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"])
        self.assertEqual((code, rest.strip()), (0, "''"))


if __name__ == "__main__":
    unittest.main()
