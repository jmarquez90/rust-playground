# 20261004-233633_overview

Reference for speed-up: `python/seq`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python/seq | 1,000 | 820.7 | 818.6 | 822.9 | 828.2 | 37.1 | 4.5% | 785.7 | 893.8 | 752.5 | 60.7 | 1,459.3 | 1.00× |
| python3.14t/thread | 1,000 | 468.5 | 466.3 | 471.1 | 474.2 | 39.3 | 8.3% | 421.6 | 551.7 | 371.6 | 81.3 | 1,181.2 | 1.75× |
| rust/baseline/rayon | 1,000 | 198.2 | 197.1 | 199.0 | 202.5 | 17.4 | 8.6% | 181.8 | 237.4 |  |  | 250.5 | 4.14× |
| rust/s9-safe/rayon | 1,000 | 35.7 | 35.4 | 35.8 | 36.1 | 3.4 | 9.4% | 31.4 | 41.9 | 35.6 |  | 52.0 | 23.02× |
| rust/s9-speed/rayon | 1,000 | 32.3 | 32.1 | 32.5 | 32.6 | 3.1 | 9.5% | 28.2 | 38.1 | 32.2 |  | 47.7 | 25.39× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| python/seq | 1 | on | 1,459.3 | 1,412.5 | 0.97 | 162.4 | 162.4 |
| python3.14t/thread | 24 | off | 1,181.2 | 2,118.9 | 1.80 | 371.4 | 371.4 |
| rust/baseline/rayon | 24 |  | 250.5 | 707.9 | 2.82 | 141.5 | 141.5 |
| rust/s9-safe/rayon | 24 |  | 52.0 | 487.3 | 9.32 | 135.2 | 135.2 |
| rust/s9-speed/rayon | 24 |  | 47.7 | 455.4 | 9.49 | 131.4 | 131.4 |

## Rust snapshots

| mode | snapshot | median_ms | vs_previous_pct | vs_previous_ci_low | vs_previous_ci_high | vs_first_pct | vs_first_ci_low | vs_first_ci_high |
|---|---|---|---|---|---|---|---|---|
| rayon | baseline | 198.2 | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| rayon | s9-safe | 35.7 | -82.0% | -82.2% | -81.9% | -82.0% | -82.2% | -81.9% |
| rayon | s9-speed | 32.3 | -9.3% | -10.0% | -8.5% | -83.7% | -83.8% | -83.6% |
