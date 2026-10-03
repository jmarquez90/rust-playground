# 20261003-003932_languages-v2

Reference for speed-up: `python/seq`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python/seq | 1,000 | 756.7 | 755.2 | 757.8 | 761.3 | 22.6 | 3.0% | 737.5 | 798.5 | 703.4 | 47.7 | 1,274.4 | 1.00× |
| python/process | 1,000 | 421.7 | 421.0 | 422.5 | 426.0 | 15.1 | 3.5% | 411.1 | 455.4 | 364.1 | 54.8 | 849.7 | 1.79× |
| python/thread | 1,000 | 857.9 | 856.8 | 858.9 | 863.1 | 23.5 | 2.7% | 842.0 | 898.3 | 800.9 | 50.9 | 1,397.1 | 0.88× |
| python3.14t/thread | 1,000 | 428.8 | 427.3 | 431.0 | 433.9 | 35.5 | 8.2% | 394.2 | 488.3 | 354.0 | 58.9 | 1,068.3 | 1.76× |
| rust/baseline/1-thread | 1,000 | 331.6 | 331.0 | 332.2 | 334.8 | 14.8 | 4.4% | 321.2 | 361.1 | nan | nan | 364.1 | 2.28× |
| rust/baseline/rayon | 1,000 | 170.9 | 170.4 | 171.4 | 172.6 | 12.4 | 7.2% | 161.1 | 188.1 | nan | nan | 214.0 | 4.43× |

## Resources

Medians per run, for the whole process (start-up and exit included). cores_used = CPU time / wall time. Peak memory in MB: the largest single process, and the whole process tree (sampled, so approximate; memory shared between processes counts in each).

| config | threads | gil | wall_median_ms | cpu_median_ms | cores_used | peak_rss_median_mb | peak_tree_rss_median_mb |
|---|---|---|---|---|---|---|---|
| python/seq | 1 | on | 1,274.4 | 1,231.1 | 0.97 | 212.6 | 212.6 |
| python/process | 24 | on | 849.7 | 2,580.0 | 3.04 | 212.6 | 673.3 |
| python/thread | 24 | on | 1,397.1 | 1,374.6 | 0.98 | 238.6 | 238.6 |
| python3.14t/thread | 24 | off | 1,068.3 | 1,907.1 | 1.79 | 370.2 | 370.2 |
| rust/baseline/1-thread | 1 |  | 364.1 | 362.1 | 0.99 | 212.6 | 212.6 |
| rust/baseline/rayon | 24 |  | 214.0 | 627.2 | 2.93 | 212.6 | 212.6 |
