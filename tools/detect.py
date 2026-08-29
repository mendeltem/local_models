#!/usr/bin/env python3
"""detect.py - misst die Maschine und schreibt ein Startprofil fuer llama-server.

Portabel: laeuft auf jeder Maschine mit NVIDIA-GPU und Python 3.9+. Die
maschinenspezifischen Werte werden gemessen, nicht gepflegt - deshalb kannst du
den Rest des Projekts einfach kopieren und hier einmal 'python detect.py' rufen.

Warum die Tensor-Tabelle statt der Metadaten:
Dynamische Quantisierungen (unsloth "UD", i-Quants) geben verschiedenen Tensoren
verschiedene Bitbreiten - Experten weniger, Attention und Embeddings mehr. Eine
Rechnung aus block_count x expert_count x nominelle Bits liegt darum daneben
(auf dem Referenzsystem um 60 Prozent). Der GGUF-Header listet jeden Tensor mit
Typ und Dimensionen; daraus laesst sich die Groesse exakt bestimmen.
"""

import json
import math
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

# Bewusst KEINE ggml-Typtabelle: die Blockgroessen aendern sich mit neuen
# Quant-Typen, und eine veraltete Tabelle rechnet still falsch (erster Versuch
# lag um Faktor 2 daneben). Stattdessen kommen die Groessen aus den
# Tensor-Offsets im Header - die stimmen per Konstruktion, fuer jeden Typ.


def read_gguf(path):
    """Liest Metadaten und Tensor-Tabelle. Gibt (kv, tensors) zurueck."""
    f = open(path, "rb")
    if f.read(4) != b"GGUF":
        raise ValueError("kein GGUF: %s" % path)
    ver, = struct.unpack("<I", f.read(4))
    ntensor, nkv = struct.unpack("<QQ", f.read(16))
    SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
           7: "<B", 10: "<Q", 11: "<q", 12: "<d"}

    def val(t):
        if t == 8:
            n, = struct.unpack("<Q", f.read(8))
            return f.read(n).decode("utf-8", "replace")
        if t == 9:
            et, n = struct.unpack("<IQ", f.read(12))
            if et == 8:
                for _ in range(n):
                    l, = struct.unpack("<Q", f.read(8))
                    f.seek(l, 1)
                return "<%d strings>" % n
            if et == 9:
                return [val(9) for _ in range(n)]
            f.seek(SZ[et] * n, 1)
            return "<%d values>" % n
        return struct.unpack(FMT[t], f.read(SZ[t]))[0]

    kv = {}
    for _ in range(nkv):
        kl, = struct.unpack("<Q", f.read(8))
        k = f.read(kl).decode("utf-8", "replace")
        t, = struct.unpack("<I", f.read(4))
        kv[k] = val(t)

    raw = []
    for _ in range(ntensor):
        nl, = struct.unpack("<Q", f.read(8))
        name = f.read(nl).decode("utf-8", "replace")
        ndim, = struct.unpack("<I", f.read(4))
        dims = struct.unpack("<%dQ" % ndim, f.read(8 * ndim))
        ttype, = struct.unpack("<I", f.read(4))
        offset, = struct.unpack("<Q", f.read(8))
        raw.append({"name": name, "type": ttype, "dims": dims, "offset": offset})

    # Datenbereich beginnt nach dem Header, ausgerichtet auf general.alignment
    align = kv.get("general.alignment", 32) or 32
    pos = f.tell()
    data_start = pos + (-pos % align)
    total = Path(path).stat().st_size
    f.close()

    # Groesse eines Tensors = Abstand zum naechsten Offset. Exakt, ohne Typtabelle.
    order = sorted(range(len(raw)), key=lambda i: raw[i]["offset"])
    for n, i in enumerate(order):
        nxt = (raw[order[n + 1]]["offset"] if n + 1 < len(order)
               else total - data_start)
        raw[i]["bytes"] = nxt - raw[i]["offset"]
    return kv, raw


