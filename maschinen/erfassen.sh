#!/usr/bin/env bash
# Erfasst diese Maschine und schreibt ihr Blatt nach maschinen/<rechnername>.md
#
#   ./maschinen/erfassen.sh              schreibt die Datei
#   ./maschinen/erfassen.sh --zeigen     nur ausgeben, nichts schreiben
#
# Auf jedem Rechner einmal laufen lassen. Das Ergebnis ist ein Blatt je
# Maschine: was sie hat, was darauf laeuft, und -- das ist der Punkt -- was
# gemessen wurde, nicht was auf der Packung steht.
#
# Modellunabhaengig: hier steht, WAS die Maschine traegt, nicht WELCHES Modell
# darauf laufen soll. Welches Modell passt, sagt tools/detect.py.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

N=$(hostname)
Z="maschinen/$N.md"
[ "${1:-}" = "--zeigen" ] && Z=/dev/stdout

mib() { awk -v b="$1" 'BEGIN{printf "%.1f", b/1024}'; }

{
echo "# $N"
echo
echo "*$(date +%Y-%m-%d) erfasst mit \`maschinen/erfassen.sh\`. Alle Zahlen gemessen."
echo "*Captured $(date +%Y-%m-%d). Every number measured, none from a spec sheet.*"
echo
echo "## Hardware"
echo
echo "| | |"
echo "|---|---|"
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null \
      | awk -F', ' '{printf "| GPU | %s, %s |\n| Treiber / driver | %s |\n",$1,$2,$3}'
    cc=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1)
    [ -n "$cc" ] && echo "| Compute Capability | $cc$([ "${cc%%.*}" -ge 9 ] 2>/dev/null && echo " (FP8 moeglich)" || echo " (bfloat16 ja, FP8 nein)") |"
else
    echo "| GPU | keine erkannt / none detected |"
fi
echo "| CPU | $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ *//') |"
echo "| Kerne / cores | $(nproc) Threads, $(lscpu 2>/dev/null | awk -F: '/^Core\(s\) per socket/{gsub(/ /,"",$2);print $2}' || echo '?') Kerne je Sockel |"
awk '/MemTotal/{printf "| RAM | %.1f GiB |\n",$2/1048576}' /proc/meminfo
awk '/SwapTotal/{printf "| Swap | %.1f GiB |\n",$2/1048576}' /proc/meminfo
echo "| System | $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || uname -s), Kernel $(uname -r) |"
echo "| Platte / disk | $(df -h "$HOME" | awk 'NR==2{print $4" frei von "$2}') |"
# Gruppenmitgliedschaft und Betriebsregel sind zweierlei. Auf Alita ist das
# Konto in der sudo-Gruppe, die Regel lautet trotzdem: im Alltag kein sudo.
# Beides nennen, sonst liest sich das Blatt als Widerspruch zur Doku.
if id -nG | grep -qw sudo; then
    if sudo -n true 2>/dev/null; then
        echo "| Rechte / privileges | in der sudo-Gruppe, ohne Passwort |"
    else
        echo "| Rechte / privileges | in der sudo-Gruppe, verlangt Passwort — Betriebsregel: im Alltag kein sudo |"
    fi
else
    echo "| Rechte / privileges | **kein sudo** |"
fi
echo

echo "## Im Betrieb gemessen / measured under load"
echo
echo "| | |"
echo "|---|---|"
if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null \
      | awk -F', ' '{printf "| VRAM belegt / used | %d von %d MiB |\n| VRAM frei / free | **%d MiB** |\n",$1,$2,$2-$1}'
    p=$(nvidia-smi --query-compute-apps=process_name,used_memory --format=csv,noheader 2>/dev/null \
        | sed 's|.*/||' | awk -F', ' '{printf "%s (%s)%s", $1, $2, (NR>0?"; ":"")}' | sed 's/; $//')
    [ -n "$p" ] && echo "| haelt VRAM / holding VRAM | $p |"
