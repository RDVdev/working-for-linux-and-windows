#ifndef NETWORK_H
#define NETWORK_H
#include "protocol.h"
#include "reliable_udp.h"
#include <netinet/in.h>
#include <stdbool.h>
#include <stdint.h>
#include <sys/types.h>

typedef enum {
    NET_RECV_OK = 1,          //full game_msg_t received
    NET_RECV_PARTIAL = 0,     //UDP chunk received & ACKed, waiting for remaining chunks
    NET_RECV_DISCONNECT = -1, //peer disconnected (TCP EOF or explicit drop)
    NET_RECV_ERROR = -2       //socket error
} net_recv_status_t;

typedef struct {
    bool is_udp;
    int listen_sock;
    int conn_sock;
    struct sockaddr_in peer_addr;
    bool connected;
    uint16_t next_msg_id;
    //inbound reliable UDP reassembly state
    uint16_t cur_recv_msg_id;
    bool recv_chunks[MAX_CHUNKS_PER_MSG];
    uint16_t expected_chunks;
} net_transport_t;

bool net_transport_init(net_transport_t *net, bool cost_cutting, uint16_t *out_port);
bool net_transport_connect(net_transport_t *net, const char *peer_ip, uint16_t peer_port);
bool net_transport_accept(net_transport_t *net);
bool net_transport_send(net_transport_t *net, const game_msg_t *msg);
net_recv_status_t net_transport_recv(net_transport_t *net, game_msg_t *out_msg);
void net_transport_disconnect(net_transport_t *net);
void net_transport_cleanup(net_transport_t *net);

#endif