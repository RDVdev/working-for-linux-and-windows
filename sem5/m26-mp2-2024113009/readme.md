# Mini Project 2

Mini-project 2 from CS3.301 Operating Systems and Networks, Monsoon 2026

## networking

### Build

```bash
cd networking
make all      # builds tempest/tempest and mastermind/mastermind
make clean
```

### tempest

```bash
tempest <city>
tempest <city> --raw
```

#### Design

- **File Modularization**:
    - `url.h` / `url.c`: Implements RFC 3986 percent-encoding for city names. Unreserved characters (`[A-Za-z0-9-_.~]`) are preserved, while spaces (`%20`) and special characters are encoded as `%XX` uppercase hex sequences.
    - `net.h` / `net.c`: Manages raw POSIX TCP sockets. Uses `getaddrinfo` for protocol-independent lookup (IPv4/IPv6). Implements `net_send_all` and `net_recv_chunk` to handle short writes, short reads, and `EINTR`. Enforces a 10-second application-level monotonic timeout using `poll()`.
    - `http.h` / `http.c`: Formats HTTP/1.1 requests (`GET /<encoded_city>?0T HTTP/1.1`) with `Host: wttr.is`, `User-Agent: curl/8.5.0` (required so `wttr.is` returns terminal ASCII text rather than HTML), and `Connection: close` (RFC 9112 Section 9.3). Dynamically reads responses up to `\r\n\r\n` to extract the HTTP status code, parses `Content-Length:`, and accumulates the response body until complete or upon server connection closure.
    - `main.c`: CLI entry point. Validates argument bounds, enforces flag placement (`--raw`), initiates the monotonic timer before connection, checks response status codes, and formats output.

- **Reading the Response Body**:
    The response is accumulated from the socket in 4096-byte chunks. Once the `\r\n\r\n` delimiter is found, the header block is isolated and scanned for `Content-Length:`. The reader then continues receiving bytes until the total body received matches or exceeds `Content-Length`, or until the server terminates the TCP connection (`recv() == 0`).

- **Detecting an Invalid Location**:
    - **HTTP Status Code**: Evaluated as the primary signal (per TA clarification Q7). Any response status code other than `200 OK` (such as `500 Internal Server Error` or `404 Not Found`) is treated as an invalid location.
    - **Body Content Inspection**: Even if status code is 200, the body is checked for substrings like `"location not found"` or `"Unknown location"`.
    - **Client-Side Validation**: Empty strings (`""`) or arguments containing only whitespace are caught immediately on the client side without issuing a network request.

#### Changed defaults

none

#### Assumptions

<!-- anything you took for granted that the spec did not state -->
- The project is compiled using GCC 14 with -std=c23 as per the assignment specifications.
- Per TA clarification Q12 & Q23, when an invalid location is requested with `--raw`, the raw HTTP request and response are printed and the program exits with a non-zero exit code (1) without printing "tempest: invalid location".
- Per TA clarification Q15, the 10-second timeout begins prior to the `connect()` call, running monotonically across connection establishment, request transmission, and response reception.
- Per TA clarification Q16 & Q17, the `--raw` flag outputs the HTTP request lines prefixed with `> ` and response header lines prefixed with `< ` followed by the verbatim response body, matching the example in the specification.
- Per TA clarification Q2 & Q8, city names containing spaces (e.g. `"New York"`) must be passed as a single quoted or escaped argument. Passing unquoted multi-word arguments results in `tempest: too many arguments`.
- Per TA clarification Q4, invoking the program without arguments (`argc == 1`) prints `tempest: invalid location` and exits with code 1.
- Per TA clarification Q6, providing `--raw` as the first argument or in the wrong position results in an error exit (`tempest: too many arguments` or `tempest: invalid location`).
- socket transmission errors now reported via specific system error using strerror(errno)

#### Known bugs

none known

### mastermind

```bash
mastermind [--cost-cutting] [--log]
```

#### Design

The mastermind application is structured into modular components to adhere strictly to separation of concerns and avoid monolithic design:

- **`protocol.h`**: Defines the wire protocol data structures and constants:
  - Discovery broadcast packet layout (`discovery_pkt_t`) with 4-byte magic `MMND`.
  - Game message packet structure (`game_msg_t`) and application verbs (`VERB_CHALLENGE`, `VERB_CHALLENGE_RESPONSE`, `VERB_GUESS`, `VERB_FEEDBACK`, `VERB_GAME_OVER`, `VERB_DISCONNECT`).
  - Reliable UDP chunk framing (`udp_chunk_t`) and acknowledgment (`udp_ack_t`).
  - All structs use `__attribute__((packed))` to ensure identical memory layouts across platforms without compiler padding.

