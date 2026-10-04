# 20261004-163351_s5-wordids

Reference for speed-up: `rust/baseline/rayon`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 1,000 | 195.8 | 194.8 | 197.0 | 200.8 | 19.4 | 9.6% | 179.4 | 237.3 | nan | nan | 247.4 | 1.00× |
| rust/s0-phases/rayon | 1,000 | 196.7 | 195.7 | 198.0 | 200.6 | 19.0 | 9.4% | 178.3 | 236.2 | 116.1 | 79.9 | 247.3 | 1.00× |
| rust/s1-profile/rayon | 1,000 | 189.2 | 188.0 | 190.3 | 193.7 | 19.1 | 9.8% | 172.6 | 229.1 | 115.1 | 74.3 | 240.6 | 1.03× |
| rust/s2-mimalloc/rayon | 1,000 | 100.1 | 99.3 | 100.8 | 102.7 | 11.6 | 11.3% | 89.9 | 126.3 | 60.9 | 38.9 | 114.8 | 1.96× |
| rust/s3-borrow/rayon | 1,000 | 70.7 | 70.3 | 71.2 | 73.1 | 9.3 | 12.7% | 63.0 | 90.2 | 42.3 | 28.3 | 83.5 | 2.77× |
| rust/s4-u32pos/rayon | 1,000 | 67.6 | 67.3 | 68.1 | 70.0 | 9.6 | 13.8% | 59.9 | 87.4 | 37.9 | 29.7 | 79.9 | 2.90× |
| rust/s5-wordids/rayon | 1,000 | 69.3 | 68.7 | 69.9 | 71.6 | 9.2 | 12.8% | 61.8 | 89.7 | 37.9 | 31.0 | 80.3 | 2.82× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 24 |  | 247.4 | 700.3 | 2.83 | 141.7 | 141.7 |
| rust/s0-phases/rayon | 24 |  | 247.3 | 700.9 | 2.83 | 141.6 | 141.6 |
| rust/s1-profile/rayon | 24 |  | 240.6 | 679.7 | 2.82 | 142.3 | 142.3 |
| rust/s2-mimalloc/rayon | 24 |  | 114.8 | 968.3 | 8.40 | 291.4 | 291.4 |
| rust/s3-borrow/rayon | 24 |  | 83.5 | 623.7 | 7.40 | 217.4 | 217.4 |
| rust/s4-u32pos/rayon | 24 |  | 79.9 | 577.7 | 7.20 | 211.4 | 211.4 |
| rust/s5-wordids/rayon | 24 |  | 80.3 | 579.1 | 7.14 | 213.4 | 213.4 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 195.8 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s0-phases | 196.7 | +0.5% | -0.3% | +1.2% | +0.5% | -0.3% | +1.2% |
| rayon | s1-profile | 189.2 | -3.8% | -4.6% | -3.1% | -3.4% | -4.2% | -2.6% |
| rayon | s2-mimalloc | 100.1 | -47.1% | -47.6% | -46.6% | -48.9% | -49.4% | -48.4% |
| rayon | s3-borrow | 70.7 | -29.4% | -30.0% | -28.6% | -63.9% | -64.2% | -63.6% |
| rayon | s4-u32pos | 67.6 | -4.4% | -5.3% | -3.5% | -65.5% | -65.8% | -65.1% |
| rayon | s5-wordids | 69.3 | +2.5% | +1.3% | +3.6% | -64.6% | -65.0% | -64.3% |
