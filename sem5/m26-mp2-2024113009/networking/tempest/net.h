#ifndef NET_H
#define NET_H
#include <stddef.h>
#include <sys/types.h>
#include <time.h>

int net_connect(const char *host, const char *port); //uses posix getaddr info and socket api
//ipv4 and ipv6

int net_get_remaining_timeout_ms(struct timespec start_time, int timeout_sec);

ssize_t net_send_all(int fd, const void *buf, size_t len, struct timespec start_time, int timeout_sec);

ssize_t net_recv_chunk(int fd, void *buf, size_t len, struct timespec start_time, int timeout_sec);

void net_close(int fd);

#endif


