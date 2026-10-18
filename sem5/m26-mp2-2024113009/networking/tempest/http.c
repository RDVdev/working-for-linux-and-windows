#include "http.h"
#include "net.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

char *http_build_request(const char *encoded_city, const char *host) {
    char buf[1024];
    int n = snprintf(buf, sizeof(buf),
        "GET /%s?0T HTTP/1.1\r\n"
        "Host: %s\r\n"
        "User-Agent: curl/8.5.0\r\n" //so that server sends ascii text and not browser html
        "Accept: */*\r\n"
        "Connection: close\r\n"
        "\r\n",
        encoded_city, host);
    if (n < 0 || (size_t)n >= sizeof(buf)) {
        return NULL;
    }
    return strdup(buf);
}

//substring search helper
static const char *case_str_search(const char *string, const char *substr) {
    if (!string || !substr) return NULL;
    size_t nlen = strlen(substr);
    while (*string) {
        if (strncasecmp(string, substr, nlen) == 0) {
            return string;
        }
        string++;
    }
    return NULL;
}

int http_read_response(int fd, http_response_t *resp, struct timespec start_time, int timeout_sec) {
    memset(resp, 0, sizeof(*resp));
    resp->content_length = -1;

    size_t cap = 8192;
    char *raw = malloc(cap);
    if (!raw) return -1;
    size_t total_read = 0;

    const char *header_end = NULL;

    while(1) {
        if (total_read + 4096 >= cap) {
            cap *= 2;
            char *tmp = realloc(raw, cap);
            if (!tmp) {
                free(raw);
                return -1;
            }
            raw = tmp;
        }
        ssize_t n = net_recv_chunk(fd, raw+total_read, 4096, start_time, timeout_sec);
        if (n == -2) {
            resp->timed_out = true;
            free(raw);
            return -1;
        }
        if (n < 0) {
            free(raw);
            return -1;
        }
        if (n == 0) {
            break; //conn closed
        }
        total_read += (size_t)n;

        //header boundary
        if (!header_end && total_read >= 4) {
            for (size_t i  = 0; i + 3 < total_read; i++) {
                if (raw[i] == '\r' && raw[i+1] == '\n' && raw[i+2] == '\r' && raw[i+3] == '\n') {
                    header_end = &raw[i];
                    break;
                }
            }
        }

        //check to see if full content lenght arrived
        if (header_end) {
            size_t hlen = (size_t)(header_end - raw);
            char saved = raw[hlen];
            raw[hlen]  = '\0';

            const char *cl = case_str_search(raw, "Content-Length:");
            if (cl) {
                resp->content_length = strtol(cl+15, NULL, 10);
            }
            raw[hlen] = saved;
            size_t body_start = hlen+4;
            size_t current_body_len = total_read - body_start;

            if (resp->content_length >= 0 && (long)current_body_len >= resp->content_length) {
                break;
            }
        }
    }

    if (!header_end) {
        free(raw);
        return -1;
    }

    size_t header_len = (size_t)(header_end - raw);
    resp->raw_headers = malloc(header_len+1);
    if (!resp->raw_headers) {
        free(raw);
        return -1;
    }
    memcpy(resp->raw_headers, raw, header_len);
    resp->raw_headers[header_len] = '\0';
    resp->raw_headers_len = header_len;

    //status code
    if (sscanf(resp->raw_headers, "HTTP/%*s %d", &resp->status_code) != 1) {
        resp->status_code = 0;
    }

    size_t body_offset = header_len+4;
    size_t raw_body_len = (total_read >= body_offset) ? (total_read - body_offset) : 0;
    size_t blen = raw_body_len;
    if (resp->content_length >=0 && (size_t)resp->content_length < blen) {
        blen=(size_t)resp->content_length;
    }
    resp->body = malloc(blen+1);
    if (!resp->body) {
        free(raw);
        return -1;
    }
    memcpy(resp->body, raw+body_offset, blen);
    resp->body[blen] = '\0';
    resp->body_len = blen;

    free(raw);
    return 0;
}

void http_response_free(http_response_t *resp) {
    if (!resp) return;
    free(resp->raw_headers);
    free(resp->body);
    memset(resp, 0, sizeof(*resp));
}