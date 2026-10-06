#!/usr/bin/env python3
"""alltag - 20 Alltagsaufgaben fuer lokale Modelle, maschinell geprueft.

    alltag.py --modell qwen3.6-64k                       mit Denken (Standard des Modells)
    alltag.py --modell qwen3.6-64k --ohne-denken         reasoning_effort none
    alltag.py --modell qwen3.6-64k --nur 08-slugify 17-zaehlen
    alltag.py --laya                                     nur die Weiche: routet Laya lokal?
    alltag.py --vergleich laeufe/A.jsonl laeufe/B.jsonl

Pruefarten: zahl, genau, json, enthaelt, zeilen, regex, python, sql, muster.
Python-Antworten laufen in einem Temp-Ordner mit Zeitgrenze (python3 -I),
SQL in einer SQLite-Datenbank im Speicher. Nur Standardbibliothek.
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
AUFGABEN = HIER / "aufgaben.json"
LAEUFE = HIER / "laeufe"
SYSTEM = "Du bist ein hilfreicher Assistent. Halte dich genau an das verlangte Antwortformat."


# ---------------------------------------------------------------- Antwort aufbereiten

def ohne_denken(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    return re.sub(r"^.*?</think>", "", text, flags=re.S).strip()


def codeblock(text):
    """Inhalt des ersten ```-Blocks, sonst der ganze Text."""
    m = re.search(r"```[\w+-]*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip()


def normal(s):
    s = s.strip().strip("`\"'*.").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)


def zahl_aus(text):
    """Letzte Zahl im Text; Komma oder Punkt als Dezimaltrenner, Tausenderpunkte erlaubt."""
    kandidaten = re.findall(r"-?\d[\d.,]*", text)
    if not kandidaten:
        return None
    z = kandidaten[-1].rstrip(".,")
    if "," in z:
        z = z.replace(".", "").replace(",", ".")
    elif z.count(".") > 1 or re.fullmatch(r"-?\d{1,3}(\.\d{3})+", z):
        z = z.replace(".", "")
    try:
        return float(z)
    except ValueError:
        return None


def woerter(text):
    return len(re.findall(r"\S+", text))


# ---------------------------------------------------------------- Pruefungen

def p_zahl(a, t):
    z = zahl_aus(t)
    return z is not None and abs(z - a["soll"]) <= a.get("toleranz", 0), f"gelesen {z}"


def p_genau(a, t):
    n = normal(t.splitlines()[-1] if t.strip() else "")
    return n in a["soll"], f"gelesen {n!r}"


def p_json(a, t):
    roh = codeblock(t)
    m = re.search(r"[\[{].*[\]}]", roh, re.S)
    try:
        wert = json.loads(m.group(0) if m else roh)
    except (json.JSONDecodeError, AttributeError):
        return False, "kein JSON"
    if isinstance(wert, list):
        wert = [normal(x) if isinstance(x, str) else x for x in wert]
        soll = [normal(x) if isinstance(x, str) else x for x in a["soll"]]
    else:
        soll = a["soll"]
    return wert == soll, f"gelesen {json.dumps(wert, ensure_ascii=False)[:120]}"


def p_enthaelt(a, t):
    n = normal(t)
    fehlt = [g for g in a.get("muss", []) if not any(normal(w) in n for w in g)]
    verboten = [w for w in a.get("darf_nicht", []) if normal(w) in n]
    return not fehlt and not verboten, f"fehlt {fehlt} verboten {verboten}" if fehlt or verboten else "ok"


def p_zeilen(a, t):
    punkte = [z for z in t.splitlines() if re.match(r"\s*([-*•]|\d+[.)])\s+", z)]
    lang = [z for z in punkte if woerter(re.sub(r"^\s*([-*•]|\d+[.)])\s+", "", z)) > a["max_woerter"]]
    ok_inhalt, grund = p_enthaelt(a, t)
    ok = len(punkte) == a["zeilen"] and not lang and ok_inhalt
    return ok, f"{len(punkte)} Punkte, {len(lang)} zu lang, {grund}"


