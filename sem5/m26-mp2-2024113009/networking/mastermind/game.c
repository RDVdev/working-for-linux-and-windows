#include "game.h"
#include <ctype.h>
#include <stdio.h>
#include <string.h>

#define ANSI_RESET  "\033[0m"
#define ANSI_YELLOW "\033[33m" //o
#define ANSI_GREEN  "\033[32m" //x
#define ANSI_RED    "\033[31m" //-

bool game_validate_sequence(const char *seq) {
    if (!seq || strlen(seq) != SEQ_LEN) {
        return false;
    }

    for(int i = 0; i < SEQ_LEN; i++)
    {
        if (!isdigit((unsigned char)seq[i])) {
            return false;
        }
    }
    return true;
}

void game_init(game_state_t *game, player_role_t role){
    memset(game, 0, sizeof(*game));
    game->role = role;
    game->attempt_count = 0;
    game->game_over = false;
    game->won = false;
}

bool game_compute_feedback(const char *master, const char *guess, char *out_feedback) {
    if (!master || !guess || !out_feedback) {
        return false;
    }
    bool master_matched[SEQ_LEN] = {false};
    bool guess_matched[SEQ_LEN] = {false};
    int red_pegs = 0;   //x:correct
    int white_pegs = 0; //o:wrong
    //counting exact matches
    for (int i = 0; i < SEQ_LEN; i++) {
        if (guess[i] == master[i]) {
            red_pegs++;
            master_matched[i] = true;
            guess_matched[i] = true;
        }
    }
    ///misplaced matches
    for (int i = 0; i < SEQ_LEN; i++) {
        if (guess_matched[i]) {
            continue;
        }
        for (int j = 0; j < SEQ_LEN; j++) {
            if (!master_matched[j] && guess[i] == master[j]) {
                white_pegs++;
                master_matched[j] = true;
                break;
            }
        }
    }
    //x, o, -
    int idx = 0;
    for (int i = 0; i < red_pegs; i++) {
        out_feedback[idx++] = 'x';
    }
    for (int i = 0; i < white_pegs; i++) {
        out_feedback[idx++] = 'o';
    }
    while (idx < SEQ_LEN) {
        out_feedback[idx++] = '-';
    }
    out_feedback[SEQ_LEN] = '\0';
    return (red_pegs == SEQ_LEN);
}

bool game_record_attempt(game_state_t *game, const char *guess, const char *feedback) {
    if (!game || !guess || !feedback || game->attempt_count >= MAX_ATTEMPTS) {
        return false;
    }

    strncpy(game->attempts[game->attempt_count].guess, guess, SEQ_LEN);
    game->attempts[game->attempt_count].guess[SEQ_LEN] = '\0';
    strncpy(game->attempts[game->attempt_count].feedback, feedback, SEQ_LEN);
    game->attempts[game->attempt_count].feedback[SEQ_LEN] = '\0';

    game->attempt_count++;

    if (strcmp(feedback, "xxxxx") == 0) {
        game->won = true;
        game->game_over = true;
    } else if (game->attempt_count >= MAX_ATTEMPTS) {
        game->won = false;
        game->game_over = true;
    }
    return game->game_over;
}

static void print_colored_pegs(const char *feedback) {
    for (int i = 0; i < SEQ_LEN; i++) {
        char c = feedback[i];
        if (c == 'o') {
            printf("%s%c%s", ANSI_YELLOW, c, ANSI_RESET);
        } else if (c == 'x') {
            printf("%s%c%s", ANSI_GREEN, c, ANSI_RESET);
        } else if (c == '-') {
            printf("%s%c%s", ANSI_RED, c, ANSI_RESET);
        } else {
            putchar(c);
        }
    }
}

void game_render_board(const game_state_t *game) {
    if (!game) return;
    //clearing terminal screen, scrollback buffer, and cursor to home
    printf("\033[2J\033[3J\033[H");
    //12 rows
    for (int i = 0; i < MAX_ATTEMPTS; i++) {
        if (i < game->attempt_count) {
            printf("%s ", game->attempts[i].guess);
            print_colored_pegs(game->attempts[i].feedback);
            printf("\n");
        } else {
            printf("***** *****\n");
        }
    }
    //separator
    printf("-----\n");
    ///mm
    if (game->role == ROLE_MASTERMIND || game->game_over) {
        printf("%s\n", game->master_sequence);
    } else {
        printf("*****\n");
    }
}