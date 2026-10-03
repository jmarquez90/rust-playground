"""Build the same index as the Rust version and time it.

Usage: python index_bench.py <folder> [seq|process|thread]

Prints the total build time, the two phases (per-file indexing, merge) and the number of workers
to stderr, and the document and distinct-word counts to stdout, in the same shape as the Rust
program so bench/run_bench.py can read both.

The thread and process modes use one worker per CPU available to this process, the same number
rayon uses by default, so the parallel configurations are compared at equal width.

If the environment variable INDEX_DUMP names a file, the finished index is also written there,
after the timer stops, in a canonical text form that the Rust program can reproduce byte for byte:
one line per (word, file), sorted by word and then by file name (both compared as UTF-8 bytes):

    <word><TAB><file name><TAB><position> <position> ...<LF>

Positions are word offsets within the file, in increasing order, separated by single spaces.
bench/run_bench.py compares the dumps' SHA-256 across configurations.
"""
import os
import re
import sys
import time
import platform
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

# Runs of letters and digits, the same split as the Rust tokenize().
TOKEN = re.compile(r"[^\W_]+")

# One worker per CPU available to this process: rayon's default thread count.
WORKERS = (os.process_cpu_count() if hasattr(os, "process_cpu_count") else None) or os.cpu_count() or 1


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
        with pool_type(max_workers=WORKERS) as pool:
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


def write_dump(path, docs, postings):
    """The canonical text form described at the top of this file."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for word in sorted(postings):
            by_doc = postings[word]
            for doc_id in sorted(by_doc, key=lambda d: docs[d]):
                f.write(f"{word}\t{docs[doc_id]}\t{' '.join(map(str, by_doc[doc_id]))}\n")


if __name__ == "__main__":  # required for the process pool
    folder = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "seq"
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()

    start = time.perf_counter()
    docs, doc_lengths, postings = build(folder, mode)
    elapsed_ms = (time.perf_counter() - start) * 1000

    print(f"  workers: {1 if mode == 'seq' else WORKERS}", file=sys.stderr)
    print(f"indexed in {elapsed_ms:.3f} ms  [mode={mode}, Python {platform.python_version()}, "
          f"GIL {'on' if gil else 'off'}]", file=sys.stderr)
    print(f"{len(docs)} documents, {len(postings)} distinct words")

    dump = os.environ.get("INDEX_DUMP")
    if dump:
        write_dump(dump, docs, postings)
