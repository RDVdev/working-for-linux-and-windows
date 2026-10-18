#include "discovery.h"
#include "game.h"
#include "logger.h"
#include "network.h"
#include "protocol.h"
#include <arpa/inet.h>
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

typedef enum {
    STATE_DISCOVERY,
    STATE_WAIT_CHALLENGE_RESP,
    STATE_CHALLENGE_PROMPT,
    STATE_INPUT_MASTER_SEQ,
    STATE_WAIT_FEEDBACK_INPUT,
    STATE_PLAYING,
    STATE_GAME_OVER,
    STATE_DISCONNECTED
} app_state_t;

static volatile sig_atomic_t g_running = 1;

static void sigint_handler(int sig) {
    (void)sig;
    g_running = 0;
}

static long get_time_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec;
}

static bool validate_feedback_string(const char *fb) {
    if (!fb || strlen(fb) != SEQ_LEN) {
        return false;
    }
    for (int i = 0; i < SEQ_LEN; i++) {
        if (fb[i] != 'x' && fb[i] != 'o' && fb[i] != '-') {
            return false;
        }
    }
    return true;
}

static bool validate_feedback_counts(const char *fb, const char *expected) {
    if (!fb || !expected) return false;
    int fb_x = 0, fb_o = 0, fb_dash = 0;
    int exp_x = 0, exp_o = 0, exp_dash = 0;
    for (int i = 0; i < SEQ_LEN; i++) {
        if (fb[i] == 'x') fb_x++;
        else if (fb[i] == 'o') fb_o++;
        else if (fb[i] == '-') fb_dash++;

        if (expected[i] == 'x') exp_x++;
        else if (expected[i] == 'o') exp_o++;
        else if (expected[i] == '-') exp_dash++;
    }
    return (fb_x == exp_x && fb_o == exp_o && fb_dash == exp_dash);
}

static void return_to_discovery(app_state_t *state, net_transport_t *net, peer_table_t *table) {
    net_transport_disconnect(net);
    *state = STATE_DISCOVERY;
    peer_table_purge_stale(table, PEER_EXPIRY_SEC);
    peer_table_render(table);
}

