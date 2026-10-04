# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow>=17"]
# ///
"""Benchmark the index build: Python (seq, process, thread) against Rust snapshots.

Run from the repo root, inside the dev container:

    uv run --python 3.14 bench/run_bench.py snapshot baseline      # build Rust, keep a copy named "baseline"
    uv run --python 3.14 bench/run_bench.py run --runs 20          # smoke test
    uv run --python 3.14 bench/run_bench.py run --rust baseline --extra-python 3.14t --runs 1000 --name languages
    uv run --python 3.14 bench/run_bench.py verify --rust baseline --extra-python 3.14t   # outputs only

Tuning experiments use rayon as the baseline. After each change: commit, take a snapshot, then
run every snapshot so far in rayon mode only, so each experiment adds one line to the chart:

    uv run --python 3.14 bench/run_bench.py snapshot s1-profile --note "lto, codegen-units"
    uv run --python 3.14 bench/run_bench.py run --no-python --rust-modes rayon \
        --rust baseline,s1-profile --runs 1000 --name s1-profile

What one experiment does:

- Copies data/*.txt to a container-local folder once (~/bench-data), so runs don't read
  through the Windows-mounted folder.
- Builds the configurations: python/seq, python/process, python/thread; python<label>/thread
  for each --extra-python interpreter (for example python3.14t/thread, free-threaded); and for
  every Rust snapshot the modes in --rust-modes: rust/<label>/1-thread (RAYON_NUM_THREADS=1)
  and rust/<label>/rayon (all cores). Python's thread and process modes use one worker per
  available CPU, rayon's default, so the parallel configurations run at the same width.
  Snapshots run in the order given to --rust (default: the order they were taken), and that
  order is kept in the charts.
- Verifies outputs first (skip with --no-verify): every configuration runs once with
  INDEX_DUMP set and writes its whole index in a canonical text form (see index_bench.py).
  The dumps' SHA-256 must all match; if not, the first differing line is shown and the run
  stops. A build that can't dump yet (no INDEX_DUMP support) is reported as not checked.
- Runs warm-up rounds (recorded, flagged) and then --runs measured rounds. Every round runs
  each configuration once, in a freshly shuffled order, so drift and background noise land
  on all configurations equally.
- Records per run:
  - build_ms, the program's own "indexed in" figure (the main metric; excludes process
    start-up), and wall_ms, the whole process measured from outside. Phase timings
    (index_ms, merge_ms) are recorded when the program prints them.
  - query_ms: the average time per search query, when a snapshot prints it. Every Rust run
    gets QUERY_BENCH=<QUERY_REPS>; snapshots that support it run their built-in query set that
    many times after the build, outside build_ms (wall_ms and cpu_ms include it).
  - cpu_ms: user + system CPU time of the whole process tree, all threads and child
    processes included. cpu_ms / wall_ms is the number of cores in use on average.
  - peak_rss_mb: peak memory of the largest single process; peak_tree_rss_mb: peak total
    memory across the process tree (sampled every 5 ms, so approximate, and memory shared
    between processes is counted in each of them).
  - threads (workers or rayon threads) and, for Python, whether the GIL was on.
  How: CPU time comes from the operating system for the process and every descendant it
  waited for (wait4). Python's process pool (forkserver, the default on Linux since 3.14) runs
  its workers under a helper process the main process never waits for, so the runner also
  samples the process tree from /proc and keeps the larger CPU figure. Memory comes only from
  /proc (each process's VmHWM, its peak since it started its program, and current RSS for the
  tree total): the operating system's own peak-memory figure (wait4's ru_maxrss) includes the
  runner's memory, inherited when the child process is created, so it isn't used.
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
import math
import os
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
import tomllib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "bench"
RESULTS = BENCH / "results"
SNAPSHOTS = Path.home() / "bench-bins"
CORPUS_COPY = Path.home() / "bench-data"
QUERY = "whale"  # the Rust program needs a query; search time is outside build_ms
QUERY_REPS = 50  # QUERY_BENCH: repetitions of a snapshot's built-in query set, for query_ms
PY_MODES = ["seq", "process", "thread"]
RUST_MODES = {"1-thread": "1", "rayon": None}  # mode -> RAYON_NUM_THREADS (None = all cores)
VERIFY_ROOT = Path.home() / "bench-verify"
SAMPLE_SECONDS = 0.005  # how often the process tree is sampled for memory and CPU
PAGE_BYTES = os.sysconf("SC_PAGE_SIZE")
CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
CPUS = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)

# Durations as printed by Rust's Duration Debug ("146.2ms", "1.2s") and by index_bench.py ("963.1 ms").
UNIT_MS = {"ns": 1e-6, "µs": 1e-3, "μs": 1e-3, "us": 1e-3, "ms": 1.0, "s": 1000.0}
DUR = r"([0-9]+(?:\.[0-9]+)?)\s*(ns|µs|μs|us|ms|s)\b"
TIMINGS = {
    "build_ms": re.compile(r"indexed in " + DUR),
    "index_ms": re.compile(r"per-file indexing:\s*" + DUR),
    "merge_ms": re.compile(r"merge:\s*" + DUR),
    "query_ms": re.compile(r"query:\s*" + DUR),
}
COUNTS = re.compile(r"(\d{1,15}) documents, (\d{1,15}) distinct words")  # bounded: no backtracking blow-up
WORKERS = re.compile(r"workers:\s*(\d{1,6})")
GIL = re.compile(r"\bGIL (on|off)\b")


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

    build = ["cargo", "build", "--release"] + (["--features", args.features] if args.features else [])
    print("Building: " + " ".join(build))
    if subprocess.run(build, cwd=REPO).returncode != 0:
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
        "features": args.features,
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
        features = f" [features: {m['features']}]" if m.get("features") else ""
        print(f"{m['label']:<16} {m['created']}  commit {str(m['git'].get('commit'))[:8]}{dirty}{features}  {m.get('note') or ''}")


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


def resolve_python(spec):
    """'3.14t' (located with uv) or 'LABEL=/path/to/python' -> (label, executable, version, gil_on)."""
    if "=" in spec:
        label, exe = (part.strip() for part in spec.split("=", 1))
    else:
        label = spec.strip()
        uv = os.environ.get("UV") or shutil.which("uv")
        if not uv:
            sys.exit(f"Can't find uv to locate Python {label}. Pass --extra-python {label}=/path/to/python instead.")
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}  # don't pick the runner's own venv
        exe = sh([uv, "python", "find", label], env=env)
        if not exe:
            sys.exit(f"uv can't find Python {label}. Install it first: uv python install {label}")
    info = sh([exe, "-c", "import platform, sys; "
               "print(platform.python_version(), getattr(sys, '_is_gil_enabled', lambda: True)())"])
    if not info:
        sys.exit(f"Couldn't run {exe}.")
    version, gil = info.split()
    return label, exe, version, gil == "True"


def build_configs(args, corpus):
    configs = []
    script = str(BENCH / "index_bench.py")
    if not args.no_python:
        for mode in PY_MODES:
            configs.append({
                "config": f"python/{mode}", "language": "python",
                "variant": f"cpython-{platform.python_version()}", "mode": mode,
                "cmd": [sys.executable, script, corpus, mode],
                "env": {}, "threads": 1 if mode == "seq" else None,
            })
    for spec in [s for s in args.extra_python.split(",") if s.strip()]:
        label, exe, version, gil_on = resolve_python(spec)
        variant = f"cpython-{version}" + ("" if gil_on else " (free-threaded)")
        print(f"Extra Python {label}: {exe} ({variant}{', GIL on' if gil_on else ''})")
        configs.append({
            "config": f"python{label}/thread", "language": "python", "variant": variant, "mode": "thread",
            "cmd": [exe, script, corpus, "thread"], "env": {}, "threads": None,
        })
    snaps = {m["label"]: m for m in load_snapshots()}
    labels = list(snaps) if args.rust is None else [
        l.strip() for l in args.rust.split(",") if l.strip() and l.strip() != "none"]
    modes = [m.strip() for m in args.rust_modes.split(",") if m.strip()]
    unknown = [m for m in modes if m not in RUST_MODES]
    if unknown or not modes:
        sys.exit(f"--rust-modes takes {', '.join(RUST_MODES)} (comma-separated); got '{args.rust_modes}'.")
    for label in labels:
        if label not in snaps:
            sys.exit(f"No snapshot named '{label}'. Available: {', '.join(snaps) or 'none'}")
        binary = str(SNAPSHOTS / label / "bin")
        for mode in modes:
            threads = RUST_MODES[mode]
            configs.append({
                "config": f"rust/{label}/{mode}", "language": "rust", "variant": label, "mode": mode,
                "cmd": [binary, corpus, QUERY], "env": {"RAYON_NUM_THREADS": threads, "QUERY_BENCH": str(QUERY_REPS)},
                "threads": int(threads) if threads else CPUS,
            })
    if not configs:
        sys.exit("Nothing to run: no Python configurations and no Rust snapshots.")
    return configs, [snaps[l] for l in labels]


class TreeSampler(threading.Thread):
    """Samples a process and all its descendants from /proc every few milliseconds.

    Keeps the peak total memory across the tree, the peak of the largest single process, and
    each process's last-seen CPU time.
    """

    def __init__(self, root):
        super().__init__(daemon=True)
        self.root = root
        self.stopping = threading.Event()
        self.peak_tree = 0    # bytes
        self.peak_single = 0  # bytes
        self.cpu_ticks = {}   # pid -> last-seen user + system time, in clock ticks
        self.samples = 0

    @staticmethod
    def read_procs():
        """pid -> (parent pid, CPU ticks, resident pages) for every process."""
        procs = {}
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open(f"/proc/{name}/stat", "rb") as f:
                    data = f.read()
            except OSError:
                continue
            # After "pid (command) ": state, ppid, ... utime is the 12th field, stime the 13th, rss the 22nd.
            rest = data[data.rfind(b")") + 2:].split()
            procs[int(name)] = (int(rest[1]), int(rest[11]) + int(rest[12]), int(rest[21]))
        return procs

    @staticmethod
    def hwm(pid):
        """A process's peak resident memory since it started its current program (VmHWM), in bytes."""
        try:
            with open(f"/proc/{pid}/status", "rb") as f:
                for line in f:
                    if line.startswith(b"VmHWM:"):
                        return int(line.split()[1]) * 1024
        except OSError:
            pass
        return 0  # gone, or a zombie with no memory left

    def sample(self):
        procs = self.read_procs()
        children = defaultdict(list)
        for pid, (ppid, _, _) in procs.items():
            children[ppid].append(pid)
        tree, stack = [], [self.root]
        while stack:
            pid = stack.pop()
            if pid in procs:
                tree.append(pid)
                stack.extend(children.get(pid, ()))
        if not tree:
            return
        rss = [procs[p][2] * PAGE_BYTES for p in tree]
        self.peak_tree = max(self.peak_tree, sum(rss))
        self.peak_single = max(self.peak_single, max(rss), max(self.hwm(p) for p in tree))
        for p in tree:
            self.cpu_ticks[p] = max(self.cpu_ticks.get(p, 0), procs[p][1])
        self.samples += 1

    def run(self):
        while not self.stopping.is_set():
            try:
                self.sample()
            except (OSError, ValueError, IndexError):  # a process vanishing mid-read is normal
                pass
            self.stopping.wait(SAMPLE_SECONDS)

    def finish(self):
        self.stopping.set()
        self.join()
        return self.samples, self.peak_tree / 2**20, self.peak_single / 2**20, \
            sum(self.cpu_ticks.values()) * 1000 / CLOCK_TICKS


