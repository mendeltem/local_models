# -*- coding: utf-8 -*-
"""Text zu Sprache, lokal, fuer jedes Projekt.

   Ein Satz, eine Datei voller Saetze oder etwas, das man
   hineinpipet — heraus kommt Audio, gepegelt und benannt. Die Stimme
   laesst sich aus einer Aufnahme klonen; ohne Vorlage spricht das
   Modell in seiner eigenen.

       stimme "Guten Morgen." -o gruss.mp3
       stimme --datei zeilen.txt --ordner ausgabe/
       echo "Noch ein Satz." | stimme -o satz.mp3
       stimme --datei zeilen.txt --ordner aus/ --referenz petra.wav

   Der Dateiname ist der Satz: acht Zeichen aus seiner Pruefsumme. Das
   heisst, ein zweiter Lauf ueberspringt, was schon da ist — man kann
   abbrechen und weitermachen, und wenn sich ein Satz aendert, aendert
   sich sein Name, statt dass eine alte Aufnahme stillschweigend
   weiterbenutzt wird. Mit -o gibt man den Namen selbst vor.

   Der Pegel wird gemessen, nicht geraten: ffmpeg liest die tatsaechliche
   Spitze ab, und genau die Differenz wird angewendet. Stille am Anfang
   und Ende faellt weg. Ohne ffmpeg im Pfad bleibt es bei WAV, roh.

   Modell: Audio8/Audio8-TTS-Preview-0.1b (Community License v1.0,
   umsatzgedeckelt). Deutsch gilt dort als experimentell. Und was fuer
   jedes Klonverfahren gilt, steht auch auf der Modellkarte: eine
   fremde Stimme nur mit Einverstaendnis.
"""
import argparse, hashlib, io, os, re, shutil, subprocess, sys

MODELL = os.environ.get("STIMME_MODELL", "Audio8/Audio8-TTS-Preview-0.1b")
SPITZE_DB = -6.0
BITRATE = "96k"
HAT_FFMPEG = shutil.which("ffmpeg") is not None


def kennung(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def spitze_von(pfad):
    p = subprocess.run(["ffmpeg", "-v", "info", "-i", pfad, "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", p.stderr or "")
    return float(m.group(1)) if m else 0.0


def dauer_von(pfad):
    if not HAT_FFMPEG:
        return 0.0
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", pfad], capture_output=True, text=True)
    try:
        return float((p.stdout or "0").strip())
    except ValueError:
        return 0.0


def nachbereiten(wav, ziel, spitze):
    """Stille abschneiden, auf die gemessene Spitze bringen, ablegen."""
    if not HAT_FFMPEG or ziel.lower().endswith(".wav"):
        shutil.move(wav, ziel)
        return 0.0
    gain = spitze - spitze_von(wav)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav,
                    "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,"
                           "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,"
                           "areverse,volume=%.2fdB,alimiter=limit=0.99" % gain,
                    "-codec:a", "libmp3lame", "-b:a", BITRATE, "-ac", "1", ziel],
                   check=True)
    os.remove(wav)
    return gain


class Sprecher:
    """Das Modell, einmal geladen, beliebig oft benutzt."""

    def __init__(self, modell=MODELL, geraet=None):
        import torch
        from transformers import AutoModel, AutoProcessor
        self.torch = torch
        self.geraet = geraet or ("cuda" if torch.cuda.is_available() else "cpu")
        genau = torch.bfloat16 if self.geraet == "cuda" else torch.float32
        print("Gerät: %s%s" % (self.geraet,
              " · " + torch.cuda.get_device_name(0) if self.geraet == "cuda" else ""),
              file=sys.stderr)
        self.prozessor = AutoProcessor.from_pretrained(modell, trust_remote_code=True)
        self.modell = AutoModel.from_pretrained(modell, trust_remote_code=True,
                                                dtype=genau).eval().to(self.geraet)
        self.rate = self.modell.config.codec_sample_rate

    def einfrieren(self, wav):
        """Aufnahme zu Codes. Einmal je Vorlage, dann nie wieder."""
        import numpy as np, soundfile as sf
        klang, _ = sf.read(wav, dtype="float32")
        if klang.ndim > 1:
            klang = klang.mean(axis=1)          # das Modell will mono
        with self.torch.inference_mode():
            codes, laengen = self.modell.encode_audio(
                self.torch.tensor(klang)[None].to(self.geraet),
                self.torch.tensor([len(klang)]).to(self.geraet))
        return codes[0, :, :int(laengen[0])].cpu().numpy().astype(np.uint16)

    def sprich(self, text, wav, referenz=None, referenztext=None, codes=None):
        import soundfile as sf
        args = {"text": [text], "return_tensors": "pt"}
        if codes is not None:
            # derselbe Weg wie mit Aufnahme, nur eine Stufe spaeter:
            # was der Codec sonst erst erzeugen muesste, liegt schon vor
            args["reference_codes"] = [codes]
            args["reference_text"] = [referenztext or ""]
        elif referenz:
            args["reference_audio"] = [referenz]
            args["reference_text"] = [referenztext or ""]
        ein = self.prozessor(**args)
        ein = {k: (v.to(self.geraet) if hasattr(v, "to") else v) for k, v in ein.items()}
        with self.torch.inference_mode():
            aus = self.modell.generate(**ein, max_new_tokens=512, temperature=0.7,
                                       top_p=0.9, top_k=50, do_sample=True,
                                       return_dict_in_generate=True)
            wellen, laengen = self.modell.decode_audio(aus.codes)
        klang = wellen[0, :int(laengen[0])].float().cpu().numpy()
        sf.write(wav, klang, self.rate)
        return wav


