# Lektionen

Fehler, die auf dieser Maschine schon einmal passiert sind. Jede Zeile hat
sie gekostet. Sie stehen hier, damit sie nicht ein zweites Mal passieren.

Die Regel dahinter ist immer dieselbe: **ein Lauf, der stillschweigend
Muell erzeugt, ist schlimmer als einer, der abstuerzt.**

---

## Messen und Bewerten

**1. Dice volumetrisch, nie schnittweise gemittelt.**
Wer Dice je Schnitt rechnet und dann ueber die Schnitte mittelt, zaehlt
jeden leeren Schnitt als 1,0 und zieht das Ergebnis nach oben. Bei WMH
sind die meisten Schnitte leer. Derselbe Datensatz ergab so 0,8182 statt
volumetrisch 0,5683 - ein Unterschied von 44 Prozent, rein durch die
Definition. Immer ueber das ganze Volumen summieren:

    dice = 2*TP / (2*TP + FP + FN)

Die Metrik-Funktionen liegen in `/home/uchralt/data/work/vergleich/metrics.py`.

**2. Eine Zahl ohne ihre Definition ist keine Zahl.**
Bevor du einen Wert aus fremdem oder eigenem aelteren Code uebernimmst:
nachsehen, wie er berechnet wird. Auch ich als Lehrer habe 0,8182 einmal
als "im Bereich guter publizierter Verfahren" bezeichnet, ohne die
Definition zu pruefen. Das war falsch.

**3. Referenzdefinition dazuschreiben.**
Die WMH-Challenge kodiert Label 2 als "andere Pathologie". Ob du es als
Laesion zaehlst oder ausschliesst, aendert die Zahlen. Die offizielle
Auswertung schliesst es aus. Beides ist vertretbar - aber es muss im
Bericht stehen, sonst vergleicht jemand spaeter mit den falschen Zahlen.

**4. Beim Hochskalieren erst die Wahrscheinlichkeiten, dann schwellen.**
Falsch:  `zoom(maske > 0.5, order=0)`
Richtig: `zoom(wahrscheinlichkeit, order=1) > 0.5`
Naechster-Nachbar auf einer Binaermaske erzeugt treppige Raender. Bei
kleinen Strukturen ist Dice randdominiert, das kostet real.

---

## Vergleiche fair halten

**5. Die Schwelle nie auf den Testdaten aussuchen.**
BIANCA liefert eine Wahrscheinlichkeitskarte. Zwischen Schwelle 0,5 und
0,99 lagen an einem Fall 23367 gegen 3828 Voxel - Faktor sechs. Wer die
beste Schwelle auf den Testfaellen sucht und berichtet, vergleicht nicht
mehr, sondern schoent. Zulaessig: je Falte auf den Trainingsfaellen
bestimmen, oder den Literaturwert fest setzen und benennen.

**6. Falten einmal wuerfeln, beide Verfahren lesen dieselbe Datei.**
Zweimal `train_test_split` mit demselben Seed ist nicht dasselbe wie
einmal gewuerfelt. Die Falten gehoeren in eine Datei, die beide Pipelines
einlesen. Hier: `folds.json`.

**7. Nach dem Bilden der Falten pruefen, nicht hoffen.**
Jeder Fall genau einmal Testfall, kein Fall doppelt, keiner vergessen.
Drei Zeilen Code, die einen ganzen Lauf retten koennen.

---

## Werkzeuge

**8. Bei fremden Werkzeugen zuerst die Hilfe lesen.**
`bianca --help`, `bet -h`, `fast --help`. Flags aus dem Gedaechtnis zu
konstruieren geht schief. Der leere Klassifikator kam daher, dass
`--querysubjectnum` und `--trainingnums` auf dieselbe Zeile zeigten -
BIANCA schliesst den Abfragefall vom Training aus, also blieben null
Trainingsfaelle. Ohne Fehlermeldung.

**9. FSL loest Dateinamen ohne Endung auf.**
Liegen `bild.nii` und `bild.nii.gz` nebeneinander, verweigert FSL mit
"not valid". Nicht kaputt, sondern mehrdeutig. Dubletten entfernen.

**10. `pkill -f <muster>` trifft die eigene Shell**, wenn das Muster in
deren Kommandozeile steht. Dasselbe gilt fuer `pgrep -f`: eine Suche nach
einem laufenden Prozess findet den eigenen Suchbefehl. Stattdessen
`systemctl --user` oder `ps -eo args | grep -c '[h]ermes'` mit der
Klammer-Schreibweise.

