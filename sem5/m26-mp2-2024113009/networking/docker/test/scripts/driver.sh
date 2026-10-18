#!/bin/sh
# Shared helper for scripted players (entrypoint PLAYER_SCRIPT mode).
#
# The game reads its prompts from stdout, so a scripted player runs
# mastermind with stdin on this FIFO and stdout/stderr captured to $OUT.
# stdbuf -oL forces line buffering: stdout is a file here (fully buffered
# by default), and some end-of-game messages are only flushed on newline.
# wait_for scans $OUT for the next expected prompt, then we write a line to
# the FIFO (fd 3). $OFF remembers how much of $OUT we already consumed so
# repeated prompts ("Enter feedback ...") are matched in order.
set -u

OUT=/tmp/player-out.txt
FIFO=/tmp/player-in.fifo
OFF=0

start_player() {
    rm -f "$OUT" "$FIFO"
    mkfifo "$FIFO"
    # open read+write so open() never blocks and the game's stdin stays
    # open until driver_finish closes it (EOF -> game exits cleanly)
    exec 3<>"$FIFO"
    # shellcheck disable=SC2086  # MASTERMIND_FLAGS is intentionally split
    stdbuf -oL mastermind $MASTERMIND_FLAGS <"$FIFO" >"$OUT" 2>&1 &
    GAME=$!
}

wait_for() {
    pat=$1
    i=0
    while [ "$i" -lt 200 ]; do
        if tail -c +$((OFF + 1)) "$OUT" 2>/dev/null | grep -qF -- "$pat"; then
            OFF=$(wc -c <"$OUT")
            return 0
        fi
        # fail fast if the game died while we were waiting
        kill -0 "$GAME" 2>/dev/null || { echo "driver: game exited early" >&2; tail -c 1500 "$OUT" >&2 || true; exit 1; }
        sleep 0.1
        i=$((i + 1))
    done
    echo "driver: timed out waiting for [$pat]" >&2
    echo "driver: ---- tail of game output ----" >&2
    tail -c 1500 "$OUT" >&2 || true
    exit 1
}

send() {
    printf '%s\n' "$1" >&3
    sleep 0.3
}

# peer_id <name> -> discovery-table ID of that player (most recent match).
# Table rows look like "<ESC>[3;1H<ESC>[K1   tatva          172.20.0.2 ...",
# all concatenated on one line because rows are positioned with ANSI codes.
peer_id() {
    grep -aF "$1" "$OUT" 2>/dev/null | tail -1 | \
        grep -oE "[0-9]+ +$1" | tail -1 | \
        grep -oE "^[0-9]+"
}

driver_finish() {
    sleep 1
    exec 3>&-            # EOF to the game
    # Note: the game polls stdin for POLLIN only, so a closed FIFO (which
    # surfaces as POLLHUP, not POLLIN) is never seen as EOF by the game.
    # SIGINT is the clean "user quits" path the game does handle (exit 0),
    # so nudge the game that way if it is still alive after the EOF.
    i=0
    while kill -0 "$GAME" 2>/dev/null && [ "$i" -lt 20 ]; do
        sleep 0.1
        i=$((i + 1))
    done
    if kill -0 "$GAME" 2>/dev/null; then
        kill -INT "$GAME" 2>/dev/null
        i=0
        while kill -0 "$GAME" 2>/dev/null && [ "$i" -lt 30 ]; do
            sleep 0.1
            i=$((i + 1))
        done
    fi
    rc=0
    wait "$GAME" 2>/dev/null || rc=$?
    exit "$rc"
}

# Every exit path (finish, timeout, game crash) replays the captured
# session to the container's stdout, so `docker compose logs` shows the
# board and prompts -- that is what run_tests.sh asserts on.
on_exit() {
    rc=$?
    trap - EXIT
    [ -n "${GAME:-}" ] && kill "$GAME" 2>/dev/null
    echo "===== scripted player session ====="
    cat "$OUT" 2>/dev/null
    exit "$rc"
}
trap on_exit EXIT
