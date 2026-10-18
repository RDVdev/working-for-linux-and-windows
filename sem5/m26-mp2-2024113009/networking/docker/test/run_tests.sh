#!/usr/bin/env bash
# Automated evaluation of the mastermind docker testbed.
#
#   ./run_tests.sh            run all scenarios
#   ./run_tests.sh tcp        scenario 1 only: full game over TCP
#   ./run_tests.sh costcut    scenario 2 only: full game over UDP with TCP blocked
#   ./run_tests.sh noblock    scenario 3 only: TCP blocked, no --cost-cutting
#                             -> challenge must FAIL to connect
#
# Each scenario starts player1 (codebreaker "tatva") and player2
# (mastermind "feena") as scripted players on an isolated compose project,
# waits for them to exit, then asserts on:
#   - container exit codes
#   - the per-player log.txt (network events, --log)
#   - the players' terminal output (boards, prompts, results)
set -u

cd "$(dirname "$0")/../.."   # networking/

PROJECT="mmtest"
BASE="docker-compose.yml"
TESTC="docker/test/compose.test.yml"
TIMEOUT=90

PASS=0
FAIL=0

say()  { printf '\n== %s\n' "$*"; }
ok()   { printf '   PASS: %s\n' "$*"; PASS=$((PASS + 1)); }
bad()  { printf '   FAIL: %s\n' "$*"; FAIL=$((FAIL + 1)); }

compose() {
    docker compose -p "$PROJECT" -f "$BASE" -f "$TESTC" "$@"
}

# teardown of the previous scenario (keeps the image)
down() {
    compose down --remove-orphans --timeout 5 >/dev/null 2>&1
}

# fetch a player's captured stdout (scripted players print the game's
# output to the container stdout at exit)
player_out() { compose logs --no-color "player$1" 2>/dev/null; }

player_log() { echo "docker/logs/player$1/log.txt"; }

