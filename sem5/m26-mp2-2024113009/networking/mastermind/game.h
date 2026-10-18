#ifndef GAME_H
#define GAME_H

#include "protocol.h"
#include <stdbool.h>

typedef enum {
    ROLE_NONE = 0,
    ROLE_MASTERMIND = 1,
    ROLE_CODEBREAKER = 2
} player_role_t;

typedef struct {
    char guess[SEQ_LEN+1];
    char feedback[SEQ_LEN+1];
} attempt_t;

typedef struct {
    char master_sequence[SEQ_LEN + 1];
    attempt_t attempts[MAX_ATTEMPTS];
    int attempt_count;
    player_role_t role;
    bool game_over;
    bool won;
} game_state_t;

bool game_validate_sequence(const char *seq);

void game_init(game_state_t *game, player_role_t role);

bool game_compute_feedback(const char *master, const char *guess, char *out_feedback);

bool game_record_attempt(game_state_t *game, const char *guess, const char *feedback);

void game_render_board(const game_state_t *game);

#endif