- **`discovery.h` / `discovery.c`**: Implements peer discovery over UDP port 61337:
  - Sockets: Binds a reusable UDP broadcast socket (`SO_BROADCAST`, `SO_REUSEADDR`, `SO_REUSEPORT`).
  - Periodic Broadcasting: Dispatches discovery beacons containing the player's name and allocated game listening port every 2 seconds.
  - Source IP Extraction: Uses `recvfrom()` to derive the peer's actual IP address directly from the UDP packet headers (`sin_addr`) rather than trusting payload contents.
  - Peer Table: Manages peer registration, deduplication, timestamp updates, and purging entries not refreshed within 5 seconds.
  - In-Place ANSI Rendering: Uses cursor save/restore sequences (`\0337`, `\0338`) so discovery table updates don't clobber the user's active input at the command prompt.

- **`game.h` / `game.c`**: Implements the Mastermind game state machine:
  - Validation: Enforces 5-digit strings (`[0-9]`) for master sequences and guesses, and 5-character strings (`[ox-]`) for feedback pegs.
  - Feedback Calculation: Implements standard Mastermind evaluation: exact matches (`x`) are matched first, followed by digit presence in alternate positions (`o`), and unmatched digits (`-`). Feedback strings are sorted (`x` then `o` then `-`) so position is not leaked.
  - Board Rendering: Formats the full 12 attempts and secret sequence, using ANSI colors (green for `x`, yellow for `o`, red for `-`). Clears the terminal and scrollback buffer (`\033[2J\033[3J\033[H`) to maintain visual clarity.

- **`network.h` / `network.c`**: Unified transport abstraction layer:
  - Supports both connection-oriented TCP (`SOCK_STREAM`) and reliable datagram UDP (`SOCK_DGRAM`).
  - Implements socket initialization, ephemeral port binding, listening/connecting, and message transmission.
  - Handles short reads and writes, loop interruptions (`EINTR`), and clean session disconnections.

- **`reliable_udp.h` / `reliable_udp.c`**: Reliable transport layer for `--cost-cutting`:
  - Splits arbitrary payloads into fragmented 32-byte chunks.
  - Implements pipelined transmission with 16-bit sequence numbering, per-chunk ACKs, monotonic timeout detection (100 ms retransmission interval), and an overall 5-second send timeout, plus lightweight 1-byte UDP keepalive heartbeats (`'P'`/`'Q'`) for idle disconnect detection.

- **`logger.h` / `logger.c`**: Microsecond logging subsystem:
  - Activated by `--log`. Formats microsecond-precision timestamps (`gettimeofday()` + `localtime()` + `strftime()`) as `[YYYY-MM-DD HH:MM:SS.uuuuuu] [LOG] <message>` into `log.txt`.

- **`main.c`**: CLI argument parsing, state coordination, and non-blocking event loop using POSIX `poll()` across standard input, discovery sockets, and peer connection sockets.

#### Discovery

- **4-Byte Magic**: `MMND` (`0x4D 0x4D 0x4E 0x44`). Any incoming UDP packet whose first 4 bytes do not match this magic constant is immediately dropped.
- **Broadcast Payload Layout**:
  - `magic` (4 bytes): `MMND`
  - `name` (32 bytes): Null-terminated player name string
  - `port` (2 bytes, network byte order): The TCP or UDP port on which this player is listening for game challenges
- **Source IP**: The player's IP address is intentionally omitted from the broadcast payload. The receiving node derives the sender's IP directly from `struct sockaddr_in` populated by `recvfrom()`, and converts it via `inet_ntop()`.

#### Message verbs

| Verb ID | Verb Name | Payload Content | Sent When |
|:---:|:---|:---|:---|
| `1` | `VERB_CHALLENGE` | Challenger's name string | Challenger initiates a match against a discovered peer ID. |
| `2` | `VERB_CHALLENGE_RESPONSE` | `"yes"` or `"no"` | Challenged player accepts or rejects the challenge request. |
| `3` | `VERB_GUESS` | 5-digit guess string (e.g. `"65731"`) | Codebreaker submits a guess attempt. |
| `4` | `VERB_FEEDBACK` | 5-character feedback string (e.g. `"ooo--"`) | Mastermind sends evaluated peg feedback to the Codebreaker. |
| `5` | `VERB_GAME_OVER` | Master sequence string (e.g. `"12345"`) | Mastermind reveals the secret code to Codebreaker upon win or after 12 attempts. |
| `6` | `VERB_DISCONNECT` | Empty | Either player quits or terminates the session prematurely. |

