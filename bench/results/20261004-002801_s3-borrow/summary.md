# 20261004-002801_s3-borrow

Reference for speed-up: `rust/baseline/rayon`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 1,000 | 180.4 | 179.7 | 181.2 | 184.1 | 15.0 | 8.2% | 167.2 | 213.2 | nan | nan | 227.7 | 1.00× |
| rust/s0-phases/rayon | 1,000 | 180.9 | 180.3 | 181.8 | 184.4 | 15.3 | 8.3% | 167.2 | 213.1 | 111.8 | 69.1 | 227.6 | 1.00× |
| rust/s1-profile/rayon | 1,000 | 175.3 | 174.6 | 176.2 | 178.6 | 16.3 | 9.1% | 161.4 | 205.4 | 110.6 | 64.7 | 222.0 | 1.03× |
| rust/s2-mimalloc/rayon | 1,000 | 92.5 | 92.0 | 93.0 | 94.1 | 8.1 | 8.6% | 84.7 | 109.1 | 57.8 | 34.0 | 106.4 | 1.95× |
| rust/s3-borrow/rayon | 1,000 | 64.5 | 64.2 | 64.9 | 66.2 | 6.9 | 10.4% | 58.5 | 79.5 | 39.6 | 24.7 | 76.5 | 2.80× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| rust/baseline/rayon | 24 |  | 227.7 | 656.3 | 2.88 |  |  |
| rust/s0-phases/rayon | 24 |  | 227.6 | 656.7 | 2.88 |  |  |
| rust/s1-profile/rayon | 24 |  | 222.0 | 637.1 | 2.87 |  |  |
| rust/s2-mimalloc/rayon | 24 |  | 106.4 | 914.0 | 8.54 |  |  |
| rust/s3-borrow/rayon | 24 |  | 76.5 | 581.8 | 7.57 |  |  |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 180.4 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s0-phases | 180.9 | +0.3% | -0.3% | +0.9% | +0.3% | -0.3% | +0.9% |
| rayon | s1-profile | 175.3 | -3.1% | -3.7% | -2.5% | -2.9% | -3.4% | -2.2% |
| rayon | s2-mimalloc | 92.5 | -47.2% | -47.6% | -46.9% | -48.7% | -49.1% | -48.4% |
| rayon | s3-borrow | 64.5 | -30.3% | -30.8% | -29.7% | -64.3% | -64.5% | -64.0% |