**11. Die Beobachtung veraendert das Beobachtete.**
Ein Wartelauf, der mit `pgrep -f "pip install"` prueft, ob eine
Installation laeuft, findet die eigenen Diagnoseshells und wartet ewig.
Muster eng fassen.

---

## Laufen lassen

**12. Nach jedem Schritt, der eine Datei erzeugt, pruefen ob sie taugt.**
Nicht nur ob sie existiert - auch ob sie Inhalt hat. Ein Klassifikator
mit shape (0,) ist 127 Bytes gross und wirft keine Ausnahme. Er sagt dann
ueberall Null vorher, Dice wird 0, und das Ergebnis sieht plausibel aus.
Die `check`-Funktion in `prep_subj.sh` ist das Muster.

**13. Alles in Logdateien, nicht nur auf die Standardausgabe.**
Ein Lauf ohne Log ist nachtraeglich nicht beurteilbar. `tee` benutzen:
Ausgabe sehen UND behalten.

**14. Wiederaufnehmbar bauen.**
`.done`-Marker je Fall, CSV zeilenweise anhaengen und beim Start die
schon fertigen ueberspringen. Bei 170 Faellen ist ein Abbruch bei Fall
160 sonst ein verlorener Tag.

**15. Viele kleine Aufgaben in EINEN Aufruf, nicht Fall fuer Fall.**
170 Faelle einzeln aus der Agentenschleife zu starten kostet je Fall
einen Denkschritt bei 32 Token pro Sekunde - teurer als die Rechnung
selbst. Ein `xargs -P 6` erledigt es in einem Aufruf. bet, fast und
flirt sind einkernig, die Maschine hat 24 Kerne.

**16. VRAM vor der GPU-Nutzung pruefen.**
Das Sprachmodell belegt rund 20,9 GiB von 24,5. Es bleiben etwa 3 GiB.
Wer mehr anfordert, killt per CUDA-OOM das Modell, das ihn gerade
steuert. FSL rechnet nur auf der CPU und ist unbedenklich.

---

## Haltung

**17. Das eigene Ergebnis einmal als fremdes lesen.**
Bevor ein Bericht rausgeht: durchgehen mit der Frage, was ein Gutachter
bemaengeln wuerde. Fehlt die Referenzdefinition? Ist die Schwelle fair
gewaehlt? Steht eine Effektstaerke neben dem p-Wert? Ist die Fallzahl
genannt?

**18. Erst pruefen, dann rechnen.**
Ein Smoke-Test mit zwei Faellen kostet Minuten und rettet Stunden. Erst
wenn der Mechanismus steht, die volle Kohorte.

**19. Unsicherheit benennen statt ueberspielen.**
"Ich weiss nicht, wie dieses Flag heisst" ist eine brauchbare Aussage.
Ein geratenes Flag, das stillschweigend nichts tut, ist es nicht.

---

## Werkzeuge, die dir das Erinnern abnehmen

Diese liegen in `/home/uchralt/qwen-serve/werkzeuge/` und sind im PATH.
Sie ersetzen die Punkte 8, 12 und 13 oben - **benutze sie, statt daran zu
denken.**

**`wie <werkzeug> [begriffe]`** - Hilfe, bisherige Aufrufe auf dieser
Maschine, und Treffer aus dem Wissensindex. Ein Aufruf kostet Sekunden.

**`lauf <kommando> ...`** - schreibt immer ein Log, prueft den
Rueckgabewert, prueft erwartete Ausgabedateien, und **druckt bei Fehlern
die Hilfe des Werkzeugs ins Log**.

    lauf --erwarte-nicht-leer modell.pkl bianca --saveclassifierdata=modell.pkl ...

**`pruefe <datei> [--gegen ref] [--binaer]`** - leer? unplausibel?
gleiche Geometrie wie die Referenz? Rueckgabewert 0 oder 1, also direkt
in Skripten verwendbar:

    pruefe ausgabe.nii.gz --gegen referenz.nii.gz || exit 1

**`kritiker --aufgabe <datei> --ergebnis <datei>`** - liest dein Ergebnis
als Gutachter gegen die Aufgabe. Faengt, was kein Assert faengt: ein
Ergebnis, das an der Frage vorbeigeht.

**`antreiber --aufgabe <datei> --ergebnis <datei>`** - Kritiker in der
Schleife, bis nichts Schweres mehr uebrig ist.

**`frag-draussen "<frage>"`** - datenfreie Frage an das grosse Modell
draussen. Der Waechter prueft sie vorher auf Patientenbezug.

