"""Kopiert den vollstaendigen Bestand von der Freigabe auf den Stick.

Kopiert wird nach <name>.laedt und erst nach bestandener Groessenpruefung
umbenannt. Eine abgebrochene Kopie sieht damit nie wie eine fertige Datei aus.

Die sieben Modelldateien werden zusaetzlich **vom Stick zurueckgelesen** und
gegen die von Hugging Face veroeffentlichte sha256 gehalten. Das prueft den
Schreibvorgang auf den Stick, nicht nur die Quelle -- die Strecke, die sonst
niemand kontrolliert.

Am Ende entsteht PRUEFSUMMEN.txt, das genau den Stickinhalt beschreibt.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time

QUELLE = "S:/AG/AG-CSB_NeuroRad/temuuleu/download/offline-bundle"
ZIEL = "E:/offline-bundle"

# Die vom Anbieter veroeffentlichten Summen. Nur diese Dateien werden
# zurueckgelesen -- bei 60 GB waere alles zu lesen zu teuer.
ORIGINAL = {
 "01-watcher/modelle/qwen2.5-0.5b-instruct-q8_0.gguf":
   "ca59ca7f13d0e15a8cfa77bd17e65d24f6844b554a7b6c12e07a5f89ff76844e",
 "01-watcher/modelle/qwen2.5-0.5b-instruct-q4_k_m.gguf":
   "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
 "02-encoder/modernbert-base/model.safetensors":
   "340ac08b74eef0d7bdec2d7981a6a3d4249bf0e6aab60634b72ad02c2b8023a9",
 "02-encoder/distilbert-base-multilingual-cased/model.safetensors":
   "fcf002be901b9ad708e0df430b8d18deaa4b3fe3519e24e9017a5ee17ca2c228",
 "07-experimentelle-modelle/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf":
   "fadc3e5f8d42bf7e894a785b05082e47daee4df26680389817e2093056f088ad",
 "07-experimentelle-modelle/medgemma-27b-text-it-Q4_K_M.gguf":
   "383b1c414d3f2f1a9c577a61e623d29a4ed4f7834f60b9e5412f5ff4e8aaf080",
 "07-experimentelle-modelle/medgemma-4b-it-Q4_K_M.gguf":
   "d842e8d2aca3fc5e613c5f9255e693768eeccae729e5c2653159eb79afe751f3",
 "07-experimentelle-modelle/Qwen3-1.7B-Q8_0.gguf":
   "0becaa825564295d82e9af4d008bca5f8b7f5f73bf1c6a0b58f7c53ef26b47fd",
 "07-experimentelle-modelle/Qwen3-4B-Instruct-2507-Q4_K_M.gguf":
   "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597",
 "07-experimentelle-modelle/Llama-3.1-8B-Instruct-Q4_K_M.gguf":
   "b3bdbf23b47d7e6bb791c99b206deb169cd5a96362a9e3399028df2faacdc506",
}


def sha256(pfad: str, block: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        while stueck := f.read(block):
            h.update(stueck)
    return h.hexdigest()


def main() -> int:
    posten = []
    for wurzel, _, dateien in os.walk(QUELLE):
        for d in dateien:
            if d.endswith(".laedt"):
                continue
            p = os.path.join(wurzel, d)
            posten.append((os.path.relpath(p, QUELLE).replace("\\", "/"),
                           os.path.getsize(p)))
    posten.sort(key=lambda t: t[1])          # klein zuerst: schnelle Fortschritte
    gesamt = sum(g for _, g in posten)

    frei = shutil.disk_usage("E:/").free
    print(f"=== {len(posten)} Dateien, {gesamt/1e9:.2f} GB ===")
    print(f"    Stick frei: {frei/1e9:.2f} GB")
    if gesamt > frei:
        print("    passt nicht -- Abbruch.")
        return 1
    print()

    ok = da = fehler = 0
    kopiert_bytes = 0
    t_start = time.time()

    for rel, soll in posten:
        q = os.path.join(QUELLE, rel)
        z = os.path.join(ZIEL, rel)
        os.makedirs(os.path.dirname(z), exist_ok=True)

        if os.path.exists(z) and os.path.getsize(z) == soll:
            da += 1
            continue

        t0 = time.time()
        try:
            shutil.copyfile(q, z + ".laedt")
        except OSError as e:
            print(f"  FEHL  {rel}: {e}", flush=True)
            fehler += 1
            continue
        dt = max(time.time() - t0, 0.001)

        ist = os.path.getsize(z + ".laedt")
        if ist != soll:
            print(f"  FEHL  {rel}  {ist} statt {soll} B", flush=True)
            os.remove(z + ".laedt")
            fehler += 1
            continue

        marke = ""
        if rel in ORIGINAL:
            h = sha256(z + ".laedt")
            if h != ORIGINAL[rel]:
                print(f"  ABWEICHUNG  {rel}", flush=True)
                print(f"    Original {ORIGINAL[rel]}")
                print(f"    Stick    {h}")
                os.remove(z + ".laedt")
                fehler += 1
                continue
            marke = "  sha256 gegen das Original bestaetigt"

        os.replace(z + ".laedt", z)
        ok += 1
        kopiert_bytes += soll
        if soll > 400_000_000:
            anteil = 100 * kopiert_bytes / gesamt
            print(f"  ok  {rel}  {soll/1e9:.2f} GB  {soll/dt/1e6:.0f} MB/s"
                  f"  [{anteil:.0f} %]{marke}", flush=True)

    dauer = (time.time() - t_start) / 60
    print()
    print(f"=== {ok} kopiert, {da} schon da, {fehler} fehlgeschlagen "
          f"in {dauer:.1f} min ===")

    # --- PRUEFSUMMEN.txt fuer genau diesen Stickinhalt ---
    print("  schreibe PRUEFSUMMEN.txt ...", flush=True)
    zeilen, inv = [], []
    for wurzel, _, dateien in os.walk(ZIEL):
        for d in dateien:
            if d in ("PRUEFSUMMEN.txt", "INVENTAR.txt") or d.endswith(".laedt"):
                continue
            p = os.path.join(wurzel, d)
            rel = os.path.relpath(p, ZIEL).replace("\\", "/")
            gr = os.path.getsize(p)
            h = ORIGINAL.get(rel) or sha256(p)
            zeilen.append(f"{h}  {gr}  ./{rel}")
            inv.append(f"{gr}\t{rel}")
    open(os.path.join(ZIEL, "PRUEFSUMMEN.txt"), "w", encoding="utf-8",
         newline="\n").write("\n".join(sorted(zeilen)) + "\n")
    open(os.path.join(ZIEL, "INVENTAR.txt"), "w", encoding="utf-8",
         newline="\n").write("\n".join(sorted(inv, key=lambda x: x.split("\t")[1])) + "\n")
    print(f"  PRUEFSUMMEN.txt: {len(zeilen)} Eintraege")

    frei = shutil.disk_usage("E:/").free
    belegt = sum(g for _, g in posten)
    print(f"  Stick: {belegt/1e9:.2f} GB belegt, {frei/1e9:.2f} GB frei")
    print()
    print("FERTIG." if not fehler else f"MIT {fehler} FEHLERN BEENDET.")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
