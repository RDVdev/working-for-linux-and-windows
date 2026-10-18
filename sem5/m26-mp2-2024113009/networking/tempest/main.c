#include "http.h"
#include "net.h"
#include "url.h"
#include <ctype.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void print_request_raw(const char *req) {
    char *copy = strdup(req);
    if (!copy) return;
    char *line = copy;
    while (*line) {
        char *crlf = strstr(line, "\r\n");
        if (crlf) {
            *crlf = '\0';
            printf("> %s\n", line);
            line = crlf+2;
            if (*line == '\0') {
                printf(">\n");
                break;
            }
        }
        else {
            printf("> %s\n", line);
            break;
        }
    }
    free(copy);
}

static void print_response_headers_raw(const char *headers) {
    char *copy = strdup(headers);
    if (!copy) return;
    char *line = copy;
    while (*line) {
        char *crlf = strstr(line, "\r\n");
        if (crlf) {
            *crlf = '\0';
            printf("< %s\n", line);
            line = crlf+2;
        }
        else {
            if (*line != '\0') {
                printf("< %s\n", line);
            }
            break;
        }
    }
    printf("<\n");
    free(copy);
}

int main(int argc, char *argv[]) {
    //arg count check
    if (argc < 2) {
        fprintf(stderr, "tempest: invalid location\n");
        return 1;
    }
    if (argc > 3) {
        fprintf(stderr, "tempest: too many arguments\n");
        return 1;
    }

    const char *city = argv[1];
    bool raw_mode = false;

    if (argc == 3) {
        if (strcmp(argv[2], "--raw") == 0) {
            raw_mode = true;
        }
        else {
            fprintf(stderr, "tempest: too many arguments\n");
            return 1;
        }
    }

    if (strcmp(city, "--raw") == 0) {
        fprintf(stderr, "tempest: invalid location\n");
        return 1;
    }
    bool all_space = true;
    for (size_t i = 0; city[i] != '\0'; i++) {
        if (!isspace((unsigned char)city[i])) {
            all_space = false;
            break;
        }
    }
    if (all_space) {
        fprintf(stderr, "tempest: invalid location\n");
        return 1;
    }

    //url encoding
    char *encoded_city = url_encode(city);
    if (!encoded_city) {
        fprintf(stderr, "internal error\n");//not mentioned in doc - jic
        return 1;
    }

    //app level timer (10s) just bef sendall
    struct timespec start_time;
    clock_gettime(CLOCK_MONOTONIC, &start_time);


    //connecting to wttr.is
    int fd = net_connect("wttr.is", "80");
    if (fd < 0) {
        free(encoded_city);
        fprintf(stderr, "tempest: connection failed\n");
        return 1;
    }

    if (net_get_remaining_timeout_ms(start_time, 10) <= 0) {
        free(encoded_city);
        net_close(fd);
        fprintf(stderr, "tempest: request timed out\n");
        return 1;
    }

    //http req
    char *request = http_build_request(encoded_city, "wttr.is");
    free(encoded_city);
    if (!request) {
        net_close(fd);
        return 1;
    }

    if (raw_mode) {
        print_request_raw(request);
    }

    //send req
    size_t req_len = strlen(request);
    ssize_t sent = net_send_all(fd, request, req_len, start_time, 10);
    free(request);
    if (sent < (ssize_t)req_len) {
        net_close(fd);
        if (sent == 0) {
            fprintf(stderr, "tempest: request timed out\n");
        }
        else {
            fprintf(stderr, "tempest: send failed: %s\n", strerror(errno));
        }
        return 1;
    }

    //receiving and parsing resp
    http_response_t resp;
    int r= http_read_response(fd, &resp, start_time, 10);
    net_close(fd);

    if (r < 0) {
        if (resp.timed_out) {
            fprintf(stderr, "tempest: request timed out\n");
        }
        else {
            fprintf(stderr, "tempest: failed to read response\n");
        }
        http_response_free(&resp);
        return 1;
    }


    //invalid loc check via status code
    bool is_invalid = (resp.status_code != 200);
    if (resp.body && (strstr(resp.body, "location not found") != NULL || strstr(resp.body, "Unknown location") != NULL)) {
        is_invalid = true;
    }

    //--raw precedence

    if (raw_mode) {
        if (resp.raw_headers) {
            print_response_headers_raw(resp.raw_headers);
        }
        if (resp.body) {
            fputs(resp.body, stdout);
        }
        http_response_free(&resp);
        // as per q23: exit with non-zero code if invalid loc, 0 if valid
        return is_invalid ? 1 : 0;
    }


    if (is_invalid) {
        fprintf(stderr, "tempest: invalid location\n");
        http_response_free(&resp);
        return 1;
    }

    //success
    if (resp.body) {
        fputs(resp.body, stdout);
    }

    http_response_free(&resp);
    return 0;
    
}
