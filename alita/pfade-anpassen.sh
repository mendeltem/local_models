#!/usr/bin/env bash
# Schreibt fest verdrahtete Pfade im Baum auf den tatsaechlichen Ort um.
#
#   ./pfade-anpassen.sh              zeigt, was sich aendern wuerde
#   ./pfade-anpassen.sh --schreiben  schreibt um, mit Sicherung
#
# Zwei Faelle:
#
#   1. Alte Namen. Das System wurde als ~/qwen-serve und ~/qwen-models
#      gebaut. Nach dem Umzug funktioniert das nur ueber Symlinks -- die
#      Skripte glauben weiter, sie wohnten an der alten Adresse. Wer den
#      Symlink entfernt, zerlegt 34 Dateien.
#
#   2. Anderes Zuhause. Auf einem neuen Rechner heisst der Benutzer anders,
#      und jeder Pfad, der /home/uchralt enthaelt, zeigt ins Leere. Das ist
#      der Grund, warum ein blosses tar-Kopieren nicht reicht.
#
# llama.cpp bleibt unangetastet -- Fremdcode, und dort steht nichts drin.
set -uo pipefail

L="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALTES_HEIM="${ALTES_HEIM:-/home/uchralt}"
SCHREIBEN=0
[ "${1:-}" = "--schreiben" ] && SCHREIBEN=1

# Reihenfolge zaehlt: die spezielleren Pfade zuerst, sonst frisst die
# Heim-Ersetzung sie auf.
ERSETZUNGEN=(
  "$ALTES_HEIM/qwen-serve|$L/system"
  "$ALTES_HEIM/qwen-models|$L/modelle"
  "$ALTES_HEIM/systemlibs|$L/systemlibs"
)
[ "$ALTES_HEIM" != "$HOME" ] && ERSETZUNGEN+=("$ALTES_HEIM|$HOME")

dateien() {
  find "$L/system" "$L/dienste" -type f \
       \( -name '*.sh' -o -name '*.py' -o -name '*.json' -o -name '*.service' -o -name '*.jinja' \) \
       ! -path '*llama.cpp*' ! -path '*__pycache__*' ! -path '*/hf-home/*' 2>/dev/null
  find "$L/system/werkzeuge" -maxdepth 1 -type f ! -name '*.md' 2>/dev/null
}

[ "$SCHREIBEN" = 1 ] && echo "== SCHREIBMODUS ==" || echo "== Probelauf, nichts wird geaendert =="
echo "   von: $ALTES_HEIM"
echo "   nach: $L  (Heim: $HOME)"
echo

if [ "$SCHREIBEN" = 1 ]; then
  SICHERUNG="$L/.pfade-sicherung-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$SICHERUNG"
  echo "   Sicherung: $SICHERUNG"
  echo
fi

gesamt=0; betroffen=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  n=0
  for e in "${ERSETZUNGEN[@]}"; do
    # grep -c gibt bei null Treffern "0" aus UND liefert 1 zurueck.
    # Ein "|| echo 0" haengt dann eine zweite Null an und zerlegt die Rechnung.
    c=$(grep -c -F "${e%%|*}" "$f" 2>/dev/null) || c=0
    n=$((n + c))
  done
  [ "$n" -gt 0 ] || continue
  betroffen=$((betroffen+1)); gesamt=$((gesamt+n))
  printf "  %-52s %3d Stellen\n" "${f#$L/}" "$n"
  if [ "$SCHREIBEN" = 1 ]; then
    ziel="$SICHERUNG/${f#$L/}"; mkdir -p "$(dirname "$ziel")"; cp -p "$f" "$ziel"
    for e in "${ERSETZUNGEN[@]}"; do
      alt="${e%%|*}"; neu="${e##*|}"
      python3 - "$f" "$alt" "$neu" <<'PY'
import sys
p, alt, neu = sys.argv[1], sys.argv[2], sys.argv[3]
with open(p, 'r', encoding='utf-8', errors='surrogateescape') as fh:
    t = fh.read()
with open(p, 'w', encoding='utf-8', errors='surrogateescape') as fh:
    fh.write(t.replace(alt, neu))
PY
    done
  fi
done < <(dateien | sort -u)

echo
echo "  $betroffen Dateien, $gesamt Stellen"
if [ "$SCHREIBEN" = 1 ]; then
  echo
  echo "  Umgeschrieben. Danach unbedingt pruefen:"
  echo "    $L/system/werkzeuge/werkzeugtest --schnell"
  echo "  Zuruecknehmen: cp -r $SICHERUNG/* $L/"
else
  echo
  echo "  Zum Ausfuehren:  $0 --schreiben"
fi
