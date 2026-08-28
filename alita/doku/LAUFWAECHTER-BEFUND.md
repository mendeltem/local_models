# Die Laufwache — was gemessen ist

Stand 27.08.2026, gemessen auf Alita-MS-7D91 gegen das laufende 27B auf
Port 8000. Die Bausteine stammen vom USB-Stick (`offline-bundle/01-watcher`),
die Grammatik ist hier repariert.

## 1. Die Grammatik hat nie funktioniert

`watcher.gbnf` war so geschrieben:

    root ::= "ok_weiter"
           | "wiederholung_erkannt_abbruch"
           | ...

Der GBNF-Parser dieses llama.cpp-Builds lehnt den Zeilenumbruch **vor** dem
`|` ab. Gemessen, jeder Aufruf:

    HTTP 400 — "Failed to initialize samplers: failed to parse grammar"

Derselbe Inhalt mit dem Strich am **Zeilenende** wird angenommen. Belegt
durch sechs Varianten: einzeilig ok, geklammert ok, Umbruch nach dem Strich
ok, Umbruch vor dem Strich Fehler.

**Warum das schlimmer ist als ein Absturz.** `watcher.py` faengt jeden
Fehler ab und gibt `RUECKFALL = "ok_weiter"` zurueck. Die Wache haette also
bei **jedem** Aufruf „alles in Ordnung" gesagt — ohne Fehlermeldung, ohne
Log, ohne dass irgendetwas auffaellt. Eine Wache, deren Ausfall wie
Zustimmung aussieht, ist schlimmer als keine, weil sie Vertrauen erzeugt.

**Empfehlung, noch offen:** „konnte nicht urteilen" muss ein **drittes**
Ergebnis sein, verschieden von `ok_weiter`, das gezaehlt und protokolliert
wird. N Fehlversuche in Folge sind selbst eine Stufe-1-Auffaelligkeit.

## 2. Frueh gegen spaet constrainen — kein messbarer Unterschied

Mit reparierter Grammatik, die vier Beispiele aus `prompt-vorlage.md`, je
drei Wiederholungen bei temperature 0:

    Label auf Token 1 erzwungen     3/4  3/4  3/4
    erst frei denken, dann Label    3/4  3/4  3/4

Deterministisch, und beide Male faellt **dieselbe** Klasse durch. Auf diesem
Testsatz bringt spaetes Constrainen nichts — es kostet rund 600 zusaetzliche
Token je Aufruf. Die Vorlage constrained auf Token 1, und das ist nach dieser
Messung in Ordnung.

**Vorbehalt:** vier Beispiele sind kein Testsatz, mit dem man das
allgemein entscheiden koennte. Die Forschungslage (CRANE, arXiv 2502.09061;
Tam et al., arXiv 2408.02442) warnt vor fruehem Formatzwang bei
Schlussfolgerungsaufgaben — nennt aber selbst reine Klassifikation als den
Fall, in dem strenge Formate eher helfen. Genau das ist diese Aufgabe.
Bei mehr Beispielen ist die Frage neu zu stellen.

**Eine Korrektur in eigener Sache.** Ein erster Durchlauf am 27.08. ergab
1/4 fuer frueh und 3/4 fuer spaet. Diese Zahl war falsch. Der alte
`watcher.py` rief mit 30 s Zeitlimit auf; bei kaltem Prompt-Cache lief das
27B darueber, und **jede** Zeitueberschreitung wurde zu `ok_weiter`. Die
vermeintlichen Urteile waren Rueckfallwerte. Damit hat derselbe Fehler, um
den es in Abschnitt 1 geht, auch die Messung ueber ihn verdorben — ein
gutes Argument dafuer, Ausfaelle sichtbar zu machen statt sie in ein
harmloses Label zu falten.

## 3. Die eine Klasse, die wirklich durchfaellt

`wiederholung_erkannt_abbruch` schlaegt in **jedem** Durchlauf fehl: das
Modell nennt drei fast gleiche, aber nicht identische Fehlversuche
`ok_weiter`. Das ist ausgerechnet eine der beiden Klassen, fuer die es das
Modell ueberhaupt geben soll — die exakte Wiederholung entscheidet Stufe 1
selbst, die aehnliche sollte das Modell erkennen.

Das ist der Punkt, an dem Arbeit lohnt: mehr und schaerfere Beispiele fuer
genau diese Abgrenzung, oder — besser — der feingetunte Encoder, sobald
gelabelte Fenster vorliegen.

## 4. Die vier Beispiele sind ein Testsatz, kein Schmuck

`prompt-vorlage.md` enthaelt vier Beispiele, eines je Klasse, aus echten
Laeufen. Sie lagen dort als Dokumentation. Ausgefuehrt haetten sie den
Grammatikfehler in Sekunden gefunden.

    python pruefe-vier-klassen.py        frueh constrainen
    python pruefe-spaet-constrainen.py   frei denken, dann Label

Beide gehoeren in `werkzeugtest`.

## 5. Was davon unberuehrt gilt

Stufe 1 (`referenz/stufe1.py`) ist der wertvolle Teil und war nie betroffen:
NaN, EMA-Divergenz, Wiederholungs-Fingerabdruck, Stillstand, Hysterese,
Retry-Cap. Von den sieben echten Fehlern des 25.08. war keiner ein
Divergenzfall — es waren fehlende Pakete, verdrehte Geometrie, leere
Artefakte und tote Ketten. Genau die faengt Stufe 1 ohne Modell.

Der naechste sinnvolle Schritt ist nicht ein besseres Prompt, sondern der
Encoder-Klassifikator: die Fenster, die `dauerlauf` taeglich erzeugt, sind
zusammen mit ihrem tatsaechlichen Ausgang bereits Trainingsmaterial. Sie
werden nur nicht eingesammelt.
