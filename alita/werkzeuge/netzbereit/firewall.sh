#!/usr/bin/env bash
# Grundschutz fuer Alita, bevor sie ans Charite-Netz geht. MIT sudo.
#
#   sudo ./firewall.sh --pruefen     nur zeigen, was passieren wuerde
#   sudo ./firewall.sh               ausfuehren
#
# BEFUND VOM 31.08.2026
#
#     ufw                inactive        keine Firewall
#     DOCKER-USER        leer            keine Regel fuer Docker-Ports
#     erreichbar         0.0.0.0:8080    openshell-cluster, restart=unless-stopped
#     SSH                inaktiv         kein Aussperr-Risiko
#
# WARUM ZWEI SCHRITTE
#
# Docker haengt seine Regeln VOR ufw in die FORWARD-Kette. Ein
# veroeffentlichter Port bleibt erreichbar, auch wenn `ufw deny 8080` gesetzt
# ist -- das ist der haeufigste Irrtum bei genau dieser Aufgabe. Die einzige
# Kette, die zuverlaessig greift, ist DOCKER-USER.
#
# Und dort steht der CONTAINER-Port (30051), nicht der veroeffentlichte (8080).
# Wer 8080 eintraegt, sperrt nichts und glaubt, er haette.
set -uo pipefail

NUR_PRUEFEN=0
[ "${1:-}" = "--pruefen" ] && NUR_PRUEFEN=1

sage() { printf "  %-46s %s\n" "$1" "$2"; }
tu() { if [ "$NUR_PRUEFEN" = 1 ]; then echo "      wuerde:  $*"; else "$@"; fi; }

[ "$(id -u)" -eq 0 ] || { echo "  als root ausfuehren (sudo)" >&2; exit 1; }

echo "── Lage ──"
sage "ufw" "$(ufw status 2>/dev/null | head -1 | sed 's/Status: //')"
sage "DOCKER-USER Regeln" "$(iptables -S DOCKER-USER 2>/dev/null | grep -c '^-A' || echo 0)"

# Aussperr-Risiko: nur relevant, wenn jemand ueber das Netz angemeldet ist.
if ss -tln 2>/dev/null | grep -qE ':22\s'; then
    sage "SSH horcht" "JA -- ufw wuerde Sie aussperren"
    echo
    echo "  Vor 'ufw enable' unbedingt:  ufw allow 22/tcp"
    echo "  Sonst ist die Maschine nur noch vor Ort erreichbar."
    [ "$NUR_PRUEFEN" = 1 ] || { echo "  ABBRUCH zur Sicherheit." >&2; exit 1; }
else
    sage "SSH horcht" "nein -- kein Aussperr-Risiko"
fi

# Welches Netz gilt als lokal? Aus der eigenen Adresse abgeleitet, nicht geraten.
LOKALNETZ=$(ip -4 -o addr show scope global 2>/dev/null \
            | awk '$2 !~ /docker|br-/ {print $4; exit}')
[ -n "$LOKALNETZ" ] || { echo "  kein Netz gefunden" >&2; exit 1; }
NETZ=$(python3 -c "import ipaddress,sys; print(ipaddress.ip_network('$LOKALNETZ', strict=False))" 2>/dev/null)
sage "eigenes Netz" "${NETZ:-$LOKALNETZ}"

echo
echo "── 1. Grundschutz ──"
tu ufw default deny incoming
tu ufw default allow outgoing
tu ufw --force enable
sage "ufw" "$([ "$NUR_PRUEFEN" = 1 ] && echo 'waere aktiv' || ufw status | head -1 | sed 's/Status: //')"

echo
echo "── 2. Docker-veroeffentlichte Ports ──"
# Jeden veroeffentlichten Container-Port einzeln behandeln. Der Port in der
# Regel ist der CONTAINER-Port, den DOCKER-USER sieht.
docker ps --format '{{.Names}}\t{{.Ports}}' 2>/dev/null | while IFS=$'\t' read -r name ports; do
    echo "$ports" | tr ',' '\n' | while read -r pp; do
        case "$pp" in
            *0.0.0.0:*) ;;
            *) continue ;;
        esac
        cport=$(echo "$pp" | sed -n 's/.*->\([0-9]*\)\/tcp.*/\1/p')
        hport=$(echo "$pp" | sed -n 's/.*0\.0\.0\.0:\([0-9]*\)->.*/\1/p')
        [ -n "$cport" ] || continue
        sage "$name  $hport -> $cport" "offen fuer ALLE"
        if iptables -C DOCKER-USER -p tcp --dport "$cport" ! -s "$NETZ" -j DROP 2>/dev/null; then
            sage "  Regel schon da" "ja"
        else
            tu iptables -I DOCKER-USER -p tcp --dport "$cport" ! -s "$NETZ" -j DROP
            sage "  begrenzt auf" "$NETZ"
        fi
    done
done

echo
echo "── Kontrolle ──"
[ "$NUR_PRUEFEN" = 1 ] && { echo "  (nur Probe, nichts geaendert)"; exit 0; }
ufw status verbose 2>/dev/null | head -6 | sed 's/^/  /'
echo
iptables -S DOCKER-USER | sed 's/^/  /'
echo
echo "  iptables-Regeln ueberleben KEINEN Neustart. Dauerhaft machen mit"
echo "  'apt install iptables-persistent' oder einer systemd-Unit."
echo "  Sauberer waere, den Container gar nicht nach aussen zu veroeffentlichen:"
echo "      docker run ... -p 127.0.0.1:8080:30051 ..."
echo "  Das setzt voraus, dass Sie wissen, wozu er da ist."
