# 20261004-174947_s7-hashers

Reference for speed-up: `rust/s6-capacity/rayon`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/s6-capacity/rayon | 1,000 | 57.1 | 56.9 | 57.5 | 58.5 | 5.5 | 9.5% | 52.4 | 68.8 | 32.5 | 24.6 | 66.7 | 1.00× |
| rust/s7-ahash/rayon | 1,000 | 52.8 | 52.5 | 53.2 | 53.9 | 5.4 | 10.1% | 47.9 | 63.0 | 30.8 | 21.9 | 62.3 | 1.08× |
| rust/s7-fxhash/rayon | 1,000 | 45.0 | 44.7 | 45.3 | 45.8 | 4.5 | 9.9% | 40.7 | 53.0 | 29.6 | 15.2 | 54.1 | 1.27× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/s6-capacity/rayon | 24 |  | 66.7 | 462.7 | 6.88 | 139.4 | 139.4 |
| rust/s7-ahash/rayon | 24 |  | 62.3 | 444.3 | 7.08 | 141.3 | 141.3 |
| rust/s7-fxhash/rayon | 24 |  | 54.1 | 426.5 | 7.83 | 137.2 | 137.2 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | s6-capacity | 57.1 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s7-ahash | 52.8 | -7.6% | -8.4% | -6.8% | -7.6% | -8.4% | -6.8% |
| rayon | s7-fxhash | 45.0 | -14.8% | -15.6% | -14.1% | -21.3% | -22.0% | -20.7% |
