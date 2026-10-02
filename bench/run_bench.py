# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow>=17"]
# ///
"""Benchmark the index build: Python (seq, process, thread) against Rust snapshots.

Run from the repo root, inside the dev container:

    uv run --python 3.14 bench/run_bench.py snapshot baseline      # build Rust, keep a copy named "baseline"
    uv run --python 3.14 bench/run_bench.py run --runs 20          # smoke test
    uv run --python 3.14 bench/run_bench.py run --runs 1000 --name baseline

What one experiment does:

- Copies data/*.txt to a container-local folder once (~/bench-data), so runs don't read
  through the Windows-mounted folder.
- Builds the configurations: python/seq, python/process, python/thread, and for every
  Rust snapshot rust/<label>/1-thread (RAYON_NUM_THREADS=1) and rust/<label>/rayon.
- Runs warm-up rounds (recorded, flagged) and then --runs measured rounds. Every round runs
  each configuration once, in a freshly shuffled order, so drift and background noise land
  on all configurations equally.
- Records two timings per run: build_ms, the program's own "indexed in" figure (the main
  metric; excludes process start-up), and wall_ms, the whole process measured from outside.
  Phase timings (index_ms, merge_ms) are recorded when the program prints them.
- Checks every run's document and distinct-word counts, so a broken optimization shows up.
- Shows a progress bar in an interactive terminal (runs done, round, elapsed, ETA). When output
  goes to a file (nohup, > log), the bar is off and a summary line is printed every 10 rounds.
- Writes bench/results/<timestamp>_<name>.feather (rewritten at checkpoints, so an
  interrupted run keeps its data) and a .json sidecar describing machine, toolchains,
  corpus and settings.
"""
import argparse
import hashlib
import json
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"
RESULTS = BENCH / "results"
SNAPSHOTS = Path.home() / "bench-bins"
CORPUS_COPY = Path.home() / "bench-data"
QUERY = "whale"  # the Rust program needs a query; search time is outside build_ms
PY_MODES = ["seq", "process", "thread"]

# Durations as printed by Rust's Duration Debug ("146.2ms", "1.2s") and by index_bench.py ("963.1 ms").
UNIT_MS = {"ns": 1e-6, "µs": 1e-3, "μs": 1e-3, "us": 1e-3, "ms": 1.0, "s": 1000.0}
DUR = r"([0-9]+(?:\.[0-9]+)?)\s*(ns|µs|μs|us|ms|s)\b"
TIMINGS = {
    "build_ms": re.compile(r"indexed in " + DUR),
    "index_ms": re.compile(r"per-file indexing:\s*" + DUR),
    "merge_ms": re.compile(r"merge:\s*" + DUR),
}
COUNTS = re.compile(r"(\d+) documents, (\d+) distinct words")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sh(cmd, **kwargs):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, **kwargs).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_state():
    git = ["git", "-c", "safe.directory=*", "--no-optional-locks", "-C", str(REPO)]
    status = sh(git + ["status", "--porcelain", "--untracked-files=no"])
    return {"commit": sh(git + ["rev-parse", "HEAD"]), "dirty": bool(status) if status is not None else None}


def machine_info():
    info = {
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "cpus_available": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
        "in_container": Path("/.dockerenv").exists(),
    }
    try:
        cpuinfo = Path("/proc/cpuinfo").read_text()
        info["cpu_model"] = next((l.split(":", 1)[1].strip() for l in cpuinfo.splitlines() if l.startswith("model name")), None)
        meminfo = Path("/proc/meminfo").read_text()
        info["mem_total"] = next((l.split(":", 1)[1].strip() for l in meminfo.splitlines() if l.startswith("MemTotal")), None)
    except OSError:
        pass
    return info


# ---------------------------------------------------------------- snapshot

