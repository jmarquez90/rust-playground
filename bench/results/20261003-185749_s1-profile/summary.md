# 20261003-185749_s1-profile

Reference for speed-up: `rust/baseline/rayon`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 1,000 | 188.2 | 187.2 | 189.6 | 193.3 | 18.8 | 9.7% | 171.7 | 231.3 | nan | nan | 237.7 | 1.00× |
| rust/s0-phases/rayon | 1,000 | 187.3 | 186.2 | 188.5 | 191.3 | 18.9 | 9.9% | 169.6 | 226.2 | 112.6 | 74.6 | 237.1 | 1.00× |
| rust/s1-profile/rayon | 1,000 | 180.5 | 179.2 | 181.6 | 184.5 | 18.2 | 9.9% | 164.5 | 218.1 | 111.3 | 68.7 | 230.2 | 1.04× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 24 |  | 237.7 | 674.9 | 2.83 | 167.6 | 167.6 |
| rust/s0-phases/rayon | 24 |  | 237.1 | 670.1 | 2.82 | 167.6 | 167.6 |
| rust/s1-profile/rayon | 24 |  | 230.2 | 646.5 | 2.82 | 167.6 | 167.6 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 188.2 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s0-phases | 187.3 | -0.5% | -1.4% | +0.3% | -0.5% | -1.4% | +0.3% |
| rayon | s1-profile | 180.5 | -3.7% | -4.5% | -2.8% | -4.1% | -5.0% | -3.3% |
