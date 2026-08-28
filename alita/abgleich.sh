#!/usr/bin/env bash
# Gleicht Alita mit dem Repo ab -- die Tafel in beide Richtungen.
#
#   ./abgleich.sh            holen, Unterschiede zeigen, nichts schreiben
#   ./abgleich.sh --hoch     Alitas Stand ins Repo bringen und pushen
#   ./abgleich.sh --runter   den Stand aus dem Repo nach Alita uebernehmen
#
# Die Tafel ist ein Anhaenge-Protokoll. Zwei Rechner, die gleichzeitig
# anhaengen, erzeugen einen Konflikt, den git nicht sinnvoll aufloest --
# deshalb wird hier NIE automatisch zusammengefuehrt, sondern gezeigt und
# gefragt. Wer zuerst hochlaedt, gewinnt; der andere sieht den Unterschied.
set -uo pipefail

L=/home/uchralt/local_agentic_system
R=$L/repo-local_models
A=$L/BLACKBOARD.md
B=$R/alita/BLACKBOARD.md

[ -d "$R/.git" ] || { echo "Kein Klon unter $R"; exit 1; }

echo "── holen ──"
git -C "$R" fetch -q origin 2>&1 | sed 's/^/  /'
lokal=$(git -C "$R" rev-parse HEAD)
fern=$(git -C "$R" rev-parse origin/main 2>/dev/null || git -C "$R" rev-parse origin/HEAD)
if [ "$lokal" = "$fern" ]; then
    echo "  Repo ist auf demselben Stand ($(git -C "$R" log -1 --format=%h))"
else
    echo "  Neues im Repo:"
    git -C "$R" log --oneline HEAD..origin/main 2>/dev/null | sed 's/^/    /'
    git -C "$R" merge -q --ff-only origin/main 2>/dev/null \
        && echo "  uebernommen -> $(git -C "$R" log -1 --format=%h)" \
        || echo "  ACHTUNG: kein schneller Vorlauf moeglich, von Hand pruefen"
fi

echo
echo "── Tafel ──"
if cmp -s "$A" "$B"; then
    echo "  Alita und Repo sind gleich ($(grep -c '^### \[' "$A") Eintraege)"
else
    na=$(grep -c '^### \[' "$A"); nb=$(grep -c '^### \[' "$B")
    echo "  Alita: $na Eintraege, Repo: $nb"
    diff <(grep '^### \[' "$B") <(grep '^### \[' "$A") \
      | sed -e 's/^>/  nur auf Alita:/' -e 's/^</  nur im Repo: /' | grep -E 'nur (auf|im)' || true
fi

case "${1:-}" in
  --hoch)
    echo
    echo "── hochladen ──"
    cp "$A" "$B"
    # NICHT die READMEs kopieren. Am 28.08. hat genau diese Zeile die im Repo
    # bearbeitete README.de.md ueberschrieben und dabei den Querverweis zur
    # englischen Fassung, den Link auf system.html und den Drei-Namen-Block
    # geloescht. Die READMEs im Repo sind eigenstaendige Dokumente, keine
    # Spiegel von Alita -- sie sind bewusst auseinandergelaufen.
    #
    # Hier gehoert nur her, was auf Alita ENTSTEHT: die Tafel und die Werkzeuge.
    for w in tafel beobachter grossauftrag pruefe-markdown; do
        cp "$L/system/werkzeuge/$w" "$R/alita/werkzeuge/" 2>/dev/null
    done
    cp "$L/abgleich.sh" "$L/qc-veroeffentlichen.sh" "$R/alita/" 2>/dev/null
    cp $L/system/laufwaechter/urteil.py $L/system/laufwaechter/pruefe.py "$R/alita/werkzeuge/" 2>/dev/null
    cp $L/dienste/*.service "$R/alita/konfiguration/" 2>/dev/null
    if git -C "$R" diff --quiet && git -C "$R" diff --cached --quiet; then
        echo "  nichts zu tun"
    else
        git -C "$R" add -A
        git -C "$R" commit -q -m "Tafel und Werkzeuge von Alita, Stand $(date +%Y-%m-%d\ %H:%M)"
        git -C "$R" push -q origin HEAD && echo "  gepusht -> $(git -C "$R" log -1 --format=%h)"
    fi ;;
  --runter)
    echo
    echo "── uebernehmen ──"
    cp "$B" "$A" && echo "  Tafel aus dem Repo nach Alita uebernommen" ;;
esac
