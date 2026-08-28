"""Vier Codeaufgaben aus der echten Arbeit dieser Maschine.

Jede hat eine maschinell pruefbare Antwort -- kein Augenmass, kein Modell als
Richter. Der Pruefcode ruft die erzeugte Funktion mit vorbereiteten Daten auf
und vergleicht mit einem Sollwert, der von Hand ausgerechnet ist.

Die Aufgaben sind bewusst aus den Fehlern gewaehlt, die auf dieser Maschine
tatsaechlich Geld gekostet haben:
  1  Label 2 -- Clara hat den Unterschied am 28.08. selbst gefunden
  2  erst hochskalieren, DANN schwellen -- der Geometriefehler vom 25.08.
  3  Detektionsmetrik statt Dice -- der microbleed-Auftrag verlangt es
  4  heterogene Bildgroessen -- zehn verschiedene in der WMH-Challenge
"""
AUFGABEN = [
 dict(
  name="dice_label",
  prompt=(
    "Schreibe eine Python-Funktion `dice(a, b)`.\n"
    "a und b sind numpy-Arrays gleicher Form mit den Werten 0, 1 oder 2.\n"
    "Der Wert 1 bedeutet Laesion, 2 bedeutet andere Pathologie und zaehlt NICHT als Laesion.\n"
    "Gib den Dice-Koeffizienten zwischen den Laesionsmasken zurueck.\n"
    "Sind beide leer, gib 1.0 zurueck.\n"
    "Nur die Funktion, keine Erklaerung, kein Beispiel."),
  pruefe="""
import numpy as np
a=np.array([0,1,1,2,2,1,0,0]); b=np.array([0,1,2,2,1,1,0,0])
r=dice(a,b)
assert abs(r-2/3)<1e-6, f"erwartet 0.666667, bekommen {r}"
assert dice(np.zeros(5),np.zeros(5))==1.0, "beide leer muss 1.0 sein"
assert abs(dice(np.array([2,2]),np.array([2,2]))-1.0)<1e-9, "nur Label 2 = beide leer"
"""),
 dict(
  name="zurueck_dann_schwellen",
  prompt=(
    "Schreibe eine Python-Funktion `nach_original(prob, zielform, schwelle=0.5)`.\n"
    "prob ist ein 2D-numpy-Array mit Wahrscheinlichkeiten zwischen 0 und 1.\n"
    "zielform ist ein Tupel (h, w).\n"
    "Skaliere prob mit scipy.ndimage.zoom und order=1 auf zielform,\n"
    "und schwelle ERST DANACH bei `schwelle`. Gib uint8 zurueck (0 oder 1).\n"
    "Die Reihenfolge ist wichtig: schwellen vor dem Skalieren waere falsch.\n"
    "Nur die Funktion."),
  pruefe="""
import numpy as np
p=np.array([[0.0,1.0],[1.0,0.0]])
r=nach_original(p,(4,4))
assert r.shape==(4,4), f"Form {r.shape} statt (4,4)"
assert r.dtype==np.uint8, f"dtype {r.dtype} statt uint8"
assert set(np.unique(r).tolist())<={0,1}, "nur 0 und 1 erlaubt"
# Bei order=1 entstehen Zwischenwerte -- wer vorher schwellt, bekommt Bloecke.
assert r.sum() not in (0,16), "sieht nach schwellen VOR dem Skalieren aus"
"""),
 dict(
  name="detektion",
  prompt=(
    "Schreibe eine Python-Funktion `treffer(pred, ref)`.\n"
    "pred und ref sind 3D-numpy-Arrays mit 0 und 1, kleine punktfoermige Herde.\n"
    "Zaehle Zusammenhangskomponenten mit scipy.ndimage.label.\n"
    "Eine Referenzkomponente gilt als GEFUNDEN, wenn sie sich mit mindestens\n"
    "einer Vorhersagekomponente ueberlappt.\n"
    "Eine Vorhersagekomponente ist FALSCHPOSITIV, wenn sie keine Referenzkomponente trifft.\n"
    "Gib ein dict zurueck: {'n_ref':..., 'n_gefunden':..., 'n_falschpositiv':...}\n"
    "Nur die Funktion."),
  pruefe="""
import numpy as np
ref=np.zeros((10,10,10),dtype=np.uint8); pred=np.zeros_like(ref)
ref[1,1,1]=1; ref[5,5,5]=1; ref[8,8,8]=1        # drei Herde
pred[1,1,1]=1                                    # trifft den ersten
pred[5,5,6]=1                                    # daneben -> kein Treffer
pred[9,1,1]=1                                    # falschpositiv
r=treffer(pred,ref)
assert r['n_ref']==3, f"n_ref {r['n_ref']} statt 3"
assert r['n_gefunden']==1, f"n_gefunden {r['n_gefunden']} statt 1"
assert r['n_falschpositiv']==2, f"n_falschpositiv {r['n_falschpositiv']} statt 2"
"""),
 dict(
  name="stapel",
  prompt=(
    "Schreibe eine Python-Funktion `auf_kante(bild, kante=256)`.\n"
    "bild ist ein 3D-numpy-Array der Form (z, y, x) mit beliebigen y und x.\n"
    "Bringe jede Schicht auf (kante, kante) mit scipy.ndimage.zoom, order=1,\n"
    "ohne die Schichtzahl z zu veraendern. Gib float32 zurueck.\n"
    "Nur die Funktion."),
  pruefe="""
import numpy as np
for form in [(48,240,240),(83,132,256),(103,128,256)]:
    b=np.random.rand(*form).astype(np.float32)
    r=auf_kante(b)
    assert r.shape==(form[0],256,256), f"{form} -> {r.shape}"
    assert r.dtype==np.float32, f"dtype {r.dtype}"
"""),
]