def gpu_info():
    """Freies und gesamtes VRAM je GPU, in MiB."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30)
        gpus = []
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) == 4:
                gpus.append({"name": parts[0], "total": int(parts[1]),
                             "used": int(parts[2]), "free": int(parts[3])})
        return gpus
    except Exception:
        return []


def host_info():
    ram_gb = threads = None
    try:
        if os.name == "nt":
            out = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory;"
                                  "(Get-CimInstance Win32_Processor "
                                  "| Measure-Object NumberOfCores -Sum).Sum"],
                                 capture_output=True, text=True, timeout=60)
            nums = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
            if nums:
                ram_gb = nums[0] / 1024**3
            if len(nums) > 1:
                threads = nums[1]
        else:
            txt = Path("/proc/meminfo").read_text()
            ram_gb = int(re.search(r"MemTotal:\s+(\d+)", txt).group(1)) / 1024**2
            txt = Path("/proc/cpuinfo").read_text()
            ids = set(re.findall(r"core id\s+:\s+(\d+)", txt))
            threads = len(ids) or os.cpu_count()
    except Exception:
        pass
    return {"ram_gb": ram_gb, "threads": threads or os.cpu_count()}


def analyse(model, ctx, reserve_mib, gpu_free_mib):
    kv, tensors = read_gguf(model)
    arch = kv.get("general.architecture", "?")
    g = lambda k, d=None: kv.get("%s.%s" % (arch, k), d)
    n_layer = g("block_count", 0)
    n_emb = g("embedding_length", 0)
    n_head = g("attention.head_count", 0)
    n_kv_head = g("attention.head_count_kv", n_head)

    # Expert-Tensoren je Layer: heissen ..._exps in llama.cpp
    per_layer = {}
    expert_bytes = other_bytes = 0
    for t in tensors:
        m = re.match(r"blk\.(\d+)\.", t["name"])
        if m and "_exps" in t["name"]:
            per_layer[int(m.group(1))] = per_layer.get(int(m.group(1)), 0) + t["bytes"]
            expert_bytes += t["bytes"]
        else:
            other_bytes += t["bytes"]

    layer_mib = (sum(per_layer.values()) / len(per_layer) / 1024**2) if per_layer else 0.0

    # --- KV-Cache ---------------------------------------------------------
    # Die Kopfdimension steht als attention.key_length / .value_length in der
    # Datei. Frueher wurde sie aus embedding_length/head_count GERATEN. Das ging
    # auf dem eigenen Referenzmodell um Faktor 2 daneben - qwen35moe meldet
    # key_length 256, geraten wurden 2048/16 = 128 - ohne dass es auffiel: die
    # Ausgabe sah wie eine Messung aus. Deshalb: lesen, und wenn nichts da ist,
    # das Raten benennen statt es zu verstecken.
    k_dim = g("attention.key_length")
    v_dim = g("attention.value_length")
    kv_geraten = k_dim is None or v_dim is None
    if kv_geraten:
        ersatz = (n_emb // n_head) if n_head else 128
        k_dim = k_dim or ersatz
        v_dim = v_dim or ersatz

    # Nicht jede Schicht haelt zwangslaeufig einen KV-Cache: hybride
    # Architekturen mischen volle Attention mit SSM- oder Sliding-Window-
    # Schichten und melden das ueber full_attention_interval bzw. ssm.*.
    # Was dort wirklich anfaellt, rechnet dieses Werkzeug NICHT aus. Die Zahl
    # unten unterstellt jeder Schicht vollen KV-Cache und ist damit eine
    # OBERGRENZE - bewusst, denn zu wenig reservieren heisst OOM beim Start.
    interval = g("full_attention_interval")
    ssm = any(str(k).startswith(arch + ".ssm.") for k in kv)
    hybrid = bool(interval) or ssm

    # K und V getrennt summiert (bei MLA-Architekturen sind sie verschieden),
    # 2 Byte je Element (f16).
    kv_mib = ctx * n_layer * n_kv_head * (k_dim + v_dim) * 2 / 1024**2
    # Nur zur Anzeige: so gross waere er, wenn full_attention_interval bedeutet,
    # dass jede n-te Schicht volle Attention hat. NICHT fuer die Empfehlung
    # benutzt - die Bedeutung des Schluessels ist nicht nachgemessen.
    kv_mib_hybrid = (kv_mib * math.ceil(n_layer / interval) / n_layer
                     if interval else None)

    usable = gpu_free_mib - reserve_mib - (other_bytes / 1024**2) - kv_mib
    fits = int(usable // layer_mib) if layer_mib > 0 else 0
    fits = max(0, min(n_layer, fits))
    ncmoe = n_layer - fits

    return {
        "arch": arch, "n_layer": n_layer, "n_emb": n_emb,
        "n_head": n_head, "n_kv_head": n_kv_head,
        "k_dim": k_dim, "v_dim": v_dim, "kv_geraten": kv_geraten,
        "hybrid": hybrid, "full_attention_interval": interval,
        "kv_mib_hybrid": kv_mib_hybrid,
        "expert_gib": expert_bytes / 1024**3, "other_gib": other_bytes / 1024**3,
        "layer_mib": layer_mib, "kv_mib": kv_mib,
        "gpu_layers_fit": fits, "ncmoe": ncmoe,
        "expert_ram_gib": (expert_bytes / 1024**3) * ncmoe / max(n_layer, 1),
    }


def main():
    import argparse
    p = argparse.ArgumentParser(
        description="Misst GPU, RAM und Modell und schreibt ein Startprofil.")
    p.add_argument("model", nargs="?", help="Pfad zur .gguf")
    p.add_argument("-c", "--ctx", type=int, default=16384)
    p.add_argument("--reserve", type=int, default=3200,
                   help="MiB VRAM fuer Compute-Puffer und Fremdprozesse "
                        "(Referenzsystem: ~3200)")
    p.add_argument("-o", "--out", help="Profil-JSON schreiben")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--print-args", action="store_true",
                   help="nur die llama-server-Argumente ausgeben")
    a = p.parse_args()

    model = a.model or os.environ.get("LOK_MODEL_PATH")
    if not model:
        cand = sorted(Path.home().glob("models/*.gguf")) + sorted(Path("/models").glob("*.gguf"))
        model = str(cand[0]) if cand else None
    if not model or not Path(model).is_file():
        print("detect: kein Modell gefunden. Pfad angeben oder LOK_MODEL_PATH setzen.",
              file=sys.stderr)
        return 2

    gpus = gpu_info()
    host = host_info()
    # Ein laufender Server haelt das VRAM schon - dann misst man Restmuell.
    try:
        busy = subprocess.run(["nvidia-smi", "--query-compute-apps=process_name",
                               "--format=csv,noheader"], capture_output=True,
                              text=True, timeout=30).stdout
        if "llama-server" in busy:
            print("WARNUNG: llama-server laeuft bereits und belegt VRAM. Fuer eine "
                  "belastbare Messung erst beenden.\n", file=sys.stderr)
    except Exception:
        pass
    if not gpus:
        print("detect: keine NVIDIA-GPU gefunden - alles auf die CPU.", file=sys.stderr)
        free = 0
    else:
        free = gpus[0]["free"]

    r = analyse(model, a.ctx, a.reserve, free)
    prof = {
        "model": str(Path(model).resolve()),
        "ctx": a.ctx, "port": a.port,
        "threads": host["threads"],
        "ncmoe": r["ncmoe"], "ngl": 99,
        "load_mode": "mmap" if (host["ram_gb"] or 0) < r["expert_ram_gib"] + 8 else "mmap+mlock",
        "gpu": gpus[0]["name"] if gpus else "keine",
        "gemessen": {
            "gpu_frei_mib": free, "layer_mib": round(r["layer_mib"], 1),
            "kv_mib": round(r["kv_mib"], 1), "nicht_experten_gib": round(r["other_gib"], 2),
            "experten_gib": round(r["expert_gib"], 2),
            "layer_auf_gpu": r["gpu_layers_fit"], "ram_gb": round(host["ram_gb"] or 0, 1),
        },
    }

    if a.print_args:
        print(" ".join(["-m", prof["model"], "-ngl", "99", "-ncmoe", str(prof["ncmoe"]),
                        "-c", str(prof["ctx"]), "-t", str(prof["threads"]),
                        "-fa", "on", "-np", "1", "-lm", prof["load_mode"],
                        "--host", "0.0.0.0", "--port", str(prof["port"])]))
        return 0

    print("Modell   : %s" % Path(model).name)
    print("  Arch %s | %d Layer | emb %d | heads %d/%d (GQA)"
          % (r["arch"], r["n_layer"], r["n_emb"], r["n_head"], r["n_kv_head"]))
    print("  Experten %.2f GiB | Rest %.2f GiB | pro Expert-Layer %.1f MiB"
          % (r["expert_gib"], r["other_gib"], r["layer_mib"]))
    print("GPU      : %s | %d MiB frei" % (prof["gpu"], free))
    print("  KV-Cache bei %d ctx: %.0f MiB (head_dim K/V %d/%d%s) | Reserve: %d MiB"
          % (a.ctx, r["kv_mib"], r["k_dim"], r["v_dim"],
             ", GERATEN" if r["kv_geraten"] else "", a.reserve))
    if r["kv_geraten"]:
        print("  ! attention.key_length fehlt in der Datei - head_dim aus "
              "embedding/heads geraten. Die KV-Zahl ist eine Schaetzung, "
              "keine Messung.", file=sys.stderr)
    if r["hybrid"]:
        print("  ! Hybride Architektur (full_attention_interval=%s%s). Die KV-Zahl "
              "unterstellt JEDER Schicht vollen Cache und ist damit eine "
              "Obergrenze." % (r["full_attention_interval"],
                               ", SSM-Schichten" if r["hybrid"] else ""),
              file=sys.stderr)
        if r["kv_mib_hybrid"]:
            print("    Haelt nur jede %s-te Schicht vollen Cache, waeren es rund "
                  "%.0f MiB - ungeprueft, nicht in der Empfehlung benutzt."
                  % (r["full_attention_interval"], r["kv_mib_hybrid"]),
                  file=sys.stderr)
    print("RAM      : %.1f GB | %d Kerne" % (host["ram_gb"] or 0, host["threads"]))
    print()
    print("-> %d von %d Expert-Layern passen auf die GPU  =>  -ncmoe %d"
          % (r["gpu_layers_fit"], r["n_layer"], r["ncmoe"]))
    print("-> %.1f GiB Experten bleiben im RAM, Lademodus %s"
          % (r["expert_ram_gib"], prof["load_mode"]))

    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
        print("\nProfil geschrieben: %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
