#!/usr/bin/env bash
# Meldet diese Maschine am Schwachstellenscanner an. MIT sudo auszufuehren.
#
#   sudo ./nessus-agent.sh /pfad/NessusAgent-<version>_amd64.deb
#
# Der Linking-Key steht NICHT in dieser Datei. Er ist ein Zugangsschluessel:
# wer ihn hat, kann eine beliebige Maschine an Ihren Scanner anmelden. Das
# Skript liest ihn aus der Umgebung oder fragt danach, und er landet weder im
# Verlauf der Shell noch in einem Repo.
#
#     NESSUS_KEY=... sudo -E ./nessus-agent.sh <paket>
#     sudo ./nessus-agent.sh <paket>          # fragt dann nach
#
# JEDER SCHRITT PRUEFT VORHER. Ein Anmeldeversuch gegen einen unerreichbaren
# Scanner hinterlaesst einen halb eingerichteten Agenten, und den sieht man
# erst, wenn der naechste Scan ihn vermisst.
set -uo pipefail

SCANNER_HOST=10.58.5.30
SCANNER_PORT=8834
GRUPPE=Linux
PAKET="${1:-}"

sage() { printf "  %-46s %s\n" "$1" "$2"; }
abbruch() { echo; echo "  ABBRUCH: $1" >&2; exit 1; }

echo "── Vorbedingungen ──"

[ "$(id -u)" -eq 0 ] || abbruch "als root ausfuehren (sudo)"
sage "als root" "ja"

# 1. Netz. Ohne das ist alles Weitere sinnlos.
if timeout 8 bash -c "cat < /dev/null > /dev/tcp/$SCANNER_HOST/$SCANNER_PORT" 2>/dev/null; then
    sage "Scanner $SCANNER_HOST:$SCANNER_PORT" "erreichbar"
else
    sage "Scanner $SCANNER_HOST:$SCANNER_PORT" "NICHT erreichbar"
    echo
    echo "  Diese Maschine liegt in $(ip -4 -o addr show scope global | awk '$2!~/docker|br-/{print $4; exit}')."
    echo "  Der Scanner liegt in 10.58.5.0/24. Solange die Maschine nicht im"
    echo "  Charite-Netz haengt, kann sich der Agent nicht anmelden."
    abbruch "erst ins richtige Netz, dann anmelden"
fi

# 2. Schon da?
if [ -x /opt/nessus_agent/sbin/nessuscli ]; then
    sage "Agent bereits installiert" "ja"
    /opt/nessus_agent/sbin/nessuscli agent status 2>&1 | sed 's/^/      /'
    echo
    read -rp "  Trotzdem neu anmelden? [j/N] " a
    [ "$a" = "j" ] || exit 0
else
    [ -n "$PAKET" ] || abbruch "Pfad zum .deb angeben"
    [ -f "$PAKET" ] || abbruch "Paket nicht gefunden: $PAKET"
    sage "Paket" "$(basename "$PAKET")"
fi

# 3. Schluessel. Nicht auf der Kommandozeile -- der landet in der History.
KEY="${NESSUS_KEY:-}"
if [ -z "$KEY" ]; then
    read -rsp "  Linking-Key: " KEY; echo
fi
[ ${#KEY} -ge 32 ] || abbruch "Key sieht zu kurz aus (${#KEY} Zeichen)"
sage "Key" "${#KEY} Zeichen, beginnt mit ${KEY:0:6}…"

echo
echo "── Installieren ──"
if [ ! -x /opt/nessus_agent/sbin/nessuscli ]; then
    dpkg -i "$PAKET" || abbruch "dpkg fehlgeschlagen"
    sage "dpkg -i" "ok"
fi

echo
echo "── Anmelden ──"
/opt/nessus_agent/sbin/nessuscli agent link \
    --key="$KEY" --host="$SCANNER_HOST" --port="$SCANNER_PORT" --groups="$GRUPPE" \
    || abbruch "Anmeldung fehlgeschlagen"
sage "agent link" "ok"

systemctl enable --now nessusagent || abbruch "Dienst startet nicht"
sage "Dienst" "$(systemctl is-active nessusagent)"

echo
echo "── Kontrolle ──"
sleep 5
/opt/nessus_agent/sbin/nessuscli agent status 2>&1 | sed 's/^/  /'
echo
echo "  Erwartet: 'Linked to: 10.58.5.30:8834' und ein Status ungleich 'Not linked'."
echo "  Der erste Scan kommt vom Server, nicht von hier -- er kann Stunden dauern."