int main(int argc, char *argv[]) {
    bool cost_cutting = false;
    bool enable_log = false;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--cost-cutting") == 0) {
            cost_cutting = true;
        } else if (strcmp(argv[i], "--log") == 0) {
            enable_log = true;
        } else {
            fprintf(stderr, "Usage: %s [--cost-cutting] [--log]\n", argv[0]);
            return 1;
        }
    }

    if (enable_log) {
        logger_init("log.txt");
    }

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sigint_handler;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
    signal(SIGPIPE, SIG_IGN);

    char my_name[MAX_NAME_LEN];
    printf("Enter your name: ");
    fflush(stdout);
    if (!fgets(my_name, sizeof(my_name), stdin)) {
        return 0;
    }
    my_name[strcspn(my_name, "\r\n")] = '\0';
    if (strlen(my_name) == 0) {
        strncpy(my_name, "Player", sizeof(my_name) - 1);
        my_name[sizeof(my_name) - 1] = '\0';
    }

    uint16_t game_port = 0;
    net_transport_t net;
    if (!net_transport_init(&net, cost_cutting, &game_port)) {
        fprintf(stderr, "Failed to initialize game network transport\n");
        return 1;
    }

    int disc_sock = discovery_init(DISCOVERY_PORT);
    if (disc_sock < 0) {
        fprintf(stderr, "Failed to initialize UDP discovery socket\n");
        net_transport_cleanup(&net);
        return 1;
    }

    peer_table_t peers;
    peer_table_init(&peers);

    app_state_t state = STATE_DISCOVERY;
    game_state_t game;
    char opponent_name[MAX_NAME_LEN] = "Opponent";
    char last_guess[SEQ_LEN + 1] = "";
    char pending_guess[SEQ_LEN + 1] = "";
    bool has_pending_guess = false;
    bool awaiting_feedback = false;
    char auto_feedback[SEQ_LEN + 1] = "";
    long last_broadcast = 0;
    long last_render = 0;
    long last_peer_activity = 0;
    long last_ping = 0;

    discovery_send_broadcast(disc_sock, DISCOVERY_PORT, my_name, game_port);
    last_broadcast = get_time_sec();
    last_render = last_broadcast;
    peer_table_render(&peers);

    while (g_running) {
        long now = get_time_sec();

        if (state == STATE_DISCOVERY) {
            if (now - last_broadcast >= BROADCAST_INTERVAL_SEC) {
                discovery_send_broadcast(disc_sock, DISCOVERY_PORT, my_name, game_port);
                last_broadcast = now;
            }
            if (peer_table_purge_stale(&peers, PEER_EXPIRY_SEC)) {
                peer_table_render_inplace(&peers);
                last_render = now;
            } else if (now - last_render >= 1) {
                if (peers.count > 0) {
                    peer_table_render_inplace(&peers);
                }
                last_render = now;
            }
        } else if (state != STATE_GAME_OVER && state != STATE_DISCONNECTED && net.is_udp && net.connected) {
            if (now - last_peer_activity >= 4) {
                printf("\n%s disconnected. Press enter to go home.\n", opponent_name);
                fflush(stdout);
                state = STATE_DISCONNECTED;
                net_transport_disconnect(&net);
            } else if (now - last_ping >= 1) {
                sendto(net.conn_sock, "P", 1, 0, (struct sockaddr *)&net.peer_addr, sizeof(net.peer_addr));
                last_ping = now;
            }
        }

        struct pollfd fds[3];
        int nfds = 0;

        fds[0].fd = STDIN_FILENO;
        fds[0].events = POLLIN;
        fds[0].revents = 0;
        nfds++;

        if (state == STATE_DISCOVERY) {
            fds[1].fd = disc_sock;
            fds[1].events = POLLIN;
            fds[1].revents = 0;
            nfds++;

            fds[2].fd = net.listen_sock;
            fds[2].events = POLLIN;
            fds[2].revents = 0;
            nfds++;
        } else if (net.connected && net.conn_sock >= 0) {
            fds[1].fd = net.conn_sock;
            fds[1].events = POLLIN;
            fds[1].revents = 0;
            nfds++;

            if (!net.is_udp && net.listen_sock >= 0) {
                fds[2].fd = net.listen_sock;
                fds[2].events = POLLIN;
                fds[2].revents = 0;
                nfds++;
            }
        }

        int poll_res = poll(fds, nfds, 500);
        if (poll_res < 0) {
            if (errno == EINTR) continue;
            break;
        }

        // 1. Process network socket events
        if (state != STATE_DISCOVERY && !net.is_udp && nfds >= 3 && (fds[2].revents & POLLIN)) {
            int busy_fd = accept(net.listen_sock, NULL, NULL);
            if (busy_fd >= 0) {
                game_msg_t rej = {.verb = VERB_CHALLENGE_RESPONSE};
                strncpy(rej.payload, "no", sizeof(rej.payload) - 1);
                send(busy_fd, &rej, sizeof(rej), 0);
                close(busy_fd);
            }
        }

        if (state == STATE_DISCOVERY && nfds >= 3 && (fds[2].revents & POLLIN)) {
            if (!net.is_udp) {
                if (net_transport_accept(&net)) {
                    game_msg_t msg;
                    net_recv_status_t st = net_transport_recv(&net, &msg);
                    if (st == NET_RECV_OK && msg.verb == VERB_CHALLENGE) {
                        strncpy(opponent_name, msg.payload, MAX_NAME_LEN - 1);
                        opponent_name[MAX_NAME_LEN - 1] = '\0';
                        state = STATE_CHALLENGE_PROMPT;
                        printf("\nChallenge from %s! Accept? (yes/no): ", opponent_name);
                        fflush(stdout);
                    }
                }
            } else {
                game_msg_t msg;
                net_recv_status_t st = net_transport_recv(&net, &msg);
                if (st == NET_RECV_OK && msg.verb == VERB_CHALLENGE) {
                    strncpy(opponent_name, msg.payload, MAX_NAME_LEN - 1);
                    opponent_name[MAX_NAME_LEN - 1] = '\0';
                    last_peer_activity = get_time_sec();
                    last_ping = last_peer_activity;
                    state = STATE_CHALLENGE_PROMPT;
                    printf("\nChallenge from %s! Accept? (yes/no): ", opponent_name);
                    fflush(stdout);
                }
            }
        }

        if (state == STATE_DISCOVERY && nfds >= 2 && (fds[1].revents & POLLIN)) {
            char p_name[MAX_NAME_LEN];
            char p_ip[INET_ADDRSTRLEN];
            uint16_t p_port = 0;
            if (discovery_recv_packet(disc_sock, p_name, sizeof(p_name), p_ip, sizeof(p_ip), &p_port) > 0) {
                peer_table_update(&peers, p_name, p_ip, p_port, my_name, game_port);
                peer_table_render_inplace(&peers);
                last_render = get_time_sec();
            }
        }

        if (state != STATE_DISCOVERY && nfds >= 2 && (fds[1].revents & POLLIN)) {
            game_msg_t msg;
            net_recv_status_t st = net_transport_recv(&net, &msg);
            if (st == NET_RECV_OK || (net.is_udp && st == NET_RECV_PARTIAL)) {
                last_peer_activity = get_time_sec();
            }
            if (st == NET_RECV_DISCONNECT || (!net.is_udp && st == NET_RECV_ERROR) ||
                (st == NET_RECV_OK && msg.verb == VERB_DISCONNECT)) {
                if (state != STATE_GAME_OVER && state != STATE_DISCONNECTED) {
                    printf("\n%s disconnected. Press enter to go home.\n", opponent_name);
                    state = STATE_DISCONNECTED;
                }
                net_transport_disconnect(&net);
            } else if (st == NET_RECV_OK) {
                if (state == STATE_WAIT_CHALLENGE_RESP && msg.verb == VERB_CHALLENGE_RESPONSE) {
                    if (strcmp(msg.payload, "yes") == 0) {
                        game_init(&game, ROLE_MASTERMIND);
                        state = STATE_INPUT_MASTER_SEQ;
                        has_pending_guess = false;
                        printf("\nChallenge accepted! Enter master sequence (5 digits): ");
                        fflush(stdout);
                    } else {
                        printf("\nChallenge rejected by %s.\n", opponent_name);
                        return_to_discovery(&state, &net, &peers);
                    }
                } else if (state == STATE_INPUT_MASTER_SEQ && game.role == ROLE_MASTERMIND && msg.verb == VERB_GUESS) {
                    strncpy(pending_guess, msg.payload, SEQ_LEN);
                    pending_guess[SEQ_LEN] = '\0';
                    has_pending_guess = true;
                } else if (state == STATE_PLAYING || state == STATE_WAIT_FEEDBACK_INPUT) {
                    if (state == STATE_PLAYING && game.role == ROLE_MASTERMIND && msg.verb == VERB_GUESS) {
                        strncpy(pending_guess, msg.payload, SEQ_LEN);
                        pending_guess[SEQ_LEN] = '\0';
                        game_compute_feedback(game.master_sequence, pending_guess, auto_feedback);
                        state = STATE_WAIT_FEEDBACK_INPUT;
                        printf("\n%s guessed: %s\nEnter feedback (5 chars using 'o', 'x', '-'): ",
                               opponent_name, pending_guess);
                        fflush(stdout);
                    } else if (game.role == ROLE_CODEBREAKER && msg.verb == VERB_FEEDBACK) {
                        awaiting_feedback = false;
                        game_record_attempt(&game, last_guess, msg.payload);
                        game_render_board(&game);

                        if (!game.game_over) {
                            printf("Enter guess (5 digits): ");
                            fflush(stdout);
                        }
                    } else if (game.role == ROLE_CODEBREAKER && msg.verb == VERB_GAME_OVER) {
                        strncpy(game.master_sequence, msg.payload, SEQ_LEN);
                        game.master_sequence[SEQ_LEN] = '\0';
                        game.game_over = true;
                        game_render_board(&game);

                        bool played_fair = true;
                        for (int a = 0; a < game.attempt_count; a++) {
                            char expected_fb[SEQ_LEN + 1];
                            game_compute_feedback(game.master_sequence, game.attempts[a].guess, expected_fb);
                            if (!validate_feedback_counts(game.attempts[a].feedback, expected_fb)) {
                                played_fair = false;
                                break;
                            }
                        }
                        if (!played_fair) {
                            printf("\nWARNING: Mastermind did not play fair! Incorrect feedback was detected.\n");
                        }

                        if (game.won) {
                            printf("\nYou solved the sequence in %d attempts!\n", game.attempt_count);
                        } else {
                            printf("\nYou ran out of attempts! Master sequence was: %s\n", game.master_sequence);
                        }
                        printf("Press enter to go home.\n");
                        state = STATE_GAME_OVER;
                    }
                }
            }
        }

        // 2. Process stdin user input
        if (fds[0].revents & POLLIN) {
            char line[128];
            if (!fgets(line, sizeof(line), stdin)) {
                break;
            }
            line[strcspn(line, "\r\n")] = '\0';

            if (state == STATE_DISCOVERY) {
                int peer_id = 0;
                if (sscanf(line, "challenge %d", &peer_id) == 1) {
                    peer_entry_t target;
                    if (peer_table_get(&peers, peer_id, &target)) {
                        strncpy(opponent_name, target.name, MAX_NAME_LEN - 1);
                        opponent_name[MAX_NAME_LEN - 1] = '\0';

                        if (net_transport_connect(&net, target.ip, target.port)) {
                            game_msg_t cmsg = {.verb = VERB_CHALLENGE};
                            strncpy(cmsg.payload, my_name, sizeof(cmsg.payload) - 1);
                            if (net_transport_send(&net, &cmsg)) {
                                last_peer_activity = get_time_sec();
                                last_ping = last_peer_activity;
                                state = STATE_WAIT_CHALLENGE_RESP;
                                printf("Challenging %s... Waiting for response...\n", opponent_name);
                            } else {
                                printf("Failed to send challenge.\n");
                                net_transport_disconnect(&net);
                            }
                        } else {
                            char cmsg2[96];
                            snprintf(cmsg2, sizeof(cmsg2), "Could not connect to %s (%s:%u).", target.name, target.ip, target.port);
                            peer_table_reset_prompt(cmsg2);
                        }
                    } else {
                        char umsg[64];
                        snprintf(umsg, sizeof(umsg), "Unknown player ID %d. Enter a valid ID.", peer_id);
                        peer_table_reset_prompt(umsg);
                    }
                } else {
                    peer_table_reset_prompt(strlen(line) > 0 ? "Type 'challenge <ID>' to challenge a player." : "");
                }
            } else if (state == STATE_CHALLENGE_PROMPT) {
                if (strcmp(line, "yes") == 0) {
                    game_msg_t resp = {.verb = VERB_CHALLENGE_RESPONSE};
                    strncpy(resp.payload, "yes", sizeof(resp.payload) - 1);
                    net_transport_send(&net, &resp);

                    game_init(&game, ROLE_CODEBREAKER);
                    awaiting_feedback = false;
                    state = STATE_PLAYING;
                    game_render_board(&game);
                    printf("Accepted! Enter your first guess (5 digits): ");
                    fflush(stdout);
                } else if (strcmp(line, "no") == 0) {
                    game_msg_t resp = {.verb = VERB_CHALLENGE_RESPONSE};
                    strncpy(resp.payload, "no", sizeof(resp.payload) - 1);
                    net_transport_send(&net, &resp);
                    return_to_discovery(&state, &net, &peers);
                } else {
                    printf("Please type 'yes' or 'no': ");
                    fflush(stdout);
                }
            } else if (state == STATE_INPUT_MASTER_SEQ) {
                if (game_validate_sequence(line)) {
                    strncpy(game.master_sequence, line, SEQ_LEN);
                    game.master_sequence[SEQ_LEN] = '\0';
                    game_render_board(&game);

                    if (has_pending_guess) {
                        has_pending_guess = false;
                        game_compute_feedback(game.master_sequence, pending_guess, auto_feedback);
                        state = STATE_WAIT_FEEDBACK_INPUT;
                        printf("\n%s guessed: %s\nEnter feedback (5 chars using 'o', 'x', '-'): ",
                               opponent_name, pending_guess);
                        fflush(stdout);
                    } else {
                        state = STATE_PLAYING;
                        printf("Master sequence set. Waiting for %s's first guess...\n", opponent_name);
                        fflush(stdout);
                    }
                } else {
                    printf("Invalid sequence! Must be exactly 5 digits (0-9).\nEnter master sequence (5 digits): ");
                    fflush(stdout);
                }
            } else if (state == STATE_WAIT_FEEDBACK_INPUT) {
                char fb_to_send[SEQ_LEN + 1];
                if (!validate_feedback_string(line)) {
                    printf("Invalid feedback! Must be 5 characters using only 'o', 'x', and '-'.\n"
                           "Enter feedback (5 chars using 'o', 'x', '-'): ");
                    fflush(stdout);
                    continue;
                } else if (!validate_feedback_counts(line, auto_feedback)) {
                    printf("Mastermind must play fair! Feedback must have correct counts of 'x', 'o', and '-'.\n"
                           "Enter feedback (5 chars using 'o', 'x', '-'): ");
                    fflush(stdout);
                    continue;
                } else {
                    strncpy(fb_to_send, line, SEQ_LEN);
                    fb_to_send[SEQ_LEN] = '\0';
                }

                game_record_attempt(&game, pending_guess, fb_to_send);

                game_msg_t fb_msg = {.verb = VERB_FEEDBACK};
                strncpy(fb_msg.payload, fb_to_send, sizeof(fb_msg.payload) - 1);
                if (!net_transport_send(&net, &fb_msg)) {
                    printf("\n%s disconnected. Press enter to go home.\n", opponent_name);
                    state = STATE_DISCONNECTED;
                    net_transport_disconnect(&net);
                    continue;
                }

                game_render_board(&game);

                if (game.game_over) {
                    game_msg_t end_msg = {.verb = VERB_GAME_OVER};
                    strncpy(end_msg.payload, game.master_sequence, sizeof(end_msg.payload) - 1);
                    net_transport_send(&net, &end_msg);

                    if (game.won) {
                        printf("\n%s found the sequence in %d attempts!\n", opponent_name, game.attempt_count);
                    } else {
                        printf("\n%s ran out of attempts! Game over.\n", opponent_name);
                    }
                    printf("Press enter to go home.\n");
                    state = STATE_GAME_OVER;
                } else {
                    state = STATE_PLAYING;
                    printf("Feedback sent. Waiting for %s's next guess...\n", opponent_name);
                    fflush(stdout);
                }
            } else if (state == STATE_PLAYING && game.role == ROLE_CODEBREAKER) {
                if (awaiting_feedback) {
                    printf("Waiting for feedback from %s...\n", opponent_name);
                    fflush(stdout);
                } else if (game_validate_sequence(line)) {
                    strncpy(last_guess, line, SEQ_LEN);
                    last_guess[SEQ_LEN] = '\0';

                    game_msg_t gmsg = {.verb = VERB_GUESS};
                    strncpy(gmsg.payload, last_guess, sizeof(gmsg.payload) - 1);
                    if (!net_transport_send(&net, &gmsg)) {
                        printf("\n%s disconnected. Press enter to go home.\n", opponent_name);
                        state = STATE_DISCONNECTED;
                        net_transport_disconnect(&net);
                    } else {
                        awaiting_feedback = true;
                        printf("Guess sent. Waiting for feedback...\n");
                        fflush(stdout);
                    }
                } else {
                    printf("Invalid guess! Must be exactly 5 digits (0-9).\nEnter guess (5 digits): ");
                    fflush(stdout);
                }
            } else if (state == STATE_GAME_OVER || state == STATE_DISCONNECTED) {
                return_to_discovery(&state, &net, &peers);
            }
        }
    }

    if (net.connected) {
        game_msg_t dc = {.verb = VERB_DISCONNECT};
        net_transport_send(&net, &dc);
    }
    net_transport_cleanup(&net);
    close(disc_sock);
    logger_close();
    printf("\nExiting mastermind.\n");
    return 0;
}
