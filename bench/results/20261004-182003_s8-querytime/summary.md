# 20261004-182003_s8-querytime

Reference for speed-up: `rust/baseline/rayon`. Times in ms, except query times (µs per query); CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | query_median_us | query_ci_low_us | query_ci_high_us | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 1,000 | 195.5 | 194.1 | 196.6 | 198.3 | 16.5 | 8.3% | 176.5 | 228.7 |  |  | 246.7 |  |  |  | 1.00× |
| rust/s0-phases/rayon | 1,000 | 196.0 | 194.7 | 197.1 | 198.2 | 16.7 | 8.4% | 175.4 | 228.3 | 115.3 | 79.8 | 247.5 |  |  |  | 1.00× |
| rust/s1-profile/rayon | 1,000 | 187.6 | 186.5 | 188.7 | 190.0 | 15.3 | 8.0% | 170.7 | 216.0 | 113.5 | 73.6 | 239.3 |  |  |  | 1.04× |
| rust/s2-mimalloc/rayon | 1,000 | 98.2 | 97.6 | 98.8 | 99.7 | 9.7 | 9.7% | 87.6 | 117.9 | 60.3 | 37.2 | 112.5 |  |  |  | 1.99× |
| rust/s3-borrow/rayon | 1,000 | 68.6 | 68.2 | 69.1 | 70.3 | 8.0 | 11.4% | 61.0 | 86.2 | 41.4 | 27.0 | 81.5 |  |  |  | 2.85× |
| rust/s4-u32pos/rayon | 1,000 | 65.7 | 65.2 | 66.1 | 67.3 | 8.0 | 11.9% | 58.1 | 82.4 | 37.3 | 28.0 | 77.5 |  |  |  | 2.98× |
| rust/s6-capacity/rayon | 1,000 | 61.2 | 60.7 | 61.5 | 62.3 | 6.9 | 11.0% | 53.3 | 75.6 | 33.4 | 27.7 | 71.8 |  |  |  | 3.20× |
| rust/s8-querytime/rayon | 1,000 | 60.8 | 60.3 | 61.2 | 62.1 | 7.0 | 11.3% | 53.6 | 75.4 | 33.3 | 27.2 | 73.2 | 3.76 | 3.74 | 3.77 | 3.22× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 24 |  | 246.7 | 698.0 | 2.83 | 142.0 | 142.0 |
| rust/s0-phases/rayon | 24 |  | 247.5 | 695.8 | 2.82 | 141.6 | 141.6 |
| rust/s1-profile/rayon | 24 |  | 239.3 | 674.8 | 2.82 | 142.1 | 142.1 |
| rust/s2-mimalloc/rayon | 24 |  | 112.5 | 957.3 | 8.52 | 291.4 | 291.4 |
| rust/s3-borrow/rayon | 24 |  | 81.5 | 612.5 | 7.49 | 217.3 | 217.3 |
| rust/s4-u32pos/rayon | 24 |  | 77.5 | 567.8 | 7.32 | 213.3 | 213.3 |
| rust/s6-capacity/rayon | 24 |  | 71.8 | 474.7 | 6.59 | 139.3 | 139.3 |
| rust/s8-querytime/rayon | 24 |  | 73.2 | 478.7 | 6.52 | 139.4 | 139.4 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high | query_median_us | query_vs_previous_pct | query_vs_previous_ci_low | query_vs_previous_ci_high |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 195.5 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |  |  |  |  |
| rayon | s0-phases | 196.0 | +0.3% | -0.7% | +1.2% | +0.3% | -0.7% | +1.2% |  |  |  |  |
| rayon | s1-profile | 187.6 | -4.3% | -5.1% | -3.4% | -4.0% | -4.9% | -3.1% |  |  |  |  |
| rayon | s2-mimalloc | 98.2 | -47.6% | -48.1% | -47.2% | -49.7% | -50.3% | -49.3% |  |  |  |  |
| rayon | s3-borrow | 68.6 | -30.2% | -30.7% | -29.4% | -64.9% | -65.2% | -64.6% |  |  |  |  |
| rayon | s4-u32pos | 65.7 | -4.3% | -5.2% | -3.4% | -66.4% | -66.7% | -66.1% |  |  |  |  |
| rayon | s6-capacity | 61.2 | -6.8% | -7.9% | -5.9% | -68.7% | -69.0% | -68.4% |  |  |  |  |
| rayon | s8-querytime | 60.8 | -0.6% | -1.6% | +0.4% | -68.9% | -69.2% | -68.6% | 3.76 |  |  |  |
