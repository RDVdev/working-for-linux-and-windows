#include "discovery.h"
#include "logger.h"
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

int discovery_init(uint16_t broadcast_port) {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        return -1;
    }


    //enabling broadcast transmission
    int broadcast_opt = 1;
    if (setsockopt(sock, SOL_SOCKET, SO_BROADCAST, &broadcast_opt, sizeof(broadcast_opt)) < 0) {
        close(sock);
        return -1;
    }

    //multiple instances - same discovery port
    int reuse_opt = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &reuse_opt, sizeof(reuse_opt));
    #ifdef SO_REUSEPORT
        setsockopt(sock, SOL_SOCKET, SO_REUSEPORT, &reuse_opt, sizeof(reuse_opt));
    #endif

    //non-blocking to allow poll() multiplexing
    int flags = fcntl(sock, F_GETFL, 0);
    if (flags >= 0) {
        fcntl(sock, F_SETFL, flags | O_NONBLOCK);
    }

    //binding to all interfaces on disc broadcast port
    struct sockaddr_in bind_addr;
    memset(&bind_addr, 0, sizeof(bind_addr));
    bind_addr.sin_family = AF_INET;
    bind_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    bind_addr.sin_port = htons(broadcast_port);

    if (bind(sock, (struct sockaddr *)&bind_addr, sizeof(bind_addr)) < 0) {
        close(sock);
        return -1;
    }

    return sock;
}

bool discovery_send_broadcast(int sock, uint16_t broadcast_port, const char *player_name, uint16_t game_listen_port) {
    if (sock < 0 || !player_name) {
        return false;
    }

    discovery_pkt_t pkt;
    memset(&pkt, 0, sizeof(pkt));
    memcpy(pkt.magic, MAGIC_BYTES, MAGIC_LEN);
    strncpy(pkt.name, player_name, MAX_NAME_LEN - 1);
    pkt.port = htons(game_listen_port);

    struct sockaddr_in dest_addr;
    memset(&dest_addr, 0, sizeof(dest_addr));
    dest_addr.sin_family = AF_INET;
    dest_addr.sin_addr.s_addr = htonl(INADDR_BROADCAST); //255.255.255.255
    dest_addr.sin_port = htons(broadcast_port);

    ssize_t sent = sendto(sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&dest_addr, sizeof(dest_addr));
    if (sent < 0) {
        //fallback to loopback broadcast only if global broadcast failed (e.g. offline sandbox)
        struct sockaddr_in loop_addr;
        memset(&loop_addr, 0, sizeof(loop_addr));
        loop_addr.sin_family = AF_INET;
        inet_pton(AF_INET, "127.255.255.255", &loop_addr.sin_addr);
        loop_addr.sin_port = htons(broadcast_port);
        sent = sendto(sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&loop_addr, sizeof(loop_addr));
    }

    if (sent == sizeof(pkt)) {
        logger_log("Sent UDP discovery broadcast (name: %s, listen_port: %u)", player_name, game_listen_port);
        return true;
    }
    return false;
}

int discovery_recv_packet(int sock, char *out_name, size_t name_max, char *out_ip, size_t ip_max, uint16_t *out_port) {
    discovery_pkt_t pkt;
    struct sockaddr_in src_addr;
    socklen_t addr_len = sizeof(src_addr);
    ssize_t n = recvfrom(sock, &pkt, sizeof(pkt), 0, (struct sockaddr *)&src_addr, &addr_len);
    if (n < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return 0; //no packets pending yay :)
        }
        return -1;
    }
    //checking packet size and 4-byte magic-id
    if ((size_t)n < sizeof(discovery_pkt_t)) {
        return 0;
    }
    if (memcmp(pkt.magic, MAGIC_BYTES, MAGIC_LEN) != 0) {
        return 0; //to ignore unrelated UDP broadcast traffic
    }
    //extracting sender's IP directly from packet's source address
    if (inet_ntop(AF_INET, &src_addr.sin_addr, out_ip, ip_max) == NULL) {
        return 0;
    }
    pkt.name[MAX_NAME_LEN - 1] = '\0';
    strncpy(out_name, pkt.name, name_max - 1);
    out_name[name_max - 1] = '\0';
    *out_port = ntohs(pkt.port);
    logger_log("Received UDP discovery from %s (%s:%u)", out_name, out_ip, *out_port);
    return 1;
}

void peer_table_init(peer_table_t *table) {
    if (!table) return;
    table->count = 0;
}

