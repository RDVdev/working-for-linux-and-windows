#include "logger.h"
#include <stdarg.h>
#include <stdio.h>
#include <sys/time.h>
#include <time.h>

static FILE *log_file = NULL;
static bool logging_enabled = false;

void logger_init(bool enabled) {
    logging_enabled = enabled;
    if (logging_enabled) {
        log_file = fopen("log.txt", "a");
        if (log_file) {
            logger_log("Logging session started");
        }
    }
}

void logger_log(const char *fmt, ...) {
    if (!logging_enabled || !log_file) {
        return;
    }

    //timestamp as per asn
    char time_buffer[30];
    struct timeval tv;
    time_t curtime;

    gettimeofday(&tv, NULL);
    curtime = tv.tv_sec;

    strftime(time_buffer, sizeof(time_buffer), "%Y-%m-%d %H:%M:%S", localtime(&curtime));

    fprintf(log_file, "[%s.%06ld] [LOG] ", time_buffer, tv.tv_usec);

    va_list args;
    va_start(args, fmt);
    vfprintf(log_file, fmt, args);
    va_end(args);

    fprintf(log_file, "\n");
    fflush(log_file);
}

void logger_close(void) {
    if (log_file) {
        logger_log("Logging session closed");
        fclose(log_file);
        log_file = NULL;
    }
    logging_enabled = false;
}