def run_once(config, extra_env=None):
    env = dict(os.environ)
    for key, value in {**config["env"], **(extra_env or {})}.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    t0 = time.perf_counter()
    proc = subprocess.Popen(config["cmd"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    sampler = TreeSampler(proc.pid)
    sampler.start()
    out, err = [], []
    readers = [threading.Thread(target=lambda s=s, b=b: b.append(s.read()), daemon=True)
               for s, b in ((proc.stdout, out), (proc.stderr, err))]
    for r in readers:
        r.start()
    # wait4 rather than proc.wait(): it also returns the CPU time and peak memory of the process
    # and of every descendant it waited for.
    _, status, usage = os.wait4(proc.pid, 0)
    wall_ms = (time.perf_counter() - t0) * 1000
    proc.returncode = os.waitstatus_to_exitcode(status)
    for r in readers:
        r.join()
    samples, tree_mb, single_mb, cpu_sampled_ms = sampler.finish()
    stdout = out[0].decode("utf-8", "replace") if out else ""
    stderr = err[0].decode("utf-8", "replace") if err else ""

    cpu_wait4_ms = (usage.ru_utime + usage.ru_stime) * 1000
    # Not usage.ru_maxrss: it counts the runner's own memory, copied into the child when it's created.
    peak_rss_mb = single_mb if samples else float("nan")
    row = {
        "wall_ms": wall_ms, "exit_code": proc.returncode, "error": None,
        # Both CPU figures can only miss time, never add it, so the larger is the better estimate.
        "cpu_ms": max(cpu_wait4_ms, cpu_sampled_ms), "cpu_wait4_ms": cpu_wait4_ms, "cpu_sampled_ms": cpu_sampled_ms,
        "peak_rss_mb": peak_rss_mb, "peak_tree_rss_mb": max(tree_mb, peak_rss_mb) if samples else float("nan"),
        "mem_samples": samples,
    }

    # Timings and counts may be printed to either stream, so search both.
    text = stdout + "\n" + stderr
    for name, pattern in TIMINGS.items():
        m = pattern.search(text)
        row[name] = float(m.group(1)) * UNIT_MS[m.group(2)] if m else float("nan")
    m = COUNTS.search(text)
    row["docs"], row["distinct_words"] = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
    m = WORKERS.search(text)
    row["threads"] = int(m.group(1)) if m else config.get("threads")
    m = GIL.search(text)
    row["gil"] = m.group(1) if m else None
    if proc.returncode != 0 or math.isnan(row["build_ms"]):
        reason = f"exit code {proc.returncode}" if proc.returncode != 0 else "no 'indexed in <time>' found in its output"
        row["error"] = f"{reason}: {(stderr.strip() or stdout.strip())[-400:]}"
    return row


def first_difference(a, b):
    """Line number and the two lines where text files a and b first differ."""
    with open(a, encoding="utf-8", errors="replace") as fa, open(b, encoding="utf-8", errors="replace") as fb:
        for n, (la, lb) in enumerate(zip_longest(fa, fb), start=1):
            if la != lb:
                return n, (la or "<end of file>").rstrip("\n")[:160], (lb or "<end of file>").rstrip("\n")[:160]
    return None


def verify(configs):
    """Run each configuration once with INDEX_DUMP set and compare the dumps' SHA-256."""
    out_dir = VERIFY_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    print("Verifying outputs: every configuration writes its whole index once")
    results = []
    for config in configs:
        path = out_dir / (re.sub(r"[^A-Za-z0-9_.-]+", "_", config["config"]) + ".txt")
        row = run_once(config, {"INDEX_DUMP": str(path)})
        entry = {"config": config["config"], "error": row["error"]}
        if path.exists():
            entry["sha256"] = sha256_file(path)
            with open(path, "rb") as f:
                entry["lines"] = sum(1 for _ in f)
            entry["dump"] = str(path)
        results.append(entry)
        if row["error"]:
            status = f"FAILED: {row['error'][-120:]}"
        elif "sha256" in entry:
            status = f"sha256 {entry['sha256'][:16]}…  {entry['lines']:,} lines"
        else:
            status = "not checked (this build doesn't write INDEX_DUMP yet)"
        print(f"  {config['config']:<30} {status}")

    dumped = [r for r in results if "sha256" in r]
    digests = {r["sha256"] for r in dumped}
    failed = [r for r in results if r["error"]]
    if len(digests) > 1:
        ref = dumped[0]
        print("  ! The outputs differ:")
        for r in dumped[1:]:
            if r["sha256"] != ref["sha256"]:
                n, a, b = first_difference(ref["dump"], r["dump"])
                print(f"    {r['config']} vs {ref['config']}, first difference at line {n:,}:")
                print(f"      {ref['config']}: {a}")
                print(f"      {r['config']}: {b}")
        print(f"  The dumps are kept in {out_dir} for diffing.")
    elif len(dumped) > 1:
        print(f"  All {len(dumped)} dumps are identical.")
        shutil.rmtree(out_dir, ignore_errors=True)  # nothing to inspect; they're tens of MB each
    else:
        shutil.rmtree(out_dir, ignore_errors=True)
        if not failed:
            print("  Fewer than two configurations could dump, so nothing was compared.")
    summary = {
        "identical": len(digests) <= 1, "compared": len(dumped), "failed": len(failed),
        "results": [{k: v for k, v in r.items() if k != "dump"} for r in results],
    }
    return summary, len(digests) <= 1 and not failed


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
        "runs": args.runs, "warmup_rounds": args.warmup, "query": QUERY, "query_bench_reps": QUERY_REPS,
        "configs": [{k: c[k] for k in ("config", "language", "variant", "mode", "cmd", "env", "threads")}
                    for c in configs],
        "python": {"executable": sys.executable, "version": sys.version},
        "rustc": sh(["rustc", "--version"], cwd=REPO),
        "rust_snapshots": snaps, "git": git_state(), "machine": machine_info(), "corpus": corpus,
        "memory_method": "proc-vmhwm",  # files without this recorded memory with the runner's own included
        "notes": ("build_ms = program's own timer (main metric). wall_ms = whole process from outside. "
                  "cpu_ms = user+system CPU of the process tree. peak_tree_rss_mb is sampled every "
                  f"{SAMPLE_SECONDS * 1000:.0f} ms."),
    }
    if not args.no_verify:
        meta["verify"], ok = verify(configs)
        if not ok:
            out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
            sys.exit("Stopped before timing: the outputs differ or a configuration failed (details above). "
                     "Use --no-verify to time anyway.")
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
            # Not security-sensitive: this only shuffles run order, and it is seeded (the seed is
            # recorded) so an experiment's order can be replayed. A cryptographic RNG can't be seeded.
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


def cmd_verify(args):
    corpus = prepare_corpus(REPO / "data", Path(args.corpus_dir).expanduser())
    configs, _ = build_configs(args, corpus["path"])
    _, ok = verify(configs)
    sys.exit(0 if ok else 1)


def add_config_args(p):
    """Options that choose the configurations; shared by run and verify."""
    p.add_argument("--rust", default=None, help="comma-separated snapshot labels (default: all; 'none' for none)")
    p.add_argument("--rust-modes", default="1-thread,rayon",
                   help="Rust modes per snapshot: 1-thread, rayon, or both (default both; tuning uses rayon)")
    p.add_argument("--no-python", action="store_true", help="skip the Python configurations")
    p.add_argument("--extra-python", default="",
                   help="more interpreters to run in thread mode, comma-separated: a uv version such as "
                        "3.14t, or LABEL=/path/to/python")
    p.add_argument("--corpus-dir", default=str(CORPUS_COPY), help="container-local copy of data/")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("snapshot", help="build the Rust program and keep a copy under a label")
    p.add_argument("label")
    p.add_argument("--note", default=None, help="what changed in this version")
    p.add_argument("--force", action="store_true", help="replace an existing snapshot")
    p.add_argument("--features", default=None,
                   help="Cargo features to build with, comma-separated (e.g. ahash); recorded with the snapshot")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("snapshots", help="list Rust snapshots")
    p.set_defaults(func=cmd_snapshots)

    p = sub.add_parser("run", help="run an experiment")
    p.add_argument("--runs", type=int, default=1000, help="measured rounds (default 1000)")
    p.add_argument("--warmup", type=int, default=5, help="warm-up rounds, recorded but flagged (default 5)")
    p.add_argument("--name", default="run", help="experiment name, used in the file name")
    add_config_args(p)
    p.add_argument("--no-verify", action="store_true", help="skip the output check before timing")
    p.add_argument("--seed", type=int, default=None, help="shuffle seed (default: random, recorded)")
    p.add_argument("--checkpoint", type=int, default=25, help="save every N rounds (default 25)")
    p.add_argument("--progress", type=int, default=None,
                   help="print a summary line every N rounds (default 100 with the bar, 10 without)")
    p.add_argument("--no-bar", action="store_true", help="turn off the progress bar")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("verify", help="check that every configuration builds an identical index, without timing")
    add_config_args(p)
    p.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
