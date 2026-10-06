#!/usr/bin/env bash
# Vergleichslauf: Qwen3.6 mit Denken, dann Qwen3.5-9B ohne/mit Denken. Schicht pausiert solange.
cd "$(dirname "$0")"
touch ~/.schicht/pause
trap 'rm -f ~/.schicht/pause; echo "pause aufgehoben $(date +%H:%M)"' EXIT
python3 alltag.py --modell qwen3.6-64k
ollama pull qwen3.5:9b >/dev/null 2>&1 || { echo "Download qwen3.5:9b gescheitert"; exit 1; }
ollama stop qwen3.6-64k
python3 alltag.py --modell qwen3.5:9b --ohne-denken
python3 alltag.py --modell qwen3.5:9b
ollama ps
echo "fertig $(date +%H:%M)"
