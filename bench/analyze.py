# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow>=17", "matplotlib>=3.9", "numpy>=2"]
# ///
"""Summarize a benchmark results file and draw its charts.

    uv run --python 3.14 bench/analyze.py                                   # newest results file
    uv run --python 3.14 bench/analyze.py bench/results/<file>.feather
    uv run --python 3.14 bench/analyze.py <file> --reference rust/baseline/1-thread

Speed-ups are against python/seq when the file has it; otherwise against the first snapshot's
rayon configuration (the tuning baseline). --reference overrides both.

Writes into bench/results/<file stem>/:

- summary.csv / summary.md: per configuration n, mean, SD, CV, percentiles, the median with a
  95% bootstrap confidence interval, phase medians, and speed-up against the reference; and a
  resources table: threads, GIL, CPU time, cores in use (CPU time / wall time), peak memory of
  the largest process and of the whole process tree (medians; files from before these were
  recorded leave it out).
- steps.csv: when there are two or more Rust snapshots, each one's change against the first
  snapshot and against the previous one, per mode, with 95% bootstrap intervals.
- Query time, when snapshots print it (QUERY_BENCH): the median time per search query in µs
  with a 95% interval (summary), and its change against the previous snapshot (steps). Columns
  stay empty for snapshots that don't print it.
- run_sequence*.png: build time against run number. Every configuration in a chart shares one
  y-axis (starting at 0) and has its own color, named in the key; Rust lines are dashed.
  - run_sequence.png, for a language comparison (Python plus one Rust snapshot, 8
    configurations at most): everything on one chart.
  - run_sequence_python.png and run_sequence_rust.png: the same split by language, when there
    are more than 8 configurations.
  - run_sequence_rust_rayon.png (and _1-thread, if run), when the file has two or more Rust
    snapshots: one chart per mode, the snapshots in step order. A tuning experiment run with
    --rust-modes rayon gives one chart that gains a line with every step.
  Older run_sequence*.png files in the folder are replaced.
  Default band (--band pct): rolling median with the rolling 16th-84th percentiles, the range
  +/-1 SD covers for normally distributed data, but not stretched by single outliers. --band sd
  draws the rolling mean +/-1 SD instead. Window = 5% of the runs, at least 10. A chart holds at
  most 8 configurations; a group with more is split into numbered parts.
- distribution.png: median, middle 50% and 5th-95th percentile per configuration.
- steps.png: median per Rust snapshot, per mode (when there are two or more snapshots).

Warm-up rounds and runs that failed or returned the wrong counts are excluded and reported.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "bench" / "results"
PY_MODES = ["seq", "process", "thread"]
RUST_MODES = ["1-thread", "rayon"]
BOOTSTRAP = 2000

# Colors validated with the dataviz palette checker on the light surface.
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
LANG_COLOR = {"python": "#2a78d6", "rust": "#eb6834"}
MODE_STYLE = {"1-thread": ("#1baf7a", "o"), "rayon": ("#eb6834", "s")}
# Series colors in fixed order. Validated: all 8 on adjacent pairs, the first 3 on all pairs.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 9, "text.color": INK,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.75, "axes.labelcolor": INK2,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
    "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
    "legend.frameon": False, "lines.solid_capstyle": "round",
})


def load(path):
    df = pd.read_feather(path) if path.suffix == ".feather" else pd.read_csv(path)
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return df, meta


def config_order(df, meta):
    labels = [s["label"] for s in meta.get("rust_snapshots", [])]
    labels += sorted(set(df.loc[df.language == "rust", "variant"]) - set(labels))
    present = list(dict.fromkeys(df["config"]))
    preferred = [f"python/{m}" for m in PY_MODES]
    preferred += sorted(c for c in present if c.startswith("python") and c not in preferred)  # e.g. python3.14t
    preferred += [f"rust/{l}/{m}" for l in labels for m in RUST_MODES]
    return [c for c in preferred if c in present] + [c for c in present if c not in preferred], labels


def boot_medians(x, rng):
    idx = rng.integers(0, len(x), size=(BOOTSTRAP, len(x)))
    return np.median(x[idx], axis=1)


def ci(values):
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def query_us(d):
    """Per-query search times in µs, or None when the configuration doesn't print them."""
    if "query_ms" not in d.columns or not d["query_ms"].notna().any():
        return None
    return d["query_ms"].dropna().to_numpy() * 1000


