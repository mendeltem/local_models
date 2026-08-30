#!/usr/bin/env python3
"""Prueft vorflug und abnahme-referenz gegen Faelle mit bekanntem Ausgang.

    python pruefe-vorflug.py            alle Faelle
    python pruefe-vorflug.py --zeigen   zusaetzlich die Ausgabe jedes Falls

Jeder Fall baut sich sein eigenes Spielverzeichnis unter tempfile und raeumt es
wieder ab. Das ist nicht Ordnungsliebe, sondern Notwendigkeit: beim ersten
Testlauf von Hand hat ein vorheriger Fall ein Verzeichnis angelegt, wodurch der
naechste Fall ploetzlich bestand -- richtiges Verhalten des Werkzeugs, falsches
Ergebnis des Tests. Ein Test, der von der Reihenfolge abhaengt, misst sich
selbst.

Erwartete Exit-Codes: 0 startklar, 1 abgelehnt, 64 Formatfehler.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HIER = Path(__file__).resolve().parent
VORFLUG = HIER / "vorflug"
ABNAHME = HIER / "abnahme-referenz"


def baue(d: Path) -> None:
    """Das Spielverzeichnis: eine Quelle mit drei Bildern, ein leeres
    Arbeitsverzeichnis, eine Datei, die es schon gibt."""
    (d / "quelle" / "BIDS_SWI").mkdir(parents=True)
    for i in (1, 2, 3):
        (d / "quelle" / "BIDS_SWI" / ("sub-0%d.nii.gz" % i)).write_text("bild", encoding="utf-8")
    (d / "arbeit").mkdir()
    (d / "arbeit" / "schon_da.md").write_text("Dice 0.66\n", encoding="utf-8")


# (name, erwarteter Exit, zusaetzliche Schalter, Auftragstext, Vorbereitung)
FAELLE = [
    ("gut", 0, [], """