def stimmen_ordner():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "stimmen")


# ── Eingefrorene Vorlagen ────────────────────────────────────────────
#
# Das Modell nimmt statt einer Aufnahme auch die Codes, die sein Codec
# daraus macht: zehn Spuren ganzer Zahlen. Aus 1,7 MB wav werden 7 KB —
# klein genug fuer ein Repository, und keine Datei mehr, die ein
# Abspieler oeffnet.
#
# Das ist eine Verkleinerung und kein Schutz. decode_audio rechnet die
# Codes zurueck in Sprache, und heraus kommt die Aufnahme. Wer die Codes
# hat, hat die Stimme. Deshalb liegt der Wortlaut im selben Behaelter,
# und deshalb gehoert ueber beides ein Schloss — siehe --schluessel.

BEHAELTER = 1


def vorlage_packen(codes, text):
    """Codes und Wortlaut in einen Klumpen, gezippt."""
    import base64, gzip, json
    roh = json.dumps({
        "fassung": BEHAELTER,
        "text": text,
        "form": list(codes.shape),
        "codes": base64.b64encode(codes.astype("<u2").tobytes()).decode("ascii"),
    }, ensure_ascii=False).encode("utf-8")
    return gzip.compress(roh, 9)


def vorlage_auspacken(klumpen):
    """Zurueck zu (Codes, Wortlaut)."""
    import base64, gzip, json
    import numpy as np
    d = json.loads(gzip.decompress(klumpen).decode("utf-8"))
    if d.get("fassung") != BEHAELTER:
        sys.exit("Unbekannte Fassung %r in der Vorlage." % d.get("fassung"))
    c = np.frombuffer(base64.b64decode(d["codes"]), dtype="<u2")
    return c.reshape(d["form"]).astype("int64"), d["text"]


def gpg_ruf(mehr):
    """Der gpg-Aufruf, mit oder ohne Frage nach der Passphrase.

       Normalerweise fragt gpg selbst — dann steht das Kennwort nirgends.
       Nur wenn STIMME_KENNWORT gesetzt ist (Skripte, Tests), geht es
       ueber die Kommandozeile, und das ist in der Prozessliste zu sehen."""
    if not shutil.which("gpg"):
        sys.exit("Dafuer braucht es gpg im Pfad.")
    ruf = ["gpg"] + mehr
    kennwort = os.environ.get("STIMME_KENNWORT")
    if kennwort:
        ruf[1:1] = ["--batch", "--pinentry-mode", "loopback",
                    "--passphrase", kennwort]
    return ruf


def verschluesseln(klumpen, ziel):
    """Symmetrisch, mit einer Passphrase — gpg fragt selbst danach.

       Symmetrisch und nicht mit einem Schluesselpaar, weil das Ziel ein
       zweiter Rechner desselben Menschen ist: dort soll ein Kennwort
       genuegen und kein mitgeschleppter privater Schluessel."""
    p = subprocess.run(gpg_ruf(["--symmetric", "--cipher-algo", "AES256",
                                "--yes", "-o", ziel]), input=klumpen)
    if p.returncode != 0 or not os.path.exists(ziel):
        sys.exit("gpg hat nichts geschrieben.")
    return ziel


def entschluesseln(pfad):
    """Nur in den Arbeitsspeicher. Auf der Platte bleibt es verschlossen."""
    p = subprocess.run(gpg_ruf(["--decrypt", "-q", pfad]), stdout=subprocess.PIPE)
    if p.returncode != 0 or not p.stdout:
        sys.exit("Konnte %s nicht oeffnen — falsche Passphrase?"
                 % os.path.basename(pfad))
    return p.stdout


