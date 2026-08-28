"""Prueft die Laufwache gegen ein laufendes Modell.

    python pruefe.py            beide Betriebsarten und die Rueckfallprobe
    python pruefe.py --schnell  nur die Rueckfallprobe (kein Modellaufruf)

Die vier Faelle stammen aus `prompt-vorlage.md` und damit aus echten Laeufen
dieser Maschine. Sie lagen dort als Dokumentation. Ausgefuehrt haetten sie
den Grammatikfehler vom 27.08. in Sekunden gefunden -- deshalb sind sie
jetzt ein Test.
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import urteil as U

FAELLE = [
    ("ok_weiter",
     '{"zustand":"laeuft","schritt":412,"seit":"00:14:22"}',
     ["epoch 8  step 410  loss 0.2214  dice 0.7612",
      "epoch 8  step 411  loss 0.2380  dice 0.7548",
      "epoch 8  step 412  loss 0.2109  dice 0.7701"],
     "keine Auffaelligkeit"),
    ("wiederholung_erkannt_abbruch",
     '{"zustand":"laeuft","schritt":3,"seit":"01:47:03"}',
     ["Versuch 7: konvertiere sub-011 ... Geometrie passt nicht, ueberspringe",
      "Versuch 8: konvertiere sub-011 ... Geometrie stimmt nicht, ueberspringe",
      "Versuch 9: konvertiere sub-011 ... Geometrie passt nicht, ueberspringe"],
     "Fingerprint aehnlich, nicht identisch (3 von 3 Fenstern)"),
    ("eskalation_cloud",
     '{"zustand":"laeuft","schritt":1,"seit":"00:02:11"}',
     ["Traceback (most recent call last):",
      '  File "train.py", line 4, in <module>', "    import torch",
      "ModuleNotFoundError: No module named 'torch'"],
     "Retry-Cap erreicht (3 von 3)"),
    ("statusdatei_widerspricht_log",
     '{"zustand":"fertig","schritt":500,"ergebnis":"169 Dateien"}',
     ["Falte 3/5 ... berechne Vorhersagen", "Getoetet"],
     "Log seit 22 min unveraendert"),
]


def durchlauf(frei_denken: bool) -> int:
    art = "erst frei denken, dann Label" if frei_denken else "Label auf Token 1"
    print(f"\n── {art} ──")
    richtig = 0
    for soll, status, log, befund in FAELLE:
        u = U.urteile(status, log, befund, frei_denken=frei_denken)
        treffer = u.label == soll
        richtig += treffer
        marke = "OK" if treffer else ("UNENTSCHIEDEN" if not u.entschieden else "ABWEICHUNG")
        print(f"  {soll:<30}{u.label:<30}{u.herkunft:<14}{marke}")
        if u.grund:
            print(f"    Grund: {u.grund[:110]}")
    print(f"  {richtig} von {len(FAELLE)} richtig")
    return richtig


def rueckfallprobe() -> bool:
    """Kaputte Grammatik darf NICHT zu ok_weiter fuehren.

    Das ist der Test auf den Fehler vom 27.08.: die Wache gab bei jedem
    Ausfall `ok_weiter` zurueck und sah dabei gesund aus.
    """
    print("\n── Rueckfallprobe: kaputte Grammatik ──")
    echt = U.GRAMMATIK
    sicherung = Path(tempfile.mkdtemp()) / "watcher.gbnf"
    shutil.copy(echt, sicherung)
    try:
        # Genau die Schreibweise, die dieser llama.cpp-Build ablehnt:
        # Zeilenumbruch VOR dem senkrechten Strich.
        echt.write_text('root ::= "ok_weiter"\n     | "eskalation_cloud"\n', encoding="utf-8")
        u = U.urteile(*FAELLE[2][1:4])
        bestanden = u.label == U.UNENTSCHIEDEN
        print(f"  geliefert: {u.label} ({u.herkunft})")
        print(f"  Grund:     {u.grund[:140]}")
        print("  " + ("BESTANDEN - Ausfall wird als Ausfall gemeldet" if bestanden
                      else "DURCHGEFALLEN - ein Ausfall sieht aus wie Zustimmung"))
        return bestanden
    finally:
        shutil.copy(sicherung, echt)
        print(f"  Grammatik wiederhergestellt ({echt.stat().st_size} Bytes)")


if __name__ == "__main__":
    nur_schnell = "--schnell" in sys.argv
    bestanden = rueckfallprobe()
    if not nur_schnell:
        spaet = durchlauf(frei_denken=True)
        frueh = durchlauf(frei_denken=False)
        print(f"\n  spaet constrainen {spaet}/4  gegen  frueh constrainen {frueh}/4")
        # Kein Anspruch mehr, dass spaet besser ist -- gemessen sind beide
        # gleich. Verlangt wird, dass ueberhaupt geurteilt wird.
        bestanden = bestanden and spaet >= 3 and frueh >= 3
    print("\n" + ("Laufwache in Ordnung." if bestanden else "Laufwache NICHT in Ordnung."))
    raise SystemExit(0 if bestanden else 1)
