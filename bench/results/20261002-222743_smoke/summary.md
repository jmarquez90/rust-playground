# 20261002-222743_smoke

Reference for speed-up: `python/seq`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python/seq | 20 | 795.4 | 777.0 | 811.0 | 806.9 | 48.2 | 6.0% | 767.5 | 867.3 | 735.7 | 50.8 | 1,367.0 | 1.00× |
| python/process | 20 | 462.1 | 441.4 | 485.4 | 467.7 | 33.7 | 7.2% | 429.3 | 525.3 | 399.0 | 59.3 | 936.0 | 1.72× |
| python/thread | 20 | 906.6 | 896.4 | 914.5 | 909.7 | 30.2 | 3.3% | 870.9 | 947.6 | 840.2 | 59.6 | 1,489.6 | 0.88× |
| rust/baseline/1-thread | 20 | 346.2 | 336.8 | 360.3 | 356.7 | 34.2 | 9.6% | 327.2 | 437.1 | nan | nan | 385.6 | 2.30× |
| rust/baseline/rayon | 20 | 177.7 | 169.3 | 184.8 | 178.5 | 11.9 | 6.7% | 164.3 | 198.3 | nan | nan | 221.5 | 4.48× |
