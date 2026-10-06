#!/usr/bin/env bash
# Sauberer Vergleich: nichts anderes auf Ollama, ein Modell nach dem anderen.
cd "$(dirname "$0")"
touch ~/.schicht/pause
trap 'rm -f ~/.schicht/pause; echo "pause aufgehoben $(date +%H:%M)"' EXIT
while pgrep -f '^opencode run' >/dev/null; do sleep 30; done
echo "Ollama frei $(date +%H:%M)"
for m in qwen3.5:9b qwen3.5-9b-32k qwen3.6-64k; do ollama stop "$m" 2>/dev/null; done
python3 -u alltag.py --modell qwen3.6-64k
ollama stop qwen3.6-64k
python3 -u alltag.py --modell qwen3.5-9b-32k --ohne-denken
python3 -u alltag.py --modell qwen3.5-9b-32k
ollama ps
echo "fertig $(date +%H:%M)"
