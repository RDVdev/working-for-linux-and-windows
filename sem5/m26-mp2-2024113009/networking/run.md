# Mastermind testbed — run guide for the TA

Everything below is run from the `networking/` directory of this repo:

```sh
cd networking/
```

Prerequisites: Docker with the compose plugin (`docker compose version`
should work) and permission to run docker (user in the `docker` group).
No other dependencies — the image build pulls `gcc:14-bookworm` and
`debian:bookworm-slim` automatically (first build downloads ~200 MB and
takes about a minute).

If your host uid/gid is not 1000:1000, prefix compose commands with
`PUID=$(id -u) PGID=$(id -g)` so the log files come out owned by you
(default is already 1000:1000 on most Linux desktops).

---

## 1. What each file is

```
networking/
├── run.md                          # this file
├── docker-compose.yml              # BASE: 4 interactive players (TCP game + UDP discovery)
├── docker-compose.costcut.yml      # OVERLAY: --cost-cutting (UDP transfer) + TCP blocked
├── docker/
│   ├── Dockerfile                  # multi-stage build: gcc-14 compiles mastermind (make,
│   │                               #   -std=c23), slim runtime gets iptables + iproute2
│   ├── entrypoint.sh               # container startup: (a) adds route 255.255.255.255 dev eth0
│   │                               #   so UDP broadcast discovery works on the isolated bridge,
│   │                               #   (b) if BLOCK_TCP=1: iptables REJECT all TCP both ways and
│   │                               #   dump the rules to /data/iptables.rules, (c) drops to
│   │                               #   PUID/PGID via setpriv so log.txt is host-owned,
│   │                               #   (d) runs the game (or a scripted-player script)
│   ├── README.md                   # short usage notes
│   ├── logs/
│   │   ├── player1/ … player4/     # bind-mounted into each container as /data:
│   │       └── (.gitkeep)          #   log.txt (game's --log output) and, in blocked runs,
│   │                               #   iptables.rules (proof the TCP block was active)
│   └── test/
│       ├── run_tests.sh            # automated scenario runner: tcp | costcut | noblock | all
│       ├── compose.test.yml        # OVERLAY: turns player1/player2 into scripted players
│       ├── compose.tcpblock.yml    # OVERLAY: BLOCK_TCP=1 but WITHOUT --cost-cutting
│       │                           #   (negative control: challenge must fail)
│       └── scripts/
│           ├── driver.sh           # shared driver: runs the game with stdin on a FIFO,
│           │                       #   watches its stdout for the next prompt, then sends a
│           │                       #   line — no sleep-based guessing; also parses the ANSI
│           │                       #   discovery table to find a peer's ID
│           ├── codebreaker.sh      # scripted player1 "tatva": accepts the challenge, guesses
│           │                       #   11111 then 12345 → wins in 2 attempts
│           └── mastermind.sh       # scripted player2 "feena": waits for tatva in the
│                                   #   discovery table, challenges, sets master 12345,
│                                   #   answers feedback x---- then xxxxx
└── mastermind/                     # student submission (compiled inside the image, unmodified)
```

How the pieces fit together:

* Every compose file runs the same image; behaviour is switched purely by
  env vars read by `entrypoint.sh`: `BLOCK_TCP` (0/1),
  `MASTERMIND_FLAGS` (e.g. `--log`, `--log --cost-cutting`), `PLAYER_SCRIPT`
  (empty = interactive, else a scripted player).
* All four players sit on one Docker bridge network `mmlan` marked
  `internal: true` — nothing can leave the compose network, so the UDP
  broadcast discovery (port 61337, "MMND" magic, every 2 s) never touches
  the IIIT-H LAN. Because an internal bridge has no default route, the
  entrypoint adds `ip route add 255.255.255.255 dev eth0` (this is why
  compose grants `NET_ADMIN`; it only affects the container's own
  namespace).
* Each container bind-mounts `docker/logs/playerN` to `/data`; the game
  runs with cwd `/data` and `--log`, so `log.txt` appears on the host,
  owned by your uid.

---

## 2. Fastest check: the automated test suite

```sh
./docker/test/run_tests.sh
```

Takes ~2–3 minutes. Expected final output (this is the known-good
reference; 22 assertions, all should PASS):

