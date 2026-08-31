"""Sammelt fertige Modelldateien aus der Freigabe ein und sortiert sie ein.

Drei Maschinen laden in drei verschiedene Arbeitsverzeichnisse, aber alles
gehoert am Ende nach offline-bundle/07-experimentelle-modelle/. Statt jedem
zu sagen, wohin er soll, sucht dieses Skript den ganzen Baum ab.

Vor dem Verschieben wird gegen die vom Anbieter veroeffentlichte sha256
geprueft. Eine Datei, deren Summe nicht stimmt, wird liegen gelassen und
gemeldet -- nie eingespielt.

Teildateien (*.laedt) werden ignoriert; sie gehoeren einem laufenden Download.
"""

from __future__ import annotations

import hashlib
import os
import time

WURZEL = "S:/AG/AG-CSB_NeuroRad/temuuleu/download"
ZIEL = os.path.join(WURZEL, "offline-bundle", "07-experimentelle-modelle")

# Dateiname -> (bytes, sha256 wie von Hugging Face veroeffentlicht)
GESUCHT = {
    "Qwen3-4B-Instruct-2507-Q4_K_M.gguf":
        (2497281120, "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"),
    "Llama-3.1-8B-Instruct-Q4_K_M.gguf":
        (4920739200, "b3bdbf23b47d7e6bb791c99b206deb169cd5a96362a9e3399028df2faacdc506"),
}


def sha256(pfad: str, block: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        while stueck := f.read(block):
            h.update(stueck)
    return h.hexdigest()


def suche(name: str) -> list[str]:
    """Alle Fundorte dieser Datei im Baum, ausser dem Zielverzeichnis."""
    treffer = []
    for wurzel, verz, dateien in os.walk(WURZEL):
        verz[:] = [v for v in verz if v != "offline-bundle" or wurzel != WURZEL]
        if os.path.normpath(wurzel) == os.path.normpath(ZIEL):
            continue
        if name in dateien:
            treffer.append(os.path.join(wurzel, name))
    return treffer


def stabil(pfad: str, sekunden: int = 5) -> bool:
    """Waechst die Datei noch? Dann gehoert sie einem laufenden Download."""
    a = os.path.getsize(pfad)
    time.sleep(sekunden)
    return os.path.getsize(pfad) == a


def main() -> int:
    os.makedirs(ZIEL, exist_ok=True)
    offen = dict(GESUCHT)
    runde = 0

    while offen and runde < 120:
        runde += 1
        for name, (soll, summe) in list(offen.items()):
            am_ziel = os.path.join(ZIEL, name)
            if os.path.exists(am_ziel) and os.path.getsize(am_ziel) >= soll:
                print(f"  --  {name} liegt schon am Ziel")
                del offen[name]
                continue

            for fund in suche(name):
                if os.path.getsize(fund) < soll or not stabil(fund):
                    continue
                print(f"  gefunden: {fund}")
                print("    rechne sha256 ...", flush=True)
                h = sha256(fund)
                if h != summe:
                    print(f"    ABWEICHUNG -- nicht eingespielt")
                    print(f"      erwartet {summe}")
                    print(f"      bekommen {h}")
                    continue
                os.replace(fund, am_ziel)
                print(f"    IDENTISCH mit dem Original, einsortiert")
                del offen[name]
                break

        if offen:
            if runde % 6 == 1:
                print(f"  warte auf: {', '.join(sorted(offen))}", flush=True)
            time.sleep(20)

    print()
    if offen:
        print("=== nicht eingetroffen ===")
        for n in sorted(offen):
            print("  ", n)
    print("=== Bundle-Ordner ===")
    for d in sorted(os.listdir(ZIEL)):
        p = os.path.join(ZIEL, d)
        if os.path.isfile(p):
            print(f"  {os.path.getsize(p):>14}  {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
