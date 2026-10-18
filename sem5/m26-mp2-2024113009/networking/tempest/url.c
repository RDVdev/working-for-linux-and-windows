#include "url.h"
#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool is_unreserved(unsigned char c) {
    return isalnum(c) || c == '-' || c == '_' || c == '.' || c == '~';
}

char *url_encode(const char *src) {
    if (!src) {
        return NULL;
    }

    size_t len = strlen(src);
    size_t max_len = len*3+1; //worst case when %xx (3 bytes) + 1 byte for null terminator
    char *dest = malloc(max_len);
    if (!dest) {
        return NULL;
    }

    char *p = dest;
    for (size_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)src[i];
        if (is_unreserved(c)) {
            *p++ = (char)c;
        }
        else {
            snprintf(p,4,"%%%02X", c);
            p += 3;
        }
    }
    *p = '\0';
    return dest;
}