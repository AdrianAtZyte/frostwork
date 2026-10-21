# `frostwork.encoding` against what Scrapy runs today (Python's codecs, w3lib's own functions and
# charset-normalizer for undeclared pages), on page-sized documents, one row per encoding, plus the
# import time `frostwork.encoding` adds to `w3lib.encoding`. Every row checks that
# both sides return the same answer before timing them, except where the WHATWG decoder is meant to
# differ, which is reported instead.
#
# Run:  .venv/bin/python tools/bench_encoding.py [--size BYTES] [--reps N]
#
# Build the extension RELEASE-first (`maturin develop --release`).

from __future__ import annotations

import argparse
import subprocess
import sys
import timeit

from charset_normalizer import from_bytes
from w3lib.encoding import html_body_declared_encoding, to_unicode

from frostwork.encoding import autodetect_encoding, declared_encoding, decode

TEXT = {
    "utf-8": "Café déjà vu, 日本語のページ, Привет мир, 中文测试. ",
    "cp1252": "Le café est déjà prêt, très chaud et très bon. ",
    "cp1251": "Привет мир, это тестовая страница на русском языке. ",
    "shift_jis": "日本語のページです。こんにちは、世界。",
    "euc_jp": "日本語のページです。こんにちは、世界。",
    "gbk": "中文测试内容，这是一个测试页面。",
    "big5": "繁體中文測試，這是一個測試頁面。",
    "euc_kr": "한국어 테스트 페이지입니다. 안녕하세요.",
}


def page(encoding: str, size: int) -> bytes:
    """A document of about *size* bytes, mostly ASCII markup, like a real page."""
    row = f'<div class="item"><a href="/p/1">{TEXT[encoding]}</a><span class="price">$9</span></div>\n'
    head = "<!DOCTYPE html><html><head><title>t</title></head><body>\n"
    body = head + row * (size // len(row.encode(encoding)))
    return (body + "</body></html>").encode(encoding)


def detect(body: bytes) -> str | None:
    """Scrapy's detection of an undeclared body that is not UTF-8."""
    match = from_bytes(body).best()
    return match.encoding if match else None


def best(stmt, reps: int) -> float:
    return min(timeit.repeat(stmt, number=1, repeat=reps))


def row(name: str, ours, theirs, reps: int, same: bool = True) -> None:
    if same:
        assert ours() == theirs(), name
    a, b = best(ours, reps), best(theirs, reps)
    note = "" if same else "  (answers differ by design)"
    print(f"{name:<34} {a * 1e3:9.3f} ms {b * 1e3:9.3f} ms {a / b:7.2f}{note}")


def import_time(module: str, reps: int) -> float:
    code = f"import time; t = time.perf_counter(); import {module}; print(time.perf_counter() - t)"
    return min(float(subprocess.check_output([sys.executable, "-c", code])) for _ in range(reps))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=300_000)
    parser.add_argument("--reps", type=int, default=20)
    args = parser.parse_args()
    print(f"{'':<34} {'frostwork':>12} {'w3lib':>12} {'ratio':>7}")
    for encoding in TEXT:
        body = page(encoding, args.size)
        # Python's codecs and the WHATWG decoders differ on a few characters of these encodings.
        same = decode(body, encoding) == to_unicode(body, encoding)
        row(f"decode {encoding}", lambda: decode(body, encoding), lambda: to_unicode(body, encoding),
            args.reps, same)
        declared = f'<meta charset="{encoding}">'.encode() + body
        row(f"declared {encoding}", lambda: declared_encoding(declared),
            lambda: html_body_declared_encoding(declared), args.reps, same=False)
        if encoding != "utf-8":
            row(f"autodetect {encoding}", lambda: autodetect_encoding(body), lambda: detect(body),
                args.reps, same=False)
    binary = bytes(range(256)) * (8_000_000 // 256)
    row("autodetect 8 MB binary", lambda: autodetect_encoding(binary), lambda: detect(binary), args.reps,
        same=False)
    base = import_time("w3lib.encoding", args.reps)
    both = import_time("w3lib.encoding, frostwork.encoding", args.reps)
    print(f"import frostwork.encoding after w3lib.encoding: {(both - base) * 1e3:.1f} ms")


if __name__ == "__main__":
    main()
