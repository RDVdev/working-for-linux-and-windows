#include "reliable_udp.h"
#include "logger.h"
#include <errno.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>

static long get_time_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

bool reliable_udp_send(int sock, const struct sockaddr_in *dest_addr, const void *data, size_t len, uint16_t msg_id) {
    if (sock < 0 || !dest_addr || !data || len == 0) {
        return false;
    }
    uint16_t total_chunks = (uint16_t)((len + CHUNK_DATA_SIZE - 1) / CHUNK_DATA_SIZE);
    if (total_chunks > MAX_CHUNKS_PER_MSG) {
        return false;
    }
    udp_chunk_t chunks[MAX_CHUNKS_PER_MSG];
    bool acked[MAX_CHUNKS_PER_MSG] = {false};
    long last_sent[MAX_CHUNKS_PER_MSG] = {0};
    const char *byte_ptr = (const char *)data;
    size_t remaining = len;
    
    //all chunks
    for (uint16_t i = 0; i < total_chunks; i++) {
        chunks[i].msg_id = htons(msg_id);
        chunks[i].seq_num = htons(i);
        chunks[i].total_chunks = htons(total_chunks);
        size_t chunk_len = remaining > CHUNK_DATA_SIZE ? CHUNK_DATA_SIZE : remaining;
        chunks[i].data_len = htons((uint16_t)chunk_len);
        memcpy(chunks[i].data, byte_ptr + (i * CHUNK_DATA_SIZE), chunk_len);
        remaining -= chunk_len;
    }
    //sending all chunks without waiting for ACKs)
    long now = get_time_ms();
    for (uint16_t i = 0; i < total_chunks; i++) {
        sendto(sock, &chunks[i], sizeof(udp_chunk_t), 0, (struct sockaddr *)dest_addr, sizeof(*dest_addr));
        last_sent[i] = now;
        logger_log("Sent UDP chunk %u/%u (msg_id: %u)", i + 1, total_chunks, msg_id);
    }
    //retransmission and ACK collection loop
    int total_acked = 0;
    long start_time = get_time_ms();
    while (total_acked < total_chunks) {
        //aborting if no ACKs received after 5 seconds
        if (get_time_ms() - start_time > 5000) {
            logger_log("Reliable UDP send timed out after 5s");
            return false;
        }
        //for incoming ACKs with 10ms poll
        struct pollfd pfd = {.fd = sock, .events = POLLIN, .revents = 0};
        int pr = poll(&pfd, 1, 10);
        if (pr > 0 && (pfd.revents & POLLIN)) {
            while (1) {
                udp_ack_t ack_pkt;
                struct sockaddr_in from_addr;
                socklen_t from_len = sizeof(from_addr);
                ssize_t n = recvfrom(sock, &ack_pkt, sizeof(ack_pkt), MSG_DONTWAIT, (struct sockaddr *)&from_addr, &from_len);
                if (n < 0) break;
                if (n == 1 && *(char *)&ack_pkt == 'P') {
                    sendto(sock, "Q", 1, 0, (struct sockaddr *)&from_addr, sizeof(from_addr));
                } else if (n == sizeof(udp_ack_t)) {
                    uint16_t ack_msg_id = ntohs(ack_pkt.msg_id);
                    uint16_t ack_seq = ntohs(ack_pkt.seq_num);
                    if (ack_msg_id == msg_id && ack_seq < total_chunks && !acked[ack_seq]) {
                        acked[ack_seq] = true;
                        total_acked++;
                        logger_log("Received ACK for chunk %u/%u (msg_id: %u)", ack_seq + 1, total_chunks, msg_id);
                    }
                }
            }
        }
        // Retransmit any un-ACKed chunk after 0.1s (100 ms)
        now = get_time_ms();
        for (uint16_t i = 0; i < total_chunks; i++) {
            if (!acked[i] && (now - last_sent[i] >= RETRANSMIT_TIMEOUT_MS)) {
                sendto(sock, &chunks[i], sizeof(udp_chunk_t), 0, (struct sockaddr *)dest_addr, sizeof(*dest_addr));
                last_sent[i] = now;
                logger_log("Retransmitted un-ACKed chunk %u/%u (msg_id: %u)", i + 1, total_chunks, msg_id);
            }
        }
    }
    return true;
}
ssize_t reliable_udp_recv_chunk(int sock, struct sockaddr_in *src_addr,
                                void *out_buf, size_t out_max,
                                uint16_t *current_msg_id,
                                bool received_chunks[],
                                uint16_t *total_chunks_expected) {
    if (sock < 0 || !src_addr || !out_buf) {
        return -1;
    }
    char buffer[sizeof(udp_chunk_t)];
    struct sockaddr_in pkt_addr;
    socklen_t addr_len = sizeof(pkt_addr);
    ssize_t n = recvfrom(sock, buffer, sizeof(buffer), 0,
                         (struct sockaddr *)&pkt_addr, &addr_len);
    if (n < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return 0; //no data pending
        }
        return -1;
    }
    if (src_addr->sin_port != 0 &&
        (pkt_addr.sin_port != src_addr->sin_port ||
         pkt_addr.sin_addr.s_addr != src_addr->sin_addr.s_addr)) {
        return -2; //ignore packets from other peers during an active session
    }
    if (n == 1 && buffer[0] == 'P') {
        sendto(sock, "Q", 1, 0, (struct sockaddr *)&pkt_addr, sizeof(pkt_addr));
        return 0;
    }
    if (n == 1 && buffer[0] == 'Q') {
        return 0;
    }
    if ((size_t)n < sizeof(udp_chunk_t)) {
        return -2;
    }
    *src_addr = pkt_addr;
    udp_chunk_t chunk;
    memcpy(&chunk, buffer, sizeof(chunk));
    uint16_t msg_id = ntohs(chunk.msg_id);
    uint16_t seq_num = ntohs(chunk.seq_num);
    uint16_t total_chunks = ntohs(chunk.total_chunks);
    uint16_t data_len = ntohs(chunk.data_len);
    //send immediate ACK back to the sender
    udp_ack_t ack_pkt;
    ack_pkt.msg_id = htons(msg_id);
    ack_pkt.seq_num = htons(seq_num);
    sendto(sock, &ack_pkt, sizeof(ack_pkt), 0, (struct sockaddr *)src_addr, sizeof(*src_addr));
    logger_log("Sent ACK for chunk %u/%u (msg_id: %u)", seq_num + 1, total_chunks, msg_id);
    // Reset state for new message
    static uint16_t s_chunk_lens[MAX_CHUNKS_PER_MSG] = {0};
    if (*total_chunks_expected == 0 || msg_id != *current_msg_id) {
        *current_msg_id = msg_id;
        *total_chunks_expected = total_chunks;
        memset(received_chunks, 0, sizeof(bool) * MAX_CHUNKS_PER_MSG);
        memset(s_chunk_lens, 0, sizeof(s_chunk_lens));
    }
    if (seq_num >= total_chunks || total_chunks > MAX_CHUNKS_PER_MSG) {
        return 0;
    }
    // Place chunk into reassembly buffer
    size_t offset = (size_t)seq_num * CHUNK_DATA_SIZE;
    if (offset + data_len <= out_max && !received_chunks[seq_num]) {
        memcpy((char *)out_buf + offset, chunk.data, data_len);
        received_chunks[seq_num] = true;
        s_chunk_lens[seq_num] = data_len;
    }
    // Check if all chunks received
    for (uint16_t i = 0; i < *total_chunks_expected; i++) {
        if (!received_chunks[i]) {
            return 0; // Still waiting for remaining chunks
        }
    }
    size_t total_size = 0;
    for (uint16_t i = 0; i < *total_chunks_expected; i++) {
        total_size += s_chunk_lens[i];
    }
    *total_chunks_expected = 0; // Reset for next message
    logger_log("Successfully reassembled message (msg_id: %u, total_bytes: %zu)", msg_id, total_size);
    return (ssize_t)total_size;
}