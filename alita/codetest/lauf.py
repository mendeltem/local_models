"""Stellt jede Aufgabe, fuehrt die Antwort aus, prueft sie.

Kein Modell urteilt. Entweder der Code rechnet das Richtige oder nicht.
"""
import json, re, sys, time, urllib.request
sys.path.insert(0, "/tmp/claude-1000/-home-uchralt/1282e1c5-ee0f-4590-ab09-ea50ffc89e22/scratchpad/codetest")
from aufgaben import AUFGABEN

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
NAME = sys.argv[2] if len(sys.argv) > 2 else "modell"

def frage(p, n=900):
    d = json.dumps({"prompt": p, "temperature": 0.0, "n_predict": n,
                    "cache_prompt": False}).encode()
    r = urllib.request.Request(URL + "/completion", data=d,
                               headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(r, timeout=900) as a:
        j = json.loads(a.read())
    return j.get("content", ""), j.get("tokens_predicted", 0), time.time() - t0

def code_holen(t):
    """Den Python-Block herausschneiden. Denkende Modelle schreiben davor."""
    for m in re.findall(r"```(?:python)?\n(.*?)```", t, re.S):
        if "def " in m:
            return m
    # kein Block: ab dem ersten 'def' bis zum Ende
    i = t.find("def ")
    return t[i:] if i >= 0 else ""

print(f"{'Aufgabe':<24}{'Ergebnis':<12}{'Token':>7}{'Zeit':>8}   Fehler")
print("-" * 86)
ok = 0
gesamt_t = gesamt_s = 0
for a in AUFGABEN:
    antwort, tok, dt = frage(a["prompt"])
    gesamt_t += tok; gesamt_s += dt
    code = code_holen(antwort)
    fehler = ""
    if not code:
        stand = "KEIN CODE"
    else:
        raum = {}
        try:
            exec(code, raum)
            exec(a["pruefe"], raum)
            stand = "richtig"; ok += 1
        except AssertionError as e:
            stand = "FALSCH"; fehler = str(e)[:44]
        except Exception as e:
            stand = type(e).__name__; fehler = str(e)[:44]
    print(f"{a['name']:<24}{stand:<12}{tok:>7}{dt:>7.1f}s   {fehler}")
print("-" * 86)
print(f"{NAME}: {ok} von {len(AUFGABEN)} richtig, {gesamt_t} Token in {gesamt_s:.0f} s "
      f"({gesamt_t/gesamt_s:.1f} tok/s)")
