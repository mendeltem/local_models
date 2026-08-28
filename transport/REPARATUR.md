# Eine Datei auf Alita muss ersetzt werden

**Betroffen:** `offline-bundle/10-vortrainierte-segmentierer/model_swinvit.pt`

    auf Alita ausgeliefert   448 923 293 B   KAPUTT
    richtig                  411 162 269 B

Die richtige Datei liegt auf diesem Stick unter demselben Pfad. Ersetzen:

    cp /media/uchralt/QWEN/offline-bundle/10-vortrainierte-segmentierer/model_swinvit.pt \
       <zielpfad>/10-vortrainierte-segmentierer/model_swinvit.pt

Danach prüfen:

    sha256sum model_swinvit.pt
    # muss sein: 1cf19eca3ed0472daf33dedd2f095b118db16edac0fc53d9e878f328ca68c988

    python -c "import torch; d=torch.load('model_swinvit.pt', map_location='cpu'); print(len(d))"

## Was passiert war

Der Download lief über den Charité-Proxy und brach nach 37 761 024 Bytes ab.
Der Wiederaufnahmeversuch mit `curl -C -` schickte einen Range-Wunsch, den
GitHub bei der Weiterleitung auf sein CDN verwarf — die Antwort begann wieder
bei Byte 0. `curl` hängte sie an das Bruchstück an:

    37 761 024 + 411 162 269 = 448 923 293

Die Datei war damit exakt um ein Bruchstück zu gross und sah trotzdem aus wie
ein vollständiger Download: `curl` meldete Erfolg, die Datei wuchs, nichts
schlug fehl.

**Verschlimmert wurde es durch eine falsche Schlussfolgerung.** Als ein
Bereichsabruf die richtige Grösse 411 162 269 meldete, wurde die Abweichung
zur vorhandenen Datei als Fehler des Headers gedeutet und die erwartete Grösse
in der Tabelle auf den kaputten Wert 448 923 293 gesetzt. Damit galt die
defekte Datei als Soll und die intakte als unvollständig. Beides ist
zurückgenommen.

## Was daraus folgt

**Grössenprüfung allein reicht nicht, wenn die Sollgrösse aus derselben
Quelle stammt wie die Datei.** Bei den sieben Hugging-Face-Modellen ist das
kein Problem: dort liefert die API eine sha256, die unabhängig vom Download
ist — deshalb sind sie nachweislich byteidentisch mit dem Original.

GitHub-Releases, Zenodo, OSF und TU Berlin veröffentlichen keine Prüfsumme.
Dort hilft nur:

* die Grösse bei der **Quelle** erfragen, nie aus der eigenen Datei ableiten,
* und bei Archiven prüfen, ob sie sich öffnen lassen (`zipfile.is_zipfile`,
  `tar -t`) — ein vorangestelltes Bruchstück fällt dabei sofort auf.

Geprüft am 27.08.2026, alle übrigen Dateien stimmen mit ihrer Quelle überein:

    model_swinvit.pt                    411 162 269   ok (nach Ersatz)
    brats_mri_segmentation_v0.1.0.zip    35 075 834   ok
    MNE-fNIRS-motor-data.zip             17 881 709   ok
    Task04_Hippocampus.tar               28 425 216   ok, md5 gegen MONAI