def cmd_snapshot(args):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.label):
        sys.exit("Snapshot labels may use letters, digits, '.', '_' and '-' only.")
    dest = SNAPSHOTS / args.label
    if dest.exists() and not args.force:
        sys.exit(f"Snapshot '{args.label}' already exists. Use --force to replace it.")

    print("Building: cargo build --release")
    if subprocess.run(["cargo", "build", "--release"], cwd=REPO).returncode != 0:
        sys.exit("cargo build failed; snapshot not taken.")

    with open(REPO / "Cargo.toml", "rb") as f:
        crate = tomllib.load(f)["package"]["name"]
    binary = Path(os.environ.get("CARGO_TARGET_DIR", REPO / "target")) / "release" / crate

    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, dest / "bin")
    meta = {
        "label": args.label,
        "created": now_iso(),
        "note": args.note,
        "git": git_state(),
        "rustc": sh(["rustc", "--version"], cwd=REPO),
        "binary_sha256": sha256_file(dest / "bin"),
        "main_rs_sha256": sha256_file(REPO / "src" / "main.rs"),
        "cargo_toml_sha256": sha256_file(REPO / "Cargo.toml"),
    }
    (dest / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"Snapshot '{args.label}' saved to {dest}")


def load_snapshots():
    snaps = []
    if SNAPSHOTS.exists():
        for d in SNAPSHOTS.iterdir():
            if (d / "bin").exists() and (d / "meta.json").exists():
                snaps.append(json.loads((d / "meta.json").read_text()))
    return sorted(snaps, key=lambda m: m["created"])


def cmd_snapshots(_args):
    snaps = load_snapshots()
    if not snaps:
        print("No snapshots yet. Take one with: uv run bench/run_bench.py snapshot <label>")
    for m in snaps:
        dirty = " (uncommitted changes)" if m["git"].get("dirty") else ""
        print(f"{m['label']:<16} {m['created']}  commit {str(m['git'].get('commit'))[:8]}{dirty}  {m.get('note') or ''}")


# ---------------------------------------------------------------- progress bar

class ProgressBar:
    """A one-line progress bar for interactive terminals. Does nothing when disabled."""

    def __init__(self, total, enabled):
        self.total, self.enabled = total, enabled
        self.done, self.label = 0, ""
        self.start = time.perf_counter()

    def update(self, label):
        self.done += 1
        self.label = label
        self.draw()

    def draw(self):
        if not self.enabled:
            return
        elapsed = time.perf_counter() - self.start
        frac = self.done / self.total if self.total else 1.0
        eta = elapsed / self.done * (self.total - self.done) if self.done else 0.0
        info = (f" {frac:4.0%}  {self.done:,}/{self.total:,} runs  {self.label}  "
                f"elapsed {fmt_duration(elapsed)}  ETA {fmt_duration(eta) if self.done else '--'}")
        cols = shutil.get_terminal_size((100, 20)).columns
        width = max(10, min(40, cols - len(info) - 3))
        filled = int(width * frac)
        line = f"|{'█' * filled}{'░' * (width - filled)}|{info}"
        sys.stdout.write("\r\033[K" + line[: cols - 1])
        sys.stdout.flush()

    def write(self, message):
        """Print a message above the bar without breaking it."""
        if self.enabled:
            sys.stdout.write("\r\033[K")
        print(message, flush=True)
        self.draw()

    def close(self):
        if self.enabled:
            self.draw()
            sys.stdout.write("\n")
            sys.stdout.flush()
            self.enabled = False


# ---------------------------------------------------------------- run

def prepare_corpus(src, dest):
    files = sorted(p for p in src.glob("*.txt"))
    if not files:
        sys.exit(f"No .txt files in {src}.")
    dest.mkdir(parents=True, exist_ok=True)
    extra = sorted(p.name for p in dest.glob("*.txt") if not (src / p.name).exists())
    if extra:
        sys.exit(f"{dest} has files that aren't in {src}: {', '.join(extra[:5])}... "
                 f"Remove them or choose another folder with --corpus-dir.")
    copied = 0
    for p in files:
        d = dest / p.name
        if not d.exists() or d.stat().st_size != p.stat().st_size:
            shutil.copy2(p, d)
            copied += 1
    digests = {p.name: sha256_file(dest / p.name) for p in files}
    combined = hashlib.sha256("".join(f"{n}:{h}\n" for n, h in sorted(digests.items())).encode()).hexdigest()
    total = sum((dest / n).stat().st_size for n in digests)
    print(f"Corpus: {len(files)} files, {total / 1e6:.1f} MB in {dest} ({copied} copied)")
    return {"source": str(src), "path": str(dest), "files": len(files), "bytes": total, "sha256": combined}


