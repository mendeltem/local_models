#!/bin/bash
# ---------------------------------------------------------------------------
# alles-laden.sh — holt den Offline-Bestand fuer Alita-MS-7D91.
#
#     bash alles-laden.sh bericht        # NUR zeigen, was fehlt. Laedt nichts.
#     bash alles-laden.sh                # alles Fehlende holen
#     bash alles-laden.sh modelle        # nur einen Abschnitt
#
# Abschnitte: waechter encoder microbleed msd eeg modelle segmentierer wmh
#             bericht pruefen
#
# Zwei Dinge, die dieses Skript von einer Liste von curl-Aufrufen unterscheiden:
#
#   1. Es kennt die erwartete Groesse jeder Datei. Damit unterscheidet es eine
#      halb geladene von einer vollstaendigen — eine halbe GGUF sieht aus wie
#      ein Modell und ist keins.
#   2. Es kann aus einem bereits vorhandenen Bestand uebernehmen statt neu zu
#      laden. Wer schon Daten auf einen Stick kopiert hat, setzt VORHANDEN:
#
#          VORHANDEN=/media/uchralt/QWEN/offline-bundle bash alles-laden.sh
#
#      Dann wird kopiert und die Groesse geprueft, statt die Leitung zu
#      belasten.
# ---------------------------------------------------------------------------

set -u   # NICHT set -e: ein gescheiterter Posten soll die anderen nicht mitreissen.

HIER="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
ZIEL="${ZIEL:-$HIER/offline-bundle}"
VORHANDEN="${VORHANDEN:-}"   # erreichbarer Bestand, aus dem kopiert werden kann
BEKANNT="${BEKANNT:-}"       # INVENTAR.txt eines NICHT erreichbaren Bestands.
                             # Der Server sieht den USB-Stick nicht — wohl aber
                             # diese Liste, wenn sie auf der Freigabe liegt.
                             # Damit wird nicht geladen, was dort schon liegt.

PROXY_URL="${PROXY_URL:-http://proxy.charite.de:8080}"
if [ -n "$PROXY_URL" ]; then
  export http_proxy="$PROXY_URL" https_proxy="$PROXY_URL"
  export HTTP_PROXY="$PROXY_URL" HTTPS_PROXY="$PROXY_URL"
fi

HF=https://huggingface.co
MZ=https://github.com/Project-MONAI/model-zoo/releases/download/hosting_storage_v1
TUB=http://doc.ml.tu-berlin.de/simultaneous_EEG_NIRS

