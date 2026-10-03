# 20261002-225404_languages

Reference for speed-up: `python/seq`. Times in ms; CI = 95% bootstrap interval of the median (2000 resamples).

| config | n | median_ms | median_ci_low | median_ci_high | mean_ms | sd_ms | cv_pct | p5_ms | p95_ms | index_median_ms | merge_median_ms | wall_median_ms | speedup |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| python/seq | 1,000 | 789.3 | 787.5 | 792.0 | 795.0 | 37.2 | 4.7% | 752.7 | 856.7 | 729.4 | 53.1 | 1,339.9 | 1.00× |
| python/process | 1,000 | 441.6 | 440.4 | 443.2 | 448.2 | 27.8 | 6.2% | 420.3 | 501.6 | 379.1 | 59.0 | 920.0 | 1.79× |
| python/thread | 1,000 | 888.4 | 886.5 | 890.7 | 897.2 | 38.7 | 4.3% | 858.9 | 960.7 | 824.3 | 56.3 | 1,463.9 | 0.89× |
| rust/baseline/1-thread | 1,000 | 345.6 | 344.5 | 347.1 | 353.3 | 27.5 | 7.8% | 327.6 | 400.5 | nan | nan | 381.7 | 2.28× |
| rust/baseline/rayon | 1,000 | 178.0 | 177.2 | 178.8 | 180.7 | 14.4 | 8.0% | 164.1 | 203.3 | nan | nan | 224.7 | 4.43× |