ENDUNGEN = [(".wav", "wav"), (".stimme", "kalt"), (".stimme.gpg", "schloss")]


def stimmen_liste():
    """Was in stimmen/ liegt, in drei Formen.

       wav      die Aufnahme selbst, daneben die .txt mit dem Wortlaut
       kalt     eingefroren: Codes und Wortlaut in einer Datei, 7 KB
       schloss  dasselbe, verschlossen — der Wortlaut steckt mit drin

       Gibt es eine Stimme in mehreren Formen, gewinnt die Aufnahme:
       sie ist das Original, alles andere ist daraus gemacht."""
    ordner = stimmen_ordner()
    if not os.path.isdir(ordner):
        return []
    gefunden = {}
    for n in sorted(os.listdir(ordner)):
        for endung, art in ENDUNGEN:
            if not n.lower().endswith(endung):
                continue
            name = n[:-len(endung)]
            pfad = os.path.join(ordner, n)
            if art == "wav":
                txt = os.path.join(ordner, name + ".txt")
                text = (io.open(txt, encoding="utf-8").read().strip()
                        if os.path.exists(txt) else None)
            else:
                text = None            # steht im Behaelter, nicht daneben
            reihe = [a for _, a in ENDUNGEN]
            if name in gefunden and reihe.index(gefunden[name][0]) <= reihe.index(art):
                continue
            gefunden[name] = (art, pfad, text)
            break
    return [(n, a, p, t) for n, (a, p, t) in sorted(gefunden.items())]


def stimme_finden(name):
    """Eine benannte Vorlage samt ihrem Wortlaut.

       Beides gehoert zusammen — ohne den Text weigert sich das Modell.
       Zurueck kommt (art, quelle, text): bei einer Aufnahme ist die
       Quelle ein Pfad, bei einer eingefrorenen sind es die Codes."""
    for n, art, pfad, text in stimmen_liste():
        if n != name:
            continue
        if art == "wav":
            if not text:
                sys.exit("Zu '%s' fehlt die Textdatei %s.txt mit dem Wortlaut."
                         % (n, n))
            return "wav", pfad, text
        klumpen = (entschluesseln(pfad) if art == "schloss"
                   else io.open(pfad, "rb").read())
        codes, text = vorlage_auspacken(klumpen)
        return "codes", codes, text
    da = ", ".join(n for n, _, _, _ in stimmen_liste()) or "keine"
    sys.exit("Unbekannte Stimme '%s'. Vorhanden: %s" % (name, da))


def texte_sammeln(a):
    if a.text:
        return [" ".join(a.text)]
    if a.datei:
        roh = io.open(a.datei, encoding="utf-8").read()
    elif not sys.stdin.isatty():
        roh = sys.stdin.read()
    else:
        return []
    return [z.strip() for z in roh.splitlines() if z.strip() and not z.lstrip().startswith("#")]