# ---------------------------------------------------------------------------
# Der Bestand: relativer Pfad | erwartete Bytes | URL
#
# Groesse 0 heisst "unbekannt" — dann kann nur auf Vorhandensein geprueft
# werden, nicht auf Vollstaendigkeit.
# ---------------------------------------------------------------------------
bestand() {
cat <<TABELLE
waechter|01-watcher/modelle/qwen2.5-0.5b-instruct-q8_0.gguf|675710816|$HF/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q8_0.gguf
waechter|01-watcher/modelle/qwen2.5-0.5b-instruct-q4_k_m.gguf|491400032|$HF/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf
encoder|02-encoder/modernbert-base/model.safetensors|598635032|$HF/answerdotai/ModernBERT-base/resolve/main/model.safetensors
encoder|02-encoder/modernbert-base/config.json|1193|$HF/answerdotai/ModernBERT-base/resolve/main/config.json
encoder|02-encoder/modernbert-base/tokenizer.json|2132967|$HF/answerdotai/ModernBERT-base/resolve/main/tokenizer.json
encoder|02-encoder/modernbert-base/tokenizer_config.json|20810|$HF/answerdotai/ModernBERT-base/resolve/main/tokenizer_config.json
encoder|02-encoder/modernbert-base/special_tokens_map.json|694|$HF/answerdotai/ModernBERT-base/resolve/main/special_tokens_map.json
encoder|02-encoder/modernbert-base/README.md|8427|$HF/answerdotai/ModernBERT-base/resolve/main/README.md
encoder|02-encoder/distilbert-base-multilingual-cased/model.safetensors|541795680|$HF/distilbert/distilbert-base-multilingual-cased/resolve/main/model.safetensors
encoder|02-encoder/distilbert-base-multilingual-cased/config.json|466|$HF/distilbert/distilbert-base-multilingual-cased/resolve/main/config.json
encoder|02-encoder/distilbert-base-multilingual-cased/tokenizer.json|1961828|$HF/distilbert/distilbert-base-multilingual-cased/resolve/main/tokenizer.json
encoder|02-encoder/distilbert-base-multilingual-cased/tokenizer_config.json|49|$HF/distilbert/distilbert-base-multilingual-cased/resolve/main/tokenizer_config.json
encoder|02-encoder/distilbert-base-multilingual-cased/vocab.txt|995526|$HF/distilbert/distilbert-base-multilingual-cased/resolve/main/vocab.txt
encoder|02-encoder/distilbert-base-multilingual-cased/README.md|7316|$HF/distilbert/distilbert-base-multilingual-cased/resolve/main/README.md
msd|04-msd-task04/Task04_Hippocampus.tar|28425216|https://msd-for-monai.s3-us-west-2.amazonaws.com/Task04_Hippocampus.tar
eeg|06-eeg-fnirs-dot/shin2018-eeg-nirs/EEG_01-26_MATLAB.zip|6091239135|$TUB/EEG/EEG_01-26_MATLAB.zip
eeg|06-eeg-fnirs-dot/shin2018-eeg-nirs/NIRS_01-26_MATLAB.zip|797840805|$TUB/NIRS/NIRS_01-26_MATLAB.zip
eeg|06-eeg-fnirs-dot/shin2018-eeg-nirs/behavior.zip|234292|$TUB/behavior.zip
eeg|06-eeg-fnirs-dot/neurodot/NeuroDOT-master.tar.gz|852435603|https://github.com/WUSTL-ORL/NeuroDOT/archive/refs/heads/master.tar.gz
eeg|06-eeg-fnirs-dot/mne-fnirs-motor/MNE-fNIRS-motor-data.zip|17881709|https://osf.io/dj3eh/download
modelle|07-experimentelle-modelle/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf|18556689568|$HF/unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF/resolve/main/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf
modelle|07-experimentelle-modelle/medgemma-4b-it-Q4_K_M.gguf|2489894720|$HF/unsloth/medgemma-4b-it-GGUF/resolve/main/medgemma-4b-it-Q4_K_M.gguf
modelle|07-experimentelle-modelle/medgemma-27b-text-it-Q4_K_M.gguf|16546405376|$HF/unsloth/medgemma-27b-text-it-GGUF/resolve/main/medgemma-27b-text-it-Q4_K_M.gguf
segmentierer|10-vortrainierte-segmentierer/model_swinvit.pt|411162269|https://github.com/Project-MONAI/MONAI-extra-test-data/releases/download/0.8.1/model_swinvit.pt
segmentierer|10-vortrainierte-segmentierer/swin_unetr_btcv_segmentation_v0.1.0.zip|230907836|$MZ/swin_unetr_btcv_segmentation_v0.1.0.zip
segmentierer|10-vortrainierte-segmentierer/brats_mri_segmentation_v0.1.0.zip|35075834|$MZ/brats_mri_segmentation_v0.1.0.zip
isles|09-isles2022/ISLES-2022.zip|1690000000|https://zenodo.org/records/7960856/files/ISLES-2022.zip?download=1
TABELLE
}

# EEGMMIDB nur auf Wunsch: 3,4 GB, ueber den Charite-Proxy nur ~0,12 MB/s
# gemessen — das sind mehrere Stunden. MIT_EEGMMIDB=1 schaltet es ein.
bestand_optional() {
  [ "${MIT_EEGMMIDB:-0}" = "1" ] || return 0
  echo "eeg|06-eeg-fnirs-dot/physionet-eegmmidb/eeg-motor-movementimagery-1.0.0.zip|1997435063|https://physionet.org/static/published-projects/eegmmidb/eeg-motor-movementimagery-dataset-1.0.0.zip"
}

alle_zeilen() { bestand; bestand_optional; }

# ---------------------------------------------------------------------------
# zustand <zielpfad> <soll> -> "fertig" | "teil" | "fehlt"
#
# Toleranz von 1 %, weil einige Sollgroessen aus der API gerundet sind.
# ---------------------------------------------------------------------------
zustand() {
  local p="$1" soll="$2" ist
  # Eine Datei traegt ihren richtigen Namen erst, wenn sie vollstaendig ist.
  # Solange geladen wird, heisst sie <name>.laedt. Damit kann keine halbe
  # Datei als fertig durchgehen — auch nicht fuer eine andere Maschine, die
  # nur ins Verzeichnis schaut.
  if [ ! -f "$p" ]; then
    [ -f "$p.laedt" ] && { echo teil; return; }
    echo fehlt; return
  fi
  ist=$(stat -c%s "$p" 2>/dev/null || echo 0)
  if [ "$soll" -le 0 ]; then
    [ "$ist" -gt 0 ] && echo fertig || echo fehlt
  elif [ "$ist" -ge $((soll - soll / 100)) ]; then
    echo fertig
  else
    echo teil
  fi
}

