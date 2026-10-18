#include "network.h"
#include "logger.h"
#include <arpa/inet.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

bool net_transport_init(net_transport_t *net, bool cost_cutting, uint16_t *out_port) {
    if (!net || !out_port) {
        return false;
    }
    memset(net, 0, sizeof(*net));
    net->is_udp = cost_cutting;
    net->conn_sock = -1;

    int type = cost_cutting ? SOCK_DGRAM : SOCK_STREAM;
    net->listen_sock = socket(AF_INET, type, 0);
    if (net->listen_sock < 0) {
        return false;
    }

    int opt = 1;
    setsockopt(net->listen_sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = 0; //os will assign any available ephemeral port

    if (bind(net->listen_sock, (struct sockaddr *)&addr, sizeof(addr)) <0) {
        close(net->listen_sock);
        net->listen_sock = -1;
        return false;
    }

    if (!cost_cutting && listen(net->listen_sock, 5) < 0) {
        close(net->listen_sock);
        net->listen_sock = -1;
        return false;
    }
    socklen_t addr_len = sizeof(addr);
    if (getsockname(net->listen_sock, (struct sockaddr *)&addr, &addr_len) < 0) {
        close(net->listen_sock);
        net->listen_sock = -1;
        return false;
    }
    *out_port = ntohs(addr.sin_port);
    if (cost_cutting) {
        net->conn_sock = net->listen_sock;
    }
    logger_log("Network transport initialized (%s, port %u)", cost_cutting ? "UDP" : "TCP", *out_port);
    return true;
}

bool net_transport_connect(net_transport_t *net, const char *peer_ip, uint16_t peer_port) {
    if (!net || !peer_ip) {
        return false;
    }
    struct sockaddr_in target;
    memset(&target, 0, sizeof(target));
    target.sin_family = AF_INET;
    target.sin_port = htons(peer_port);
    if (inet_pton(AF_INET, peer_ip, &target.sin_addr) <= 0) {
        return false;
    }
    if (net->is_udp) {
        net->peer_addr = target;
        net->connected = true;
        logger_log("Configured UDP endpoint %s:%u", peer_ip, peer_port);
        return true;
    }
    net->conn_sock = socket(AF_INET, SOCK_STREAM, 0);
    if (net->conn_sock < 0) {
        return false;
    }
    if (connect(net->conn_sock, (struct sockaddr *)&target, sizeof(target)) < 0) {
        close(net->conn_sock);
        net->conn_sock = -1;
        return false;
    }
    net->peer_addr = target;
    net->connected = true;
    logger_log("TCP connected to %s:%u", peer_ip, peer_port);
    return true;
}
bool net_transport_accept(net_transport_t *net) {
    if (!net || net->is_udp) {
        return false;
    }
    socklen_t len = sizeof(net->peer_addr);
    net->conn_sock = accept(net->listen_sock, (struct sockaddr *)&net->peer_addr, &len);
    if (net->conn_sock < 0) {
        return false;
    }
    net->connected = true;
    char ip[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &net->peer_addr.sin_addr, ip, sizeof(ip));
    logger_log("Accepted TCP connection from %s:%u", ip, ntohs(net->peer_addr.sin_port));
    return true;
}
bool net_transport_send(net_transport_t *net, const game_msg_t *msg) {
    if (!net || !msg) {
        return false;
    }
    if (net->is_udp) {
        uint16_t mid = net->next_msg_id++;
        bool ok = reliable_udp_send(net->conn_sock, &net->peer_addr, msg, sizeof(game_msg_t), mid);
        if (ok) {
            logger_log("Sent UDP game message (verb: %u, msg_id: %u)", msg->verb, mid);
        } else {
            logger_log("Failed to send reliable UDP message (peer timed out)");
        }
        return ok;
    }
    const char *buf = (const char *)msg;
    size_t total = 0;
    while (total < sizeof(game_msg_t)) {
        ssize_t n = send(net->conn_sock, buf + total, sizeof(game_msg_t) - total, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            return false;
        }
        total += (size_t)n;
    }
    logger_log("Sent TCP game message (verb: %u)", msg->verb);
    return true;
}
net_recv_status_t net_transport_recv(net_transport_t *net, game_msg_t *out_msg) {
    if (!net || !out_msg) {
        return NET_RECV_ERROR;
    }
    if (net->is_udp) {
        ssize_t res = reliable_udp_recv_chunk(net->conn_sock, &net->peer_addr,
                                             out_msg, sizeof(game_msg_t),
                                             &net->cur_recv_msg_id,
                                             net->recv_chunks,
                                             &net->expected_chunks);
        if (res > 0) {
            net->connected = true;
            logger_log("Received complete UDP game message (verb: %u)", out_msg->verb);
            return NET_RECV_OK;
        } else if (res == 0) {
            return NET_RECV_PARTIAL;
        } else {
            return NET_RECV_ERROR;
        }
    }
    char *buf = (char *)out_msg;
    size_t total = 0;
    while (total < sizeof(game_msg_t)) {
        ssize_t n = recv(net->conn_sock, buf + total, sizeof(game_msg_t) - total, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            return NET_RECV_ERROR;
        }
        if (n == 0) {
            logger_log("TCP peer closed connection (EOF)");
            return NET_RECV_DISCONNECT;
        }
        total += (size_t)n;
    }
    logger_log("Received TCP game message (verb: %u)", out_msg->verb);
    return NET_RECV_OK;
}
void net_transport_disconnect(net_transport_t *net) {
    if (!net) return;
    if (!net->is_udp && net->conn_sock >= 0) {
        close(net->conn_sock);
        net->conn_sock = -1;
    }
    net->connected = false;
    memset(&net->peer_addr, 0, sizeof(net->peer_addr));
    net->cur_recv_msg_id = 0;
    memset(net->recv_chunks, 0, sizeof(net->recv_chunks));
    net->expected_chunks = 0;
    logger_log("Transport session disconnected");
}
void net_transport_cleanup(net_transport_t *net) {
    if (!net) return;
    net_transport_disconnect(net);
    if (net->listen_sock >= 0) {
        close(net->listen_sock);
        net->listen_sock = -1;
    }
}