# 20261004-172204_s6-capacity

Reference for speed-up: `rust/baseline/rayon`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 1,000 | 189.1 | 188.1 | 190.2 | 192.2 | 16.3 | 8.5% | 172.1 | 221.5 | nan | nan | 238.5 | 1.00× |
| rust/s0-phases/rayon | 1,000 | 188.3 | 187.5 | 189.2 | 191.8 | 17.1 | 8.9% | 171.8 | 223.6 | 112.9 | 74.9 | 237.1 | 1.00× |
| rust/s1-profile/rayon | 1,000 | 182.2 | 181.3 | 183.3 | 184.6 | 14.6 | 7.9% | 165.9 | 212.2 | 112.0 | 69.9 | 230.5 | 1.04× |
| rust/s2-mimalloc/rayon | 1,000 | 94.9 | 94.5 | 95.6 | 96.8 | 8.9 | 9.2% | 86.0 | 113.4 | 59.6 | 35.0 | 109.2 | 1.99× |
| rust/s3-borrow/rayon | 1,000 | 66.6 | 66.2 | 66.9 | 68.3 | 7.8 | 11.5% | 59.6 | 82.4 | 41.2 | 25.1 | 78.7 | 2.84× |
| rust/s4-u32pos/rayon | 1,000 | 63.4 | 63.1 | 64.1 | 65.1 | 7.1 | 10.9% | 57.2 | 77.7 | 37.1 | 26.2 | 74.9 | 2.98× |
| rust/s6-capacity/rayon | 1,000 | 59.1 | 58.7 | 59.5 | 60.4 | 7.2 | 12.0% | 51.9 | 73.9 | 33.0 | 25.9 | 69.0 | 3.20× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 24 |  | 238.5 | 680.4 | 2.86 | 141.8 | 141.8 |
| rust/s0-phases/rayon | 24 |  | 237.1 | 678.0 | 2.86 | 141.7 | 141.7 |
| rust/s1-profile/rayon | 24 |  | 230.5 | 656.9 | 2.85 | 142.4 | 142.4 |
| rust/s2-mimalloc/rayon | 24 |  | 109.2 | 944.5 | 8.63 | 291.3 | 291.3 |
| rust/s3-borrow/rayon | 24 |  | 78.7 | 608.0 | 7.70 | 217.4 | 217.4 |
| rust/s4-u32pos/rayon | 24 |  | 74.9 | 564.3 | 7.54 | 213.4 | 213.4 |
| rust/s6-capacity/rayon | 24 |  | 69.0 | 470.6 | 6.76 | 139.4 | 139.4 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 189.1 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s0-phases | 188.3 | -0.4% | -1.2% | +0.3% | -0.4% | -1.2% | +0.3% |
| rayon | s1-profile | 182.2 | -3.2% | -4.0% | -2.5% | -3.6% | -4.4% | -2.9% |
| rayon | s2-mimalloc | 94.9 | -47.9% | -48.3% | -47.4% | -49.8% | -50.2% | -49.3% |
| rayon | s3-borrow | 66.6 | -29.8% | -30.5% | -29.4% | -64.8% | -65.1% | -64.5% |
| rayon | s4-u32pos | 63.4 | -4.7% | -5.4% | -3.6% | -66.4% | -66.7% | -66.1% |
| rayon | s6-capacity | 59.1 | -6.8% | -7.9% | -6.0% | -68.7% | -69.0% | -68.5% |