#### Reliable transfer over UDP (`--cost-cutting`)

- **Chunk Layout (`udp_chunk_t`)**:
  - `msg_id` (uint16_t): Monotonically increasing message identifier.
  - `seq_num` (uint16_t): Zero-indexed chunk sequence number.
  - `total_chunks` (uint16_t): Total number of chunks comprising the complete message.
  - `data_len` (uint16_t): Length of the payload in this chunk (up to 32 bytes).
  - `data` (32 bytes): Binary payload slice.
- **ACK Layout (`udp_ack_t`)**:
  - `msg_id` (uint16_t): Echoes message ID being acknowledged.
  - `seq_num` (uint16_t): Echoes chunk sequence number being acknowledged.
- **Pipelined Transmission & Retransmission Scheme**:
  - The sender transmits all chunks `0 .. total_chunks - 1` immediately in a pipeline without waiting for individual ACKs first.
  - A 100 ms (0.1 s) retransmission timer is enforced via `poll()`. Any chunk `i` whose matching ACK `(msg_id, i)` has not arrived within 100 ms is retransmitted.
  - If all chunks are not acknowledged within 5 seconds, `reliable_udp_send()` declares the transport session lost and returns `false`.
  - The receiver verifies the sender address against the active peer, checks incoming sequence numbers, stores chunks in a reassembly buffer, and immediately sends an ACK for each valid chunk (including duplicate chunks whose previous ACK was lost). Once `total_chunks` distinct chunks are assembled, the complete message is delivered.

#### Disconnection handling

- **TCP**:
  - Socket reads use `recv()`. If `recv()` returns `0`, the remote peer closed the TCP connection (EOF / FIN).
  - If `recv()` returns `-1` with `ECONNRESET` or `EPIPE`, the socket was reset abruptly.
  - Upon detecting EOF, the local connection socket is closed (`close()`) and set to `-1` so it is immediately removed from the `poll()` descriptor set.
  - If disconnection occurs mid-game, the player is notified (`<Name> disconnected. Press enter to go home.`) and transitions to `STATE_DISCONNECTED`. If the match was already over (`STATE_GAME_OVER`), socket closure is handled silently without error spam.
- **UDP**:
  - If a player terminates via `SIGINT`, `SIGHUP`, or `SIGTERM`, a `VERB_DISCONNECT` message is dispatched before exit.
  - While connected in an active game session, peers exchange 1-byte UDP keepalive heartbeats (`'P'` ping / `'Q'` pong) every 1 second; if no UDP packet or heartbeat is received from the peer for 4 seconds (e.g. after `SIGKILL`), the session is declared disconnected.
  - If a player dies abruptly while sending or packets drop continuously for 5 seconds, `reliable_udp_send()` times out and returns `false`.
  - The caller interprets this transport timeout as peer disconnection, sets `net.connected = false`, and allows the remaining player to press Enter and return to discovery.

#### Changed defaults

- Discovery broadcast interval: 2 seconds (default, unchanged).
- Discovery peer expiry: 5 seconds (default, unchanged).
- Reliable UDP retransmit timeout: 100 ms / 0.1 seconds (default, unchanged).

#### Assumptions

- Compiles with GCC 14 under `-std=c23 -D_POSIX_C_SOURCE=200809L -D_XOPEN_SOURCE=700 -Wall -Wextra -Werror -Wno-unused-parameter` linking only `-lm`.
- Running via `mastermind` or `./mastermind` are both valid execution formats.
- Discovery occurs across IPv4 broadcast on UDP port 61337.
- Player names containing spaces or special characters are supported up to 31 characters.
- If a Codebreaker submits a guess before the Mastermind finishes entering the secret code, the guess is buffered asynchronously and evaluated the instant the secret code is validated.
- Feedback pegs are sorted (`x` followed by `o` followed by `-`) per standard rules so peg positions do not leak digit positions.
- In accordance with TA Clarifications Q20, Q33, and Q34, the Mastermind manually types the 5-character feedback string (`o`, `x`, `-`), which is validated for character set (`[ox-]`), length (5), and fair-play peg counts matching the true evaluation; Codebreaker also verifies all rounds upon the game over sequence reveal.
- Incoming challenges received on the listening socket while already in an active game are automatically rejected with `"no"` (`VERB_CHALLENGE_RESPONSE`) per TA Clarification Q30.
- When a game ends, pressing Enter cleanly disconnects the session and restores the discovery menu.
- Last seen column in peer discovery list is now refreshed in-place every second.
- Per TA Clarification Q29 (option b), the discovery prompt (`> `) is at a fixed screen row below a reserved 10-row peer area. When a peer joins, leaves or its `Last Seen` changes, only the table rows are redrawn (cursor saved/restored with `\0337`/`\0338`), so whatever the user is typing at the prompt is never erased. The table is fully cleared (`\033[2J`) only when returning to the discovery screen (Q10). Only the first 10 peers are displayed; a gap of blank rows between the table and the prompt is expected when fewer peers are online.
- Discovery broadcasting is stopped after a challenge is accepted by the players.

