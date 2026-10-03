FROM rust:1.99-slim-trixie

# Packages the JetBrains IDE backend needs inside the container, plus git and gdb.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl unzip procps git gdb libxext6 libxrender1 libxtst6 libxi6 libfreetype6 \
 && rm -rf /var/lib/apt/lists/* \
 && rustup component add clippy rustfmt rust-src \
 && useradd -m -s /bin/bash dev \
 && mkdir -p /home/dev/target /usr/local/cargo/registry \
 && chown dev /home/dev/target /usr/local/cargo/registry

USER dev
