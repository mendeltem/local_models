"""ai_use_cases_overview (index.html) -> Fakten.

Die Seite haelt ihre Karten als Aufrufe im Quelltext:
    U(cluster, anbieter, reife, qualitaet, wachstum, E(name), E(wachstum), E(kennzahl),
      E(detail), E(quelle), flag_t, E(flag_x))
    E(en, de) -> {"en": ..., "de": ...}
js_literal_to_json (Wiki-Tool) kann keine Aufrufe. Hier wird der Block
ausgeschnitten, Kommentare entfernt und mit genau diesen zwei Funktionen
ausgewertet - ohne eingebaute Namen, also ohne Zugriff auf irgendetwas sonst.
"""

import ast
import hashlib
import html
import re
from pathlib import Path


def block(quelltext, name):
    """Text des Literals nach 'const NAME =' bis zur passenden Klammer."""
    m = re.search(rf"^const {name}\s*=\s*", quelltext, re.M)
    if not m:
        raise ValueError(f"const {name} nicht gefunden")
    i = m.end()
    auf = quelltext[i]
    zu = {"[": "]", "{": "}"}[auf]
    tiefe, j, in_str = 0, i, None
    while j < len(quelltext):
        c = quelltext[j]
        if in_str:
            if c == "\\":
                j += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'`":
            in_str = c
        elif c == "/" and quelltext[j + 1] == "/":
            j = quelltext.index("\n", j)
            continue
        elif c == auf:
            tiefe += 1
        elif c == zu:
            tiefe -= 1
            if tiefe == 0:
                return quelltext[i:j + 1]
        j += 1
    raise ValueError(f"const {name}: Klammer nicht geschlossen")


def ohne_kommentare(js):
    aus, i, in_str = [], 0, None
    while i < len(js):
        c = js[i]
        if in_str:
            aus.append(c)
            if c == "\\":
                aus.append(js[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "\"'":
            in_str = c
            aus.append(c)
        elif js.startswith("//", i):
            i = js.find("\n", i)
            if i < 0:
                break
            continue
        else:
            aus.append(c)
        i += 1
    return "".join(aus)


def U(c, prov, mat, q, g, name, glab, metric, detail, src, ft=None, fx=None):
    return {"c": c, "prov": prov, "mat": mat, "q": q, "g": g, "name": name, "glab": glab,
            "metric": metric, "detail": detail, "src": src, "flag": {"t": ft, "x": fx}}


def E(en, de):
    return {"en": en, "de": de}


def ausserhalb_strings(js, fn):
    """fn nur auf die Teile anwenden, die nicht in Anfuehrungszeichen stehen."""
    teile, i, start, in_str = [], 0, 0, None
    while i < len(js):
        c = js[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
                teile.append(js[start:i + 1])
                start = i + 1
        elif c in "\"'":
            teile.append(fn(js[start:i]))
            start, in_str = i, c
        i += 1
    teile.append(fn(js[start:]) if not in_str else js[start:])
    return "".join(teile)


def _python(teil):
    teil = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', teil)  # blanke JS-Schluessel
    for js, py in (("true", "True"), ("false", "False"), ("null", "None")):
        teil = re.sub(rf"\b{js}\b", py, teil)
    return teil


def auswerten(js):
    py = ausserhalb_strings(ohne_kommentare(js), _python)
    baum = ast.parse(py, mode="eval")
    for knoten in ast.walk(baum):  # nur Literale und die zwei Helfer
        if isinstance(knoten, ast.Call) and not (isinstance(knoten.func, ast.Name) and knoten.func.id in ("U", "E")):
            raise ValueError("unerwarteter Aufruf im Literal")
        if isinstance(knoten, (ast.Attribute, ast.Lambda, ast.Subscript)):
            raise ValueError(f"unerwarteter Ausdruck: {type(knoten).__name__}")
    return eval(compile(baum, "<uc>", "eval"), {"__builtins__": {}, "U": U, "E": E})


def klar(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


# Belegqualitaet der Karte (QUAL_LABELS der Seite) -> Status im Sinne der Wiki
STATUS = {3: "getragen", 2: "vorschlag", 1: "vorschlag"}
BELEG = {3: "solide", 2: "mittel", 1: "duenn"}


def lies_usecases(index_html, sprache="de"):
    q = Path(index_html).read_text(encoding="utf-8")
    karten = auswerten(block(q, "UC"))
    cluster = {c["n"]: c for c in auswerten(block(q, "CLUSTERS"))}
    fakten = []
    for k in karten:
        name = klar(k["name"][sprache])
        cl = cluster.get(k["c"], {})
        aussage = (f"{name} ({klar(cl.get('title', {}).get(sprache, ''))}): {klar(k['metric'][sprache])}. "
                   f"{klar(k['detail'][sprache])}")
        slug = re.sub(r"[^a-z0-9]+", "-", klar(k["name"]["en"]).lower()).strip("-")
        fakten.append({
            "id": f"usecases/{slug}", "quelle": "ai_use_cases_overview", "pfad": "index.html",
            "bereich": "ai_use_cases", "typ": "befund", "status": STATUS[k["q"]], "beleg": BELEG[k["q"]],
            "stand": "", "herkunft": klar(k["src"][sprache]), "titel": name, "aussage": aussage,
            "traegt": "", "traegt_nicht": "",
            "beleg_hinweis": klar(k["flag"]["x"][sprache]) if isinstance(k["flag"]["x"], dict) else "",
            "bruchindikator": "", "verweist_auf": [],
            "anbieter": k["prov"], "reife": k["mat"], "wachstum": k["g"], "cluster": klar(cl.get("title", {}).get(sprache, "")),
            "hash": hashlib.sha256(repr(k).encode("utf-8")).hexdigest()[:12],
        })
    return fakten
