#!/bin/sh
# Scripted mastermind (the player who INITIATES the challenge).
# Sets master sequence 12345, then answers feedback prompts with the
# correct pegs (validated by the game against its own computation).
set -u
. /opt/test/driver.sh

start_player

wait_for "Enter your name:"
send "feena"

# wait until the other player shows up in the discovery table, then challenge
i=0
ID=""
while [ "$i" -lt 150 ]; do
    ID=$(peer_id tatva)
    [ -n "$ID" ] && break
    sleep 0.1
    i=$((i + 1))
done
if [ -z "$ID" ]; then
    echo "driver: never discovered peer 'tatva'" >&2
    tail -c 1500 "$OUT" >&2 || true
    exit 1
fi

send "challenge $ID"

wait_for "Enter master sequence (5 digits):"
send "12345"

# attempt 1: tatva guesses 11111 -> feedback x----
wait_for "Enter feedback (5 chars using 'o', 'x', '-'):"
send "x----"

# attempt 2: tatva guesses 12345 -> feedback xxxxx (game over)
wait_for "Enter feedback (5 chars using 'o', 'x', '-'):"
send "xxxxx"

wait_for "Press enter to go home."
send ""

driver_finish
