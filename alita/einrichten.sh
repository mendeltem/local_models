#!/usr/bin/env bash
# Bringt das lokale agentische System auf einem Rechner hoch.
#
#   ./einrichten.sh            legt Symlinks und Dienste an, prueft die Umgebung
#   ./einrichten.sh --pruefen  prueft nur, aendert nichts
#
# Braucht kein sudo. Aendert nichts, was schon da ist.
set -uo pipefail

L="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NUR_PRUEFEN=0
[ "${1:-}" = "--pruefen" ] && NUR_PRUEFEN=1

ok()   { printf "  \033[32mok\033[0m      %-26s %s\n" "$1" "${2:-}"; }
warn() { printf "  \033[33mfehlt\033[0m   %-26s %s\n" "$1" "${2:-}"; }
fehl() { printf "  \033[31mFEHLER\033[0m  %-26s %s\n" "$1" "${2:-}"; FEHLER=$((FEHLER+1)); }
FEHLER=0

echo "── Verzeichnis ──"
for d in system modelle dienste; do
    [ -d "$L/$d" ] && ok "$d" "$(du -sh "$L/$d" 2>/dev/null | cut -f1)" || fehl "$d" "fehlt"
done

echo
echo "── Symlinks der alten Pfade ──"
verknuepfe() {  # <ziel-im-baum> <alter-pfad>
    local ziel="$L/$1" alt="$2"
    if [ -L "$alt" ]; then
        [ "$(readlink -f "$alt")" = "$(readlink -f "$ziel")" ] && ok "$(basename $alt)" "zeigt richtig" \
            || fehl "$(basename $alt)" "zeigt woandershin: $(readlink "$alt")"
    elif [ -e "$alt" ]; then
        fehl "$(basename $alt)" "existiert und ist kein Symlink - von Hand pruefen"
    elif [ "$NUR_PRUEFEN" = 1 ]; then
        warn "$(basename $alt)" "wuerde angelegt"
    else
        ln -s "$ziel" "$alt" && ok "$(basename $alt)" "angelegt"
    fi
}
verknuepfe system     "$HOME/qwen-serve"
verknuepfe modelle    "$HOME/qwen-models"
verknuepfe systemlibs "$HOME/systemlibs"

echo
echo "── Fest verdrahtete Pfade ──"
FREMD=$(grep -rl "/home/uchralt/qwen-serve\|/home/uchralt/qwen-models" "$L/system" "$L/dienste" \
        --include='*.sh' --include='*.py' --include='*.json' --include='*.service' 2>/dev/null \
        | grep -v llama.cpp | wc -l)
HEIM=$(grep -rl "/home/uchralt" "$L/system" "$L/dienste" \
       --include='*.sh' --include='*.py' --include='*.json' --include='*.service' 2>/dev/null \
       | grep -v llama.cpp | wc -l)
if [ "$FREMD" -eq 0 ] && { [ "$HOME" = /home/uchralt ] || [ "$HEIM" -eq 0 ]; }; then
    ok "Pfade" "keine alten Namen mehr"
else
    [ "$FREMD" -gt 0 ] && warn "alte Namen" "$FREMD Dateien nennen ~/qwen-serve oder ~/qwen-models"
    [ "$HOME" != /home/uchralt ] && [ "$HEIM" -gt 0 ] && \
        fehl "fremdes Zuhause" "$HEIM Dateien nennen /home/uchralt, Ihr Heim ist $HOME"
    echo "          -> $L/pfade-anpassen.sh --schreiben"
fi

echo
echo "── Rechenumgebung ──"
DL="$HOME/miniconda3/envs/dl/bin/python"
if [ -x "$DL" ]; then
    ok "conda dl" "$($DL --version 2>&1)"
    for m in torch monai nibabel numpy; do
        v=$($DL -c "import $m;print(getattr($m,'__version__','?'))" 2>/dev/null) \
            && ok "  $m" "$v" || fehl "  $m" "nicht importierbar"
    done
    $DL -c "import torch;exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null \
        && ok "  CUDA" "$($DL -c "import torch;print(torch.cuda.get_device_name(0))" 2>/dev/null)" \
        || warn "  CUDA" "keine GPU sichtbar - CPU-Betrieb"
else
    fehl "conda dl" "$DL fehlt - ohne sie laeuft nichts Gerechnetes"
fi

echo
echo "── llama.cpp ──"
LS="$L/system/llama.cpp/build/bin/llama-server"
[ -x "$LS" ] && ok "llama-server" "gebaut" \
    || warn "llama-server" "nicht gebaut: cd system/llama.cpp && cmake -B build && cmake --build build -j"

echo
echo "── Gewichte ──"
for f in modelle/Qwen3.8-27B-UD-Q4_K_M.gguf modelle/embedding/bge-m3-Q8_0.gguf \
         modelle/waechter/qwen2.5-0.5b-instruct-q8_0.gguf; do
    [ -f "$L/$f" ] && ok "$(basename $f)" "$(du -h "$L/$f" | cut -f1)" || warn "$(basename $f)" "fehlt"
done

echo
echo "── Bildgebung (optional) ──"
for w in bet flirt fslmaths recon-all mri_synthseg hd-bet; do
    command -v "$w" >/dev/null 2>&1 && ok "$w" || warn "$w" "nicht im PATH"
done

echo
echo "── systemd-Benutzerdienste ──"
UD="$HOME/.config/systemd/user"
if [ "$NUR_PRUEFEN" = 1 ]; then
    for u in "$L"/dienste/*.service; do
        n=$(basename "$u")
        [ -e "$UD/$n" ] && ok "$n" "schon eingerichtet" || warn "$n" "wuerde eingerichtet"
    done
else
    mkdir -p "$UD"
    for u in "$L"/dienste/*.service; do
        n=$(basename "$u")
        if [ -e "$UD/$n" ]; then ok "$n" "war schon da, unveraendert"
        else install -m 644 "$u" "$UD/$n" && ok "$n" "eingerichtet"; fi
    done
    systemctl --user daemon-reload 2>/dev/null
    loginctl enable-linger "$USER" 2>/dev/null && ok "Linger" "Dienste ueberleben Abmelden" \
        || warn "Linger" "nicht setzbar - Dienste enden mit der Sitzung"
fi

echo
echo "════════════════════════════════════════"
if [ "$FEHLER" -eq 0 ]; then
    echo "  Bereit. Naechster Schritt:"
    echo "    $L/system/nach-neustart.sh"
    echo "    $L/system/werkzeuge/werkzeugtest --schnell"
else
    echo "  $FEHLER Punkt(e) muessen von Hand geklaert werden, siehe oben."
fi
exit $FEHLER
