"""Macht den Stick abfahrbereit, ohne alle 48 GB neu zu hashen.

Gehasht wird nur, was es braucht:

  * Dateien ohne Eintrag in PRUEFSUMMEN.txt
  * Dateien, deren Eintrag eine ANDERE Groesse nennt als die Datei hat --
    das sind die gefaehrlichen: Qwen3-Coder steht dort mit dem Hash seines
    Teilstuecks von 15 GB. Bliebe der stehen, saehe die Pruefung auf Alita
    aus wie Datenverlust, obwohl die Datei in Ordnung ist.

  * Eintraege zu Dateien, die es nicht mehr gibt, fallen raus.

Alles Uebrige wurde heute Vormittag gehasht und hat sich seither nicht
geaendert -- erneutes Lesen waere reine Zeitverschwendung.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time

BUNDLE = "E:/offline-bundle"
PRUEF = os.path.join(BUNDLE, "PRUEFSUMMEN.txt")
INV = os.path.join(BUNDLE, "INVENTAR.txt")
FREIGABE = "S:/AG/AG-CSB_NeuroRad/temuuleu/download"

MEDGEMMA = "07-experimentelle-modelle/medgemma-27b-text-it-Q4_K_M.gguf"
MEDGEMMA_SOLL = 16546405376


def sha256(pfad: str, block: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        while stueck := f.read(block):
            h.update(stueck)
    return h.hexdigest()


def uebernimm_waechter_hash(ist: dict) -> tuple[str, int] | None:
    """Liest die vom Kopier-Waechter bestaetigte sha256 aus seinem Protokoll.

    Nur uebernehmen, wenn die Datei genau die Groesse hat, die der Waechter
    geprueft hat. Sonst lieber selbst rechnen.
    """
    import glob
    if ist.get(MEDGEMMA) != MEDGEMMA_SOLL:
        return None
    muster = os.path.join(
        os.environ.get("TEMP", "C:/Users/TEMUULEU/AppData/Local/Temp"),
        "claude", "T--Projects", "*", "tasks", "*.output")
    for datei in glob.glob(muster):
        try:
            with open(datei, encoding="utf-8", errors="replace") as f:
                inhalt = f.read()
        except OSError:
            continue
        if "medgemma-27b" not in inhalt.lower():
            continue
        for zeile in inhalt.splitlines():
            if zeile.strip().startswith("OK  sha256 "):
                h = zeile.split()[-1]
                if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                    return (h, MEDGEMMA_SOLL)
    return None


def warte_auf_medgemma(minuten: int = 30) -> bool:
    ziel = os.path.join(BUNDLE, MEDGEMMA)
    teil = ziel + ".laedt"
    print("=== warte auf das Ende des MedGemma-Vergleichs ===")
    for _ in range(minuten * 4):
        if os.path.exists(ziel) and os.path.getsize(ziel) >= MEDGEMMA_SOLL:
            print("  MedGemma-27B umbenannt -- der Vergleich war erfolgreich.")
            return True
        if not os.path.exists(teil) and not os.path.exists(ziel):
            print("  ABBRUCH: weder Datei noch Teildatei da. Vergleich fehlgeschlagen.")
            return False
        time.sleep(15)
    print("  Zeitgrenze erreicht.")
    return False


def main() -> int:
    if not warte_auf_medgemma():
        return 1

    # --- vorhandene Eintraege einlesen ---
    bekannt: dict[str, tuple[str, int]] = {}
    if os.path.exists(PRUEF):
        with open(PRUEF, encoding="utf-8") as f:
            for zeile in f:
                teile = zeile.split(None, 2)
                if len(teile) == 3:
                    bekannt[teile[2].strip().lstrip("./")] = (teile[0], int(teile[1]))

    # --- tatsaechlichen Bestand aufnehmen ---
    ist: dict[str, int] = {}
    for wurzel, _, dateien in os.walk(BUNDLE):
        for d in dateien:
            if d in ("PRUEFSUMMEN.txt", "INVENTAR.txt") or d.endswith(".laedt"):
                continue
            p = os.path.join(wurzel, d)
            rel = os.path.relpath(p, BUNDLE).replace("\\", "/")
            ist[rel] = os.path.getsize(p)

    fehlend = [r for r in ist if r not in bekannt]
    veraltet = [r for r in ist if r in bekannt and bekannt[r][1] != ist[r]]
    verwaist = [r for r in bekannt if r not in ist]

    print()
    print("=== Abgleich ===")
    print(f"  Dateien auf dem Stick:        {len(ist)}")
    print(f"  ohne Pruefsumme:              {len(fehlend)}")
    print(f"  Pruefsumme veraltet (Groesse anders): {len(veraltet)}")
    for r in veraltet:
        print(f"     {r}\n       Eintrag {bekannt[r][1]} B, Datei {ist[r]} B")
    print(f"  Eintraege ohne Datei:         {len(verwaist)}")
    for r in verwaist:
        print(f"     {r}")

    # Die sha256 von MedGemma-27B hat der Kopier-Waechter beim Vergleich
    # beider Seiten schon gerechnet. Sie noch einmal zu rechnen waere 16,5 GB
    # Lesen fuer nichts -- also aus seinem Protokoll uebernehmen.
    geschenkt = uebernimm_waechter_hash(ist)
    if geschenkt:
        bekannt[MEDGEMMA] = geschenkt
        fehlend[:] = [r for r in fehlend if r != MEDGEMMA]
        veraltet[:] = [r for r in veraltet if r != MEDGEMMA]
        print()
        print("  sha256 von MedGemma-27B aus dem Kopierprotokoll uebernommen:")
        print(f"    {geschenkt[0]}")

    zu_hashen = sorted(set(fehlend) | set(veraltet), key=lambda r: ist[r])
    gesamt = sum(ist[r] for r in zu_hashen)
    print(f"\n  zu hashen: {len(zu_hashen)} Dateien, {gesamt/1e9:.2f} GB")

    for i, rel in enumerate(zu_hashen, 1):
        p = os.path.join(BUNDLE, rel)
        t0 = time.time()
        h = sha256(p)
        bekannt[rel] = (h, ist[rel])
        dt = max(time.time() - t0, 0.001)
        print(f"  [{i}/{len(zu_hashen)}] {rel}  {ist[rel]/1e9:.2f} GB  "
              f"{ist[rel]/dt/1e6:.0f} MB/s", flush=True)

    for rel in verwaist:
        bekannt.pop(rel, None)

    with open(PRUEF, "w", encoding="utf-8", newline="\n") as f:
        for rel in sorted(bekannt):
            h, b = bekannt[rel]
            f.write(f"{h}  {b}  ./{rel}\n")
    print(f"\n  PRUEFSUMMEN.txt: {len(bekannt)} Eintraege")

    with open(INV, "w", encoding="utf-8", newline="\n") as f:
        for rel in sorted(ist):
            f.write(f"{ist[rel]}\t{rel}\n")
    print(f"  INVENTAR.txt:    {len(ist)} Eintraege")

    for ordner in (FREIGABE, os.path.join(FREIGABE, "rest_download")):
        try:
            with open(INV, encoding="utf-8") as q, \
                 open(os.path.join(ordner, "INVENTAR-usb.txt"), "w",
                      encoding="utf-8", newline="\n") as w:
                w.write(q.read())
            print(f"  INVENTAR-usb.txt -> {ordner}")
        except OSError as e:
            print(f"  (Freigabe {ordner} nicht beschreibbar: {e})")

    teilreste = []
    for wurzel, _, dateien in os.walk(BUNDLE):
        for d in dateien:
            if d.endswith(".laedt"):
                p = os.path.join(wurzel, d)
                teilreste.append((os.path.getsize(p),
                                  os.path.relpath(p, BUNDLE).replace("\\", "/")))
    print("\n=== unvollstaendige Teildateien ===")
    if teilreste:
        for b, r in teilreste:
            print(f"  {b/1e9:.2f} GB  {r}")
        print("  (als .laedt erkennbar -- koennen nie mit einer fertigen Datei "
              "verwechselt werden)")
    else:
        print("  keine")

    # --- Abgleich gegen die vom Anbieter veroeffentlichten Summen ---
    # PRUEFSUMMEN.txt sagt nur, dass der Stick sich selbst treu bleibt.
    # Erst dieser Vergleich beweist, dass der Download heil ankam.
    herk = os.path.join(BUNDLE, "HERKUNFTS-PRUEFSUMMEN.txt")
    if os.path.exists(herk):
        print()
        print("=== gegen die veroeffentlichten Summen des Anbieters ===")
        gut = schlecht = offen = 0
        with open(herk, encoding="utf-8") as f:
            for zeile in f:
                if zeile.startswith("#") or not zeile.strip():
                    continue
                t = zeile.split()
                if len(t) < 3:
                    continue
                oid, groesse, rel = t[0], int(t[1]), t[2]
                if rel not in bekannt or bekannt[rel][1] != groesse:
                    print(f"  offen      {rel}")
                    offen += 1
                elif bekannt[rel][0] == oid:
                    print(f"  IDENTISCH  {rel}")
                    gut += 1
                else:
                    print(f"  ABWEICHUNG {rel}")
                    print(f"    Anbieter {oid}")
                    print(f"    Stick    {bekannt[rel][0]}")
                    schlecht += 1
        print()
        print(f"  {gut} identisch, {schlecht} abweichend, {offen} offen")
        if schlecht:
            print("  ACHTUNG: abweichende Dateien nicht verwenden, neu laden.")

    gesamt_b = sum(ist.values())
    print(f"\n=== Stick: {len(ist)} Dateien, {gesamt_b/1e9:.2f} GB ===")
    print("FERTIG. Der Stick kann ausgeworfen werden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