def build_configs(args, corpus):
    configs = []
    if not args.no_python:
        for mode in PY_MODES:
            configs.append({
                "config": f"python/{mode}", "language": "python",
                "variant": f"cpython-{platform.python_version()}", "mode": mode,
                "cmd": [sys.executable, str(BENCH / "index_bench.py"), corpus, mode],
                "env": {},
            })
    snaps = {m["label"]: m for m in load_snapshots()}
    labels = list(snaps) if args.rust is None else [l for l in args.rust.split(",") if l and l != "none"]
    for label in labels:
        if label not in snaps:
            sys.exit(f"No snapshot named '{label}'. Available: {', '.join(snaps) or 'none'}")
        binary = str(SNAPSHOTS / label / "bin")
        for mode, threads in [("1-thread", "1"), ("rayon", None)]:
            configs.append({
                "config": f"rust/{label}/{mode}", "language": "rust", "variant": label, "mode": mode,
                "cmd": [binary, corpus, QUERY], "env": {"RAYON_NUM_THREADS": threads},
            })
    if not configs:
        sys.exit("Nothing to run: no Python configurations and no Rust snapshots.")
    return configs, [snaps[l] for l in labels]


def run_once(config):
    env = dict(os.environ)
    for key, value in config["env"].items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    t0 = time.perf_counter()
    proc = subprocess.run(config["cmd"], capture_output=True, text=True, env=env)
    wall_ms = (time.perf_counter() - t0) * 1000

    # Timings and counts may be printed to either stream, so search both.
    text = proc.stdout + "\n" + proc.stderr
    row = {"wall_ms": wall_ms, "exit_code": proc.returncode, "error": None}
    for name, pattern in TIMINGS.items():
        m = pattern.search(text)
        row[name] = float(m.group(1)) * UNIT_MS[m.group(2)] if m else float("nan")
    m = COUNTS.search(text)
    row["docs"], row["distinct_words"] = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    if proc.returncode != 0 or row["build_ms"] != row["build_ms"]:  # NaN check
        reason = f"exit code {proc.returncode}" if proc.returncode != 0 else "no 'indexed in <time>' found in its output"
        row["error"] = f"{reason}: {(proc.stderr.strip() or proc.stdout.strip())[-400:]}"
    return row


def save(rows, path):
    import pandas as pd

    df = pd.DataFrame(rows)
    # Each language must agree with itself on the counts; a mismatch means a broken build.
    df["counts_match"] = False
    for lang, group in df[df["exit_code"] == 0].groupby("language"):
        expected = Counter(zip(group["docs"], group["distinct_words"])).most_common(1)[0][0]
        df.loc[group.index, "counts_match"] = (group["docs"] == expected[0]) & (group["distinct_words"] == expected[1])
    df["ok"] = (df["exit_code"] == 0) & df["counts_match"] & df["build_ms"].notna()
    try:
        df.to_feather(path)
        return path
    except ImportError:  # pyarrow missing: fall back to CSV rather than lose the data
        csv = path.with_suffix(".csv")
        df.to_csv(csv, index=False)
        return csv