```
== scenario tcp: full game over TCP
   PASS: codebreaker exited 0
   PASS: mastermind exited 0
   PASS: codebreaker won in 2 attempts
   PASS: codebreaker saw hidden board
   PASS: mastermind saw the win
   PASS: mastermind board shows master sequence
   PASS: codebreaker log.txt written
   PASS: mastermind log.txt written
   PASS: codebreaker used TCP transport
   PASS: codebreaker accepted TCP connection
   PASS: mastermind sent GAME_OVER over TCP
== scenario costcut: full game over UDP, TCP blocked at the container
   PASS: iptables REJECT rule for TCP active
   PASS: codebreaker exited 0
   PASS: mastermind exited 0
   PASS: codebreaker won in 2 attempts
   PASS: mastermind saw the win
   PASS: codebreaker used UDP transport
   PASS: codebreaker sent UDP chunks
   PASS: codebreaker received ACKs
   PASS: codebreaker got GAME_OVER over UDP
== scenario noblock: TCP blocked but --cost-cutting NOT given
   PASS: challenge failed to connect (TCP really blocked)
   PASS: no game traffic over blocked TCP

22 passed, 0 failed
```

Individual scenarios (each is self-contained: it starts a throwaway
compose project `mmtest`, plays a full scripted game, asserts, tears
down):

```sh
./docker/test/run_tests.sh tcp       # scenario 1: full game over TCP
./docker/test/run_tests.sh costcut   # scenario 2: full game over UDP, TCP blocked
./docker/test/run_tests.sh noblock   # scenario 3: negative control
```

What each scenario actually proves:

| scenario | containers | proves |
|---|---|---|
| `tcp` | player1 = codebreaker "tatva", player2 = mastermind "feena", TCP mode | discovery across containers, TCP challenge/accept, 2-attempt game, win messages on both sides, `log.txt` shows `Network transport initialized (TCP`, `Accepted TCP connection`, `Sent TCP game message (verb: 5)` (GAME_OVER) |
| `costcut` | same two players, `--cost-cutting` + `BLOCK_TCP=1` | the same full game completes when **every TCP packet is rejected** inside both containers — so state transfer really went over the reliable-UDP path: `log.txt` shows `Network transport initialized (UDP`, `Sent UDP chunk`, `Received ACK for chunk`, `Received complete UDP game message (verb: 5)`; also asserts the iptables REJECT rules were active (`docker/logs/player1/iptables.rules`) |
| `noblock` | TCP blocked but **no** `--cost-cutting` | control experiment: the challenge fails with `Could not connect` and no game traffic is logged — proving the `costcut` pass came from the UDP transfer, not from TCP sneaking through |

Scripted players talk to the game through a FIFO and wait for its exact
prompts (e.g. `Accept? (yes/no):`, `Enter guess (5 digits):`), so there is
no timing guesswork; they replay the full captured session to the
container's stdout so you can inspect it afterwards (see §5).

Note on the scripted exit: the game polls stdin for `POLLIN` only, so it
does not notice EOF when the FIFO writer closes (a closed FIFO surfaces
as `POLLHUP`). The driver therefore finishes with SIGINT, which the game
handles cleanly (flushes logs, exits 0). Interactive runs are unaffected.

---

## 3. Manual run — 4 players over TCP (normal mode)

```sh
docker compose up -d --build
```

Starts `player1` … `player4`. Each is a live `mastermind` waiting for a
name. Attach to one (repeat in 2+ terminals to play against yourself):

```sh
docker compose attach player1        # detach without killing: Ctrl-p then Ctrl-q
```

Play:

1. Type a name (e.g. `alice`) and Enter.
2. Wait ~2–6 s: the "Players Online" table fills as discovery broadcasts
   arrive (every player broadcasts every 2 s).
3. On the challenger's terminal type `challenge <ID>` (the ID column of
   the table), e.g. `challenge 1`.
4. On the other terminal answer `yes` (or `no`).
5. The **challenger becomes mastermind**: enter a 5-digit master
   sequence, e.g. `12345`.
6. The **acceptor becomes codebreaker**: guess 5-digit sequences; after
   each guess the mastermind must enter feedback of 5 chars using only
   `x` (exact digit+position, shown green), `o` (right digit, wrong
   position, shown yellow), `-` (miss, shown red) with the right counts
   of each — the game validates that the mastermind plays fair.
7. 12 attempts max; the codebreaker wins by feedback `xxxxx`. Both sides
   then show `Press enter to go home.` — Enter returns to the
   discovery table for another round.
8. Ctrl-C (while attached) quits the game; container exits.

Sanity checks while it runs:

```sh
# discovery is crossing containers: each player should list the OTHER names
grep -o "Received UDP discovery from [a-z0-9]*" docker/logs/player1/log.txt | sort -u

# transport really is TCP
grep "Network transport initialized" docker/logs/player1/log.txt
#   -> Network transport initialized (TCP, port <ephemeral>)

# a completed game leaves its verbs in the log (1=CHALLENGE 2=RESP 3=GUESS 4=FEEDBACK 5=GAME_OVER)
grep "game message" docker/logs/player2/log.txt
```

