#include "net.h"
#include <errno.h>
#include <netdb.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

int net_get_remaining_timeout_ms(struct timespec start_time, int timeout_sec) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0) {
        return 0;
    }
    long elapsed_ms = (now.tv_sec - start_time.tv_sec) * 1000L + (now.tv_nsec - start_time.tv_nsec) / 1000000L;
    long total_ms = (long)timeout_sec * 1000L;
    if (elapsed_ms >= total_ms) {
        return 0;
    }
    return (int)(total_ms - elapsed_ms);
}

int net_connect(const char *host, const char *port) {
    struct addrinfo hints;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC; //ipv4/6
    hints.ai_socktype = SOCK_STREAM; //tcp
    struct addrinfo *res = NULL;
    int err = getaddrinfo(host, port, &hints, &res);
    if (err != 0) {
        return -1;
    }
    int fd = -1;
    for (struct addrinfo *p = res; p != NULL; p = p->ai_next) {
        fd = socket(p->ai_family, p->ai_socktype, p->ai_protocol);
        if (fd < 0) {
            continue;
        }
        if (connect(fd, p->ai_addr, p->ai_addrlen) == 0) {
            break; //connected successfully
        }
        close(fd);
        fd = -1;
    }
    freeaddrinfo(res);
    return fd;
}

ssize_t net_send_all(int fd, const void *buf, size_t len, struct timespec start_time, int timeout_sec) {
    size_t total_sent = 0;
    const char *ptr = (const char *)buf;
    while (total_sent < len) {
        int rem_ms = net_get_remaining_timeout_ms(start_time, timeout_sec);
        if (rem_ms <= 0) {
            return 0; //app level timeout
        }
        struct pollfd pfd = {
            .fd = fd,
            .events = POLLOUT,
            .revents = 0
        };
        int pr = poll(&pfd, 1, rem_ms);
        if (pr < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (pr == 0) {
            return 0; //app levle timeout
        }
        ssize_t n = send(fd, ptr + total_sent, len - total_sent, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (n == 0) {
            return -1; //premature connection termination
        }
        total_sent += (size_t)n;
    }
    return (ssize_t)total_sent;
}

ssize_t net_recv_chunk(int fd, void *buf, size_t len, struct timespec start_time, int timeout_sec) {
    while (1) {
        int rem_ms = net_get_remaining_timeout_ms(start_time, timeout_sec);
        if (rem_ms <= 0) {
            return -2; //app level timeout
        }
        struct pollfd pfd = {
            .fd = fd,
            .events = POLLIN,
            .revents = 0
        };
        int pr = poll(&pfd, 1, rem_ms);
        if (pr < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (pr == 0) {
            return -2; //app level timeout
        }
        ssize_t n = recv(fd, buf, len, 0);
        if (n < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        return n; // >0 is bytes read, 0 is EOF
    }
}

void net_close(int fd) {
    if (fd >= 0) {
        close(fd);
    }
}