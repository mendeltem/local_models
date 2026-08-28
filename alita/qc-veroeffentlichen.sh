#!/usr/bin/env bash
# Veroeffentlicht ein QC-HTML als eigenes GitHub-Repo mit Pages.
#
#   ./qc-veroeffentlichen.sh <projekt> <qc.html> <datensatz-kennung>
#   ./qc-veroeffentlichen.sh --pruefen <projekt> <qc.html> <datensatz-kennung>
#
# Beispiel:
#   ./qc-veroeffentlichen.sh unet-wmh /home/uchralt/data/work/unet-qc/qc.html wmh-challenge
#
# WARUM ES DIESES SKRIPT GIBT
#
# Ein QC-HTML enthaelt Hirnschnitte in voller Aufloesung, eingebettet als PNG.
# Bei einem oeffentlichen Datensatz ist das unbedenklich -- bei eigenen
# Kohorten waeren es Patientenbilder auf fremden Servern. Ein privates Repo
# hilft dabei nicht: es ist Zugriffsschutz, keine Pseudonymisierung.
#
# Deshalb prueft dieses Skript VOR jedem Push, ob der Datensatz ausdruecklich
# freigegeben ist, und bricht sonst ab. Die Freigabe ist eine Datei, die
# jemand bewusst anlegen muss -- kein Schalter, den man im Vorbeigehen setzt.
set -uo pipefail

L=/home/uchralt/local_agentic_system
FREIGABEN=$L/datensaetze-oeffentlich
NUR_PRUEFEN=0
[ "${1:-}" = "--pruefen" ] && { NUR_PRUEFEN=1; shift; }

