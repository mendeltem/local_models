#!/usr/bin/env python3
"""test_detect.py - Unit-Tests fuer tools/detect.py, nur Standardbibliothek.

Aufruf aus dem Repo-Wurzelverzeichnis:  python3 -m unittest tools.test_detect -v

Die GGUF-Dateien sind synthetisch: Header, Metadaten und Tensor-Tabelle nach
GGUF v3, Datenbereich mit Nullen. Tensor-Offsets sind - wie im echten Format -
relativ zum ausgerichteten Beginn des Datenbereichs.
"""

import io
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.detect import analyse, gpu_info, host_info, read_gguf  # noqa: E402

# GGUF-Wertetypen (siehe SZ/FMT in detect.read_gguf)
UI32, STR, ARR, F64 = 4, 8, 9, 12
MiB = 1024 ** 2


def _q(buf, v):
    buf.write(struct.pack("<Q", v))


def _i(buf, v):
    buf.write(struct.pack("<I", v))


def _s(buf, text):
    b = text.encode("utf-8")
    _q(buf, len(b))
    buf.write(b)


def _kv_write(buf, key, t, val):
    _s(buf, key)
    _i(buf, t)
    if t == STR:
        _s(buf, val)
    elif t == UI32:
        _i(buf, val)
    elif t == F64:
        buf.write(struct.pack("<d", val))
    elif t == ARR:                      # nur String-Arrays, wie tokenizer.ggml.tokens
        _i(buf, STR)
        _q(buf, len(val))
        for s in val:
            _s(buf, s)
    else:
        raise ValueError("Typ %d im Test nicht unterstuetzt" % t)


def build_gguf(kv, tensors, align=32):
    """Schreibt eine minimale GGUF-v3-Datei und gibt den Pfad zurueck.

    kv      - dict key -> (typ, wert)
    tensors - Liste von dicts mit name, dims, nbytes (Vielfaches von align)
    """
    buf = io.BytesIO()
    buf.write(b"GGUF")
    _i(buf, 3)
    _q(buf, len(tensors))
    _q(buf, len(kv))
    for key, (t, val) in kv.items():
        _kv_write(buf, key, t, val)

    offset = 0
    for t in tensors:
        assert t["nbytes"] % align == 0, "nbytes muss ausgerichtet sein"
        _s(buf, t["name"])
        _i(buf, len(t["dims"]))
        for d in t["dims"]:
            _q(buf, d)
        _i(buf, t.get("type", 0))
        _q(buf, offset)
        offset += t["nbytes"]

    buf.write(b"\x00" * (-buf.tell() % align))
    buf.write(b"\x00" * offset)

    fd, path = tempfile.mkstemp(suffix=".gguf")
    with os.fdopen(fd, "wb") as f:
        f.write(buf.getvalue())
    return path


def llama_kv(key_length=128, value_length=128, **extra):
    kv = {
        "general.architecture": (STR, "llama"),
        "llama.block_count": (UI32, 4),
        "llama.embedding_length": (UI32, 2048),
        "llama.attention.head_count": (UI32, 16),
        "llama.attention.head_count_kv": (UI32, 8),
    }
    if key_length is not None:
        kv["llama.attention.key_length"] = (UI32, key_length)
    if value_length is not None:
        kv["llama.attention.value_length"] = (UI32, value_length)
    kv.update(extra)
    return kv


def moe_tensors(n_layers=4, expert_bytes=MiB):
    """Je Layer zwei Experten-Tensoren (Name enthaelt _exps) und eine Norm."""
    tens = [dict(name="token_embd.weight", dims=[2048, 128], nbytes=MiB)]
    for l in range(n_layers):
        tens.append(dict(name="blk.%d.attn_norm.weight" % l, dims=[2048], nbytes=8192))
        tens.append(dict(name="blk.%d.ffn_up_exps.weight" % l, dims=[2048, 128, 2],
                         nbytes=expert_bytes))
        tens.append(dict(name="blk.%d.ffn_down_exps.weight" % l, dims=[128, 2048, 2],
                         nbytes=expert_bytes))
    tens.append(dict(name="output.weight", dims=[2048, 128], nbytes=MiB))
    return tens


class TempGguf:
    """Kontextmanager: baut die Datei und loescht sie wieder."""

    def __init__(self, kv, tensors):
        self.kv, self.tensors = kv, tensors

    def __enter__(self):
        self.path = build_gguf(self.kv, self.tensors)
        return self.path

    def __exit__(self, *exc):
        os.unlink(self.path)