def main():
    p = argparse.ArgumentParser(
        description="Text zu Sprache, lokal.",
        epilog="Ohne --referenz spricht das Modell in seiner eigenen Stimme.")
    p.add_argument("text", nargs="*", help="der Satz, direkt")
    p.add_argument("--datei", "-f", help="Datei mit einem Satz je Zeile (# ist ein Kommentar)")
    p.add_argument("--ordner", "-d", default=".", help="wohin, bei mehreren Sätzen")
    p.add_argument("-o", "--aus", help="Zieldatei, bei genau einem Satz")
    p.add_argument("--stimme", "-s", help="eine Vorlage aus stimmen/, etwa: frau")
    p.add_argument("--stimmen", action="store_true", help="zeigen, welche Vorlagen da sind")
    p.add_argument("--referenz", "-r", help="WAV mit der Stimme, die geklont werden soll")
    p.add_argument("--referenztext", help="was auf dieser Aufnahme gesagt wird, wortgleich")
    p.add_argument("--spitze", type=float, default=SPITZE_DB, help="Zielpegel in dB (Standard −6)")
    p.add_argument("--modell", default=MODELL)
    p.add_argument("--geraet", choices=["cuda", "cpu"])
    p.add_argument("--neu", action="store_true", help="auch überschreiben, was schon da ist")
    p.add_argument("--liste", action="store_true", help="nur zeigen, was entstünde")
    p.add_argument("--einfrieren", metavar="NAME",
                   help="Aufnahme zu Codes: 1,7 MB werden 7 KB, ohne Audiodatei")
    p.add_argument("--schluessel", action="store_true",
                   help="das Eingefrorene mit einer Passphrase verschließen (gpg)")
    a = p.parse_args()

    if a.stimmen:
        vor = stimmen_liste()
        if not vor:
            return print("Keine Vorlagen in %s." % stimmen_ordner())
        wie = {"wav": "Aufnahme", "kalt": "eingefroren", "schloss": "verschlossen"}
        for n, art, quelle, text in vor:
            if art == "wav":
                was = "%5.1f s" % dauer_von(quelle)
                zeigt = text or "OHNE TEXT — unbrauchbar"
            else:
                was = "%5.0f KB" % (os.path.getsize(quelle) / 1024.0)
                zeigt = "Wortlaut steckt im Behälter"
            print("%-12s %-12s %8s  %s" % (n, wie[art], was,
                  (zeigt[:48] + "…") if len(zeigt) > 48 else zeigt))
        return

    if a.einfrieren:
        art, quelle, text = stimme_finden(a.einfrieren)
        if art != "wav":
            sys.exit("'%s' ist schon eingefroren." % a.einfrieren)
        klumpen = vorlage_packen(Sprecher(a.modell, a.geraet).einfrieren(quelle), text)
        ziel = os.path.join(stimmen_ordner(), a.einfrieren + ".stimme"
                            + (".gpg" if a.schluessel else ""))
        if a.schluessel:
            verschluesseln(klumpen, ziel)
        else:
            io.open(ziel, "wb").write(klumpen)
        print("%s  %.0f KB  (aus %.0f KB Aufnahme)"
              % (os.path.basename(ziel), os.path.getsize(ziel) / 1024.0,
                 os.path.getsize(quelle) / 1024.0))
        if not a.schluessel:
            print("Ungeschützt: aus diesen Codes läßt sich die Aufnahme "
                  "zurückrechnen.\nFür ein öffentliches Repository --schluessel "
                  "dazunehmen.")
        return

    # Eine benannte Vorlage ist nur eine Abkürzung für Aufnahme plus Wortlaut.
    a.codes = None
    if a.stimme:
        art, quelle, a.referenztext = stimme_finden(a.stimme)
        if art == "codes":
            a.codes = quelle
        else:
            a.referenz = quelle

    texte = texte_sammeln(a)
    if not texte:
        p.print_help()
        sys.exit("\nKein Text: als Argument, mit --datei oder über die Standardeingabe.")
    if a.aus and len(texte) > 1:
        sys.exit("-o geht nur bei genau einem Satz; sonst --ordner benutzen.")
    if a.referenz and not os.path.exists(a.referenz):
        sys.exit("Referenz nicht gefunden: " + a.referenz)
    if a.referenz and not a.referenztext:
        sys.exit("Zu --referenz gehört --referenztext: der Wortlaut der Aufnahme, "
                 "wortgleich. Das Modell braucht ihn, um Stimme von Inhalt zu "
                 "trennen, und bricht sonst ab — erst nach dem Laden der Gewichte.")

    os.makedirs(a.ordner, exist_ok=True)
    plan = []
    for t in texte:
        ziel = a.aus or os.path.join(a.ordner, kennung(t) + (".mp3" if HAT_FFMPEG else ".wav"))
        plan.append((t, ziel, os.path.exists(ziel) and not a.neu))

    if a.liste:
        for t, ziel, da in plan:
            print("%-1s %-28s %s" % ("·" if da else "+", os.path.basename(ziel),
                                     t[:60] + ("…" if len(t) > 60 else "")))
        print("\n%d neu, %d schon da" % (sum(1 for _, _, d in plan if not d),
                                         sum(1 for _, _, d in plan if d)))
        return

    offen = [x for x in plan if not x[2]]
    if not offen:
        return print("Nichts zu tun — alles schon da.")
    if not HAT_FFMPEG:
        print("ffmpeg fehlt: es bleibt bei rohem WAV, ungepegelt.", file=sys.stderr)

    sprecher = Sprecher(a.modell, a.geraet)
    roh = os.path.join(a.ordner, "_roh.wav")
    for t, ziel, _ in offen:
        sprecher.sprich(t, roh, a.referenz, a.referenztext, a.codes)
        g = nachbereiten(roh, ziel, a.spitze)
        print("%-28s %5.1f s  %+5.1f dB  %s" %
              (os.path.basename(ziel), dauer_von(ziel), g,
               t[:52] + ("…" if len(t) > 52 else "")))


if __name__ == "__main__":
    main()
