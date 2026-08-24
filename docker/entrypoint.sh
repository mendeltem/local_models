#!/bin/sh
# Vermisst die GPU des Hosts und startet llama-server passend dazu.
# Genau das macht das Image portabel: dieselbe Zeile ergibt auf einer 4090
# -ncmoe 0 und auf einer 3060 etwa -ncmoe 25.
set -e

MODEL="${LOK_MODEL_PATH:-/models/model.gguf}"
if [ ! -f "$MODEL" ]; then
    echo "Kein Modell unter $MODEL. Volume mounten:" >&2
    echo "  docker run -v /pfad/zu/models:/models ..." >&2
    exit 2
fi

if [ "$#" -gt 0 ]; then
    exec llama-server -m "$MODEL" "$@"      # explizite Argumente gewinnen
fi

ARGS=$(python3 /app/detect.py "$MODEL" -c "${LOK_CTX:-16384}" \
       --port "${LOK_PORT:-8080}" --print-args)
echo "detect.py: llama-server $ARGS"
exec llama-server $ARGS
