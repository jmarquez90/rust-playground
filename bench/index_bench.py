"""Build the same index as the Rust version and time it.

Usage: python index_bench.py <folder> [seq|process|thread]

Prints the total build time and the two phases (per-file indexing, merge) to stderr,
and the document and distinct-word counts to stdout, in the same shape as the Rust
program so bench/run_bench.py can read both.
"""
import re
import sys
import time
import platform
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

# Runs of letters and digits, the same split as the Rust tokenize().
TOKEN = re.compile(r"[^\W_]+")


def index_file(path):
    """One file's share of the index: name, word count, word -> positions."""
    words = TOKEN.findall(path.read_text(encoding="utf-8").lower())
    postings = defaultdict(list)
    for pos, word in enumerate(words):
        postings[word].append(pos)
    return path.name, len(words), postings


def build(folder, mode):
    paths = [p for p in Path(folder).iterdir() if p.suffix == ".txt"]

    t = time.perf_counter()
    if mode == "seq":
        doc_indexes = [index_file(p) for p in paths]
    else:
        pool_type = ProcessPoolExecutor if mode == "process" else ThreadPoolExecutor
        with pool_type() as pool:
            doc_indexes = list(pool.map(index_file, paths))
    index_ms = (time.perf_counter() - t) * 1000

    # Merge: word -> {doc id -> positions}
    t = time.perf_counter()
    docs, doc_lengths, postings = [], [], defaultdict(dict)
    for doc_id, (name, length, doc_postings) in enumerate(doc_indexes):
        docs.append(name)
        doc_lengths.append(length)
        for word, positions in doc_postings.items():
            postings[word][doc_id] = positions
    merge_ms = (time.perf_counter() - t) * 1000

    print(f"  per-file indexing: {index_ms:.3f} ms", file=sys.stderr)
    print(f"  merge: {merge_ms:.3f} ms", file=sys.stderr)
    return docs, doc_lengths, postings


if __name__ == "__main__":  # required for the process pool
    folder = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "seq"
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()

    start = time.perf_counter()
    docs, doc_lengths, postings = build(folder, mode)
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(f"indexed in {elapsed_ms:.3f} ms  [mode={mode}, Python {platform.python_version()}, "
          f"GIL {'on' if gil else 'off'}]", file=sys.stderr)
    print(f"{len(docs)} documents, {len(postings)} distinct words")
