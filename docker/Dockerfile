# Portables Image: llama-server + lok, ohne Modell.
# Das Modell wird als Volume gemountet - ein 18-GB-Layer im Image waere unbrauchbar.
#
# Basis ist das offizielle llama.cpp-Server-Image. Fuer CUDA 12 statt 13:
#   ghcr.io/ggml-org/llama.cpp:server-cuda
FROM ghcr.io/ggml-org/llama.cpp:server-cuda13

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-minimal \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY tools/lok.py tools/detect.py /app/
COPY docker/entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

ENV LOK_MODEL_PATH=/models/model.gguf \
    LOK_CTX=16384 \
    LOK_PORT=8080 \
    LOK_URL=http://127.0.0.1:8080/v1

EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