Tear down:

```sh
docker compose down --remove-orphans
```

---

## 4. Manual run — cost-cutting mode (TCP blocked)

```sh
docker compose -f docker-compose.yml -f docker-compose.costcut.yml up -d --build
```

Same 4 players, but each container:

* runs `mastermind --log --cost-cutting`, and
* rejects **all TCP in both directions** via iptables before the game
  starts (REJECT, not DROP, so a blocked `connect()` fails immediately
  instead of hanging ~130 s on SYN retransmits). UDP discovery is
  untouched.

Attach and play exactly as in §3 — the whole game (challenge, guesses,
feedback, game-over) must work over the reliable-UDP transport despite
TCP being dead. A game over TCP is impossible here; if the student's
`--cost-cutting` path is broken, the challenge simply never completes.

Verify the block was actually in force:

```sh
cat docker/logs/player1/iptables.rules     # dumped by the entrypoint at startup
#   expect: -A INPUT  -p tcp -j REJECT --reject-with icmp-port-unreachable
#           -A OUTPUT -p tcp -j REJECT --reject-with icmp-port-unreachable
#   (UDP rules must NOT be there)

grep "Network transport initialized" docker/logs/player1/log.txt
#   -> Network transport initialized (UDP, port <ephemeral>)

# watch the reliable-UDP machinery while a game runs
grep -E "Sent UDP chunk|Received ACK|Retransmitted" docker/logs/player1/log.txt
```

Tear down:

```sh
docker compose -f docker-compose.yml -f docker-compose.costcut.yml down --remove-orphans
```

---

## 5. Where to check what

| what | where |
|---|---|
| per-player network log (`--log`, appended) | `docker/logs/playerN/log.txt` |
| proof the TCP block was active (blocked runs only) | `docker/logs/playerN/iptables.rules` |
| terminal output (interactive attach, entrypoint messages) | `docker compose logs playerN` or `docker compose attach playerN` |
| container state / exit codes | `docker compose ps -a` |
| test-suite results | stdout of `./docker/test/run_tests.sh` |

Useful `log.txt` lines and what they mean:

| log line | meaning |
|---|---|
| `Sent UDP discovery broadcast (name: X, listen_port: P)` | this player announced itself |
| `Received UDP discovery from Y (ip:port)` | discovery crossed containers |
| `Network transport initialized (TCP, port P)` / `(UDP, port P)` | which transport the game picked (`--cost-cutting` → UDP) |
| `TCP connected to …` / `Accepted TCP connection from …` | TCP challenge/accept handshake |
| `Sent/Received TCP game message (verb: N)` | verbs: 1=CHALLENGE 2=RESPONSE 3=GUESS 4=FEEDBACK 5=GAME_OVER 6=DISCONNECT |
| `Sent UDP chunk i/n (msg_id: M)` / `Received ACK for chunk …` / `Retransmitted un-ACKed chunk …` | reliable-UDP transfer in `--cost-cutting` mode |
| `Received complete UDP game message (verb: N)` | a UDP message was reassembled |

Note `docker compose logs` prefixes every line with the service name
(e.g. `player2-1  | `); `log.txt` has no prefix.

---

## 6. Reset / cleanup

```sh
# stop everything (both modes, plus any leftover test project)
docker compose down --remove-orphans
docker compose -p mmtest down --remove-orphans

# clear generated logs (host-owned, no sudo needed)
rm -f docker/logs/player*/log.txt docker/logs/player*/iptables.rules

# optional: drop the image to force a full rebuild next time
docker rmi mastermind-testbed:latest
```

Logs are appended, never truncated, by the program itself — delete them
before a run if you want per-run logs. `.gitignore` already excludes
`log.txt` and `iptables.rules`, so they never end up in a commit.

---

## 7. Known observations about the submission (not blockers)

* `main.c` calls `logger_init("log.txt")` but the parameter is `bool` —
  it compiles (non-null pointer → `true`) and logging works, though it is
  a type bug.
* The main loop polls stdin for `POLLIN` only, so the game cannot exit on
  EOF of a redirected stdin (closed FIFO → `POLLHUP`, never observed).
  Interactive use is unaffected; the test driver exits via SIGINT.
* The discovery fallback broadcasts to `127.255.255.255` when the global
  broadcast send fails — harmless here (the entrypoint route makes the
  global broadcast succeed), and visible in `log.txt` as a self-receipt
  from `127.0.0.1` if it ever triggers.