def summarize(data, order, reference, rng):
    boots = {c: boot_medians(data[c]["build_ms"].to_numpy(), rng) for c in order}
    qboots = {c: boot_medians(query_us(data[c]), rng) for c in order if query_us(data[c]) is not None}
    ref_median = float(np.median(data[reference]["build_ms"]))
    rows = []
    for c in order:
        d = data[c]
        x = d["build_ms"].to_numpy()
        lo, hi = ci(boots[c])
        s_lo, s_hi = ci(boots[reference] / boots[c])
        q = query_us(d)
        q_lo, q_hi = ci(qboots[c]) if c in qboots else (float("nan"), float("nan"))
        rows.append({
            "config": c, "language": d["language"].iloc[0], "n": len(x),
            "mean_ms": x.mean(), "sd_ms": x.std(ddof=1), "cv_pct": 100 * x.std(ddof=1) / x.mean(),
            "min_ms": x.min(), "p5_ms": np.percentile(x, 5), "p25_ms": np.percentile(x, 25),
            "median_ms": np.median(x), "median_ci_low": lo, "median_ci_high": hi,
            "p75_ms": np.percentile(x, 75), "p95_ms": np.percentile(x, 95), "max_ms": x.max(),
            "index_median_ms": d["index_ms"].median(), "merge_median_ms": d["merge_ms"].median(),
            "wall_median_ms": d["wall_ms"].median(),
            "query_median_us": float(np.median(q)) if q is not None else float("nan"),
            "query_ci_low_us": q_lo, "query_ci_high_us": q_hi,
            "speedup": ref_median / np.median(x), "speedup_ci_low": s_lo, "speedup_ci_high": s_hi,
            **resources(d),
        })
    return pd.DataFrame(rows), boots, qboots


RESOURCE_COLUMNS = ["threads", "gil", "cpu_median_ms", "cores_used", "peak_rss_median_mb", "peak_tree_rss_median_mb"]


def resources(d):
    """Median resource use for one configuration; NaN where the file predates these columns."""
    nan = float("nan")
    has = lambda col: col in d.columns and d[col].notna().any()
    threads = d["threads"].dropna() if has("threads") else None
    gil = d["gil"].dropna() if has("gil") else None
    return {
        "threads": int(threads.mode().iloc[0]) if threads is not None and len(threads) else nan,
        "gil": gil.mode().iloc[0] if gil is not None and len(gil) else "",
        "cpu_median_ms": d["cpu_ms"].median() if has("cpu_ms") else nan,
        "cores_used": (d["cpu_ms"] / d["wall_ms"]).median() if has("cpu_ms") else nan,
        "peak_rss_median_mb": d["peak_rss_mb"].median() if has("peak_rss_mb") else nan,
        "peak_tree_rss_median_mb": d["peak_tree_rss_mb"].median() if has("peak_tree_rss_mb") else nan,
    }


def steps_table(summary, boots, qboots, labels):
    rows = []
    for mode in RUST_MODES:
        configs = [f"rust/{l}/{mode}" for l in labels if f"rust/{l}/{mode}" in boots]
        for i, c in enumerate(configs):
            first, prev = configs[0], configs[max(i - 1, 0)]
            med = summary.set_index("config").loc[c, "median_ms"]
            row = {"mode": mode, "snapshot": c.split("/")[1], "config": c, "median_ms": med}
            for name, base in (("vs_first", first), ("vs_previous", prev)):
                change = 100 * (boots[c] / boots[base] - 1)
                base_med = summary.set_index("config").loc[base, "median_ms"]
                row[f"{name}_pct"] = 100 * (med / base_med - 1)
                row[f"{name}_ci_low"], row[f"{name}_ci_high"] = ci(change)
            # Query time against the previous snapshot, when both print it.
            row["query_median_us"] = summary.set_index("config").loc[c, "query_median_us"]
            row["query_vs_previous_pct"] = row["query_vs_previous_ci_low"] = row["query_vs_previous_ci_high"] = float("nan")
            if c in qboots and prev in qboots and prev != c:
                prev_q = summary.set_index("config").loc[prev, "query_median_us"]
                row["query_vs_previous_pct"] = 100 * (row["query_median_us"] / prev_q - 1)
                row["query_vs_previous_ci_low"], row["query_vs_previous_ci_high"] = ci(100 * (qboots[c] / qboots[prev] - 1))
            rows.append(row)
    return pd.DataFrame(rows)