menschlich() { numfmt --to=iec --suffix=B "$1" 2>/dev/null || echo "$1 B"; }

# ist_bytes <pfad> — Groesse der Datei oder ihrer .laedt-Fassung, 0 wenn weg.
ist_bytes() {
  stat -c%s "$1" 2>/dev/null || stat -c%s "$1.laedt" 2>/dev/null || echo 0
}

# schon_anderswo <relpfad> <soll>
# Wahr, wenn die Datei laut INVENTAR.txt in einem anderen Bestand vollstaendig
# vorliegt. INVENTAR.txt ist "bytes<TAB>relpfad", erzeugt vom Abschnitt pruefen.
schon_anderswo() {
  local rel="$1" soll="$2"
  [ -n "$BEKANNT" ] && [ -f "$BEKANNT" ] || return 1
  awk -F'	' -v p="$rel" -v s="$soll" \
    '$2==p { if (s<=0 ? $1>0 : $1>=s-s/100) gefunden=1 } END{ exit !gefunden }' "$BEKANNT"
}

# ---------------------------------------------------------------------------
hartnaeckig() {
  local url="$1" ziel="$2" max="${3:-40}" i=0 bisher roh="$2.laedt"
  mkdir -p "$(dirname "$ziel")"
  while [ "$i" -lt "$max" ]; do
    i=$((i + 1))
    # -C -                       setzt an der Abbruchstelle wieder auf
    # --retry-all-errors         wiederholt auch bei 5xx (HF liefert sporadisch 503)
    # --speed-limit/--speed-time bricht ab, wenn 60 s lang unter 10 KB/s.
    #                            Ohne das haengt ein toter Download stundenlang,
    #                            ohne dass es jemand merkt.
    if curl -sSL --fail --retry 5 --retry-all-errors --retry-delay 5 \
            --speed-limit 10240 --speed-time 60 -C - -o "$roh" "$url"; then
      # Erst jetzt den richtigen Namen vergeben. mv innerhalb desselben
      # Dateisystems ist atomar — es gibt keinen Moment, in dem die Datei
      # unter ihrem echten Namen unvollstaendig existiert.
      mv -f "$roh" "$ziel" || { echo "  FEHL Umbenennen von $roh"; return 1; }
      printf '  ok    %-50s %s\n' "$(basename "$ziel")" "$(menschlich "$(stat -c%s "$ziel")")"
      return 0
    fi
    bisher=$(stat -c%s "$roh" 2>/dev/null || echo 0)
    printf '  ...   Versuch %d abgebrochen bei %s, setze wieder auf\n' "$i" "$(menschlich "$bisher")"
    sleep 5
  done
  printf '  FEHL  %s nach %d Versuchen\n' "$(basename "$ziel")" "$max"
  return 1
}

# hole <relpfad> <soll> <url>
hole() {
  local rel="$1" soll="$2" url="$3" ziel="$ZIEL/$1" z
  z=$(zustand "$ziel" "$soll")

  if [ "$z" = fertig ]; then
    printf '  --    %-50s schon vollstaendig\n' "$(basename "$rel")"
    return 0
  fi

  if schon_anderswo "$rel" "$soll"; then
    printf '  ueb   %-50s liegt schon im anderen Bestand
' "$(basename "$rel")"
    return 0
  fi

  # Aus einem vorhandenen Bestand uebernehmen, statt die Leitung zu belasten.
  if [ -n "$VORHANDEN" ] && [ -f "$VORHANDEN/$rel" ] \
     && [ "$(zustand "$VORHANDEN/$rel" "$soll")" = fertig ]; then
    mkdir -p "$(dirname "$ziel")"
    if cp "$VORHANDEN/$rel" "$ziel" && [ "$(zustand "$ziel" "$soll")" = fertig ]; then
      printf '  kop   %-50s aus vorhandenem Bestand\n' "$(basename "$rel")"
      return 0
    fi
    printf '  FEHL  Kopie von %s unvollstaendig, lade neu\n' "$(basename "$rel")"
  fi

  [ "$z" = teil ] && printf '  ...   %-50s unvollstaendig, setze auf\n' "$(basename "$rel")"
  hartnaeckig "$url" "$ziel"
}

abschnitt() { printf '\n=== %s ===\n' "$1"; }

