#!/bin/sh
# hartnaeckig <url> <zieldatei> [sollgroesse] [max_versuche]
#
# Ein einzelner Download, der Abbruch und Stillstand uebersteht.
#
#     sh hartnaeckig.sh https://.../modell.gguf ./modell.gguf 18556689568
#
# Die Sollgroesse ist optional, aber dringend empfohlen. Ohne sie kann das
# Skript nicht wissen, ob die Datei vollstaendig ist -- und genau daran ist
# eine frueherer Fassung gescheitert (siehe REPARATUR.md).
#
# ---------------------------------------------------------------------------
# WARUM DIESES SKRIPT SO AUSSIEHT
#
# `-C -`  setzt an der Abbruchstelle wieder auf. Notwendig bei 18-GB-Dateien
#         ueber eine Leitung, die alle paar Minuten abreisst.
#
#         ABER: `-C -` schickt einen Range-Wunsch. Verwirft der Server ihn --
#         GitHub tut das bei der Weiterleitung auf sein CDN --, kommt die
#         Antwort ab Byte 0 und wird an das Bruchstueck ANGEHAENGT. Die Datei
#         wird zu gross statt zu klein, curl meldet Erfolg, und sie laesst
#         sich nicht laden. Deshalb die Groessenpruefung unten: ohne sie ist
#         `-C -` gefaehrlicher als nuetzlich.
#
# `.laedt` Geladen wird unter einem anderen Namen, umbenannt erst nach
#         bestandener Pruefung. `mv` innerhalb eines Dateisystems ist atomar --
#         es gibt keinen Moment, in dem die Datei unter ihrem echten Namen
#         unvollstaendig existiert. Das schuetzt auch fremde Prozesse: wer nur
#         ins Verzeichnis schaut, kann eine halbe GGUF nicht fuer ein Modell
#         halten.
#
# --speed-limit/--speed-time
#         bricht ab, wenn 60 s lang unter 10 KB/s. Ohne das haengt ein toter
#         Download stundenlang und sieht dabei aus wie ein langsamer. Genau
#         das ist passiert: ein Download stand eine halbe Stunde bei 359 MB.
#
# --retry-all-errors
#         wiederholt auch bei 5xx. Hugging Face liefert ueber manche Proxys
#         sporadisch 503.
# ---------------------------------------------------------------------------

url="$1"; ziel="$2"; soll="${3:-0}"; max="${4:-40}"
[ -n "$url" ] && [ -n "$ziel" ] || {
  echo "Aufruf: hartnaeckig <url> <zieldatei> [sollgroesse] [max_versuche]" >&2
  exit 2
}

roh="$ziel.laedt"
mkdir -p "$(dirname "$ziel")"

# Schon fertig? Dann nichts tun.
if [ -f "$ziel" ] && [ "$soll" -gt 0 ]; then
  ist=$(stat -c%s "$ziel" 2>/dev/null || echo 0)
  if [ "$ist" -eq "$soll" ]; then
    echo "--   $(basename "$ziel") liegt vollstaendig vor"
    exit 0
  fi
  echo "!!   $(basename "$ziel") hat $ist statt $soll Bytes -- wird neu geladen"
  mv "$ziel" "$roh"
fi

i=0
while [ "$i" -lt "$max" ]; do
  i=$((i + 1))

  # Ein zu grosses Bruchstueck ist nicht wiederaufnehmbar: es enthaelt bereits
  # eine doppelte Stelle. Weiterladen wuerde den Fehler nur vergroessern.
  if [ "$soll" -gt 0 ] && [ -f "$roh" ]; then
    ist=$(stat -c%s "$roh" 2>/dev/null || echo 0)
    if [ "$ist" -gt "$soll" ]; then
      echo "!!   Bruchstueck ist groesser als das Soll ($ist > $soll) -- verworfen"
      rm -f "$roh"
    fi
  fi

  if curl -sSL --fail --retry 5 --retry-all-errors --retry-delay 5 \
          --speed-limit 10240 --speed-time 60 -C - -o "$roh" "$url"; then
    ist=$(stat -c%s "$roh" 2>/dev/null || echo 0)
    if [ "$soll" -gt 0 ] && [ "$ist" -ne "$soll" ]; then
      echo "!!   $ist Bytes statt $soll -- nicht uebernommen, neuer Versuch"
      rm -f "$roh"
      continue
    fi
    mv "$roh" "$ziel" || { echo "FEHL Umbenennen von $roh" >&2; exit 1; }
    echo "ok   $(basename "$ziel")  $ist Bytes  (Versuch $i)"
    exit 0
  fi

  bisher=$(stat -c%s "$roh" 2>/dev/null || echo 0)
  echo "...  Versuch $i abgebrochen bei $bisher Bytes, setze wieder auf"
  sleep 5
done

echo "FEHL $(basename "$ziel") nach $max Versuchen" >&2
exit 1
