# 20261004-010152_s4-u32pos

Reference for speed-up: `rust/baseline/rayon`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 1,000 | 183.5 | 182.7 | 184.9 | 190.9 | 22.1 | 11.6% | 168.5 | 237.5 | nan | nan | 230.9 | 1.00× |
| rust/s0-phases/rayon | 1,000 | 185.1 | 183.8 | 186.6 | 190.9 | 21.5 | 11.2% | 167.8 | 233.4 | 112.9 | 71.7 | 232.8 | 0.99× |
| rust/s1-profile/rayon | 1,000 | 177.9 | 177.0 | 179.0 | 184.1 | 20.6 | 11.2% | 162.2 | 227.3 | 111.6 | 66.2 | 225.1 | 1.03× |
| rust/s2-mimalloc/rayon | 1,000 | 93.6 | 93.0 | 94.3 | 97.2 | 12.0 | 12.4% | 84.3 | 121.3 | 58.3 | 35.4 | 107.7 | 1.96× |
| rust/s3-borrow/rayon | 1,000 | 65.3 | 64.8 | 65.7 | 68.3 | 9.8 | 14.4% | 58.0 | 89.5 | 40.3 | 24.9 | 77.3 | 2.81× |
| rust/s4-u32pos/rayon | 1,000 | 62.8 | 62.3 | 63.4 | 65.8 | 10.1 | 15.3% | 55.9 | 86.9 | 36.5 | 26.3 | 74.0 | 2.92× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 24 |  | 230.9 | 665.3 | 2.87 | 141.3 | 141.3 |
| rust/s0-phases/rayon | 24 |  | 232.8 | 667.6 | 2.87 | 141.3 | 141.3 |
| rust/s1-profile/rayon | 24 |  | 225.1 | 646.3 | 2.86 | 141.8 | 141.8 |
| rust/s2-mimalloc/rayon | 24 |  | 107.7 | 921.9 | 8.47 | 291.3 | 291.3 |
| rust/s3-borrow/rayon | 24 |  | 77.3 | 592.1 | 7.55 | 217.4 | 217.4 |
| rust/s4-u32pos/rayon | 24 |  | 74.0 | 553.6 | 7.40 | 213.4 | 213.4 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 183.5 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s0-phases | 185.1 | +0.9% | -0.2% | +1.8% | +0.9% | -0.2% | +1.8% |
| rayon | s1-profile | 177.9 | -3.9% | -4.7% | -2.9% | -3.0% | -3.9% | -2.3% |
| rayon | s2-mimalloc | 93.6 | -47.4% | -47.9% | -47.0% | -49.0% | -49.5% | -48.5% |
| rayon | s3-borrow | 65.3 | -30.2% | -31.0% | -29.6% | -64.4% | -64.8% | -64.1% |
| rayon | s4-u32pos | 62.8 | -3.8% | -4.8% | -2.6% | -65.8% | -66.2% | -65.4% |
