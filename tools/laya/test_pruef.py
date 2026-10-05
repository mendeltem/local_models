"""Unit-Tests fuer pruef.py. Ohne Laya-Dienst: die Antworten kommen aus einer Attrappe."""

import unittest

import pruef


def choice(wahl, p):
    return {"type": "choice", "choice": wahl, "answer_confidence": p}


def noul(p):
    return {"type": "noul", "noul": p}


class Attrappe:
    """Liefert je Text eine feste Antwort und zaehlt Aufrufe."""

    def __init__(self, antworten):
        self.antworten = antworten
        self.n = 0

    def __call__(self, nutzlast):
        self.n += 1
        (text,) = nutzlast["state"].values()
        return {"answers": self.antworten(text, nutzlast["questions"])}


class TestAufteilung(unittest.TestCase):
    def test_fest_und_rund_dreissig_prozent(self):
        texte = [f"anfrage {i}" for i in range(1000)]
        zurueck = [t for t in texte if pruef.zurueckgehalten(t)]
        self.assertEqual(zurueck, [t for t in texte if pruef.zurueckgehalten(t)])
        self.assertTrue(250 < len(zurueck) < 350, len(zurueck))

    def test_aufteilen_verliert_nichts(self):
        faelle = [{"text": f"t{i}"} for i in range(50)]
        suche, zurueck = pruef.aufteilen(faelle)
        self.assertEqual(len(suche) + len(zurueck), 50)
        self.assertFalse({f["text"] for f in suche} & {f["text"] for f in zurueck})

    def test_echte_faelle_lesbar(self):
        for reihe in pruef.REIHEN:
            faelle = pruef.lade(reihe)
            self.assertTrue(faelle, reihe)
            self.assertTrue(all("text" in f and "soll" in f for f in faelle), reihe)


class TestCache(unittest.TestCase):
    def test_gleiche_frage_nur_einmal(self):
        a = Attrappe(lambda t, q: {"route": choice("coding", 0.9)})
        laya = pruef.Laya(senden=a)
        q = {"route": {"type": "choice"}}
        laya.frage("request", "x", q)
        laya.frage("request", "x", q)
        laya.frage("request", "y", q)
        self.assertEqual(a.n, 2)
        self.assertEqual(laya.aufrufe, 2)


class TestRoute(unittest.TestCase):
    CFG = {"instr": "Who?", "trivial": 0, "coding": 0, "schwer": 0, "schwelle": 0.8}

    def kosten(self, soll, ist, p):
        laya = pruef.Laya(senden=Attrappe(lambda t, q: {"route": choice(ist, p)}))
        return pruef.route_kosten(laya, [{"text": "a", "soll": soll}], self.CFG)

    def test_treffer_kostet_nichts(self):
        r = self.kosten("coding", "coding", 0.95)
        self.assertEqual((r["kosten"], r["treffer"]), (0, 1))

    def test_schwer_zu_niedrig_ist_am_teuersten(self):
        teuer = self.kosten("schwer", "coding", 0.95)["kosten"]
        billig = self.kosten("coding", "schwer", 0.95)["kosten"]
        self.assertGreater(teuer, billig)
        self.assertEqual(teuer, pruef.ROUTE_KOSTEN[("schwer", "coding")])

    def test_unsicher_wird_rueckfrage(self):
        r = self.kosten("schwer", "trivial", 0.5)
        self.assertEqual(r["rueckfragen"], 1)
        self.assertEqual(r["kosten"], pruef.RUECKFRAGE_KOSTEN)

    def test_schwer_auch_unsicher_keine_rueckfrage(self):
        # frag gibt schwer immer an Claude, also zaehlt es als Entscheidung
        r = self.kosten("schwer", "schwer", 0.4)
        self.assertEqual((r["rueckfragen"], r["treffer"]), (0, 1))


class TestWaechter(unittest.TestCase):
    def kosten(self, soll, p, schwelle=0.5):
        laya = pruef.Laya(senden=Attrappe(lambda t, q: {"gefahr": noul(p)}))
        return pruef.waechter_kosten(laya, [{"text": "rm", "soll": soll}], {"instr": 0, "schwelle": schwelle})

    def test_verpasst_teurer_als_fehlalarm(self):
        self.assertEqual(self.kosten(True, 0.1)["kosten"], pruef.WAECHTER_VERPASST)
        self.assertEqual(self.kosten(False, 0.9)["kosten"], pruef.WAECHTER_FEHLALARM)

    def test_schwelle_wirkt(self):
        self.assertEqual(self.kosten(True, 0.2, schwelle=0.5)["treffer"], 0)
        self.assertEqual(self.kosten(True, 0.2, schwelle=0.1)["treffer"], 1)


class TestNachpruefung(unittest.TestCase):
    def test_zwei_fragen_je_fall(self):
        a = Attrappe(lambda t, q: {"ohne_beleg": noul(0.9), "rueckfrage": noul(0.1)})
        r = pruef.nach_kosten(pruef.Laya(senden=a),
                              [{"text": "Fertig!", "soll": {"ohne_beleg": True, "rueckfrage": False}}],
                              {"beleg": 0, "rueck": 0, "schwelle": 0.5})
        self.assertEqual((r["treffer"], r["n"], r["kosten"]), (2, 2, 0))

    def test_uebersehene_behauptung_zaehlt_doppelt(self):
        a = Attrappe(lambda t, q: {"ohne_beleg": noul(0.1), "rueckfrage": noul(0.1)})
        r = pruef.nach_kosten(pruef.Laya(senden=a),
                              [{"text": "Fertig!", "soll": {"ohne_beleg": True, "rueckfrage": False}}],
                              {"beleg": 0, "rueck": 0, "schwelle": 0.5})
        self.assertEqual(r["kosten"], 1.0)  # 2.0 Fehler / 2 Fragen


class TestOptimiere(unittest.TestCase):
    def test_findet_bessere_schwelle_und_bricht_ab(self):
        # Gefaehrliches bekommt 0.2, Harmloses 0.05: nur eine tiefe Schwelle trennt
        def antwort(text, q):
            return {"gefahr": noul(0.2 if text.startswith("rm") else 0.05)}
        a = Attrappe(antwort)
        faelle = [{"text": "rm -rf x", "soll": True}, {"text": "ls", "soll": False}]
        protokoll = []
        cfg, k = pruef.optimiere(pruef.Laya(senden=a), "waechter", faelle,
                                 {"instr": 0, "schwelle": 0.5}, protokoll=protokoll)
        self.assertEqual(k, 0)
        self.assertTrue(0.05 < cfg["schwelle"] <= 0.2, cfg)
        self.assertTrue(protokoll)

    def test_kandidaten_erweitern_den_pool(self):
        alt = {k: list(v) for k, v in pruef.ROUTE_POOL.items()}
        try:
            raum = pruef.achsen("route", {"route": {"coding": ["neu formuliert"]}})
            self.assertEqual(len(raum["coding"]), len(alt["coding"]) + 1)
            self.assertIn("neu formuliert", pruef.ROUTE_POOL["coding"])
            # zweiter Aufruf darf nicht noch einmal anhaengen
            raum = pruef.achsen("route", {"route": {"coding": ["neu formuliert"]}})
            self.assertEqual(len(raum["coding"]), len(alt["coding"]) + 1)
        finally:
            pruef.ROUTE_POOL = alt


if __name__ == "__main__":
    unittest.main()
