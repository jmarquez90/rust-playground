# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.2", "pyarrow>=17", "matplotlib>=3.9", "numpy>=2"]
# ///
"""Summarize a benchmark results file and draw its charts.

    uv run --python 3.14 bench/analyze.py                                   # newest results file
    uv run --python 3.14 bench/analyze.py bench/results/<file>.feather
    uv run --python 3.14 bench/analyze.py <file> --reference rust/baseline/1-thread

Writes into bench/results/<file stem>/:

- summary.csv / summary.md: per configuration n, mean, SD, CV, percentiles, the median with a
  95% bootstrap confidence interval, phase medians, and speed-up against the reference.
- steps.csv: when there are two or more Rust snapshots, each one's change against the first
  snapshot and against the previous one, per mode, with 95% bootstrap intervals.
- run_sequence.png: build time against run number, one panel per configuration. Default band
  (--band pct): rolling median with the rolling 16th-84th percentiles, the range +/-1 SD covers
  for normally distributed data, but not stretched by single outliers. --band sd draws the
  rolling mean +/-1 SD instead. Window = 5% of the runs, at least 10.
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
    preferred = [f"python/{m}" for m in PY_MODES] + [f"rust/{l}/{m}" for l in labels for m in RUST_MODES]
    present = list(dict.fromkeys(df["config"]))
    return [c for c in preferred if c in present] + [c for c in present if c not in preferred], labels


def boot_medians(x, rng):
    idx = rng.integers(0, len(x), size=(BOOTSTRAP, len(x)))
    return np.median(x[idx], axis=1)


def ci(values):
    lo, hi = np.percentile(values, [2.5, 97.5])
    return float(lo), float(hi)


def summarize(data, order, reference, rng):
    boots = {c: boot_medians(data[c]["build_ms"].to_numpy(), rng) for c in order}
    ref_median = float(np.median(data[reference]["build_ms"]))
    rows = []
    for c in order:
        d = data[c]
        x = d["build_ms"].to_numpy()
        lo, hi = ci(boots[c])
        s_lo, s_hi = ci(boots[reference] / boots[c])
        rows.append({
            "config": c, "language": d["language"].iloc[0], "n": len(x),
            "mean_ms": x.mean(), "sd_ms": x.std(ddof=1), "cv_pct": 100 * x.std(ddof=1) / x.mean(),
            "min_ms": x.min(), "p5_ms": np.percentile(x, 5), "p25_ms": np.percentile(x, 25),
            "median_ms": np.median(x), "median_ci_low": lo, "median_ci_high": hi,
            "p75_ms": np.percentile(x, 75), "p95_ms": np.percentile(x, 95), "max_ms": x.max(),
            "index_median_ms": d["index_ms"].median(), "merge_median_ms": d["merge_ms"].median(),
            "wall_median_ms": d["wall_ms"].median(),
            "speedup": ref_median / np.median(x), "speedup_ci_low": s_lo, "speedup_ci_high": s_hi,
        })
    return pd.DataFrame(rows), boots


def steps_table(summary, boots, labels):
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
            rows.append(row)
    return pd.DataFrame(rows)


def chart_run_sequence(data, order, out, band="pct"):
    n_cfg = len(order)
    ncols = 1 if n_cfg <= 4 else 2
    nrows = -(-n_cfg // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.4 * ncols, 1.9 * nrows + 0.6), squeeze=False)
    for ax in axes.flat[n_cfg:]:
        ax.set_visible(False)
    for ax, c in zip(axes.flat, order):
        d = data[c].sort_values("run_index")
        x = d["run_index"].to_numpy() + 1
        y = d["build_ms"].to_numpy()
        window = max(10, len(y) // 20)
        roll = pd.Series(y).rolling(window, center=True, min_periods=max(3, window // 2))
        if band == "sd":
            center = roll.mean().to_numpy()
            sd = roll.std().to_numpy()
            band_lo, band_hi = center - sd, center + sd
        else:
            center = roll.median().to_numpy()
            band_lo, band_hi = roll.quantile(0.16).to_numpy(), roll.quantile(0.84).to_numpy()
        color = LANG_COLOR.get(d["language"].iloc[0], MUTED)

        lo, hi = np.percentile(y, [0.5, 99.5])
        pad = (hi - lo) * 0.15 or 1.0
        ax.set_ylim(max(0, lo - pad), hi + pad)
        above = int((y > hi + pad).sum())

        ax.scatter(x, y, s=2.5, color=MUTED, alpha=0.3, linewidths=0, zorder=1)
        ax.fill_between(x, band_lo, band_hi, color=color, alpha=0.14, linewidth=0, zorder=2)
        ax.plot(x, center, color=color, linewidth=1.5, zorder=3)
        ax.grid(axis="y")
        ax.set_xlim(0, len(y) + 1)
        ax.set_title(c, pad=14)
        note = f"median {np.median(y):,.1f} ms · SD {y.std(ddof=1):,.1f} ms · window {window} runs"
        if above:
            note += f" · {above} run{'s' if above > 1 else ''} above the range shown"
        ax.text(0, 1.02, note, transform=ax.transAxes, color=INK2, fontsize=8, va="bottom")
    for ax in axes[-1]:
        ax.set_xlabel("Run")
    for ax in axes[:, 0]:
        ax.set_ylabel("Build time (ms)")
    title = ("rolling mean with a ±1 SD band" if band == "sd"
             else "rolling median with a 16th–84th percentile band (the ±1 SD range, robust to outliers)")
    fig.suptitle(f"Build time across runs: {title}", x=0.01, ha="left",
                 fontsize=11, fontweight="bold")
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
    parser.add_argument("--reference", default=None, help="configuration for speed-ups (default python/seq)")
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

    order, labels = config_order(good, meta)
    data = {c: good[good["config"] == c] for c in order}
    reference = args.reference or ("python/seq" if "python/seq" in data else order[0])
    if reference not in data:
        sys.exit(f"Reference '{reference}' not in this file. Choose one of: {', '.join(order)}")

    rng = np.random.default_rng(0)
    summary, boots = summarize(data, order, reference, rng)
    out_dir = path.parent / path.stem
    out_dir.mkdir(exist_ok=True)
    summary.to_csv(out_dir / "summary.csv", index=False)

    cols = ["config", "n", "median_ms", "median_ci_low", "median_ci_high", "mean_ms", "sd_ms", "cv_pct",
            "p5_ms", "p95_ms", "index_median_ms", "merge_median_ms", "wall_median_ms", "speedup"]
    fmt = {c: "{:,.1f}" for c in cols} | {"config": "{}", "n": "{:,}", "cv_pct": "{:.1f}%", "speedup": "{:.2f}×"}
    md = [f"# {path.stem}", "", f"Reference for speed-up: `{reference}`. Times in ms; CI = 95% bootstrap "
          f"interval of the median ({BOOTSTRAP} resamples).", "", to_markdown(summary, cols, fmt)]

    rust_labels = [l for l in labels if any(c.startswith(f"rust/{l}/") for c in order)]
    if len(rust_labels) >= 2:
        steps = steps_table(summary, boots, rust_labels)
        steps.to_csv(out_dir / "steps.csv", index=False)
        chart_steps(steps, summary, out_dir / "steps.png")
        scols = ["mode", "snapshot", "median_ms", "vs_previous_pct", "vs_previous_ci_low", "vs_previous_ci_high",
                 "vs_first_pct", "vs_first_ci_low", "vs_first_ci_high"]
        sfmt = {c: "{:+.1f}%" for c in scols} | {"mode": "{}", "snapshot": "{}", "median_ms": "{:,.1f}"}
        md += ["", "## Rust snapshots", "", to_markdown(steps, scols, sfmt)]

    chart_run_sequence(data, order, out_dir / "run_sequence.png", args.band)
    chart_distribution(summary, reference, out_dir / "distribution.png")
    (out_dir / "summary.md").write_text("\n".join(md) + "\n")

    with pd.option_context("display.width", 160, "display.max_columns", 20):
        print(summary[["config", "n", "median_ms", "median_ci_low", "median_ci_high", "sd_ms", "cv_pct",
                       "index_median_ms", "merge_median_ms", "speedup"]].round(2).to_string(index=False))
    print(f"Wrote {out_dir.relative_to(REPO)}/: summary.csv, summary.md, "
          + ("steps.csv, steps.png, " if len(rust_labels) >= 2 else "") + "run_sequence.png, distribution.png")


if __name__ == "__main__":
    main()
