# Mastermind evaluation testbed image.
# Build context is networking/ (the compose file sets it), so paths below
# are relative to networking/.
#
# Stage 1: compile with gcc 14 (the assignment requires -std=c23, which
# needs gcc >= 14; the project Makefile picks up gcc-14 or falls back to gcc).
FROM gcc:14-bookworm AS build
WORKDIR /build
COPY mastermind/ ./mastermind/
RUN make -C mastermind

# Stage 2: slim runtime. iptables is installed because the "cost-cutting"
# test profile simulates the institute banning TCP by dropping TCP packets
# inside the container (requires NET_ADMIN, granted by compose).
FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends iptables iproute2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /build/mastermind/mastermind /usr/local/bin/mastermind
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
# scripted players used by docker/test/run_tests.sh (PLAYER_SCRIPT mode)
COPY docker/test/scripts/ /opt/test/
RUN chmod +x /usr/local/bin/entrypoint.sh /opt/test/*.sh

# log.txt is written into the working directory; each compose service
# bind-mounts its own directory here so the host can read the logs.
WORKDIR /data

ENV BLOCK_TCP=0 \
    MASTERMIND_FLAGS= \
    PLAYER_SCRIPT=

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["--log"]