fi
awk '/MemAvailable/{printf "| RAM verfuegbar / available | %.1f GiB |\n",$2/1048576}' /proc/meminfo
echo "| Uptime | $(uptime -p 2>/dev/null | sed 's/^up //') |"
echo

if getent group agent-net >/dev/null 2>&1; then
    echo "| Agenten-Netzsperre | Gruppe \`agent-net\` vorhanden |"
    if timeout 10 sg agent-net -c 'curl -s -o /dev/null -m 6 https://github.com' 2>/dev/null; then
        echo "| Sperre wirksam? | **NEIN — ein Prozess in agent-net erreicht das Netz** |"
    else
        echo "| Sperre wirksam? | ja, gemessen: kein Zugang aus \`agent-net\` |"
    fi
fi
echo

echo "## Was laeuft / what is running"
echo
if systemctl --user list-units --type=service --state=running --no-legend >/dev/null 2>&1; then
    n=$(systemctl --user list-units --type=service --state=running --no-legend 2>/dev/null | wc -l)
    echo "$n systemd-Benutzerdienste. Auf Loopback horchende Ports:"
    echo
    echo '```'
    ss -ltnp 2>/dev/null | awk 'NR>1 && $4 ~ /127.0.0.1/ {split($4,a,":"); split($NF,b,"\""); printf "  %-6s %s\n", a[length(a)], b[2]}' | sort -u
    echo '```'
else
    echo "Keine systemd-Benutzerdienste."
fi
echo

echo "## Modelle auf der Platte / models on disk"
echo
gef=0
for d in "$HOME/local_agentic_system/modelle" "$HOME/qwen-models" "$HOME/models" "$HOME/.cache/huggingface"; do
    [ -d "$d" ] || continue
    gef=1
    echo "\`${d/#$HOME/~}\`"
    echo
    echo '```'
    du -sh "$d"/* 2>/dev/null | sed "s|$d/|  |" | sort -h | tail -12
    echo '```'
    echo
done
[ "$gef" -eq 1 ] || echo "Keine bekannten Modellverzeichnisse gefunden."
echo

echo "## Rechenumgebung / compute environment"
echo
echo "| | |"
echo "|---|---|"
for e in "$HOME/miniconda3/envs"/*; do
    [ -x "$e/bin/python" ] || continue
    v=$("$e/bin/python" --version 2>&1 | cut -d' ' -f2)
    t=$("$e/bin/python" -c "import torch;print(f'torch {torch.__version__}, CUDA {torch.cuda.is_available()}')" 2>/dev/null || echo "kein torch")
    echo "| conda \`$(basename "$e")\` | Python $v, $t |"
done
for w in llama-server llama-cli git gh python3; do
    p=$(command -v $w 2>/dev/null) && echo "| \`$w\` | ${p/#$HOME/~} |"
done
echo

echo "## Bildgebung / imaging tools"
echo
gef=0
for w in bet flirt fslmaths bianca recon-all mri_convert mri_synthseg mri_WMHsynthseg samseg hd-bet microbleednet dcm2niix nnUNetv2_predict; do
    if command -v "$w" >/dev/null 2>&1; then
        [ "$gef" -eq 0 ] && { echo '```'; gef=1; }
        printf "  %-20s %s\n" "$w" "$(command -v $w | sed "s|$HOME|~|")"
    fi
done
[ "$gef" -eq 1 ] && echo '```' || echo "Keine gefunden."
echo
echo "---"
echo
echo "*Erneuern mit \`./maschinen/erfassen.sh\`. Was ueber diese Maschine hinausgeht --"
echo "welches Modell wie schnell laeuft -- steht in [tools/](../tools/) und [docs/](../docs/).*"
} > "$Z"

[ "$Z" = /dev/stdout ] || echo "  geschrieben: $Z  ($(wc -l < "$Z") Zeilen)"
