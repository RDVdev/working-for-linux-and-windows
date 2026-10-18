#ifndef DISCOVERY_H
#define DISCOVERY_H

#include "protocol.h"
#include <netinet/in.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <time.h>

#define DISCOVERY_PORT 61337
#define BROADCAST_INTERVAL_SEC 2
#define PEER_EXPIRY_SEC 5
#define MAX_PEERS 32
#define DISCOVERY_ROWS 10 /* peer rows shown on screen; prompt sits right below them */

typedef struct {
    char name[MAX_NAME_LEN];
    char ip[INET_ADDRSTRLEN];
    uint16_t port;
    time_t last_seen;
} peer_entry_t;

typedef struct {
    peer_entry_t peers[MAX_PEERS];
    int count;
} peer_table_t;

int discovery_init(uint16_t broadcast_port);

bool discovery_send_broadcast(int sock, uint16_t broadcast_port, const char *player_name, uint16_t game_listen_port);

int discovery_recv_packet(int sock, char *out_name, size_t name_max, char *out_ip, size_t ip_max, uint16_t *out_port);

void peer_table_init(peer_table_t *table);

bool peer_table_update(peer_table_t *table, const char *name, const char *ip, uint16_t port, const char *my_name, uint16_t my_port);

bool peer_table_purge_stale(peer_table_t *table, int expiry_sec);

bool peer_table_get(const peer_table_t *table, int id, peer_entry_t *out_peer);

void peer_table_render(const peer_table_t *table);

void peer_table_render_inplace(const peer_table_t *table);
void peer_table_reset_prompt(const char *msg);

#endif