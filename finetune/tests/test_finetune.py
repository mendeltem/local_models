"""Tests fuer das Finetune-Geruest. Ohne Netz, ohne GPU, ohne echtes Modell."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "training"))
import ausfragen  # noqa: E402
import erzeugen  # noqa: E402
import unsloth_sft  # noqa: E402
from quellen import usecases, wiki  # noqa: E402

EINTRAG = """---
id: kein-zyklus
typ: regel
status: getragen
thema: knowledge/speicher
stand: 2026-10-03
herkunft: Vorgabe Mendel
verweist_auf: [a, b]
---

# Kein Standardzyklus ohne Pruefung

## Aussage
Erst die Absorption pruefen.

## Trägt
Neue Chats.

## Trägt nicht
Dass ein Zyklus ausgeschlossen ist.

## Bruchindikator
keiner, Verfahrensregel
"""

README = """# wiki
| Typ | Ordner | Bedeutung |
|---|---|---|
| axiom | `axioms/` | Setzung von Mendel. Kein Befund. |
| befund | `findings/` | Belegtes Ergebnis mit Quelle und Datum. |

Status: `getragen`, `vorschlag` (unbestätigt oder mit Annahme), `offen`, `gebrochen` (bleibt stehen, mit Datum und Quelle).
"""

SEITE = """<script>
const CLUSTERS = [
  {n:1, title:{en:"Mobility", de:"Mobilität"}},
];
function U(c,prov,mat,q,g,name,glab,metric,detail,src,ft,fx){return {c};}
const E=(en,de)=>({en,de});
const UC = [
  // ---- Cluster 1 ----
  U(1,"Waymo","prod",3,"explosive",
    E("Robotaxis","Robotaxis"), E("x","x"), E("<b>~500k rides</b>","<b>~500k Fahrten</b>"),
    E("Detail: 50k -> 500k; \\"Zitat\\" // kein Kommentar","Detail: 50k → 500k; \\"Zitat\\" // kein Kommentar"),
    E("Waymo (2026)","Waymo (2026)"), "good", E("tracked","erfasst")),
  U(1,"Aurora","early",1,"strong", E("Trucks","Trucks"), E("y","y"), E("100k miles","100k Meilen"),
    E("d","d"), E("s","s"), "warn", null),
];
</script>"""


class TestQuellen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        w = Path(self.tmp.name)
        (w / "knowledge" / "speicher" / "rules").mkdir(parents=True)
        (w / "knowledge" / "speicher" / "rules" / "kein-zyklus.md").write_text(EINTRAG)
        (w / "knowledge" / "speicher" / "INDEX.md").write_text("# index")
        (w / "README.md").write_text(README)
        self.w = w

    def tearDown(self):
        self.tmp.cleanup()

    def test_wiki_eintrag(self):
        (f,) = wiki.lies_wiki(self.w)
        self.assertEqual(f["id"], "wiki/speicher/kein-zyklus")
        self.assertEqual((f["typ"], f["status"], f["verweist_auf"]), ("regel", "getragen", ["a", "b"]))
        self.assertEqual(f["traegt_nicht"], "Dass ein Zyklus ausgeschlossen ist.")
        self.assertEqual(f["titel"], "Kein Standardzyklus ohne Pruefung")

    def test_bereichsfilter(self):
        self.assertEqual(wiki.lies_wiki(self.w, bereiche=["anderes"]), [])

    def test_begriffe(self):
        b = {x["begriff"]: x for x in wiki.lies_begriffe(self.w)}
        self.assertEqual(b["axiom"]["art"], "typ")
        self.assertEqual(b["vorschlag"]["bedeutung"], "unbestätigt oder mit Annahme")
        self.assertFalse(b["Trägt nicht"]["geprueft"])  # selbst formuliert, nicht aus der Wiki

    def test_usecases(self):
        p = self.w / "index.html"
        p.write_text(SEITE)
        a, b = usecases.lies_usecases(p)
        self.assertEqual(a["id"], "usecases/robotaxis")
        self.assertEqual((a["status"], a["beleg"], b["status"], b["beleg"]), ("getragen", "solide", "vorschlag", "duenn"))
        self.assertIn("~500k Fahrten", a["aussage"])            # HTML entfernt
        self.assertIn("// kein Kommentar", a["aussage"])        # // im String ist kein Kommentar
        self.assertIn('"Zitat"', a["aussage"])
        self.assertEqual(a["cluster"], "Mobilität")
        self.assertEqual(b["beleg_hinweis"], "")                 # null-Hinweis

    def test_usecases_lehnt_fremde_aufrufe_ab(self):
        with self.assertRaises(ValueError):
            usecases.auswerten('[U(1,"a","p",3,"g",E("a","b"),0,0,0,0), open("x")]')


class Attrappe:
    def __init__(self, antworten):
        self.antworten, self.gesehen = antworten, []

    def __call__(self, nutzlast):
        frage = nutzlast["messages"][-1]["content"]
        self.gesehen.append(nutzlast)
        return {"choices": [{"message": {"content": self.antworten(frage)}}], "usage": {"completion_tokens": 3}}


MC = {"id": "m", "art": "wirkung", "form": "mc", "frage": "F?", "optionen": {"A": "a", "B": "b", "C": "c", "D": "d"}, "richtig": "B"}
FREI = {"id": "f", "art": "wirkung", "form": "frei", "frage": "F?", "muss": [["hbm"], ["je gpu", "pro gpu"]], "darf_nicht": ["rein zyklisch"]}


class TestAusfragen(unittest.TestCase):
    def test_buchstabe(self):
        erlaubt = set("ABCD")
        for text, b in (("B", "B"), ("B) weil", "B"), ("(C)", "C"), ("Antwort: D", "D"), ("Die richtige Option ist A) a", "A"),
                        ("A oder B", "A"), ("keine Ahnung", None)):
            self.assertEqual(ausfragen.lies_buchstabe(text, erlaubt), b, text)

    def test_frei(self):
        self.assertEqual(ausfragen.bewerte(FREI, "HBM wächst je GPU stark")[0], 1)
        self.assertEqual(ausfragen.bewerte(FREI, "HBM wächst stark")[0], 0)
        p, grund = ausfragen.bewerte(FREI, "HBM pro GPU, aber rein zyklisch")
        self.assertEqual(p, 0)
        self.assertIn("verboten", grund)

    def test_umlaute_gleich(self):
        s = dict(FREI, muss=[["Größe"]], darf_nicht=[])
        self.assertEqual(ausfragen.bewerte(s, "die groesse")[0], 1)

    def test_denken_entfernt(self):
        self.assertEqual(ausfragen.ohne_denken("<think>A ist falsch</think>B"), "B")
        self.assertEqual(ausfragen.ohne_denken("erst denken</think>\nC"), "C")

    def test_mischen_haelt_richtige_antwort(self):
        for n in range(4):
            opt, richtig = ausfragen.mischung(MC, n)
            self.assertEqual(opt[richtig], "b")
        self.assertNotEqual(ausfragen.mischung(MC, 1)[1], ausfragen.mischung(MC, 0)[1])

    def test_lauf_mit_attrappe(self):
        a = Attrappe(lambda f: "B" if "A)" in f else "HBM je GPU")
        m = ausfragen.Modell("http://x/v1", "test", {"reasoning_effort": "none"}, senden=a)
        erg = ausfragen.ausfragen(m, [MC, FREI], log=lambda *_: None)
        self.assertEqual([e["punkt"] for e in erg], [1, 1])
        self.assertEqual(a.gesehen[0]["reasoning_effort"], "none")
        self.assertEqual(a.gesehen[0]["temperature"], 0)
        self.assertEqual(ausfragen.zusammenfassen(erg)["wirkung"]["anteil"], 1.0)

    def test_vergleich(self):
        with tempfile.TemporaryDirectory() as d:
            for name, punkte in (("a", [0, 1]), ("b", [1, 0])):
                zeilen = [{"modell": name}] + [{"id": i, "runde": 0, "art": "wirkung", "punkt": p} for i, p in zip("xy", punkte)]
                Path(d, name).write_text("\n".join(json.dumps(z) for z in zeilen))
            text = ausfragen.vergleiche(Path(d, "a"), Path(d, "b"))
        self.assertIn("verbessert     x", text)
        self.assertIn("VERSCHLECHTERT y", text)

    def test_echte_sonden_gueltig(self):
        sonden = ausfragen.lade_sonden()
        self.assertGreaterEqual(len(sonden), 18)
        for s in sonden:
            self.assertIn(s["art"], ausfragen.ARTEN, s["id"])
            if s["form"] == "mc":
                self.assertIn(s["richtig"], s["optionen"], s["id"])
            else:
                self.assertTrue(s["muss"], s["id"])


class TestErzeugen(unittest.TestCase):
    F = {"id": "wiki/x/y", "titel": "T", "aussage": "A", "traegt_nicht": "N", "bruchindikator": "keiner",
         "typ": "mechanismus", "status": "vorschlag"}

    def test_status_bestimmt_antwort(self):
        b = erzeugen.aus_vorlagen([self.F], [])
        arten = {x["art"]: x["messages"][2]["content"] for x in b}
        self.assertTrue(arten["aussage"].startswith("Unbestätigt"))
        self.assertEqual(arten["grenze"], "N")
        self.assertNotIn("bruch", arten)                       # "keiner" wird nicht trainiert
        self.assertIn("unbestätigter Vorschlag", arten["status"])

    def test_axiom_ist_setzung(self):
        b = erzeugen.aus_vorlagen([dict(self.F, typ="axiom", status="getragen")], [])
        a = {x["art"]: x["messages"][2]["content"] for x in b}
        self.assertTrue(a["aussage"].startswith("Das ist eine Setzung von Mendel"))
        self.assertIn("Axiom", a["status"])

    def test_getragen_ohne_statusfrage(self):
        b = erzeugen.aus_vorlagen([dict(self.F, status="getragen")], [])
        self.assertNotIn("status", {x["art"] for x in b})

    def test_llm_entwuerfe_ungeprueft_und_validiert(self):
        antwort = json.dumps([{"frage": "F", "optionen": {"A": "1", "B": "2", "C": "3", "D": "4"}, "richtig": "C"},
                              {"frage": "kaputt", "optionen": {"A": "1"}, "richtig": "A"}])
        llm = erzeugen.LLM("http://x/v1", "m", senden=Attrappe(lambda f: "Hier: " + antwort))
        s = erzeugen.sonden_entwurf(llm, [self.F], log=lambda *_: None)
        self.assertEqual(len(s), 1)
        self.assertFalse(s[0]["geprueft"])
        self.assertEqual(s[0]["art"], "umschreibung")

    def test_ueberschneidung_wird_erkannt(self):
        with tempfile.TemporaryDirectory() as d:
            daten = Path(d)
            erzeugen.schreibe(daten / "train" / "x.jsonl",
                              [erzeugen.beispiel("Was ist 17 mal 23? Antworte nur mit der Zahl!", "391", "", "x")])
            with mock.patch.object(erzeugen, "DATEN", daten):
                verstoss, _, n, _ = erzeugen.pruefen()
        self.assertEqual(n, 1)
        self.assertIn("erhalt-rechnen", verstoss)              # Satzzeichen und Gross/klein egal


class TestTraining(unittest.TestCase):
    def test_trocken_laedt_und_filtert(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.jsonl")
            p.write_text("\n".join(json.dumps(erzeugen.beispiel("f", "a", f, "x", g)) for f, g in
                                   (("wiki/memory_supply/a", True), ("usecases/b", False))))
            cfg = {"daten": {"dateien": [str(p)], "nur_geprueft": False, "bereiche": ["memory_supply"]},
                   "training": {"seed": 1}}
            self.assertEqual([b["fakt"] for b in unsloth_sft.lade_daten(cfg)], ["wiki/memory_supply/a"])
            cfg["daten"].update(bereiche=[], nur_geprueft=True)
            self.assertEqual(len(unsloth_sft.lade_daten(cfg)), 1)

    def test_kaputtes_beispiel(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.jsonl")
            p.write_text(json.dumps({"messages": [{"role": "user", "content": "f"}], "fakt": "x"}))
            with self.assertRaises(ValueError):
                unsloth_sft.lade_daten({"daten": {"dateien": [str(p)]}, "training": {"seed": 1}})

    def test_config_vollstaendig(self):
        cfg = json.loads((HIER / "training" / "config.json").read_text())
        for k in ("modell", "lora", "training", "daten", "ausgabe", "gguf"):
            self.assertIn(k, cfg)
        self.assertFalse(cfg["load_in_4bit"])                   # Qwen3.5: kein QLoRA


if __name__ == "__main__":
    unittest.main()