auftrag  probe-gut
arbeit   {d}/arbeit
ziel     verlinken
frage    Liegen die Bilder im Arbeitsverzeichnis?
quelle   {d}/quelle/BIDS_SWI
soll     genau {{arbeit}}/swi/*.nii.gz 3
ziel     rechnen
frage    Gibt es einen Bericht mit Dice?
quelle   {{arbeit}}/swi
bleibt   datei {{arbeit}}/schon_da.md
soll     enthaelt {{arbeit}}/bericht.md Dice
""", None),

    # Der Fall vom 27.08.: die Abnahme verlangt Dateien im Arbeitsverzeichnis,
    # niemand legt sie an, und die Quelle ist nicht aufloesbar.
    ("microbleed-27-08", 1, [], """
auftrag  microbleed-27-08
arbeit   {d}/arbeit
ziel     rechnen
frage    Sind die Mikroblutungen gerechnet und berichtet?
quelle   {{arbeit}}/swi
soll     datei {{arbeit}}/bericht.md
""", None),

    # Der Fall vom 27.08. in seiner ECHTEN Gestalt: das Verzeichnis EXISTIERT,
    # es ist nur leer. BLACKBOARD [2] sagt "beide Verzeichnisse sind leer",
    # nicht "fehlen". Eine Auflösbarkeitspruefung, die nur den Pfadknoten sucht,
    # laesst genau diesen Fall durch -- und der Test waere gruen, waehrend er
    # seinen einzigen Fall verfehlt.
    ("quelle-existiert-aber-leer", 1, [], """
auftrag  microbleed-27-08-echt
arbeit   {d}/arbeit
ziel     rechnen
frage    Sind die Mikroblutungen gerechnet und berichtet?
quelle   {{arbeit}}/swi
soll     datei {{arbeit}}/bericht.md
""", "leeres_swi"),

    # 'bleibt' beschreibt eine Voraussetzung, und die betrifft typisch die
    # EINGAENGE -- die liegen ausserhalb von 'arbeit'. Wer auch bleibt
    # einsperrt, lehnt jeden Auftrag ab, der seine Quelldaten im Blick behaelt.
    ("bleibt-darf-ausserhalb-liegen", 0, [], """
auftrag  quelle-im-blick
arbeit   {d}/arbeit
ziel     verlinken
frage    Liegen die Bilder im Arbeitsverzeichnis?
quelle   {d}/quelle/BIDS_SWI
bleibt   genau {d}/quelle/BIDS_SWI/*.nii.gz 3
soll     genau {{arbeit}}/swi/*.nii.gz 3
""", None),

    ("kriterium-schon-wahr", 1, [], """
auftrag  geschenkter-punkt
arbeit   {d}/arbeit
ziel     berichten
frage    Steht Dice im Bericht?
quelle   {d}/quelle/BIDS_SWI
soll     enthaelt {{arbeit}}/schon_da.md Dice
""", None),

    ("zyklus", 1, [], """
auftrag  zyklus
arbeit   {d}/arbeit
ziel     a
frage    A entsteht aus B
quelle   {{arbeit}}/b/x.txt
soll     datei {{arbeit}}/a/x.txt
ziel     b
frage    B entsteht aus A
quelle   {{arbeit}}/a/x.txt
soll     datei {{arbeit}}/b/x.txt
""", None),

    ("schreibt-ausserhalb", 1, [], """
auftrag  daneben
arbeit   {d}/arbeit
ziel     daneben
frage    Schreibt es ausserhalb des Arbeitsverzeichnisses?
quelle   {d}/quelle/BIDS_SWI
soll     datei {d}/quelle/ergebnis.md
""", None),

    ("ziel-ohne-soll", 1, [], """
auftrag  absichtserklaerung
arbeit   {d}/arbeit
ziel     irgendwas
frage    Was soll dabei herauskommen?
quelle   {d}/quelle/BIDS_SWI
""", None),

    ("unbekanntes-wort", 64, [], """
auftrag  tippfehler
arbeit   {d}/arbeit
zeil     verlinken
""", None),

    # Wiederaufnahme: dasselbe wie 'gut', aber die erste Stufe ist schon getan.
    ("wiederaufnahme-ohne-schalter", 1, [], """
auftrag  probe-gut
arbeit   {d}/arbeit
ziel     verlinken
frage    Liegen die Bilder im Arbeitsverzeichnis?
quelle   {d}/quelle/BIDS_SWI
soll     genau {{arbeit}}/swi/*.nii.gz 3
""", "erledige_stufe1"),

    ("wiederaufnahme-mit-schalter", 0, ["--fortsetzen"], """
auftrag  probe-gut
arbeit   {d}/arbeit
ziel     verlinken
frage    Liegen die Bilder im Arbeitsverzeichnis?
quelle   {d}/quelle/BIDS_SWI
soll     genau {{arbeit}}/swi/*.nii.gz 3
""", "erledige_stufe1"),
]


def leeres_swi(d: Path) -> None:
    """Das Verzeichnis anlegen, aber leer lassen -- die Lage vom 27.08."""
    (d / "arbeit" / "swi").mkdir()


def erledige_stufe1(d: Path) -> None:
    (d / "arbeit" / "swi").mkdir()
    for i in (1, 2, 3):
        shutil.copy(d / "quelle" / "BIDS_SWI" / ("sub-0%d.nii.gz" % i),
                    d / "arbeit" / "swi")


def lauf(argv: list[str]) -> tuple[int, str]:
    r = subprocess.run([sys.executable] + argv, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr)


def rundlauf(zeigen: bool) -> bool:
    """vorflug --liste erzeugt eine Liste, die abnahme lesen kann: erst 0
    erfuellt, nach der Arbeit 1. Das ist die Naht zwischen beiden Werkzeugen."""
    d = Path(tempfile.mkdtemp(prefix="vorflug-test-"))
    try:
        baue(d)
        auf = d / "j.auftrag"
        auf.write_text(FAELLE[0][3].format(d=d.as_posix()), encoding="utf-8")
        code, aus = lauf([str(VORFLUG), str(auf), "--liste", "verlinken"])
        if code != 0 or not aus.strip():
            print("  Rundlauf: --liste lieferte nichts (exit %d)" % code)
            return False
        liste = d / "ziel1.abnahme"
        liste.write_text(aus, encoding="utf-8")
        _, vorher = lauf([str(ABNAHME), str(liste)])
        erledige_stufe1(d)
        _, nachher = lauf([str(ABNAHME), str(liste)])
        ok = "Abnahme: 0 erfuellt" in vorher and "Abnahme: 1 erfuellt" in nachher
        if zeigen or not ok:
            print("  vorher : %s" % vorher.strip().splitlines()[-1:])
            print("  nachher: %s" % nachher.strip().splitlines()[-1:])
        return ok
    finally:
        shutil.rmtree(d, ignore_errors=True)


def historische(zeigen: bool) -> int:
    """Die rekonstruierten Auftraege muessen LESBAR sein.

    Ihr Urteil laesst sich hier nicht pruefen -- die Pfade darin sind
    Alita-Pfade und existieren auf keiner anderen Maschine. Was sich pruefen
    laesst, ist das Format: unbekannte Woerter, fehlende Werte, Kriterien mit
    einem Verb, das es nicht gibt. Genau daran ist die erste Fassung dieser
    Dateien gescheitert (eine bleibt-Zeile ohne Verb, eine erfundene
    'ziel:'-Syntax), und das faellt hier in einer Sekunde auf.
    """
    ordner = HIER.parent / "auftrag" / "historisch"
    dateien = sorted(ordner.glob("*.auftrag")) if ordner.is_dir() else []
    if not dateien:
        print("%-30s keine gefunden unter %s" % ("historische Auftraege", ordner))
        return 0
    schlecht = 0
    for f in dateien:
        code, aus = lauf([str(VORFLUG), str(f), "--zeigen"])
        ok = code == 0
        schlecht += 0 if ok else 1
        print("%-30s lesbar: %s" % (f.name, "OK" if ok else "FEHLER (exit %d)" % code))
        if zeigen or not ok:
            for z in aus.strip().splitlines():
                print("    " + z)
    return schlecht


def main() -> int:
    zeigen = "--zeigen" in sys.argv
    fehler = 0
    for name, erwartet, schalter, vorlage, vorbereitung in FAELLE:
        d = Path(tempfile.mkdtemp(prefix="vorflug-test-"))
        try:
            baue(d)
            if vorbereitung == "erledige_stufe1":
                erledige_stufe1(d)
            elif vorbereitung == "leeres_swi":
                leeres_swi(d)
            auf = d / "j.auftrag"
            auf.write_text(vorlage.format(d=d.as_posix()), encoding="utf-8")
            code, aus = lauf([str(VORFLUG), str(auf)] + schalter)
            ok = code == erwartet
            fehler += 0 if ok else 1
            print("%-30s erwartet %2d, bekommen %2d  %s"
                  % (name, erwartet, code, "OK" if ok else "FEHLER"))
            if zeigen or not ok:
                for z in aus.strip().splitlines():
                    print("    " + z.replace(d.as_posix(), "…"))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    rund = rundlauf(zeigen)
    print("%-30s %s" % ("rundlauf vorflug->abnahme", "OK" if rund else "FEHLER"))
    if not rund:
        fehler += 1
    fehler += historische(zeigen)

    print()
    print("bestanden." if not fehler else "%d Faelle fehlgeschlagen." % fehler)
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
