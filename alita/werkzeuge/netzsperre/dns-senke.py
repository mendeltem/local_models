#!/usr/bin/env python3
"""DNS-Senke: beantwortet jede Anfrage mit NXDOMAIN und schreibt sie mit.

Laeuft innerhalb der Netzsperre auf 127.0.0.1:53. Verbindungen auf nackte IPs
scheitern ohnehin an der fehlenden Route -- die sieht die Senke nicht. Alles,
was ueber einen Namen geht, steht danach im Protokoll.

Das Protokoll ist ein Messwert, kein Betriebsdetail: es zeigt, was das Modell
stillschweigend voraussetzt und deshalb in den Auftrag gehoert.

Nur Standardbibliothek, keine Abhaengigkeit -- innerhalb der Sperre laesst sich
nichts nachinstallieren.

GESCHRIEBEN AUF VICTUS, NICHT AUF ALITA GELAUFEN.
"""

import argparse
import socket
import struct
import sys
import time

# Anfragetypen, die haeufig genug vorkommen, um sie zu benennen
TYPEN = {1: "A", 2: "NS", 5: "CNAME", 12: "PTR", 15: "MX", 16: "TXT",
         28: "AAAA", 33: "SRV", 65: "HTTPS"}


def name_lesen(daten, pos):
    """Liest einen DNS-Namen ab pos. Gibt (name, neue_position) zurueck."""
    teile = []
    while pos < len(daten):
        laenge = daten[pos]
        if laenge == 0:
            pos += 1
            break
        if laenge & 0xC0 == 0xC0:      # Zeiger - in Anfragen unueblich
            pos += 2
            break
        pos += 1
        teile.append(daten[pos:pos + laenge].decode("ascii", "replace"))
        pos += laenge
    return ".".join(teile), pos


def antwort_nxdomain(anfrage):
    """Baut die kuerzestmoegliche NXDOMAIN-Antwort auf die Anfrage."""
    if len(anfrage) < 12:
        return None
    kennung = anfrage[:2]
    # QR=1 (Antwort), RD aus der Anfrage uebernehmen, RA=0, RCODE=3 (NXDOMAIN)
    rd = anfrage[2] & 0x01
    flags = struct.pack("!BB", 0x80 | rd, 0x03)
    zaehler = struct.pack("!HHHH", 1, 0, 0, 0)   # eine Frage, keine Antwort
    return kennung + flags + zaehler + anfrage[12:]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--protokoll", default="netzversuche.log")
    p.add_argument("--port", type=int, default=53)
    p.add_argument("--adresse", default="127.0.0.1")
    a = p.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind((a.adresse, a.port))
    except OSError as e:
        # Port 53 braucht auch im Namensraum Rechte; mit --map-root-user da.
        print("dns-senke: kann %s:%d nicht belegen (%s)" % (a.adresse, a.port, e),
              file=sys.stderr)
        return 3

    print("dns-senke: hoert auf %s:%d, Protokoll %s" % (a.adresse, a.port, a.protokoll),
          file=sys.stderr)

    with open(a.protokoll, "a", encoding="utf-8", buffering=1) as prot:
        while True:
            try:
                daten, absender = s.recvfrom(2048)
            except KeyboardInterrupt:
                return 0
            except OSError:
                continue

            name, pos = ("?", 12)
            typ = 0
            try:
                name, pos = name_lesen(daten, 12)
                if pos + 2 <= len(daten):
                    typ, = struct.unpack("!H", daten[pos:pos + 2])
            except Exception:
                pass

            prot.write("%s\t%s\t%s\n" % (
                time.strftime("%Y-%m-%d %H:%M:%S"),
                TYPEN.get(typ, str(typ)),
                name or "(leer)"))

            ant = antwort_nxdomain(daten)
            if ant:
                try:
                    s.sendto(ant, absender)
                except OSError:
                    pass


if __name__ == "__main__":
    sys.exit(main())