def run_sequence_groups(order):
    """Which configurations share a chart.

    Language comparison (Python plus at most one Rust snapshot, 8 configurations at most): one
    chart. Otherwise Python gets one chart; Rust with one snapshot gets one chart with its modes;
    Rust with two or more snapshots (tuning) gets one chart per mode, snapshots in step order.
    A chart holds at most 8 configurations (the palette's limit); a bigger group is split into parts.
    """
    python = [c for c in order if c.startswith("python")]
    rust = [c for c in order if c.startswith("rust/")]
    other = [c for c in order if c not in python and c not in rust]
    groups = []

    def add(key, title, configs):
        n = len(SERIES)
        parts = [configs[i:i + n] for i in range(0, len(configs), n)]
        for i, part in enumerate(parts):
            many = len(parts) > 1
            groups.append((f"{key}_{i + 1}" if many else key,
                           f"{title} (part {i + 1} of {len(parts)})" if many else title, part))

    snapshots = list(dict.fromkeys(c.split("/")[1] for c in rust))
    if python and rust and len(snapshots) == 1 and len(python) + len(rust) <= len(SERIES) and not other:
        groups.append(("", "Python and Rust", python + rust))
        return groups
    if python:
        add("python", "Python", python)
    if len(snapshots) == 1:
        add("rust", "Rust", rust)
    elif rust:
        for mode in RUST_MODES:
            in_mode = [c for c in rust if c.endswith(f"/{mode}")]
            if in_mode:
                add(f"rust_{mode}", f"Rust, {mode}", in_mode)
        rest = [c for c in rust if not any(c.endswith(f"/{m}") for m in RUST_MODES)]
        if rest:
            add("rust_other", "Rust, other", rest)
    if other:
        add("other", "Other", other)
    return groups


