#!/bin/bash
# ---------------------------------------------------------------------------
# rest_download.sh — laedt den Rest, waehrend ein anderer Lauf noch arbeitet.
#
# Gedacht fuer ein zweites Terminal: `alles-laden.sh` haengt an einer grossen
# Datei, und die uebrigen Posten sollen nicht darauf warten.
#
#     bash rest_download.sh              # alles Fehlende ausser dem,
#                                        # was gerade jemand anderes laedt
#     bash rest_download.sh --zeigen     # nur anzeigen, nichts laden
#     bash rest_download.sh medgemma-27b # nur Posten, deren Pfad das Muster
#                                        # enthaelt — wenn nur EINE bestimmte
#                                        # Datei gebraucht wird
#     BEKANNT=./INVENTAR-usb.txt bash rest_download.sh
#
# ---------------------------------------------------------------------------
# WARUM DIESES SKRIPT VORSICHTIG IST
#
# Zwei curl-Prozesse mit `-C -` auf derselben Datei haengen beide an dieselbe
# Datei an, jeder ab seiner eigenen Position. Das Ergebnis hat am Ende
# ungefaehr die richtige Groesse und ist trotzdem Muell — und es faellt erst
# auf, wenn das Modell nicht laedt.
#
# Deshalb wird vor jedem Posten geprueft, ob die Zieldatei gerade waechst.
# Waechst sie, laedt sie schon jemand: Finger weg.
#
# Das ist kein Ersatz fuer eine echte Sperre. Wenn der andere Lauf gerade
# zwischen zwei Wiederholungsversuchen steht, waechst die Datei kurz nicht
# und dieses Skript koennte zugreifen. Fuer den Fall gibt es unten noch eine
# Sperrdatei.
# ---------------------------------------------------------------------------

set -u

HIER="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Tabelle und Funktionen aus alles-laden.sh uebernehmen, statt sie zu
# verdoppeln. Zwei Listen, die auseinanderlaufen, sind schlimmer als eine.
if [ ! -f "$HIER/alles-laden.sh" ]; then
  echo "alles-laden.sh liegt nicht neben diesem Skript." >&2
  exit 2
fi
# shellcheck disable=SC1091
NUR_FUNKTIONEN=1 . "$HIER/alles-laden.sh"

ZEIGEN=0
MUSTER=()
for a in "$@"; do
  if [ "$a" = "--zeigen" ]; then ZEIGEN=1; else MUSTER+=("$a"); fi
done

# passt <relpfad> — ohne Muster passt alles; sonst muss ein Muster
# als Teilzeichenkette im Pfad vorkommen. Damit laesst sich ein einzelner
# Posten holen:  bash rest_download.sh medgemma-27b
passt() {
  [ "${#MUSTER[@]}" -eq 0 ] && return 0
  local m
  for m in "${MUSTER[@]}"; do
    case "$1" in *"$m"*) return 0 ;; esac
  done
  return 1
}

PROBEZEIT="${PROBEZEIT:-4}"        # Sekunden, ueber die auf Wachstum geprueft wird
SPERRVERZ="${SPERRVERZ:-$ZIEL/.sperren}"
mkdir -p "$SPERRVERZ"

# ---------------------------------------------------------------------------
# waechst <datei> — wahr, wenn die Datei innerhalb der Probezeit groesser wird
# ---------------------------------------------------------------------------
waechst() {
  local p="$1" a b
  # Geladen wird in <name>.laedt, also dort nachsehen.
  [ -f "$p" ] || p="$p.laedt"
  [ -f "$p" ] || return 1
  a=$(stat -c%s "$p" 2>/dev/null || echo 0)
  sleep "$PROBEZEIT"
  b=$(stat -c%s "$p" 2>/dev/null || echo 0)
  [ "$b" -gt "$a" ]
}

# ---------------------------------------------------------------------------
# sperre_nehmen <relpfad> — legt eine Sperrdatei an; scheitert, wenn schon da.
#
# mkdir ist atomar: entweder es klappt oder das Verzeichnis gab es schon.
# Damit greifen sich zwei Laeufe nicht denselben Posten, auch wenn beide
# gleichzeitig starten.
# ---------------------------------------------------------------------------
sperre_nehmen() {
  local name; name=$(echo "$1" | tr '/' '_')
  mkdir "$SPERRVERZ/$name" 2>/dev/null
}
sperre_freigeben() {
  local name; name=$(echo "$1" | tr '/' '_')
  rmdir "$SPERRVERZ/$name" 2>/dev/null
}

# ---------------------------------------------------------------------------
aufraeumen() {
  # Bei Strg-C die eigene Sperre nicht liegen lassen, sonst blockiert sie
  # den naechsten Lauf.
  [ -n "${AKTUELL:-}" ] && sperre_freigeben "$AKTUELL"
  exit 130
}
trap aufraeumen INT TERM

AKTUELL=""
geladen=0; uebersprungen=0; belegt=0; gescheitert=0

printf '\n=== Rest-Download ===\n'
[ -n "${BEKANNT:-}" ] && printf 'Bekannter anderer Bestand: %s\n' "$BEKANNT"
printf 'Ziel: %s\n\n' "$ZIEL"

while IFS='|' read -r gruppe rel soll url; do
  [ -n "${rel:-}" ] || continue
  passt "$rel" || continue

  ziel="$ZIEL/$rel"
  kurz=$(basename "$rel")

  z=$(zustand "$ziel" "$soll")
  if [ "$z" = fertig ]; then
    uebersprungen=$((uebersprungen + 1)); continue
  fi
  if schon_anderswo "$rel" "$soll"; then
    printf '  ueb   %-50s liegt im anderen Bestand\n' "$kurz"
    uebersprungen=$((uebersprungen + 1)); continue
  fi

  # Nimmt sich schon jemand dieser Datei an?
  if ! sperre_nehmen "$rel"; then
    printf '  BELEGT %-49s (Sperre gesetzt)\n' "$kurz"
    belegt=$((belegt + 1)); continue
  fi
  if waechst "$ziel"; then
    printf '  BELEGT %-49s (waechst gerade)\n' "$kurz"
    sperre_freigeben "$rel"
    belegt=$((belegt + 1)); continue
  fi

  if [ "$ZEIGEN" = 1 ]; then
    printf '  wuerde %-49s %s\n' "$kurz" "$(menschlich "$soll")"
    sperre_freigeben "$rel"; continue
  fi

  AKTUELL="$rel"
  printf '  ->    %-50s %s\n' "$kurz" "$(menschlich "$soll")"
  if hartnaeckig "$url" "$ziel"; then
    geladen=$((geladen + 1))
  else
    gescheitert=$((gescheitert + 1))
  fi
  sperre_freigeben "$rel"
  AKTUELL=""
done < <(alle_zeilen)

printf '\n  geladen %d | schon da oder anderswo %d | belegt %d | gescheitert %d\n' \
  "$geladen" "$uebersprungen" "$belegt" "$gescheitert"

if [ "$belegt" -gt 0 ]; then
  printf '  %d Posten laedt gerade ein anderer Lauf. Dieses Skript spaeter\n' "$belegt"
  printf '  nochmal starten, dann holt es sie nach.\n'
fi

rmdir "$SPERRVERZ" 2>/dev/null
printf '\n'; df -h "$ZIEL" | tail -1
