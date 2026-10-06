#!/usr/bin/env bash
# Taegliche Recherche: Claude liest fragen.md und den letzten Stand, sucht im Netz,
# schreibt stand/<heute>.md und NEU.md. Commit nur lokal, nie Push.
#
#   tag.sh            normaler Lauf (laeuft ueber recherche.timer jeden Morgen)
#   tag.sh --trocken  zeigt nur, was liefe
#
# Nur Websuche, Lesen und Schreiben in diesem Ordner. Kein Bash fuer Claude.
set -euo pipefail

HIER="$(cd "$(dirname "$0")" && pwd)"
REPO="$(git -C "$HIER" rev-parse --show-toplevel)"
HEUTE="$(date +%F)"
ZIEL="stand/$HEUTE.md"
MODELL="${RECHERCHE_MODELL:-sonnet}"
BUDGET="${RECHERCHE_BUDGET_USD:-3}"
cd "$HIER"

LETZTER="$(ls stand/*.md 2>/dev/null | grep -v "$HEUTE" | sort | tail -1 || true)"
if [[ -e "$ZIEL" ]]; then
    echo "$ZIEL gibt es schon, nichts zu tun."
    exit 0
fi

AUFTRAG="Lies fragen.md und arbeite den Auftrag ab. Letzter Stand: ${LETZTER:-keiner}.
Heute ist $HEUTE. Recherchiere mit der Websuche, was sich seit dem letzten Stand geaendert hat.
Schreibe den fortgeschriebenen Stand nach $ZIEL und die Aenderungen nach NEU.md
(NEU.md ueberschreiben, erste Zeile: '# Neu am $HEUTE'). Halte dich an die Belegregeln.
Schreibe nur diese zwei Dateien."

BEFEHL=(nice -n 10 claude -p "$AUFTRAG" --model "$MODELL" --max-budget-usd "$BUDGET"
        --permission-mode dontAsk --no-session-persistence
        --allowedTools WebSearch WebFetch Read Write Edit Glob Grep)

if [[ "${1:-}" == "--trocken" ]]; then
    printf '%q ' "${BEFEHL[@]}"; echo
    exit 0
fi

mkdir -p logs
"${BEFEHL[@]}" > "logs/$HEUTE.log" 2>&1 || echo "claude endete mit Fehler, siehe logs/$HEUTE.log"

# Abnahme: Datei da, nicht duerr, mit Quellen, NEU.md von heute
fehler=""
if [[ ! -s "$ZIEL" ]]; then fehler="$ZIEL fehlt"
elif (( $(wc -l < "$ZIEL") < 30 )); then fehler="$ZIEL hat unter 30 Zeilen"
elif ! grep -q "https\?://" "$ZIEL"; then fehler="$ZIEL ohne Quellen"
elif ! grep -q "Neu am $HEUTE" NEU.md 2>/dev/null; then fehler="NEU.md nicht von heute"
fi

if [[ -n "$fehler" ]]; then
    echo "Recherche $HEUTE nicht abgenommen: $fehler"
    command -v notify-send >/dev/null && notify-send "Recherche $HEUTE" "nicht abgenommen: $fehler" || true
    exit 1
fi

git -C "$REPO" add "recherche/$ZIEL" recherche/NEU.md
git -C "$REPO" -c user.name="recherche (Claude)" -c user.email=mendeltem@googlemail.com \
    commit -q -m "recherche: Stand $HEUTE" -- "recherche/$ZIEL" recherche/NEU.md
echo "Recherche $HEUTE abgenommen und lokal committet."
command -v notify-send >/dev/null && notify-send "Recherche $HEUTE" "$(sed -n 2,6p NEU.md)" || true