wait_exit() { # wait_exit <seconds> <service>...
    local deadline=$(( $(date +%s) + $1 )) cid
    shift
    while :; do
        local all_done=1
        for svc in "$@"; do
            cid=$(compose ps -aq "$svc")
            if [ -n "$cid" ]; then
                if [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" = "true" ]; then
                    all_done=0
                fi
            fi
        done
        [ "$all_done" = "1" ] && return 0
        if [ "$(date +%s)" -ge "$deadline" ]; then
            return 1
        fi
        sleep 1
    done
}

exit_code() {
    local cid
    cid=$(compose ps -aq "$1")
    docker inspect -f '{{.State.ExitCode}}' "$cid" 2>/dev/null || echo "missing"
}

# remove stale log files of a player so scenario assertions start clean
clear_log() {
    rm -f "docker/logs/player$1/log.txt" "docker/logs/player$1/iptables.rules"
}

# ---------------------------------------------------------------- scenarios

scenario_tcp() {
    say "scenario tcp: full game over TCP"
    down
    clear_log 1; clear_log 2

    if ! compose up -d --build player1 player2 > /tmp/mm_up.log 2>&1; then
        bad "compose up failed (see /tmp/mm_up.log)"
        return
    fi

    if ! wait_exit "$TIMEOUT" player1 player2; then
        bad "players did not finish within ${TIMEOUT}s"
        down
        return
    fi

    local rc1 rc2
    rc1=$(exit_code player1); rc2=$(exit_code player2)
    [ "$rc1" = "0" ] && ok "codebreaker exited 0" || bad "codebreaker exit=$rc1"
    [ "$rc2" = "0" ] && ok "mastermind exited 0" || bad "mastermind exit=$rc2"

    local out1 out2
    out1=$(player_out 1); out2=$(player_out 2)

    echo "$out1" | grep -q "You solved the sequence in 2 attempts" \
        && ok "codebreaker won in 2 attempts" || bad "codebreaker win message missing"
    echo "$out1" | grep -q $'\*\*\*\*\*' \
        && ok "codebreaker saw hidden board" || bad "codebreaker board missing"
    echo "$out2" | grep -q "tatva found the sequence in 2 attempts" \
        && ok "mastermind saw the win" || bad "mastermind win message missing"
    # compose logs prefixes each line with "player2-1  | ", so strip it
    # before running anchored matches
    echo "$out2" | sed 's/^[^|]*| //' | grep -q "^12345$" \
        && ok "mastermind board shows master sequence" || bad "master sequence not on mastermind board"

    local log1 log2
    log1=$(player_log 1); log2=$(player_log 2)
    [ -s "$log1" ] && ok "codebreaker log.txt written" || bad "codebreaker log.txt missing"
    [ -s "$log2" ] && ok "mastermind log.txt written" || bad "mastermind log.txt missing"
    grep -q "Network transport initialized (TCP" "$log1" 2>/dev/null \
        && ok "codebreaker used TCP transport" || bad "codebreaker transport not TCP"
    grep -q "Accepted TCP connection" "$log1" 2>/dev/null \
        && ok "codebreaker accepted TCP connection" || bad "no accepted TCP connection logged"
    grep -q "Sent TCP game message (verb: 5)" "$log2" 2>/dev/null \
        && ok "mastermind sent GAME_OVER over TCP" || bad "GAME_OVER not sent over TCP"

    down
}

scenario_costcut() {
    say "scenario costcut: full game over UDP, TCP blocked at the container"
    down
    clear_log 1; clear_log 2

    if ! docker compose -p "$PROJECT" -f "$BASE" -f "$TESTC" \
            -f docker-compose.costcut.yml up -d --build player1 player2 \
            > /tmp/mm_up.log 2>&1; then
        bad "compose up failed (see /tmp/mm_up.log)"
        return
    fi

    # proof that TCP really is blocked inside the containers: the
    # entrypoint dumps the active rules into the bind-mounted log dir
    local rules1
    rules1="docker/logs/player1/iptables.rules"
    if grep -q -- '-p tcp -j REJECT' "$rules1" 2>/dev/null; then
        ok "iptables REJECT rule for TCP active"
    else
        bad "no TCP REJECT rule found"
    fi

    if ! wait_exit "$TIMEOUT" player1 player2; then
        bad "players did not finish within ${TIMEOUT}s"
        down
        return
    fi

    local rc1 rc2
    rc1=$(exit_code player1); rc2=$(exit_code player2)
    [ "$rc1" = "0" ] && ok "codebreaker exited 0" || bad "codebreaker exit=$rc1"
    [ "$rc2" = "0" ] && ok "mastermind exited 0" || bad "mastermind exit=$rc2"

    local out1 out2
    out1=$(player_out 1); out2=$(player_out 2)

    echo "$out1" | grep -q "You solved the sequence in 2 attempts" \
        && ok "codebreaker won in 2 attempts" || bad "codebreaker win message missing"
    echo "$out2" | grep -q "tatva found the sequence in 2 attempts" \
        && ok "mastermind saw the win" || bad "mastermind win message missing"

    local log1 log2
    log1=$(player_log 1); log2=$(player_log 2)
    grep -q "Network transport initialized (UDP" "$log1" 2>/dev/null \
        && ok "codebreaker used UDP transport" || bad "codebreaker transport not UDP"
    grep -q "Sent UDP chunk" "$log1" 2>/dev/null \
        && ok "codebreaker sent UDP chunks" || bad "no UDP chunks in codebreaker log"
    grep -q "Received ACK for chunk" "$log1" 2>/dev/null \
        && ok "codebreaker received ACKs" || bad "no ACKs in codebreaker log"
    grep -q "Received complete UDP game message (verb: 5)" "$log1" 2>/dev/null \
        && ok "codebreaker got GAME_OVER over UDP" || bad "GAME_OVER not received over UDP"

    down
}

scenario_noblock() {
    say "scenario noblock: TCP blocked but --cost-cutting NOT given"
    down
    clear_log 1; clear_log 2

    if ! docker compose -p "$PROJECT" -f "$BASE" -f "$TESTC" \
            -f docker/test/compose.tcpblock.yml up -d --build player1 player2 \
            > /tmp/mm_up.log 2>&1; then
        bad "compose up failed (see /tmp/mm_up.log)"
        return
    fi

    if ! wait_exit "$TIMEOUT" player1 player2; then
        bad "players did not finish within ${TIMEOUT}s"
        down
        return
    fi

    local out1 out2 log1 log2
    out1=$(player_out 1); out2=$(player_out 2)
    log1=$(player_log 1); log2=$(player_log 2)

    echo "$out2" | grep -qi "Could not connect" \
        && ok "challenge failed to connect (TCP really blocked)" \
        || bad "expected a connection failure"
    echo "$out1" | grep -q "You solved" && bad "a game was played over blocked TCP" || true
    grep -q "Sent TCP game message (verb: 3)" "$log2" 2>/dev/null \
        && bad "guess sent despite blocked TCP" || ok "no game traffic over blocked TCP"

    down
}

# ----------------------------------------------------------------- dispatch

case "${1:-all}" in
    tcp)     scenario_tcp ;;
    costcut) scenario_costcut ;;
    noblock) scenario_noblock ;;
    all)     scenario_tcp; scenario_costcut; scenario_noblock ;;
    *)       echo "usage: $0 [tcp|costcut|noblock|all]" >&2; exit 2 ;;
esac

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
