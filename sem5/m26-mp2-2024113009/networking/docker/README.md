# Mastermind evaluation testbed (Docker)

> **Full TA guide — exact commands, expected output, and what each file
> contains — is in [`../run.md`](../run.md).**

Four isolated containers, each running one interactive `mastermind`
instance, so the networking part can be evaluated on a safe network
(the assignment forbids testing on the IIIT-H LAN — the compose bridge
never touches it: broadcasts stay inside `mmlan`).

All commands below are run from `networking/`.

## Normal run (TCP game + UDP discovery)

```sh
docker compose up -d --build
```

Starts `player1` … `player4`. Each waits for a name on its own terminal.
Attach to one of them:

```sh
docker compose attach player1      # detach: Ctrl-p Ctrl-q, Ctrl-c kills it
```

Type a name, wait ~5 s for the discovery table to fill, then
`challenge <ID>` on one player and `yes`/`no` on the other.

## Cost-cutting run (TCP blocked at the container, game uses `--cost-cutting`)

```sh
docker compose -f docker-compose.yml -f docker-compose.costcut.yml up -d --build
```

Same four players, but every container:

* runs `mastermind --log --cost-cutting` (UDP state transfer), and
* gets `NET_ADMIN` + an entrypoint rule set that **rejects all TCP in both
  directions** (`iptables`), while UDP discovery keeps working. This
  simulates the institute banning TCP on the LAN. REJECT (not DROP) is
  used so a blocked `connect()` fails immediately instead of hanging ~130 s
  on SYN retransmissions.
* leaves proof of the active rules in `docker/logs/playerN/iptables.rules`.

## Logs

| what | where |
|---|---|
| per-player network log (`--log`) | `docker/logs/playerN/log.txt` (appended, never overwritten) |
| active iptables rules (blocked runs) | `docker/logs/playerN/iptables.rules` |
| terminal output of a container | `docker compose logs playerN` |

The game runs as your host uid/gid (`PUID`/`PGID`, default 1000:1000), so
the log files are owned by you — no `sudo` needed to read or delete them.

## Automated tests

```sh
docker/test/run_tests.sh            # all scenarios
docker/test/run_tests.sh tcp        # full scripted game over TCP
docker/test/run_tests.sh costcut    # full scripted game over UDP with TCP blocked
docker/test/run_tests.sh noblock    # TCP blocked, no --cost-cutting: challenge must fail
```

The runner starts `player1` (codebreaker *tatva*) and `player2`
(mastermind *feena*) as scripted players on a throwaway compose project
(`mmtest`), waits for them to exit, and asserts on exit codes, `log.txt`,
and the captured terminal output (boards, prompts, win messages).
Scripted players live in `docker/test/scripts/` and drive the game
through a FIFO by waiting for its prompts — no timing guessing.

Scenarios:

* **tcp** — discovery, challenge, 2-attempt game, GAME_OVER over TCP.
* **costcut** — same game, but every TCP packet is rejected in the
  containers and the state transfer goes over the reliable-UDP path
  (chunking, seq numbers, ACKs, 0.1 s retransmits — all asserted in
  `log.txt`).
* **noblock** — TCP blocked but the game runs in TCP mode: the challenge
  must fail with "Could not connect", proving `BLOCK_TCP` really cuts TCP.

## Layout

```
networking/
├── docker-compose.yml            # 4 players, TCP mode (base)
├── docker-compose.costcut.yml    # overlay: --cost-cutting + block TCP
├── docker/
│   ├── Dockerfile                # gcc-14 build stage -> slim runtime + iptables/iproute2
│   ├── entrypoint.sh             # broadcast route, BLOCK_TCP, PUID drop, PLAYER_SCRIPT
│   ├── logs/playerN/             # bind-mounted log.txt destinations
│   └── test/
│       ├── run_tests.sh          # scenario runner + assertions
│       ├── compose.test.yml      # overlay: scripted players
│       ├── compose.tcpblock.yml  # overlay: block TCP, keep TCP mode
│       └── scripts/              # driver.sh, codebreaker.sh, mastermind.sh
```

## Notes / assumptions

* Discovery uses UDP broadcast on port 61337 inside an isolated compose
  bridge (`mmlan`, `internal: true`), so nothing can leak to the host
  network or the internet. An `internal` bridge has no default route,
  which makes `sendto(255.255.255.255)` fail with ENETUNREACH; the
  entrypoint therefore adds an explicit limited-broadcast route
  (`ip route add 255.255.255.255 dev eth0`, needs the `NET_ADMIN` cap
  compose grants every player; it only affects the container's own
  network namespace). Verified: broadcasts reach all four containers.
* The game binds its listening port to `0.0.0.0` with an OS-assigned port
  and advertises it in the discovery packet; no fixed ports, so several
  compose projects can run side by side.
* The game polls stdin for `POLLIN` only, so it does not notice EOF on a
  redirected stdin (a closed FIFO surfaces as `POLLHUP`); the scripted
  players therefore finish with SIGINT, which the game handles cleanly
  (flushes logs, exits 0). Interactive runs are unaffected (Ctrl-C is the
  normal quit path anyway).
* `log.txt` is opened in append mode by the program itself; tests delete
  it before each scenario so assertions are per-scenario.
