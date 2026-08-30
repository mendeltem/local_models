#!/usr/bin/env bash
# Netzsperre ohne Root.
#
# Spannt einen Benutzer-, Mount- und Netz-Namensraum auf, in dem es nur
# Loopback gibt. Kein Weg nach draussen -- keine Regel, die man vergessen kann,
# die Route existiert schlicht nicht.
#
#   ./netzsperre.sh -- ./mein-lauf.sh [argumente]
#   ./netzsperre.sh --pruefen          # nur nachsehen, ob es hier geht
#   ./netzsperre.sh --mit-server -- ./mein-lauf.sh
#
# --mit-server startet llama-server MIT HINEIN. Das ist noetig, weil das
# Loopback im neuen Namensraum nicht das Loopback des Rechners ist: ein Server,
# der vorher draussen laeuft, ist von drinnen nicht erreichbar.
#
# Jede Namensaufloesung wird protokolliert (dns-senke.py) und mit NXDOMAIN
# beantwortet. Das Protokoll ist ein Messwert, kein Betriebsdetail: es zeigt,
# was das Modell stillschweigend voraussetzt.
#
# GESCHRIEBEN AUF VICTUS, NICHT AUF ALITA GELAUFEN. Zuerst --pruefen.
set -u

HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTOKOLL="${NETZSPERRE_PROTOKOLL:-$PWD/netzversuche.log}"
SERVER_START="${LLAMA_START:-$HOME/start-llama.sh}"
SERVER_PORT="${LLAMA_PORT:-8080}"
MIT_SERVER=0

fehler(){ printf 'netzsperre: %s\n' "$*" >&2; }

# --------------------------------------------------------------- Vorpruefung
pruefen(){
    local ok=0
    printf '%-42s' "unshare vorhanden"
    if command -v unshare >/dev/null; then echo "ja"; else echo "NEIN"; ok=1; fi

    printf '%-42s' "ip (iproute2) vorhanden"
    if command -v ip >/dev/null; then echo "ja"; else echo "NEIN"; ok=1; fi

    printf '%-42s' "unprivilegierte Benutzernamensraeume"
    local v; v=$(cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "-")
    if [ "$v" = "0" ]; then echo "AUS (=0) -- geht nicht"; ok=1
    else echo "an oder ohne Schalter ($v)"; fi

    printf '%-42s' "Namensraum laesst sich aufspannen"
    if unshare -rmn --  true 2>/dev/null; then echo "ja"; else echo "NEIN"; ok=1; fi

    printf '%-42s' "drinnen ist wirklich kein Netz"
    local aus
    aus=$(unshare -rmn -- sh -c 'ip route show 2>/dev/null | wc -l' 2>/dev/null || echo "?")
    if [ "$aus" = "0" ]; then echo "ja (keine Route)"; else echo "FRAGLICH ($aus Routen)"; ok=1; fi

    printf '%-42s' "python3 fuer die DNS-Senke"
    if command -v python3 >/dev/null; then echo "ja"; else echo "NEIN"; ok=1; fi

    echo
    if [ $ok -eq 0 ]; then
        echo "Der Prueflauf sieht gut aus. Gegenprobe im Ernstfall trotzdem machen:"
        echo "  ./netzsperre.sh -- curl -s -m 5 https://example.com   # MUSS scheitern"
    else
        echo "Mindestens eine Voraussetzung fehlt -- siehe oben."
        echo "Ohne Benutzernamensraeume bleibt nur: Netzwerkkabel ziehen und WLAN aus."
    fi
    return $ok
}

# ------------------------------------------------------------------ Argumente
while [ $# -gt 0 ]; do
    case "$1" in
        --pruefen)     pruefen; exit $? ;;
        --mit-server)  MIT_SERVER=1; shift ;;
        --)            shift; break ;;
        -h|--help)     sed -n '2,22p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *)             fehler "unbekannt: $1"; exit 64 ;;
    esac
done

[ $# -gt 0 ] || { fehler "kein Befehl angegeben (nach --)"; exit 64; }

command -v unshare >/dev/null || { fehler "unshare fehlt"; exit 3; }

# Was drinnen laeuft. Wird als Datei uebergeben, damit Anfuehrungszeichen
# im Befehl nicht durch eine zweite Shell-Auswertung laufen.
INNEN="$(mktemp)"
trap 'rm -f "$INNEN"' EXIT

{
    printf '%s\n' '#!/bin/sh'
    printf '%s\n' 'set -u'
    # Loopback hochziehen -- ohne das geht drinnen nicht einmal 127.0.0.1
    printf '%s\n' 'ip link set lo up 2>/dev/null || true'

    # Eigene resolv.conf ueber die des Rechners legen. Braucht den
    # Mount-Namensraum; ausserhalb bleibt die Datei unveraendert.
    printf 'printf "nameserver 127.0.0.1\\n" > %s\n' '"$RESOLV"'
    printf '%s\n' 'mount --bind "$RESOLV" /etc/resolv.conf 2>/dev/null || true'

    printf '%s\n' 'python3 "$SENKE" --protokoll "$PROTOKOLL" & SENKE_PID=$!'
    printf '%s\n' 'sleep 0.3'

    if [ "$MIT_SERVER" = "1" ]; then
        printf '%s\n' 'if [ -x "$SERVER_START" ]; then'
        printf '%s\n' '  "$SERVER_START" >/tmp/llama-innen.log 2>&1 & SRV_PID=$!'
        printf '%s\n' '  n=0'
        printf '%s\n' '  while [ $n -lt 120 ]; do'
        printf '%s\n' '    if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex((\"127.0.0.1\",int(\"'"$SERVER_PORT"'\")))==0 else 1)"; then break; fi'
        printf '%s\n' '    n=$((n+1)); sleep 5'
        printf '%s\n' '  done'
        printf '%s\n' '  [ $n -lt 120 ] || echo "netzsperre: llama-server kam nicht hoch" >&2'
        printf '%s\n' 'else'
        printf '%s\n' '  echo "netzsperre: $SERVER_START nicht ausfuehrbar" >&2'
        printf '%s\n' 'fi'
    fi

    printf '%s\n' '"$@"; ERG=$?'
    printf '%s\n' '[ -n "${SRV_PID:-}" ] && kill "$SRV_PID" 2>/dev/null'
    printf '%s\n' 'kill "$SENKE_PID" 2>/dev/null'
    printf '%s\n' 'exit $ERG'
} > "$INNEN"
chmod +x "$INNEN"

RESOLV="$(mktemp)"
export RESOLV PROTOKOLL SERVER_START MIT_SERVER
export SENKE="$HIER/dns-senke.py"

echo "netzsperre: Netz gesperrt, Protokoll -> $PROTOKOLL" >&2
unshare --user --map-root-user --mount --net -- "$INNEN" "$@"
ERG=$?
rm -f "$RESOLV"

if [ -s "$PROTOKOLL" ]; then
    echo "netzsperre: $(wc -l < "$PROTOKOLL") Netzversuche protokolliert:" >&2
    sort "$PROTOKOLL" | awk '{print $NF}' | sort | uniq -c | sort -rn | head -10 >&2
else
    echo "netzsperre: kein Netzversuch" >&2
fi
exit $ERG
