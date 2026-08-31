"""Kopiert nur das Neue von der Freigabe auf den Stick.

Alita hat den Bestand vom Vormittag bereits uebernommen. Neu seit 13:30 sind
die Wheels und drei kleine Sprachmodelle -- zusammen 9,8 GB statt 60.

Kopiert wird nach <name>.laedt und erst nach bestandener Pruefung umbenannt.
Die drei Modelle werden gegen die von Hugging Face veroeffentlichte sha256
geprueft, nicht nur gegen die Quelle: damit ist belegt, dass die Datei dem
Original entspricht und nicht nur der Kopie auf der Freigabe.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time

QUELLE = "S:/AG/AG-CSB_NeuroRad/temuuleu/download/offline-bundle"
ZIEL = "E:/offline-bundle"

# relpfad -> erwartete sha256 (leer = nur Groesse pruefen)
MODELLE = {
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


def sammle() -> list[str]:
    """Alle relativen Pfade, die mitfahren sollen."""
    posten = list(MODELLE)
    for wurzel, _, dateien in os.walk(os.path.join(QUELLE, "05-wheels")):
        for d in dateien:
            p = os.path.join(wurzel, d)
            posten.append(os.path.relpath(p, QUELLE).replace("\\", "/"))
    for d in ("WELCHE-MASCHINE.md", "PRUEFSUMMEN.txt"):
        if os.path.exists(os.path.join(QUELLE, d)):
            posten.append(d)
    return posten


def main() -> int:
    posten = sammle()
    gesamt = sum(os.path.getsize(os.path.join(QUELLE, r)) for r in posten)
    print(f"=== {len(posten)} Dateien, {gesamt/1e9:.2f} GB ===")
    print()

    ok = uebersprungen = fehler = 0
    t_start = time.time()

    for rel in posten:
        q = os.path.join(QUELLE, rel)
        z = os.path.join(ZIEL, rel)
        soll = os.path.getsize(q)
        os.makedirs(os.path.dirname(z), exist_ok=True)

        if os.path.exists(z) and os.path.getsize(z) == soll:
            uebersprungen += 1
            continue

        t0 = time.time()
        # Erst nach .laedt, damit eine abgebrochene Kopie nie wie eine fertige
        # Datei aussieht -- auch nicht fuer jemanden, der nur ins Verzeichnis schaut.
        shutil.copyfile(q, z + ".laedt")
        dt = max(time.time() - t0, 0.001)

        ist = os.path.getsize(z + ".laedt")
        if ist != soll:
            print(f"  FEHL  {rel}  {ist} statt {soll} B")
            os.remove(z + ".laedt")
            fehler += 1
            continue

        if rel in MODELLE:
            # Rueckwaerts vom Stick lesen: das prueft den Schreibvorgang,
            # nicht nur die Quelle.
            h = sha256(z + ".laedt")
            if h != MODELLE[rel]:
                print(f"  ABWEICHUNG  {rel}")
                print(f"    Original {MODELLE[rel]}")
                print(f"    Stick    {h}")
                os.remove(z + ".laedt")
                fehler += 1
                continue
            marke = "sha256 gegen das Original bestaetigt"
        else:
            marke = ""

        os.replace(z + ".laedt", z)
        ok += 1
        if soll > 100_000_000:
            print(f"  ok  {rel}  {soll/1e9:.2f} GB  {soll/dt/1e6:.0f} MB/s  {marke}",
                  flush=True)

    print()
    print(f"=== {ok} kopiert, {uebersprungen} schon da, {fehler} fehlgeschlagen "
          f"in {(time.time()-t_start)/60:.1f} min ===")

    frei = shutil.disk_usage(ZIEL).free
    belegt = sum(
        os.path.getsize(os.path.join(w, d))
        for w, _, ds in os.walk(ZIEL) for d in ds
    )
    print(f"  Stick: {belegt/1e9:.2f} GB belegt, {frei/1e9:.2f} GB frei")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
