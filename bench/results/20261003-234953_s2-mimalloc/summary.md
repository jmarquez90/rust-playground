# 20261003-234953_s2-mimalloc

Reference for speed-up: `rust/baseline/rayon`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 1,000 | 184.9 | 183.5 | 186.1 | 192.6 | 40.7 | 21.1% | 167.6 | 232.8 | nan | nan | 232.8 | 1.00× |
| rust/s0-phases/rayon | 1,000 | 183.3 | 182.3 | 184.9 | 191.0 | 31.0 | 16.2% | 167.1 | 232.5 | 112.6 | 71.0 | 232.7 | 1.01× |
| rust/s1-profile/rayon | 1,000 | 176.7 | 175.8 | 177.9 | 183.3 | 24.3 | 13.2% | 160.7 | 223.8 | 111.0 | 66.0 | 224.2 | 1.05× |
| rust/s2-mimalloc/rayon | 1,000 | 95.3 | 94.5 | 95.8 | 98.6 | 20.0 | 20.3% | 85.4 | 120.0 | 59.2 | 35.7 | 109.6 | 1.94× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 24 |  | 232.8 | 667.8 | 2.87 | 187.5 | 187.5 |
| rust/s0-phases/rayon | 24 |  | 232.7 | 665.5 | 2.86 | 187.5 | 187.5 |
| rust/s1-profile/rayon | 24 |  | 224.2 | 641.8 | 2.86 | 187.5 | 187.5 |
| rust/s2-mimalloc/rayon | 24 |  | 109.6 | 925.8 | 8.38 | 289.1 | 289.1 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 184.9 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s0-phases | 183.3 | -0.8% | -1.7% | +0.3% | -0.8% | -1.7% | +0.3% |
| rayon | s1-profile | 176.7 | -3.6% | -4.6% | -2.7% | -4.4% | -5.2% | -3.4% |
| rayon | s2-mimalloc | 95.3 | -46.1% | -46.6% | -45.7% | -48.5% | -49.0% | -48.0% |