class TestReadGguf(unittest.TestCase):

    def test_metadata(self):
        kv = llama_kv(**{"general.name": (STR, "Testmodell"),
                         "llama.rope.freq_base": (F64, 10000.0)})
        with TempGguf(kv, moe_tensors()) as path:
            meta, _ = read_gguf(path)
        self.assertEqual(meta["general.architecture"], "llama")
        self.assertEqual(meta["general.name"], "Testmodell")
        self.assertEqual(meta["llama.block_count"], 4)
        self.assertEqual(meta["llama.attention.key_length"], 128)
        self.assertEqual(meta["llama.rope.freq_base"], 10000.0)

    def test_string_array_is_skipped_not_loaded(self):
        kv = llama_kv(**{"tokenizer.ggml.tokens": (ARR, ["a", "bc", "def"])})
        with TempGguf(kv, moe_tensors()) as path:
            meta, tensors = read_gguf(path)
        self.assertEqual(meta["tokenizer.ggml.tokens"], "<3 strings>")
        # Nach dem Array muss der Lesezeiger stimmen, sonst waeren die Tensoren Muell
        self.assertEqual(len(tensors), len(moe_tensors()))

    def test_tensor_table(self):
        tens = moe_tensors()
        with TempGguf(llama_kv(), tens) as path:
            _, tensors = read_gguf(path)
        self.assertEqual([t["name"] for t in tensors], [t["name"] for t in tens])
        self.assertEqual(tensors[2]["dims"], (2048, 128, 2))

    def test_tensor_bytes_from_offsets(self):
        # Kern von detect.py: Groesse = Abstand zum naechsten Offset, auch beim letzten
        tens = moe_tensors()
        with TempGguf(llama_kv(), tens) as path:
            _, tensors = read_gguf(path)
        self.assertEqual([t["bytes"] for t in tensors], [t["nbytes"] for t in tens])

    def test_bad_magic(self):
        fd, path = tempfile.mkstemp(suffix=".gguf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(b"BAD!" + b"\x00" * 20)
            with self.assertRaises(ValueError) as exc:
                read_gguf(path)
            self.assertIn("kein GGUF", str(exc.exception))
        finally:
            os.unlink(path)

    def test_bad_magic_closes_file(self):
        fd, path = tempfile.mkstemp(suffix=".gguf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(b"BAD!" + b"\x00" * 20)
            opened = []
            real_open = open

            def spy(*a, **k):
                f = real_open(*a, **k)
                opened.append(f)
                return f
            with patch("builtins.open", spy):
                with self.assertRaises(ValueError):
                    read_gguf(path)
            self.assertTrue(opened and all(f.closed for f in opened))
        finally:
            os.unlink(path)

    def test_empty_model(self):
        with TempGguf({}, []) as path:
            kv, tensors = read_gguf(path)
        self.assertEqual(kv, {})
        self.assertEqual(tensors, [])


class TestAnalyse(unittest.TestCase):

    # Fester Aufbau: 4 Layer, je Layer 2 MiB Experten, 2 MiB + 4 x 8 KiB Rest.
    # KV-Cache bei ctx 1024: 1024 * 4 Layer * 8 KV-Koepfe * (128+128) * 2 B = 16 MiB
    OTHER_MIB = 2 + 4 * 8192 / MiB
    KV_MIB = 16.0

    def run_analyse(self, kv=None, gpu_free_mib=0, reserve_mib=100, ctx=1024):
        with TempGguf(kv or llama_kv(), moe_tensors()) as path:
            return analyse(path, ctx, reserve_mib, gpu_free_mib)

    def test_sizes(self):
        r = self.run_analyse(gpu_free_mib=10_000)
        self.assertAlmostEqual(r["layer_mib"], 2.0)
        self.assertAlmostEqual(r["expert_gib"], 8 / 1024)
        self.assertAlmostEqual(r["other_gib"], self.OTHER_MIB / 1024)
        self.assertAlmostEqual(r["kv_mib"], self.KV_MIB)
        self.assertFalse(r["kv_geraten"])
        self.assertFalse(r["hybrid"])

    def test_ncmoe_partial_fit(self):
        # Nach Reserve, Rest und KV bleiben 5 MiB: zwei Layer a 2 MiB passen
        free = 100 + self.OTHER_MIB + self.KV_MIB + 5
        r = self.run_analyse(gpu_free_mib=free)
        self.assertEqual(r["gpu_layers_fit"], 2)
        self.assertEqual(r["ncmoe"], 2)
        self.assertAlmostEqual(r["expert_ram_gib"], (8 / 1024) * 2 / 4)

    def test_ncmoe_everything_fits_is_capped(self):
        r = self.run_analyse(gpu_free_mib=100_000)
        self.assertEqual(r["gpu_layers_fit"], 4)
        self.assertEqual(r["ncmoe"], 0)

    def test_ncmoe_nothing_fits_not_negative(self):
        r = self.run_analyse(gpu_free_mib=50)
        self.assertEqual(r["gpu_layers_fit"], 0)
        self.assertEqual(r["ncmoe"], 4)

    def test_no_experts(self):
        tens = [t for t in moe_tensors() if "_exps" not in t["name"]]
        with TempGguf(llama_kv(), tens) as path:
            r = analyse(path, 1024, 100, 100_000)
        self.assertEqual(r["layer_mib"], 0.0)
        self.assertEqual(r["ncmoe"], 4)

    def test_head_dim_guessed_is_flagged(self):
        r = self.run_analyse(kv=llama_kv(key_length=None, value_length=None),
                             gpu_free_mib=10_000)
        self.assertTrue(r["kv_geraten"])
        self.assertEqual((r["k_dim"], r["v_dim"]), (2048 // 16, 2048 // 16))

    def test_hybrid_full_attention_interval(self):
        kv = llama_kv(**{"llama.full_attention_interval": (UI32, 4)})
        r = self.run_analyse(kv=kv, gpu_free_mib=10_000)
        self.assertTrue(r["hybrid"])
        # Empfehlung bleibt auf der Obergrenze, die Hybridzahl ist nur Anzeige
        self.assertAlmostEqual(r["kv_mib"], self.KV_MIB)
        self.assertAlmostEqual(r["kv_mib_hybrid"], self.KV_MIB / 4)

    def test_hybrid_ssm_key(self):
        kv = llama_kv(**{"llama.ssm.state_size": (UI32, 128)})
        r = self.run_analyse(kv=kv, gpu_free_mib=10_000)
        self.assertTrue(r["hybrid"])
        self.assertIsNone(r["kv_mib_hybrid"])


class TestGpuInfo(unittest.TestCase):

    def test_parses_csv(self):
        out = SimpleNamespace(stdout="NVIDIA GeForce RTX 4070 Laptop GPU, 8188, 1076, 7112\n"
                                     "Zweite, 4096, 0, 4096\n")
        with patch("subprocess.run", return_value=out):
            gpus = gpu_info()
        self.assertEqual(gpus[0], {"name": "NVIDIA GeForce RTX 4070 Laptop GPU",
                                   "total": 8188, "used": 1076, "free": 7112})
        self.assertEqual(len(gpus), 2)

    def test_skips_malformed_lines(self):
        out = SimpleNamespace(stdout="kaputt\nGPU, 100, 10, 90\n")
        with patch("subprocess.run", return_value=out):
            self.assertEqual(len(gpu_info()), 1)

    def test_missing_nvidia_smi(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("nvidia-smi")):
            self.assertEqual(gpu_info(), [])


@unittest.skipIf(os.name == "nt", "Linux-Zweig von host_info")
class TestHostInfo(unittest.TestCase):

    FILES = {
        "/proc/meminfo": "MemTotal:       16384000 kB\nMemFree:  8192000 kB\n",
        # Zwei Threads je Kern: gezaehlt werden die verschiedenen core ids
        "/proc/cpuinfo": "processor\t: 0\ncore id\t\t: 0\n\n"
                         "processor\t: 1\ncore id\t\t: 0\n\n"
                         "processor\t: 2\ncore id\t\t: 1\n",
    }

    def test_reads_proc(self):
        def fake(path, *a, **k):
            return self.FILES[str(path)]
        with patch.object(Path, "read_text", autospec=True, side_effect=fake):
            info = host_info()
        self.assertAlmostEqual(info["ram_gb"], 16384000 / 1024 ** 2)
        self.assertEqual(info["threads"], 2)

    def test_unreadable_proc_falls_back(self):
        with patch.object(Path, "read_text", side_effect=OSError("nope")):
            info = host_info()
        self.assertIsNone(info["ram_gb"])
        self.assertEqual(info["threads"], os.cpu_count())


if __name__ == "__main__":
    unittest.main()
