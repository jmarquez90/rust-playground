FROM rust:1.99-slim-trixie

# Packages the JetBrains IDE backend needs inside the container, plus git and gdb.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl unzip procps git gdb linux-perf libxext6 libxrender1 libxtst6 libxi6 libfreetype6 \
 && rm -rf /var/lib/apt/lists/* \
 && rustup component add clippy rustfmt rust-src \
 && useradd -m -s /bin/bash dev \
 && mkdir -p /home/dev/target /usr/local/cargo/registry \
 && chown dev /home/dev/target /usr/local/cargo/registry

USER dev

# Profiling: cargo flamegraph (uses perf from linux-perf above)
RUN cargo install flamegraph

# Python tooling for bench/: uv, the Pythons the scripts use, and their packages
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
RUN uv python install 3.14 3.14t
RUN uv run --python 3.14 --with "pandas>=2.2" --with "pyarrow>=17" --with "matplotlib>=3.9" --with "numpy>=2" \
      python -c "import pandas, pyarrow, matplotlib, numpy"