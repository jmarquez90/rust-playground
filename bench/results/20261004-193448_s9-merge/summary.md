# 20261004-193448_s9-merge

Reference for speed-up: `rust/s8-querytime/rayon`. Times in ms, except query times (µs per query); CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | query_median_us | query_ci_low_us | query_ci_high_us | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/s8-querytime/rayon | 1,000 | 57.4 | 57.1 | 57.7 | 58.8 | 5.6 | 9.6% | 52.7 | 69.0 | 33.0 | 24.4 | 69.0 | 3.74 | 3.72 | 3.75 | 1.00× |
| rust/s9-dashmap/rayon | 1,000 | 43.3 | 43.1 | 43.5 | 43.8 | 3.6 | 8.3% | 39.6 | 49.8 | 32.7 | 10.4 | 57.1 | 3.76 | 3.74 | 3.77 | 1.33× |
| rust/s9-sharded/rayon | 1,000 | 43.8 | 43.4 | 44.0 | 44.0 | 3.2 | 7.2% | 39.7 | 49.3 | 32.7 | 10.7 | 55.1 | 3.95 | 3.93 | 3.95 | 1.31× |
| rust/s9-segments/rayon | 1,000 | 32.8 | 32.6 | 33.0 | 33.3 | 2.9 | 8.8% | 29.8 | 38.1 | 32.7 |  | 49.9 | 4.33 | 4.32 | 4.35 | 1.75× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/s8-querytime/rayon | 24 |  | 69.0 | 471.9 | 6.80 | 139.4 | 139.4 |
| rust/s9-dashmap/rayon | 24 |  | 57.1 | 536.5 | 9.36 | 141.4 | 141.4 |
| rust/s9-sharded/rayon | 24 |  | 55.1 | 595.0 | 10.80 | 171.4 | 171.4 |
| rust/s9-segments/rayon | 24 |  | 49.9 | 450.9 | 9.02 | 135.3 | 135.3 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high | query_median_us | query_vs_previous_pct | query_vs_previous_ci_low | query_vs_previous_ci_high | query_vs_first_pct | query_vs_first_ci_low | query_vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rayon | s8-querytime | 57.4 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | 3.74 |  |  |  |  |  |  |
| rayon | s9-dashmap | 43.3 | -24.6% | -25.2% | -24.1% | -24.6% | -25.2% | -24.1% | 3.76 | +0.6% | +0.1% | +1.1% | +0.6% | +0.1% | +1.1% |
| rayon | s9-sharded | 43.8 | +1.2% | +0.3% | +1.8% | -23.8% | -24.4% | -23.3% | 3.95 | +5.0% | +4.4% | +5.5% | +5.6% | +5.0% | +6.1% |
| rayon | s9-segments | 32.8 | -25.0% | -25.6% | -24.4% | -42.8% | -43.3% | -42.4% | 4.33 | +9.9% | +9.4% | +10.5% | +16.0% | +15.5% | +16.7% |