PROJEKT="${1:-}"; QC="${2:-}"; DATENSATZ="${3:-}"
[ -n "$PROJEKT" ] && [ -n "$QC" ] && [ -n "$DATENSATZ" ] || {
    sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

fehler=0
sage() { printf "  %-46s %s\n" "$1" "$2"; }

echo "── Pruefungen ──"

# 1. Freigabe des Datensatzes -- die wichtigste
if [ -f "$FREIGABEN/$DATENSATZ" ]; then
    sage "Datensatz '$DATENSATZ' freigegeben" "ja"
    echo "      $(head -1 "$FREIGABEN/$DATENSATZ")"
else
    sage "Datensatz '$DATENSATZ' freigegeben" "NEIN -- ABBRUCH"
    echo
    echo "  Es gibt keine Freigabe unter $FREIGABEN/$DATENSATZ."
    echo "  Ein QC-HTML enthaelt Hirnschnitte in voller Aufloesung. Ohne"
    echo "  ausdrueckliche Freigabe geht es nirgendwohin."
    echo
    echo "  Freigegeben sind bisher:"
    ls "$FREIGABEN" 2>/dev/null | sed 's/^/    /' || echo "    (keine)"
    echo
    echo "  Eine Freigabe legt ein Mensch an, mit Begruendung:"
    echo "    echo 'WMH Segmentation Challenge, oeffentlich unter wmh.isi.uu.nl' \\"
    echo "      > $FREIGABEN/<kennung>"
    exit 1
fi

# 2. Datei da und lesbar
[ -f "$QC" ] && sage "Datei vorhanden" "$(du -h "$QC" | cut -f1)" || { sage "Datei vorhanden" "NEIN"; fehler=1; }

# 3. Offline-tauglich
# grep -c gibt bei null Treffern "0" aus UND liefert 1 zurueck; ein
# "|| echo 0" haengt dann eine zweite Null an. Deshalb -o und wc -l.
n=$(grep -oE 'src="https?://|href="https?://|@import[[:space:]]+url\(https?' "$QC" 2>/dev/null | wc -l)
[ "$n" -eq 0 ] && sage "keine externen Verweise" "ja" || { sage "keine externen Verweise" "$n gefunden -- ABBRUCH"; fehler=1; }

# 4. Groesse
b=$(stat -c%s "$QC"); mb=$((b/1048576))
[ "$mb" -lt 50 ] && sage "unter 50 MB" "${mb} MB" || { sage "unter 50 MB" "${mb} MB -- zu gross"; fehler=1; }

# 5. Enthaelt es ueberhaupt Bilder
i=$(grep -o 'data:image/[a-z]*;base64' "$QC" | wc -l)
sage "eingebettete Bilder" "$i"

[ "$fehler" -eq 0 ] || { echo; echo "  Pruefung fehlgeschlagen, nichts veroeffentlicht."; exit 1; }
[ "$NUR_PRUEFEN" -eq 1 ] && { echo; echo "  Alle Pruefungen bestanden. Ohne --pruefen wuerde jetzt veroeffentlicht."; exit 0; }

# ---------------------------------------------------------------- bauen
REPO="qc-$PROJEKT"
ARB=$L/repos/$REPO
echo
echo "── Repo bauen: $REPO ──"
rm -rf "$ARB"; mkdir -p "$ARB"
cp "$QC" "$ARB/index.html"

# Kennzahlen aus dem Projektverzeichnis, falls vorhanden
QD=$(dirname "$QC")
ZAHLEN=""
[ -f "$QD/ergebnisse.csv" ] && ZAHLEN=$(/home/uchralt/miniconda3/envs/dl/bin/python - "$QD/ergebnisse.csv" <<'PY'
import csv, statistics as st, sys
r=list(csv.DictReader(open(sys.argv[1])))
if not r or 'dice' not in r[0]: raise SystemExit
d=[float(x['dice']) for x in r]
print(f"| Faelle / cases | {len(r)} |")
print(f"| Dice (Mittel / mean) | {st.mean(d):.4f} |")
print(f"| Dice (Median) | {st.median(d):.4f} |")
print(f"| Dice (Spanne / range) | {min(d):.4f} – {max(d):.4f} |")
for k,n in (('sensitivitaet','Sensitivitaet / sensitivity'),('praezision','Praezision / precision')):
    if k in r[0]: print(f"| {n} | {st.mean([float(x[k]) for x in r]):.4f} |")
PY
)

cat > "$ARB/README.md" <<README
# ${PROJEKT} — quality control

Eine einzelne HTML-Seite mit den Schnittbildern und Overlays eines
Segmentierungslaufs. **Sie laedt nichts aus dem Netz** — alle Bilder sind als
base64 eingebettet. Herunterladen und im Browser oeffnen genuegt, auch auf
einem Rechner ohne Internet.

*A single HTML page with slice images and overlays from a segmentation run.
**It loads nothing from the network** — every image is embedded as base64.
Download it and open it in a browser; no internet required.*

**→ [index.html](index.html)**

## Datensatz / dataset

\`${DATENSATZ}\` — $(head -1 "$FREIGABEN/$DATENSATZ")

## Ergebnis / result

| | |
|---|---|
${ZAHLEN:-| — | — |}

## Wie die Seite entstanden ist / how it was made

Erzeugt von einem lokalen Agenten auf einer Workstation ohne Netzzugang zu den
Daten. Aufbau, Werkzeuge und Messwerte des Systems:
[mendeltem/local_models → alita](https://github.com/mendeltem/local_models/tree/main/alita)

*Produced by a local agent on a workstation with no network access to the data.
System, tools and measurements: see the link above.*

## Was hier nicht liegt / what is not here

Keine Bilddaten ausserhalb dieser einen Seite, keine Modellgewichte, keine
Rohdaten. Die Seite zeigt ausschliesslich einen oeffentlich freigegebenen
Datensatz.

*No image data beyond this single page, no model weights, no raw data. The page
shows an explicitly released public dataset only.*
README

cat > "$ARB/.gitignore" <<'EOF'
*.nii
*.nii.gz
*.pt
*.pth
*.gguf
*.dcm
EOF

echo "  index.html  $(du -h "$ARB/index.html" | cut -f1)"
echo "  README.md   $(wc -l < "$ARB/README.md") Zeilen"

# ---------------------------------------------------------------- anlegen
echo
echo "── anlegen und pushen ──"
export PATH="$HOME/.local/bin:$PATH"
cd "$ARB"
git init -q -b main && git add -A
git -c user.name=mendeltem -c user.email=mendeltem@googlemail.com \
    commit -q -m "$PROJEKT: QC als eine Seite, ohne externe Verweise

Datensatz: $DATENSATZ
$(head -1 "$FREIGABEN/$DATENSATZ")

Erzeugt von einem lokalen Agenten. Aufbau des Systems:
github.com/mendeltem/local_models/tree/main/alita"

if gh repo view "mendeltem/$REPO" >/dev/null 2>&1; then
    echo "  Repo besteht schon, pushe hinein"
    git remote add origin "git@github.com:mendeltem/$REPO.git" 2>/dev/null
    git push -qf origin main
else
    gh repo create "$REPO" --public --source=. --remote=origin --push \
       --description "QC page for $PROJEKT — self-contained, no external requests" \
       >/dev/null 2>&1 && echo "  angelegt und gepusht"
fi

sleep 2
gh api -X POST "repos/mendeltem/$REPO/pages" -f "source[branch]=main" -f "source[path]=/" >/dev/null 2>&1 \
  && echo "  Pages eingeschaltet" || echo "  Pages: schon aktiv oder nicht setzbar"
echo
echo "  Repo:  https://github.com/mendeltem/$REPO"
echo "  Seite: https://mendeltem.github.io/$REPO/"
