# Everything viva runs on student code: concurrency builds and runs, xv6 builds and qemu.
FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libc6-dev make bc \
        gcc-riscv64-linux-gnu binutils-riscv64-linux-gnu qemu-system-misc \
    && rm -rf /var/lib/apt/lists/*

ENV TOOLPREFIX=riscv64-linux-gnu-
WORKDIR /w
