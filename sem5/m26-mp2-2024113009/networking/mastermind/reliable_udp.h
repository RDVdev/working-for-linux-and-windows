#ifndef RELIABLE_UDP_H
#define RELIABLE_UDP_H

#include "protocol.h"
#include <netinet/in.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define RETRANSMIT_TIMEOUT_MS 100 //0.1 seconds per assignment spec
#define MAX_CHUNKS_PER_MSG 16

bool reliable_udp_send(int sock, const struct sockaddr_in *dest_addr, const void *data, size_t len, uint16_t msg_id);

ssize_t reliable_udp_recv_chunk(int sock, struct sockaddr_in *src_addr, void *out_buf, size_t out_max, uint16_t *current_msg_id, bool received_chunks[], uint16_t *total_chunks_expected);

#endif