bool peer_table_update(peer_table_t *table, const char *name, const char *ip, uint16_t port, const char *my_name, uint16_t my_port) {
    if (!table || !name || !ip) return false;

    //filter self broadcast
    if (strcmp(name, my_name) == 0 && port == my_port) {
        return false;
    }

    time_t now = time(NULL);

    //update existing peer if matching (name and port) or (ip and port)
    for (int i = 0; i < table->count; i++) {
        if ((table->peers[i].port == port && strcmp(table->peers[i].name, name) == 0) ||
            (table->peers[i].port == port && strcmp(table->peers[i].ip, ip) == 0)) {
            // If existing was loopback and new is real LAN IP, upgrade to real LAN IP
            if (strcmp(table->peers[i].ip, "127.0.0.1") == 0 && strcmp(ip, "127.0.0.1") != 0) {
                strncpy(table->peers[i].ip, ip, INET_ADDRSTRLEN - 1);
                table->peers[i].ip[INET_ADDRSTRLEN - 1] = '\0';
            }
            strncpy(table->peers[i].name, name, MAX_NAME_LEN - 1);
            table->peers[i].name[MAX_NAME_LEN - 1] = '\0';
            table->peers[i].last_seen = now;
            return false; // Existing peer refreshed - structure did not change
        }
    }

    // Adding new peer if capacity allows
    if (table->count < MAX_PEERS) {
        strncpy(table->peers[table->count].name, name, MAX_NAME_LEN - 1);
        table->peers[table->count].name[MAX_NAME_LEN - 1] = '\0';
        strncpy(table->peers[table->count].ip, ip, INET_ADDRSTRLEN - 1);
        table->peers[table->count].ip[INET_ADDRSTRLEN - 1] = '\0';
        table->peers[table->count].port = port;
        table->peers[table->count].last_seen = now;
        table->count++;
        return true; // Brand new peer joined!
    }
    return false;
}

bool peer_table_purge_stale(peer_table_t *table, int expiry_sec) {
    if (!table) return false;
    time_t now = time(NULL);
    bool changed = false;
    for (int i = 0; i < table->count; ) {
        if (now - table->peers[i].last_seen >= expiry_sec) {
            // Shifting down to remove stale entry
            for (int j = i; j < table->count - 1; j++) {
                table->peers[j] = table->peers[j + 1];
            }
            table->count--;
            changed = true;
        } else {
            i++;
        }
    }
    return changed;
}

bool peer_table_get(const peer_table_t *table, int id, peer_entry_t *out_peer) {
    if (!table || !out_peer || id < 1 || id > table->count) {
        return false;
    }
    *out_peer = table->peers[id - 1];
    return true;
}

//fixed layout: rows 1-2 title/header, rows 3..(2+DISCOVERY_ROWS) peers,
// then the separator and the prompt at fixed rows so the prompt never moves
// when peers join or leave (TA clarification Q29, option b).
#define SEPARATOR_ROW (3 + DISCOVERY_ROWS)
#define PROMPT_ROW (SEPARATOR_ROW + 1)

static void draw_table(const peer_table_t *table) {
    printf("\033[1;1H\033[KPlayers Online:");
    printf("\033[2;1H\033[K%-3s %-15s %-15s %-7s %s", "ID", "Name", "IP Addr", "Port", "Last Seen");
    time_t now = time(NULL);
    for (int i = 0; i < DISCOVERY_ROWS; i++) {
        printf("\033[%d;1H\033[K", 3 + i);
        if (i < table->count) {
            long elapsed = (long)(now - table->peers[i].last_seen);
            if (elapsed < 0) elapsed = 0;
            printf("%-3d %-15s %-15s %-7u %ld s. ago",
                   i + 1,
                   table->peers[i].name,
                   table->peers[i].ip,
                   table->peers[i].port,
                   elapsed);
        }
    }
    printf("\033[%d;1H\033[K----------------------------------------------", SEPARATOR_ROW);
}

void peer_table_render(const peer_table_t *table) {
    if (!table) return;
    //clearing terminal screen and scrollback per TA clarification Q10
    printf("\033[2J\033[3J\033[H");
    draw_table(table);
    printf("\033[%d;1H> ", PROMPT_ROW);
    fflush(stdout);
}

void peer_table_render_inplace(const peer_table_t *table) {
    if (!table) return;
    //save cursor (user's partially typed input stays untouched), redraw table rows, restore cursor
    printf("\0337");
    draw_table(table);
    printf("\0338");
    fflush(stdout);
}

void peer_table_reset_prompt(const char *msg) {
    //message goes on the row below the prompt; prompt returns to its fixed row
    printf("\033[%d;1H\033[K%s", PROMPT_ROW + 1, msg ? msg : "");
    printf("\033[%d;1H\033[K> ", PROMPT_ROW);
    fflush(stdout);
}