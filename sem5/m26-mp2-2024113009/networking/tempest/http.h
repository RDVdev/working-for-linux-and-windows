#ifndef HTTP_H
#define HTTP_H
#include <stdbool.h>
#include <stddef.h>
#include <time.h>

typedef struct {
    int status_code;
    char *raw_headers;
    size_t raw_headers_len;
    char *body;
    size_t body_len;
    long content_length;
    bool timed_out;
} http_response_t;

char *http_build_request(const char *encoded_city, const char *host);

int http_read_response(int fd, http_response_t *resp, struct timespec start_time, int timeout_sec);

void http_response_free(http_response_t *resp);

#endif