"""Tests fuer alltag.py: jede Aufgabe gegen eine bekannt gute und eine bekannt schlechte
Antwort, damit keine Pruefung alles durchwinkt oder alles ablehnt."""

import json
import unittest

import alltag

GUT = {
    "01-kosten": "302,40",
    "02-wochentag": "Freitag",
    "03-mail-json": '```json\n{"name": "Petra Lindqvist", "datum": "2026-03-03", "betrag": 1249.90}\n```',
    "04-tickets": '["rechnung", "technik", "kündigung", "rechnung", "technik"]',
    "05-uebersetzen": "The delivery is delayed by two weeks because a component is missing. We apologize.",
    "06-zusammenfassen": "- Fernwärmenetz Nordviertel wird ab Mai erneuert, rund 1.800 Haushalte betroffen.\n"
                         "- Warmwasser-Unterbrechungen werden 48 Stunden vorher angekündigt.\n"
                         "- Fertigstellung im Herbst 2027, Kosten 14 Mio. Euro.",
    "07-regex": r"\b\d{5}\b",
    "08-slugify": "```python\nimport re\n\ndef slugify(text):\n    t = text.lower()\n"
                  "    for a, b in (('ä','ae'),('ö','oe'),('ü','ue'),('ß','ss')):\n        t = t.replace(a, b)\n"
                  "    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')\n```",
    "09-bugfix": "def gleitender_schnitt(werte, n):\n    teil = werte[-n:]\n    return sum(teil) / n",
    "10-sql": "SELECT k.name, SUM(b.betrag) AS umsatz FROM kunden k JOIN bestellungen b ON b.kunde_id = k.id "
              "GROUP BY k.id ORDER BY umsatz DESC LIMIT 1;",
    "11-shell": "find . -type f -name '*.log' -mtime +7 | wc -l",
    "12-log": "3",
    "13-csv": "Nord",
    "14-commit": "fix(client): timeout fuer grosse Exporte auf 30 s erhoehen",
    "15-unbekannt": "Dazu liegen mir keine verlässlichen Informationen vor; die Firma ist mir nicht bekannt.",
    "16-primzahlen": "[53, 59, 61, 67, 71, 73, 79]",
    "17-zaehlen": "4",
    "18-mail": "Sehr geehrter Herr Krause,\n\nseit drei Tagen ist die Heizung im Bad kalt. "
               "Könnten Sie bitte einen Termin mit einem Handwerker vereinbaren?\n\nVielen Dank und freundliche Grüße",
    "19-gib": "22,35",
    "20-code-lesen": "8 4",
}

SCHLECHT = {
    "01-kosten": "302,04",
    "02-wochentag": "Donnerstag",
    "03-mail-json": '{"name": "Petra Lindqvist", "datum": "03.03.2026", "betrag": 1249.9}',
    "04-tickets": '["rechnung", "technik", "kuendigung", "technik", "technik"]',
    "05-uebersetzen": "The Lieferung is late by two weeks. Sorry.",
    "06-zusammenfassen": "- Netz wird erneuert.\n- Kosten 14 Mio.",
    "07-regex": r"\d{5}",
    "08-slugify": "def slugify(text):\n    return text.lower().replace(' ', '-')",
    "09-bugfix": "def gleitender_schnitt(werte, n):\n    teil = werte[-n:-1]\n    return sum(teil) / len(teil)",
    "10-sql": "SELECT name, betrag AS umsatz FROM kunden JOIN bestellungen ON kunde_id = kunden.id "
              "ORDER BY betrag DESC LIMIT 1;",
    "11-shell": "find . -name '*.log' -mtime +7 -delete | wc -l",
    "12-log": "4",
    "13-csv": "Sued",
    "14-commit": "Timeout erhoeht",
    "15-unbekannt": "Die Brennholz Kowalski GmbH erzielte 2025 rund 2,3 Mio. Euro Umsatz.",
    "16-primzahlen": "[51, 53, 59, 61, 67, 71, 73, 79]",
    "17-zaehlen": "3",
    "18-mail": "Hallo, kannst du dich bitte um die Heizung im Bad kümmern und einen Termin machen?",
    "19-gib": "24",
    "20-code-lesen": "7 4",
}


class TestJedeAufgabe(unittest.TestCase):
    def test_gut_und_schlecht_fuer_alle_20(self):
        aufgaben = alltag.lade()
        self.assertEqual(len(aufgaben), 20)
        self.assertEqual({a["id"] for a in aufgaben}, set(GUT), "jede Aufgabe braucht ein gutes Beispiel")
        self.assertEqual(set(GUT), set(SCHLECHT))
        for a in aufgaben:
            with self.subTest(a["id"]):
                ok, grund = alltag.bewerte(a, GUT[a["id"]])
                self.assertTrue(ok, f"gute Antwort abgelehnt: {grund}")
                ok, grund = alltag.bewerte(a, SCHLECHT[a["id"]])
                self.assertFalse(ok, f"schlechte Antwort angenommen: {grund}")

    def test_routen_gueltig(self):
        for a in alltag.lade():
            self.assertIn(a["route"], ("trivial", "coding"), a["id"])


class TestHilfen(unittest.TestCase):
    def test_zahl_aus(self):
        for text, soll in (("302,40 €", 302.4), ("Das sind 1.249,90 Euro", 1249.9), ("22.35", 22.35),
                           ("Antwort: 1.800", 1800.0), ("keine", None), ("Es sind 4.", 4.0)):
            self.assertEqual(alltag.zahl_aus(text), soll, text)

    def test_denkteil_entfernt(self):
        self.assertEqual(alltag.ohne_denken("<think>lang</think>\n4"), "4")
        self.assertEqual(alltag.ohne_denken("halb</think>4"), "4")

    def test_python_endlosschleife_hat_zeitgrenze(self):
        a = {"art": "python", "tests": "assert True"}
        ok, grund = alltag.p_python(a, "while True:\n    pass", grenze=1)
        self.assertEqual((ok, grund), (False, "Zeitgrenze"))

    def test_kaputte_antwort_beendet_lauf_nicht(self):
        ok, grund = alltag.bewerte({"art": "regex", "treffer": [], "nicht": []}, "(")
        self.assertFalse(ok)


class TestLauf(unittest.TestCase):
    def test_lauf_mit_falschem_modell(self):
        gesendet = []

        def senden(nutzlast):
            gesendet.append(nutzlast)
            return {"choices": [{"message": {"content": "<think>x</think>Freitag"}}],
                    "usage": {"completion_tokens": 5}}
        m = alltag.Modell("http://x/v1", "m", {"reasoning_effort": "none"}, senden=senden)
        erg = alltag.laufen(m, alltag.lade(["02-wochentag", "17-zaehlen"]), log=lambda s: None)
        self.assertEqual([e["ok"] for e in erg], [True, False])
        self.assertEqual(gesendet[0]["reasoning_effort"], "none")
        self.assertEqual(gesendet[0]["temperature"], 0)


if __name__ == "__main__":
    unittest.main()