# ---------------------------------------------------------------------------
lade_abschnitt() {
  local wunsch="$1" gefunden=0 gruppe rel soll url
  while IFS='|' read -r gruppe rel soll url; do
    [ "$gruppe" = "$wunsch" ] || continue
    [ "$gefunden" -eq 0 ] && { abschnitt "$wunsch"; gefunden=1; }
    hole "$rel" "$soll" "$url"
  done < <(alle_zeilen)
}

lade_microbleed() {
  abschnitt "microbleed — vortrainierte Gewichte (Google Drive)"
  local d="$ZIEL/03-microbleednet-modelle"
  # Vier Dateien, zusammen 46 MB. Wenn sie da sind, nichts tun.
  if [ "$(ls -1 "$d"/*.pth 2>/dev/null | wc -l)" -ge 4 ]; then
    echo "  --    4 Gewichtsdateien schon vorhanden"; return 0
  fi
  if schon_anderswo "03-microbleednet-modelle/Microbleednet_cdet_model.pth" 13760347; then
    echo "  ueb   liegt schon im anderen Bestand"; return 0
  fi
  if [ -n "$VORHANDEN" ] && [ -d "$VORHANDEN/03-microbleednet-modelle" ]; then
    mkdir -p "$d" && cp "$VORHANDEN/03-microbleednet-modelle"/*.pth "$d"/ 2>/dev/null \
      && { echo "  kop   aus vorhandenem Bestand"; return 0; }
  fi
  # Google Drive braucht ein Bestaetigungstoken fuer grosse Dateien — curl reicht nicht.
  python -m pip install --quiet ${PROXY_URL:+--proxy "$PROXY_URL"} gdown || {
    echo "  FEHL  gdown liess sich nicht installieren"; return 1; }
  mkdir -p "$d"
  # Laut README: Dateien NICHT umbenennen, alle in EIN Verzeichnis.
  python -m gdown --folder \
    "https://drive.google.com/drive/folders/1pqTFbvPVANFngMx0Z6Z352k0xPIMa9JA" -O "$d"
}

lade_wmh() {
  abschnitt "wmh — Zweitbefunder der Challenge (DataverseNL)"
  local d="$ZIEL/08-wmh-zweitbefunder"
  if [ "$(find "$d" -name result.nii.gz 2>/dev/null | wc -l)" -ge 120 ]; then
    echo "  --    120 Zusatzannotationen schon vorhanden"; return 0
  fi
  if schon_anderswo "08-wmh-zweitbefunder/additional_annotations/observer_o3/training/Utrecht/2/result.nii.gz" 0; then
    echo "  ueb   liegt schon im anderen Bestand"; return 0
  fi
  if [ -n "$VORHANDEN" ] && \
     [ "$(find "$VORHANDEN/08-wmh-zweitbefunder" -name result.nii.gz 2>/dev/null | wc -l)" -ge 120 ]; then
    mkdir -p "$d" && cp -r "$VORHANDEN/08-wmh-zweitbefunder/." "$d"/ \
      && { echo "  kop   aus vorhandenem Bestand"; return 0; }
  fi
  mkdir -p "$d"
  # Der Gesamtsatz ist 8,76 GB und liegt schon auf der Zielmaschine. Gebraucht
  # werden nur die 120 Dateien der beiden Zweitbefunder (1,7 MB): damit laesst
  # sich rechnen, wie einig sich zwei Menschen sind — die Obergrenze fuer jedes
  # Modell.
  curl -sSL --fail -m 120 \
    "https://dataverse.nl/api/datasets/:persistentId/?persistentId=doi:10.34894/AECRSD" \
    -o "$d/wmh_meta.json" || { echo "  FEHL  Metadaten nicht erreichbar"; return 1; }
  python - "$d" <<'PYTHON'
import json, os, sys, urllib.request
d = sys.argv[1]
proxy = os.environ.get("https_proxy") or os.environ.get("http_proxy")
op = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {}))
meta = json.load(open(os.path.join(d, "wmh_meta.json"), encoding="utf-8"))
ziel = [f for f in meta["data"]["latestVersion"]["files"]
        if (f.get("directoryLabel") or "").startswith("additional_annotations")]
ok = 0
for f in ziel:
    rel = (f.get("directoryLabel") or "") + "/" + f["dataFile"]["filename"]
    pfad = os.path.join(d, *rel.split("/"))
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    if os.path.exists(pfad) and os.path.getsize(pfad) == f["dataFile"]["filesize"]:
        ok += 1; continue
    try:
        with op.open("https://dataverse.nl/api/access/datafile/%d" % f["dataFile"]["id"],
                     timeout=90) as a:
            open(pfad, "wb").write(a.read())
        ok += 1
    except Exception as e:
        print("  FEHL", rel, e)
print("  ok    %d/%d Zusatzannotationen" % (ok, len(ziel)))
PYTHON
}

# ---------------------------------------------------------------------------
bericht() {
  abschnitt "Bericht — was fehlt, was ist da (es wird nichts geladen)"
  local gruppe rel soll url z fehlt=0 offen=0 anderswo=0
  printf '  %-8s %-52s %10s  %s\n' ZUSTAND DATEI SOLL IST
  while IFS='|' read -r gruppe rel soll url; do
    z=$(zustand "$ZIEL/$rel" "$soll")
    # Was in einem anderen Bestand vollstaendig vorliegt, ist nicht "fehlt".
    if [ "$z" != fertig ] && schon_anderswo "$rel" "$soll"; then
      anderswo=$((anderswo + 1))
      printf '  %-8s %-52s %10s  %s
' anderswo "${rel:0:52}" "$(menschlich "$soll")" "-"
      continue
    fi
    case "$z" in
      fertig) continue ;;
      teil)   offen=$((offen + soll - $(ist_bytes "$ZIEL/$rel"))) ;;
      fehlt)  fehlt=$((fehlt + 1)); offen=$((offen + soll)) ;;
    esac
    printf '  %-8s %-52s %10s  %s\n' "$z" "${rel:0:52}" \
      "$(menschlich "$soll")" \
      "$(b=$(ist_bytes "$ZIEL/$rel"); [ "$b" -gt 0 ] && menschlich "$b" || echo -)"
  done < <(alle_zeilen)
  if [ "$anderswo" -gt 0 ]; then
    printf '
  %d Posten liegen im anderen Bestand und werden nicht geladen.
' "$anderswo"
  fi
  printf '\n  Noch zu laden: %s\n' "$(menschlich "$offen")"
  printf '  Frei auf %s: %s\n' "$ZIEL" "$(df -h "$ZIEL" 2>/dev/null | tail -1 | awk '{print $4}')"
}

pruefen() {
  abschnitt "Pruefsummen erzeugen"
  # Der Stick hat einen Health-Warning und hat schon einmal Daten verloren.
  # Ohne Pruefsummen ist jede Annahme ueber Dateiinhalte wertlos.
  ( cd "$ZIEL" && find . -type f ! -name PRUEFSUMMEN.txt ! -name INVENTAR.txt ! -name '*.laedt' -print0 \
      | xargs -0 sha256sum > PRUEFSUMMEN.txt )
  # INVENTAR.txt ist die Liste, die eine ANDERE Maschine lesen kann, um zu
  # wissen, was hier liegt — auch wenn sie diesen Datentraeger nicht sieht.
  ( cd "$ZIEL" && find . -type f ! -name PRUEFSUMMEN.txt ! -name INVENTAR.txt ! -name '*.laedt' \
      -printf '%s	%P
' | sort -k2 > INVENTAR.txt )
  echo "  INVENTAR.txt geschrieben — auf die Freigabe legen, dort dann"
  echo "  BEKANNT=/pfad/INVENTAR.txt bash alles-laden.sh"
  printf '  %s Dateien, %s\n' \
    "$(wc -l < "$ZIEL/PRUEFSUMMEN.txt")" "$(du -sh "$ZIEL" | cut -f1)"
  echo "  Spaeter pruefen mit:  cd $ZIEL && sha256sum -c PRUEFSUMMEN.txt"
}

# Wird dieses Skript mit NUR_FUNKTIONEN=1 gesourct, endet es hier und
# stellt nur seine Funktionen und die Bestandstabelle bereit. So kann
# rest_download.sh dieselbe Tabelle benutzen, statt sie zu verdoppeln.
[ "${NUR_FUNKTIONEN:-0}" = "1" ] && return 0

# --- Ablauf ---------------------------------------------------------------
mkdir -p "$ZIEL"
[ -n "$VORHANDEN" ] && echo "Vorhandener Bestand: $VORHANDEN"
for a in ${*:-waechter encoder microbleed msd eeg modelle segmentierer isles wmh bericht pruefen}; do
  case "$a" in
    waechter|encoder|msd|eeg|modelle|segmentierer|isles) lade_abschnitt "$a" ;;
    microbleed) lade_microbleed ;;
    wmh)        lade_wmh ;;
    bericht)    bericht ;;
    pruefen)    pruefen ;;
    *)          echo "Unbekannter Abschnitt: $a" ;;
  esac
done

abschnitt "Fertig"
df -h "$ZIEL" | tail -1