def rolling_band(y, window, band):
    roll = pd.Series(y).rolling(window, center=True, min_periods=max(3, window // 2))
    if band == "sd":
        center, sd = roll.mean().to_numpy(), roll.std().to_numpy()
        return center, center - sd, center + sd
    return roll.median().to_numpy(), roll.quantile(0.16).to_numpy(), roll.quantile(0.84).to_numpy()


def chart_run_sequence(data, configs, title, out, band="pct"):
    """One chart with a shared y-axis from 0: each configuration is a colored line and band."""
    from matplotlib.legend_handler import HandlerTuple
    from matplotlib.patches import Patch

    n_runs = max(len(data[c]) for c in configs)
    window = max(10, n_runs // 20)
    pooled = np.concatenate([data[c]["build_ms"].to_numpy() for c in configs])
    ymax = float(np.percentile(pooled, 99.5)) * 1.1

    series = []
    for i, c in enumerate(configs):
        d = data[c].sort_values("run_index")
        x = d["run_index"].to_numpy() + 1
        y = d["build_ms"].to_numpy()
        series.append((c, SERIES[i], x, y) + rolling_band(y, window, band))

    fig, ax = plt.subplots(figsize=(11, 4.8))
    above = 0
    for c, color, x, y, center, lo, hi in series:  # dots and bands first...
        ax.scatter(x, y, s=2, color=color, alpha=0.18, linewidths=0, zorder=1, rasterized=True)
        ax.fill_between(x, lo, hi, color=color, alpha=0.13, linewidth=0, zorder=2)
        above += int((y > ymax).sum())
    handles, labels = [], []
    for c, color, x, y, center, lo, hi in series:  # ...then every line on top
        style = (0, (5, 2)) if c.startswith("rust") else "-"  # language as a second cue: Rust dashed
        ax.plot(x, center, color=color, linewidth=1.8, linestyle=style, zorder=3)
        handles.append((Patch(facecolor=color, alpha=0.13, linewidth=0),
                        plt.Line2D([], [], color=color, linewidth=1.8, linestyle=style)))
        labels.append(f"{c}\nmedian {np.median(y):,.0f} ms · SD {y.std(ddof=1):,.0f} ms")

    ax.set_xlim(0, n_runs + 1)
    ax.set_ylim(0, ymax)
    ax.grid(axis="y")
    ax.set_xlabel("Run")
    ax.set_ylabel("Build time (ms)")
    ax.set_title(f"{title}: build time across runs", pad=18)
    how = ("line = rolling mean · band = ±1 SD" if band == "sd"
           else "line = rolling median · band = 16th–84th percentile (the ±1 SD range, robust to outliers)")
    note = f"{how} · window {window} runs · dots = single runs"
    if above:
        note += f" · {above} run{'s' if above > 1 else ''} above the range shown"
    ax.text(0, 1.015, note, transform=ax.transAxes, color=INK2, fontsize=8, va="bottom")
    ax.legend(handles, labels, handler_map={tuple: HandlerTuple(ndivide=1, pad=0)},
              loc="upper left", bbox_to_anchor=(1.01, 1.0), title="Configuration", title_fontsize=8,
              fontsize=8, handlelength=2.2, labelspacing=1.0, alignment="left")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def chart_distribution(summary, reference, out):
    s = summary.sort_values("median_ms", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(s) + 1.4))
    y = np.arange(len(s))[::-1]
    xmax = s["p95_ms"].max()
    for yi, (_, r) in zip(y, s.iterrows()):
        color = LANG_COLOR.get(r["language"], MUTED)
        ax.plot([r["p5_ms"], r["p95_ms"]], [yi, yi], color=color, linewidth=1.5, zorder=2)
        ax.plot([r["p25_ms"], r["p75_ms"]], [yi, yi], color=color, linewidth=8, solid_capstyle="butt", zorder=3)
        ax.plot([r["median_ms"]] * 2, [yi - 0.11, yi + 0.11], color=SURFACE, linewidth=1.6,
                solid_capstyle="butt", zorder=4)
        label = f"{r['median_ms']:,.0f} ms"
        if r["config"] != reference:
            label += f"  ·  {r['speedup']:.2f}× vs {reference}"
        ax.text(r["p95_ms"] + xmax * 0.015, yi, label, va="center", color=INK2, fontsize=8)
    ax.set_yticks(y, s["config"])
    ax.set_xlim(0, xmax * 1.45)
    ax.set_ylim(-0.7, len(s) - 0.3)
    ax.grid(axis="x")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Build time (ms)")
    n = int(summary["n"].min())
    ax.set_title(f"Build time per configuration ({n:,} runs each)", pad=18)
    ax.text(0, 1.015, "white tick = median · thick bar = middle 50% · thin line = 5th–95th percentile",
            transform=ax.transAxes, color=INK2, fontsize=8, va="bottom")
    handles = [plt.Line2D([], [], color=LANG_COLOR[l], linewidth=8, solid_capstyle="butt", label=l.capitalize())
               for l in LANG_COLOR if l in set(summary["language"])]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def chart_steps(steps, summary, out):
    labels = list(dict.fromkeys(steps["snapshot"]))
    x = np.arange(len(labels))
    s = summary.set_index("config")
    fig, ax = plt.subplots(figsize=(max(6, 1.3 * len(labels) + 3), 4))
    for mode in RUST_MODES:
        m = steps[steps["mode"] == mode]
        if m.empty:
            continue
        color, marker = MODE_STYLE[mode]
        xi = [labels.index(v) for v in m["snapshot"]]
        med = m["median_ms"].to_numpy()
        err = np.array([med - s.loc[m["config"], "median_ci_low"].to_numpy(),
                        s.loc[m["config"], "median_ci_high"].to_numpy() - med])
        ax.plot(xi, med, color=color, linewidth=1.5, zorder=2)
        ax.errorbar(xi, med, yerr=err, fmt="none", ecolor=color, elinewidth=1.2, capsize=3, zorder=3)
        ax.scatter(xi, med, s=50, marker=marker, color=color, edgecolors=SURFACE, linewidths=2, zorder=4, label=mode)
        last = m.iloc[-1]
        text = f"{mode}: {last['median_ms']:,.0f} ms"
        if len(m) > 1:
            text += f" ({last['vs_first_pct']:+.0f}% vs {labels[0]})".replace("-", "−")
        ax.annotate(text, (xi[-1], med[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", color=INK2, fontsize=8)
    ax.set_xticks(x, labels)
    ax.set_xlim(-0.4, len(labels) - 0.4 + 1.6)
    ax.set_ylim(0, None)
    ax.grid(axis="y")
    ax.set_ylabel("Median build time (ms)")
    ax.set_title("Rust snapshots: median build time per mode", pad=18)
    ax.text(0, 1.015, "error bars = 95% confidence interval of the median (often smaller than the marker)",
            transform=ax.transAxes, color=INK2, fontsize=8, va="bottom")
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def to_markdown(df, cols, fmt):
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(fmt.get(c, "{}").format(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", nargs="?", help="results file (default: newest in bench/results)")
    parser.add_argument("--reference", default=None,
                        help="configuration for speed-ups (default python/seq, else the first snapshot's rayon run)")
    parser.add_argument("--band", choices=["pct", "sd"], default="pct",
                        help="run-sequence band: 16th-84th percentiles (default) or mean +/-1 SD")
    args = parser.parse_args()

    if args.results:
        path = Path(args.results).resolve()
    else:
        files = sorted(RESULTS.glob("*.feather")) + sorted(RESULTS.glob("*.csv"))
        if not files:
            sys.exit("No results files in bench/results.")
        path = max(files, key=lambda p: p.stat().st_mtime)
    df, meta = load(path)

    measured = df[~df["warmup"].astype(bool)]
    bad = measured[~measured["ok"].astype(bool)]
    good = measured[measured["ok"].astype(bool)]
    print(f"{path.name}: {len(df)} rows, {int(df['warmup'].astype(bool).sum())} warm-up, "
          f"{len(bad)} excluded (failed or wrong counts), {len(good)} analyzed")
    if good.empty:
        sys.exit("Nothing to analyze.")
    for lang, g in good.groupby("language"):
        print(f"  counts ({lang}): {g['docs'].iloc[0]} documents, {g['distinct_words'].iloc[0]} distinct words")

    if meta.get("memory_method") != "proc-vmhwm":
        # Earlier runner versions recorded peak memory that included the runner's own memory.
        good = good.drop(columns=[c for c in ("peak_rss_mb", "peak_tree_rss_mb") if c in good.columns])
        print("  peak memory not shown: this file was recorded before the runner measured it correctly")
    order, labels = config_order(good, meta)
    data = {c: good[good["config"] == c] for c in order}
    if args.reference:
        reference = args.reference
    elif "python/seq" in data:
        reference = "python/seq"
    else:  # tuning: the first snapshot's rayon run is the baseline
        reference = next((c for c in order if c.startswith("rust/") and c.endswith("/rayon")), order[0])
    if reference not in data:
        sys.exit(f"Reference '{reference}' not in this file. Choose one of: {', '.join(order)}")

    rng = np.random.default_rng(0)
    summary, boots, qboots = summarize(data, order, reference, rng)
    has_query = summary["query_median_us"].notna().any()
    out_dir = path.parent / path.stem
    out_dir.mkdir(exist_ok=True)
    summary.to_csv(out_dir / "summary.csv", index=False)

    cols = ["config", "n", "median_ms", "median_ci_low", "median_ci_high", "mean_ms", "sd_ms", "cv_pct",
            "p5_ms", "p95_ms", "index_median_ms", "merge_median_ms", "wall_median_ms", "speedup"]
    if has_query:
        cols[-1:-1] = ["query_median_us", "query_ci_low_us", "query_ci_high_us"]
    fmt = {c: "{:,.1f}" for c in cols} | {"config": "{}", "n": "{:,}", "cv_pct": "{:.1f}%", "speedup": "{:.2f}×"}
    fmt |= {c: "{:,.2f}" for c in ("query_median_us", "query_ci_low_us", "query_ci_high_us")}
    units = "Times in ms, except query times (µs per query)" if has_query else "Times in ms"
    md = [f"# {path.stem}", "", f"Reference for speed-up: `{reference}`. {units}; CI = 95% bootstrap "
          f"interval of the median ({BOOTSTRAP} resamples).", "", to_markdown(summary, cols, fmt).replace("| nan ", "|  ")]
    has_resources = summary["cpu_median_ms"].notna().any()
    if has_resources:
        rcols = ["config", "threads", "gil", "wall_median_ms", "cpu_median_ms", "cores_used",
                 "peak_rss_median_mb", "peak_tree_rss_median_mb"]
        rfmt = {"config": "{}", "gil": "{}", "threads": "{:.0f}", "wall_median_ms": "{:,.1f}",
                "cpu_median_ms": "{:,.1f}", "cores_used": "{:.2f}", "peak_rss_median_mb": "{:,.1f}",
                "peak_tree_rss_median_mb": "{:,.1f}"}
        md += ["", "## Resources", "", "Medians per run, for the whole process (start-up and exit included). "
               "cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the "
               "whole process tree (sampled, so approximate; memory shared between processes counts in each).",
               "", to_markdown(summary.fillna({"threads": float("nan")}), rcols, rfmt).replace("nan", "")]

    rust_labels = [l for l in labels if any(c.startswith(f"rust/{l}/") for c in order)]
    if len(rust_labels) >= 2:
        steps = steps_table(summary, boots, qboots, rust_labels)
        steps.to_csv(out_dir / "steps.csv", index=False)
        chart_steps(steps, summary, out_dir / "steps.png")
        scols = ["mode", "snapshot", "median_ms", "vs_previous_pct", "vs_previous_ci_low", "vs_previous_ci_high",
                 "vs_first_pct", "vs_first_ci_low", "vs_first_ci_high"]
        if has_query:
            scols += ["query_median_us", "query_vs_previous_pct", "query_vs_previous_ci_low", "query_vs_previous_ci_high"]
        sfmt = {c: "{:+.1f}%" for c in scols} | {"mode": "{}", "snapshot": "{}", "median_ms": "{:,.1f}",
                                                 "query_median_us": "{:,.2f}"}
        md += ["", "## Rust snapshots", "", to_markdown(steps, scols, sfmt).replace("| nan ", "|  ").replace("| +nan% ", "|  ")]

    for old in out_dir.glob("run_sequence*.png"):  # replaced below; the grouping may have changed
        old.unlink()
    run_files = []
    for key, title, configs in run_sequence_groups(order):
        name = f"run_sequence_{key}.png" if key else "run_sequence.png"
        chart_run_sequence(data, configs, title, out_dir / name, args.band)
        run_files.append(name)
    chart_distribution(summary, reference, out_dir / "distribution.png")
    (out_dir / "summary.md").write_text("\n".join(md) + "\n")

    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(summary[["config", "n", "median_ms", "median_ci_low", "median_ci_high", "sd_ms", "cv_pct",
                       "index_median_ms", "merge_median_ms", "speedup"]
                      + (["query_median_us"] if has_query else [])].round(2).to_string(index=False))
        if has_resources:
            print(summary[["config", "threads", "gil", "cpu_median_ms", "cores_used", "peak_rss_median_mb",
                           "peak_tree_rss_median_mb"]].round(2).to_string(index=False))
    print(f"Wrote {out_dir.relative_to(REPO)}/: summary.csv, summary.md, "
          + ("steps.csv, steps.png, " if len(rust_labels) >= 2 else "") + ", ".join(run_files) + ", distribution.png")


if __name__ == "__main__":
    main()