def fmt_duration(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def cmd_run(args):
    corpus = prepare_corpus(REPO / "data", Path(args.corpus_dir).expanduser())
    configs, snaps = build_configs(args, corpus["path"])
    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**32)
    rng = random.Random(seed)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"{stamp}_{args.name}.feather"
    meta = {
        "experiment": args.name, "created": now_iso(), "seed": seed,
        "runs": args.runs, "warmup_rounds": args.warmup, "query": QUERY,
        "configs": [{k: c[k] for k in ("config", "language", "variant", "mode", "cmd", "env")} for c in configs],
        "python": {"executable": sys.executable, "version": sys.version},
        "rustc": sh(["rustc", "--version"], cwd=REPO),
        "rust_snapshots": snaps, "git": git_state(), "machine": machine_info(), "corpus": corpus,
        "notes": "build_ms = program's own timer (main metric). wall_ms = whole process from outside.",
    }
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))

    total_rounds = args.warmup + args.runs
    print(f"{len(configs)} configurations x ({args.warmup} warm-up + {args.runs} measured) rounds -> {out.name}")
    rows, measured = [], defaultdict(int)
    recent = defaultdict(list)
    bar = ProgressBar(total_rounds * len(configs), enabled=not args.no_bar and sys.stdout.isatty())
    every = args.progress or (100 if bar.enabled else 10)
    start = time.perf_counter()
    bar.draw()
    try:
        for rnd in range(total_rounds):
            warmup = rnd < args.warmup
            order = configs[:]
            rng.shuffle(order)
            for pos, config in enumerate(order):
                row = {
                    "experiment": args.name, "round": rnd, "position": pos,
                    "config": config["config"], "language": config["language"],
                    "variant": config["variant"], "mode": config["mode"],
                    "warmup": warmup, "run_index": -1 if warmup else measured[config["config"]],
                    "timestamp": now_iso(),
                }
                row.update(run_once(config))
                rows.append(row)
                bar.update(f"{'warm-up · ' if warmup else ''}round {rnd + 1}/{total_rounds}")
                if row["error"]:
                    bar.write(f"  ! {config['config']} failed: {row['error'][-200:]}")
                if not warmup:
                    measured[config["config"]] += 1
                    recent[config["config"]] = (recent[config["config"]] + [row["build_ms"]])[-50:]

            done = rnd + 1
            if done % args.checkpoint == 0 or done == total_rounds:
                save(rows, out)
            if done % every == 0 or done == total_rounds:
                elapsed = time.perf_counter() - start
                eta = elapsed / done * (total_rounds - done)
                medians = "  ".join(f"{c}: {statistics.median(v):.0f}" for c, v in recent.items() if v)
                bar.write(f"round {done}/{total_rounds}  elapsed {fmt_duration(elapsed)}  ETA {fmt_duration(eta)}  "
                          f"median ms (last 50): {medians}")
        bar.close()
    except KeyboardInterrupt:
        bar.close()
        print("Interrupted; saving what was measured.")
    written = save(rows, out)
    failures = sum(1 for r in rows if r["error"])
    print(f"Saved {len(rows)} runs to {written}" + (f" ({failures} failed)" if failures else ""))
    print(f"Next: uv run --python 3.14 bench/analyze.py {written.relative_to(REPO)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("snapshot", help="build the Rust program and keep a copy under a label")
    p.add_argument("label")
    p.add_argument("--note", default=None, help="what changed in this version")
    p.add_argument("--force", action="store_true", help="replace an existing snapshot")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("snapshots", help="list Rust snapshots")
    p.set_defaults(func=cmd_snapshots)

    p = sub.add_parser("run", help="run an experiment")
    p.add_argument("--runs", type=int, default=1000, help="measured rounds (default 1000)")
    p.add_argument("--warmup", type=int, default=5, help="warm-up rounds, recorded but flagged (default 5)")
    p.add_argument("--name", default="run", help="experiment name, used in the file name")
    p.add_argument("--rust", default=None, help="comma-separated snapshot labels (default: all; 'none' for none)")
    p.add_argument("--no-python", action="store_true", help="skip the Python configurations")
    p.add_argument("--corpus-dir", default=str(CORPUS_COPY), help="container-local copy of data/")
    p.add_argument("--seed", type=int, default=None, help="shuffle seed (default: random, recorded)")
    p.add_argument("--checkpoint", type=int, default=25, help="save every N rounds (default 25)")
    p.add_argument("--progress", type=int, default=None,
                   help="print a summary line every N rounds (default 100 with the bar, 10 without)")
    p.add_argument("--no-bar", action="store_true", help="turn off the progress bar")
    p.set_defaults(func=cmd_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
