"""Tests fuer schicht.py. Ohne GPU und ohne Agenten: der Ende-zu-Ende-Test nutzt
das Werkzeug "befehl" in einem frischen Git-Repo."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import schicht


def schreibe(ordner, name, text, abnahme):
    Path(ordner, f"{name}.txt").write_text(text)
    Path(ordner, f"{name}.abnahme").write_text(abnahme)


class TestAuftrag(unittest.TestCase):
    def test_kopf_und_pruefungen(self):
        with tempfile.TemporaryDirectory() as d:
            schreibe(d, "01-x", "mach was\n", "# werkzeug: hermes\n# grenze: 15\n# nach: 00-y\n"
                     "# freier Kommentar\ndatei a.py\n\nbefehl true\n")
            a = schicht.lies_auftrag(Path(d, "01-x.txt"))
        self.assertEqual((a["werkzeug"], a["grenze_min"], a["nach"]), ("hermes", 15.0, "00-y"))
        self.assertEqual(a["pruefungen"], ["datei a.py", "befehl true"])
        self.assertEqual(a["text"], "mach was")

    def test_standardwerte_ohne_abnahme(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "01-x.txt").write_text("t")
            a = schicht.lies_auftrag(Path(d, "01-x.txt"))
        self.assertEqual((a["werkzeug"], a["grenze_min"], a["pruefungen"]), ("opencode", 40.0, []))

    def test_echte_auftraege_lesbar(self):
        auftraege = schicht.alle_auftraege()
        self.assertTrue(auftraege)
        namen = {a["name"] for a in auftraege}
        for a in auftraege:
            self.assertIn(a["werkzeug"], ("opencode", "hermes", "befehl"), a["name"])
            self.assertTrue(a["pruefungen"], f"{a['name']} hat keine Abnahme")
            if a["nach"]:
                self.assertIn(a["nach"], namen, f"{a['name']}: Vorgaenger fehlt")


class TestReihenfolge(unittest.TestCase):
    A = [{"name": "01", "nach": ""}, {"name": "02", "nach": "01"}, {"name": "03", "nach": ""}]

    def test_erster_offener(self):
        self.assertEqual(schicht.naechster(self.A, {})["name"], "01")

    def test_wartet_auf_bestandenen_vorgaenger(self):
        nicht = {"01": {"bestanden": False}}
        self.assertEqual(schicht.naechster(self.A, nicht)["name"], "03")
        ja = {"01": {"bestanden": True}}
        self.assertEqual(schicht.naechster(self.A, ja)["name"], "02")

    def test_nichts_mehr(self):
        alle = {n: {"bestanden": True} for n in ("01", "02", "03")}
        self.assertIsNone(schicht.naechster(self.A, alle))


class TestAbnahme(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        Path(self.d.name, "a.py").write_text("def f():\n    return 42\n")
        Path(self.d.name, "out").mkdir()
        for i in range(3):
            Path(self.d.name, "out", f"z{i}.txt").write_text(str(i))

    def tearDown(self):
        self.d.cleanup()

    def p(self, zeile):
        return schicht.pruefe(zeile, self.d.name)[0]

    def test_verben_gut_und_schlecht(self):
        # jede Pruefung gegen ein bekannt gutes UND ein bekannt schlechtes Ergebnis
        self.assertTrue(self.p("datei a.py"))
        self.assertFalse(self.p("datei b.py"))
        self.assertTrue(self.p("genau out/*.txt 3"))
        self.assertFalse(self.p("genau out/*.txt 4"))
        self.assertTrue(self.p("enthaelt a.py return 42"))
        self.assertFalse(self.p("enthaelt a.py return 43"))
        self.assertTrue(self.p("befehl python3 -c 'import a; assert a.f() == 42'"))
        self.assertFalse(self.p("befehl python3 -c 'import a; assert a.f() == 0'"))

    def test_unbekanntes_verb_faellt_durch(self):
        ok, hinweis = schicht.pruefe("vielleicht a.py", self.d.name)
        self.assertFalse(ok)
        self.assertIn("unbekannt", hinweis)

    def test_befehl_zeitgrenze(self):
        with mock.patch.object(schicht, "BEFEHL_GRENZE", 1):
            ok, hinweis = schicht.pruefe("befehl sleep 5", self.d.name)
        self.assertEqual((ok, hinweis), (False, "Zeitgrenze"))


class TestSchonung(unittest.TestCase):
    def test_pause_mindestens_und_halbe_laufzeit(self):
        self.assertEqual(schicht.pause_nach(60), schicht.PAUSE_MIN * 60)
        self.assertEqual(schicht.pause_nach(7200), 3600)

    def frei(self, **ueber):
        werte = dict(gpu=(50, []), ram=16.0, mensch=None)
        werte.update(ueber)
        with mock.patch.object(schicht, "gpu_zustand", return_value=werte["gpu"]), \
             mock.patch.object(schicht, "ram_frei_gb", return_value=werte["ram"]), \
             mock.patch.object(schicht, "mensch_aktiv", return_value=werte["mensch"]):
            return schicht.warum_warten()

    def test_gruende(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(schicht, "PAUSE", Path(d, "pause")):
            self.assertIsNone(self.frei())
            self.assertIn("Grad", self.frei(gpu=(80, [])))
            self.assertIn("fremder", self.frei(gpu=(50, ["123, llama-server"])))
            self.assertIn("RAM", self.frei(ram=2.0))
            self.assertIn("Mensch", self.frei(mensch="opencode run x"))
            Path(d, "pause").touch()
            self.assertIn("Pausendatei", self.frei())

    def test_warte_bis_frei_schlaeft_bis_grund_weg(self):
        gruende = iter(["GPU 80 Grad", "GPU 80 Grad", None])
        geschlafen = []
        with mock.patch.object(schicht, "warum_warten", side_effect=lambda: next(gruende)):
            schicht.warte_bis_frei(log=lambda m: None, schlafen=geschlafen.append)
        self.assertEqual(len(geschlafen), 2)

    def test_mensch_erkennung(self):
        ps = ("  10 opencode run Schreib Tests\n  11 /usr/bin/python3 /home/v/.local/bin/frag x\n"
              "  12 hermes gateway run\n  13 /bin/bash\n")
        with mock.patch.object(schicht.subprocess, "run", return_value=mock.Mock(stdout=ps)):
            self.assertIn("opencode", schicht.mensch_aktiv())
            self.assertIsNone(schicht.mensch_aktiv(eigene={10, 11}))


class TestEndeZuEnde(unittest.TestCase):
    """Echter Durchlauf mit Werkzeug 'befehl': Arbeitsbaum, Abnahme, Commit, Aufraeumen."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repo = t / "repo"
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        (self.repo / "README").write_text("x\n")
        g = ["git", "-C", str(self.repo)] + schicht.IDENTITAET
        subprocess.run(g + ["add", "."], check=True)
        subprocess.run(g + ["commit", "-q", "-m", "start"], check=True)
        self.patches = [mock.patch.object(schicht, "HOME", t / "home"),
                        mock.patch.object(schicht, "ERGEBNISSE", t / "home" / "ergebnisse.jsonl"),
                        mock.patch.object(schicht, "laya_hinweis", return_value=None)]
        for p in self.patches:
            p.start()
        (t / "home").mkdir()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def auftrag(self, text, pruefungen, grenze_min=1):
        return {"name": "01-test", "text": text, "werkzeug": "befehl", "grenze_min": grenze_min,
                "repo": str(self.repo), "nach": "", "pruefungen": pruefungen}

    def zweige(self):
        r = subprocess.run(["git", "-C", str(self.repo), "branch", "--list", "schicht/*"],
                           capture_output=True, text=True)
        return r.stdout.split()

    def test_bestanden_landet_auf_eigenem_zweig(self):
        e = schicht.ein_auftrag(self.auftrag("echo 42 > antwort.txt", ["enthaelt antwort.txt 42"]), log=lambda m: None)
        self.assertTrue(e["bestanden"])
        self.assertTrue(e["zweig"].startswith("schicht/01-test-"))
        # Arbeitsordner des Menschen unberuehrt, Ergebnis nur auf dem Zweig
        self.assertFalse((self.repo / "antwort.txt").exists())
        inhalt = subprocess.run(["git", "-C", str(self.repo), "show", f"{e['zweig']}:antwort.txt"],
                                capture_output=True, text=True).stdout
        self.assertEqual(inhalt.strip(), "42")
        msg = subprocess.run(["git", "-C", str(self.repo), "log", "-1", "--format=%an|%B", e["zweig"]],
                             capture_output=True, text=True).stdout
        self.assertTrue(msg.startswith("schicht (Qwen lokal)|schicht 01-test: 1/1 Abnahme"))
        # Arbeitsbaum entfernt, Ergebnis protokolliert
        self.assertFalse(list((schicht.HOME / "baeume").iterdir()))
        self.assertEqual(json.loads(schicht.ERGEBNISSE.read_text())["name"], "01-test")

    def test_ohne_aenderung_kein_zweig(self):
        e = schicht.ein_auftrag(self.auftrag("true", ["datei antwort.txt"]), log=lambda m: None)
        self.assertFalse(e["bestanden"])
        self.assertIsNone(e["zweig"])
        self.assertEqual(self.zweige(), [])

    def test_zeitgrenze_bricht_ab(self):
        e = schicht.ein_auftrag(self.auftrag("echo teil > a.txt; sleep 30", ["datei a.txt"], grenze_min=0.05),
                                log=lambda m: None)
        self.assertTrue(e["abgebrochen"])
        self.assertFalse(e["bestanden"])  # Abnahme erfuellt, aber Zeitgrenze zaehlt als nicht bestanden
        self.assertLess(e["dauer_s"], 20)

    def test_nachfolger_baut_auf_vorgaenger_auf(self):
        e1 = schicht.ein_auftrag(self.auftrag("echo 42 > antwort.txt", ["datei antwort.txt"]), log=lambda m: None)
        a2 = dict(self.auftrag("cat antwort.txt > kopie.txt", ["enthaelt kopie.txt 42"]), name="02-folge")
        e2 = schicht.ein_auftrag(a2, log=lambda m: None, basis=e1["zweig"])
        self.assertTrue(e2["bestanden"], e2["abnahme"])
        # ohne Basis fehlt die Datei des Vorgaengers
        a3 = dict(a2, name="03-ohne")
        self.assertFalse(schicht.ein_auftrag(a3, log=lambda m: None)["bestanden"])

    def test_stand_datei(self):
        a = self.auftrag("echo 42 > antwort.txt", ["enthaelt antwort.txt 42"])
        with mock.patch.object(schicht, "STAND", schicht.HOME / "STAND.md"):
            schicht.ein_auftrag(a, log=lambda m: None)
            schicht.schreibe_stand([a, dict(a, name="02-offen", nach="01-test")], schicht.ergebnisse())
            stand = (schicht.HOME / "STAND.md").read_text()
        self.assertIn("| 01-test | bestanden 1/1 |", stand)
        self.assertIn("| 02-offen | offen (nach 01-test) |", stand)


if __name__ == "__main__":
    unittest.main()