---

## 20. DIE ESKALATIONSREGEL

Wenn du dir bei einem Werkzeug oder einer Methode nicht sicher bist,
gilt diese Reihenfolge. Sie ist keine Empfehlung:

    1. wie <werkzeug>            nachschlagen, was es wirklich kann
    2. suchen.py "<begriffe>"    im lokalen Wissen suchen
    3. frag-draussen "<frage>"   datenfrei nach draussen fragen
    4. erst dann eine Annahme treffen - und sie AUSDRUECKLICH benennen

**Raten ohne die Schritte 1 bis 3 ist die teuerste Handlung, die du auf
dieser Maschine ausfuehren kannst.** Der leere BIANCA-Klassifikator kam
daher: Flags aus dem Gedaechtnis konstruiert, kein Blick in die Hilfe,
kein Fehler beim Laufen, drei Stunden Rechenzeit auf falscher Grundlage.

`wie bianca` haette vier Sekunden gedauert.

Und: "Ich weiss nicht, wie dieses Flag heisst" ist eine brauchbare
Aussage. Ein geratenes Flag, das stillschweigend nichts tut, ist es nicht.

---

## FreeSurfer 8.2.0 — was geht und was nicht

Liegt in `/home/uchralt/freesurfer/8.2.0`, Lizenz ist eingespielt. Die
Umgebung wird beim Start gesetzt, `$FREESURFER_HOME` ist da.

**LAEUFT** (Python-basiert, ueber das mitgelieferte `fspython`):

    mri_synthseg    Gewebesegmentierung aus BELIEBIGEM Kontrast, ohne
                    Registrierung. Liefert Volumina je Struktur als CSV
                    und eine eigene Qualitaetsbewertung.
                    Gemessen: 71 s je Fall auf 6 CPU-Kernen.
                      mri_synthseg --i <bild> --o <seg> --vol <csv> --qc <csv> --cpu --threads 6

    mri_synthsr     T1 aus FLAIR synthetisieren. ACHTUNG: erzeugt 1 mm
                    isotrop aus 3-mm-Schichten - die Details zwischen den
                    Schichten sind ERFUNDEN, nicht gemessen. Fuer Anatomie
                    mit Vorsicht, fuer Ausrichtung brauchbar.

    mri_WMHsynthseg Laesionen UND Gewebe aus beliebigem Kontrast.
                    Modell liegt unter models/WMH-SynthSeg_v10_231110.pth

**LAEUFT NICHT:**

    recon-all       braucht /bin/tcsh, ist auf dieser Maschine nicht
                    installiert und braucht sudo oder conda dafuer
    mri_convert     braucht libitkvnl-5.3.so.1 - im .deb NICHT enthalten
    samseg          dieselbe Ursache

Die C++-Werkzeuge fehlen, weil das Paket ohne Paketverwaltung entpackt
wurde und seine Systemabhaengigkeiten nicht mitkamen. Wenn du eines davon
brauchst: sagen, nicht umgehen.

**SPEICHER:** mri_WMHsynthseg wurde bei Systemlast 22 vom Kern
abgeschossen (OOM). Vor dem Start `free -g` pruefen, mindestens 8 GiB
frei haben, und nicht parallel zu anderen schweren Laeufen starten.

---

## Deine Umgebung

Du laeufst in der conda-Umgebung **`dl`**. Darin liegt alles Fachliche:

    torch 2.6.0+cu124   MONAI 1.5.2      nnU-Net 2.8.1
    nibabel  scipy      scikit-learn     scikit-image
    MNE 1.12  braindecode              torch-geometric
    transformers  timm  torchmetrics

Ein einfaches `python skript.py` benutzt damit das richtige Python. Du
musst NICHT jedes Mal den vollen Pfad schreiben.

FSL und FreeSurfer sind ebenfalls gesetzt: `$FSLDIR`, `$FREESURFER_HOME`,
`$SUBJECTS_DIR`. `bet`, `fast`, `flirt`, `bianca`, `mri_synthseg` sind
direkt aufrufbar.

**Wenn ein Import trotzdem fehlschlaegt**, ist das Paket wirklich nicht da
- nicht die falsche Umgebung. Dann sagen, nicht mit `pip install`
nachinstallieren: diese Maschine hat kein Netz fuer dich.

Fuer Arbeiten am Inferenzserver selbst gaebe es `qwen-serve`, aber das
brauchst du im Normalfall nicht.
