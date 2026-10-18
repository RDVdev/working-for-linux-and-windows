#!/bin/sh
# Scripted codebreaker (the player who ACCEPTS the challenge).
# Role: guesses. Mastermind is expected to use 12345; we guess 11111 then
# 12345 so the game ends on attempt 2 with a win.
set -u
. /opt/test/driver.sh

start_player

wait_for "Enter your name:"
send "tatva"

# wait until the challenger's challenge arrives, then accept
wait_for "Accept? (yes/no):"
send "yes"

# the first prompt after accepting is "Enter your first guess (5 digits):"
wait_for "Enter your first guess (5 digits):"
send "11111"

# subsequent guesses use the short prompt "Enter guess (5 digits):"
wait_for "Enter guess (5 digits):"
send "12345"

wait_for "Press enter to go home."
send ""

driver_finish