#### Known bugs

none known

## xv6

### Build

```bash
cd xv6
make qemu     # boot xv6; Ctrl-A X to quit
make clean
```

### Run

```bash
# in the xv6 shell
cowtest
alarmtest
usertests -q

# or from outside
./test-xv6.py cowtest
./test-xv6.py alarmtest
./test-xv6.py -q usertests
```

### Copy-on-write fork

- **Reference counting (`kalloc.c`)**:
  - Maintained an array `kref.count` sized for all physical pages between `KERNBASE` and `PHYSTOP` (32,768 pages), guarded by a spinlock `kref.lock`.
  - Pages start with refcount `1` in `kalloc()` and `freerange()`.
  - In `kfree()`, we decrement the refcount; the page is only returned to `kmem.freelist` when its count drops to `0`. If other processes still share it, `kfree()` returns immediately.
  - Helper functions `kref_inc()` and `kref_get()` manage references safely.
- **Marking pages COW (`uvmcopy` & `riscv.h`)**:
  - We use bit 8 (`1L << 8`) as `PTE_COW`, which is one of the two software-reserved bits (RSW) in RISC-V PTEs.
  - In `uvmcopy()`, instead of allocating new memory, we map the parent's physical pages directly into the child. If a page is writable (`PTE_W`), we clear `PTE_W`, set `PTE_COW` in both parent and child page tables, and increment the physical page's refcount with `kref_inc()`.
- **Duplicating on write fault (`usertrap` & `cowfault`)**:
  - When either process writes to a shared page, the MMU triggers a store page fault (`scause == 15`).
  - `usertrap()` catches this and invokes `cowfault(p->pagetable, va)`:
    - If `kref_get(pa) == 1` (only one process is left referencing the page), we don't allocate; we just clear `PTE_COW` and restore `PTE_W` in place.
    - If `kref_get(pa) > 1`, we allocate a fresh page with `kalloc()`, copy the data using `memmove()`, release the old page reference via `kfree()`, and map the new page with `PTE_W` enabled and `PTE_COW` cleared.
- **Kernel writes via `copyout` (`vm.c`)**:
  - When the kernel writes into user memory (e.g. pipe or file reads), user-mode traps do not fire. In `copyout()`, if the target page has `PTE_COW` set, we call `cowfault()` to allocate a private copy and re-query `walkaddr()` before copying bytes into it.

### Alarms

 **`struct proc` fields added**:
  - `alarm_interval`: ticks between alarm triggers (`0` to disable).
  - `alarm_handler`: address of the user callback function.
  - `alarm_ticks`: ticks elapsed since the last alarm.
  - `alarm_running`: flag (`1`/`0`) marking whether a handler is actively executing.
  - `saved_tf`: embedded `struct trapframe` to save the interrupted user state. We embedded it directly into `struct proc` instead of using `kalloc()` so we don't waste a whole 4KB page for 288 bytes or risk running out of memory.
- **Stopping re-entrancy**:
  - In `usertrap()`, we only increment ticks and trigger alarms if `!p->alarm_running`.
  - When the timer expires, we set `p->alarm_running = 1`, save the current trapframe into `p->saved_tf`, and set `p->trapframe->epc = p->alarm_handler`.
  - If more timer interrupts arrive while the handler is running, the kernel yields CPU time as normal but won't invoke the handler again.
- **State restored by `sigreturn`**:
  - `sys_sigreturn()` restores the entire saved trapframe (`*p->trapframe = p->saved_tf`) and resets `alarm_running = 0`.
  - It returns `p->trapframe->a0` so xv6's `syscall()` wrapper doesn't clobber the user's restored `a0` register. This lets the interrupted code resume with all registers intact.

### Assumptions

- Already stated in spec but stating again:
- `sigalarm(0, 0)` or `sigalarm(0, fn)` cancels any pending alarm and resets tick counters.
- Address `0` is treated as a valid user function pointer in xv6, so we only reject negative ticks (`ticks < 0`).
- Child processes do not inherit alarm timers across `fork()`.

### Known bugs

- **alarm**: none known
- **cow**: none known