def p_regex(a, t):
    muster = codeblock(t).splitlines()[0].strip() if t.strip() else ""
    muster = re.sub(r"^r?(['\"])(.*)\1$", r"\2", muster.strip("`"))
    try:
        rx = re.compile(muster)
    except re.error as e:
        return False, f"kein Regex: {e}"
    falsch = [s for s in a["treffer"] if not rx.search(s)] + [s for s in a["nicht"] if rx.search(s)]
    return not falsch, f"{muster!r} falsch bei {falsch}" if falsch else f"{muster!r}"


def p_python(a, t, grenze=10):
    code = codeblock(t) + "\n\n" + a["tests"] + "\n"
    with tempfile.TemporaryDirectory() as d:
        Path(d, "loesung.py").write_text(code)
        try:
            r = subprocess.run([sys.executable, "-I", "loesung.py"], cwd=d, capture_output=True,
                               text=True, timeout=grenze, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return False, "Zeitgrenze"
    fehler = (r.stderr.strip().splitlines() or [""])[-1]
    return r.returncode == 0, "Tests ok" if r.returncode == 0 else fehler[:120]


def p_sql(a, t):
    sql = codeblock(t)
    db = sqlite3.connect(":memory:")
    try:
        db.executescript(a["setup"])
        zeilen = [list(z) for z in db.execute(sql).fetchall()]
    except sqlite3.Error as e:
        return False, f"SQL-Fehler: {e}"
    finally:
        db.close()
    return zeilen == a["soll"], f"Zeilen {zeilen}"


def p_muster(a, t):
    rein = codeblock(t)
    if a.get("einzeilig"):
        rein = rein.strip().strip("`")
        if "\n" in rein:
            return False, "mehr als eine Zeile"
    fehlt = [m for m in a.get("muss_re", []) if not re.search(m, rein, re.M)]
    verboten = [m for m in a.get("nicht_re", []) if re.search(m, rein)]
    zu_lang = ("max_zeichen" in a and len(rein) > a["max_zeichen"]) or \
              ("max_woerter" in a and woerter(rein) > a["max_woerter"])
    ok = not fehlt and not verboten and not zu_lang
    return ok, "ok" if ok else f"fehlt {fehlt} verboten {verboten} zu lang {zu_lang}"


PRUEFE = {"zahl": p_zahl, "genau": p_genau, "json": p_json, "enthaelt": p_enthaelt, "zeilen": p_zeilen,
          "regex": p_regex, "python": p_python, "sql": p_sql, "muster": p_muster}


def bewerte(aufgabe, antwort):
    try:
        ok, grund = PRUEFE[aufgabe["art"]](aufgabe, antwort)
    except Exception as e:  # eine kaputte Antwort darf den Lauf nicht beenden
        ok, grund = False, f"Pruefung scheiterte: {type(e).__name__}: {e}"
    return bool(ok), grund


# ---------------------------------------------------------------- Modell und Lauf

class Modell:
    def __init__(self, url, modell, extra=None, max_tokens=8192, senden=None):
        self.url = url.rstrip("/") + "/chat/completions"
        self.modell, self.extra, self.max_tokens = modell, extra or {}, max_tokens
        self.senden = senden or self._http

    def _http(self, nutzlast):
        req = urllib.request.Request(self.url, json.dumps(nutzlast).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.load(r)

    def frage(self, text):
        nutzlast = dict({"model": self.modell, "temperature": 0, "seed": 0, "max_tokens": self.max_tokens,
                         "messages": [{"role": "system", "content": SYSTEM},
                                      {"role": "user", "content": text}]}, **self.extra)
        r = self.senden(nutzlast)
        return ohne_denken(r["choices"][0]["message"].get("content") or ""), r.get("usage", {})


def lade(nur=None):
    aufgaben = json.loads(AUFGABEN.read_text(encoding="utf-8"))
    return [a for a in aufgaben if not nur or a["id"] in nur]


def laufen(modell, aufgaben, log=print):
    erg = []
    for a in aufgaben:
        t = time.time()
        try:
            antwort, usage = modell.frage(a["prompt"])
        except OSError as e:
            antwort, usage = "", {"fehler": str(e)}
        ok, grund = bewerte(a, antwort)
        erg.append({"id": a["id"], "art": a["art"], "ok": ok, "grund": grund, "antwort": antwort[:2000],
                    "sek": round(time.time() - t, 1), "token": usage.get("completion_tokens")})
        log(f"  {'+' if ok else '-'} {a['id']:18} {erg[-1]['sek']:6.1f} s  {grund[:70]}")
    return erg


def laya_weiche(aufgaben, log=print):
    """Wie wuerde frag die Aufgaben routen? Erwartet: lokal (trivial oder coding)."""
    sys.path.insert(0, str(HIER.parent / "laya"))
    import frag
    import pruef
    route_cfg, _ = frag.beste_fassung()
    laya = pruef.Laya()
    erg = []
    for a in aufgaben:
        label, p, _, sek = frag.entscheide(laya, a["prompt"], route_cfg)
        erg.append({"id": a["id"], "soll": a["route"], "ist": label, "p": round(p, 2), "ok": label == a["route"]})
        log(f"  {'+' if label == a['route'] else '-'} {a['id']:18} soll {a['route']:8} ist {label:8} p={p:.2f}")
    return erg


def vergleiche(pfad_a, pfad_b):
    def lade_lauf(p):
        z = [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
        return z[0], {e["id"]: e for e in z[1:]}
    ka, a = lade_lauf(pfad_a)
    kb, b = lade_lauf(pfad_b)
    zeilen = [f"{'Aufgabe':18} {ka['name'][:20]:>20} {kb['name'][:20]:>20}"]
    for i in sorted(set(a) | set(b)):
        fa = f"{'ok' if a[i]['ok'] else '--'} {a[i]['sek']:6.1f}s" if i in a else "-"
        fb = f"{'ok' if b[i]['ok'] else '--'} {b[i]['sek']:6.1f}s" if i in b else "-"
        zeilen.append(f"{i:18} {fa:>20} {fb:>20}")
    for k, e in (("A", a), ("B", b)):
        zeilen.append(f"{k}: {sum(x['ok'] for x in e.values())}/{len(e)} in {sum(x['sek'] for x in e.values()):.0f} s")
    return "\n".join(zeilen)


def main(argv=None):
    ap = argparse.ArgumentParser(description="20 Alltagsaufgaben fuer lokale Modelle.")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--modell")
    ap.add_argument("--ohne-denken", action="store_true", help='setzt {"reasoning_effort": "none"}')
    ap.add_argument("--extra", default="{}")
    ap.add_argument("--nur", nargs="*")
    ap.add_argument("--laya", action="store_true")
    ap.add_argument("--vergleich", nargs=2)
    a = ap.parse_args(argv)

    if a.vergleich:
        print(vergleiche(*a.vergleich))
        return 0
    aufgaben = lade(a.nur)
    if a.laya:
        erg = laya_weiche(aufgaben)
        print(f"Laya: {sum(e['ok'] for e in erg)}/{len(erg)} wie erwartet")
        return 0
    if not a.modell:
        ap.error("--modell fehlt")
    extra = json.loads(a.extra)
    if a.ohne_denken:
        extra["reasoning_effort"] = "none"
    name = a.modell + ("-ohne-denken" if a.ohne_denken else "")
    print(f"{len(aufgaben)} Aufgaben an {name}")
    t = time.time()
    erg = laufen(Modell(a.url, a.modell, extra), aufgaben)
    LAEUFE.mkdir(exist_ok=True)
    ziel = LAEUFE / f"{time.strftime('%Y%m%d-%H%M')}_{re.sub(r'[^A-Za-z0-9.-]+', '_', name)}.jsonl"
    kopf = {"name": name, "modell": a.modell, "extra": extra, "zeit": time.strftime("%Y-%m-%d %H:%M"),
            "dauer_s": round(time.time() - t)}
    ziel.write_text("".join(json.dumps(z, ensure_ascii=False) + "\n" for z in [kopf] + erg), encoding="utf-8")
    print(f"{sum(e['ok'] for e in erg)}/{len(erg)} bestanden in {kopf['dauer_s']} s -> {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
