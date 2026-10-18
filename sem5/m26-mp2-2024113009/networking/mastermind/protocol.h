#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define MAGIC_LEN 4
#define MAGIC_BYTES "MMND" //mastermin net discov

#define MAX_NAME_LEN 32
#define SEQ_LEN 5
#define MAX_ATTEMPTS 12


//udp discovery broadcast packet
typedef struct {
    char magic[MAGIC_LEN];
    char name[MAX_NAME_LEN];
    uint16_t port;
} __attribute__((packed)) discovery_pkt_t;


// game msg verbs
typedef enum {
    VERB_CHALLENGE = 1, //how it starts: init to peer says challenge
    VERB_CHALLENGE_RESPONSE = 2, //peer to init, yes or no
    VERB_GUESS = 3, //codebreaker to mm
    VERB_FEEDBACK = 4, //mm to codebreaker
    VERB_GAME_OVER = 5, //mm to codebreaker: reveals master as the end
    VERB_DISCONNECT = 6 //abrupt leave by either player
} msg_verb_t;

typedef struct {
    uint8_t verb;
    char payload[64];
} __attribute__((packed)) game_msg_t;

// reliable udp transfer structs
#define CHUNK_DATA_SIZE 32

typedef struct {
    uint16_t msg_id;
    uint16_t seq_num;
    uint16_t total_chunks;
    uint16_t data_len;
    char data[CHUNK_DATA_SIZE];
} __attribute__((packed)) udp_chunk_t;

typedef struct {
    uint16_t msg_id;
    uint16_t seq_num;
} __attribute__((packed)) udp_ack_t;

//attribute packed used throughout to tell the compiler to pack them as closely as possible with no padding

#endif