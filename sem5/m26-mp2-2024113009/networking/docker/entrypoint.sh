#!/bin/sh
set -eu

# --- Make UDP broadcast discovery work on Docker's isolated bridge -------
# The compose network uses "internal: true", so containers have no default
# route. sendto(255.255.255.255) needs one and fails with ENETUNREACH,
# which silently kills discovery between players. An explicit link route
# for the limited broadcast fixes that (requires NET_ADMIN, which compose
# grants to every player). Best effort: ignored if not permitted.
if command -v ip >/dev/null 2>&1; then
    ip route add 255.255.255.255 dev eth0 2>/dev/null || true
fi

# --- Simulate "the institute blocks TCP" (cost-cutting evaluation) ------
if [ "${BLOCK_TCP:-0}" = "1" ]; then
    echo "[entrypoint] BLOCK_TCP=1: rejecting all TCP traffic in both directions (UDP still allowed)" >&2
    # REJECT (not DROP) so connect() fails immediately instead of hanging
    # for ~130s waiting for SYN retransmissions.
    iptables -A OUTPUT -p tcp -j REJECT --reject-with icmp-port-unreachable
    iptables -A INPUT  -p tcp -j REJECT --reject-with icmp-port-unreachable
    # leave durable proof of the active rules in the bind-mounted log dir
    # (the game may exit before any test gets a chance to docker exec)
    iptables-save > /data/iptables.rules 2>/dev/null || true
fi

# --- Drop privileges so bind-mounted log.txt is owned by the host user ---
# iptables/ip above needed root; the game itself does not. PUID/PGID are
# set by docker-compose (host uid/gid), overridable via environment.
run() {
    if [ "$(id -u)" = "0" ] && [ "${PUID:-0}" != "0" ]; then
        # log.txt must end up owned by the host user; /data is a bind mount
        # whose stale files may be root-owned from earlier runs.
        chown -R "$PUID:${PGID:-$PUID}" /data 2>/dev/null || true
        exec setpriv --reuid="$PUID" --regid="${PGID:-$PUID}" --clear-groups -- "$@"
    fi
    exec "$@"
}

if [ -n "${PLAYER_SCRIPT:-}" ]; then
    echo "[entrypoint] running scripted player: $PLAYER_SCRIPT" >&2
    run sh -c "$PLAYER_SCRIPT"
fi

echo "[entrypoint] starting mastermind ${MASTERMIND_FLAGS:-} (log: /data/log.txt)" >&2
# shellcheck disable=SC2086  # word splitting of MASTERMIND_FLAGS is intended
run mastermind ${MASTERMIND_FLAGS:-}
