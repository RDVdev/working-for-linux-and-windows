 CC := $(shell which gcc-14 2>/dev/null || echo gcc)
CFLAGS = -std=c23 -D_POSIX_C_SOURCE=200809L -D_XOPEN_SOURCE=700 \
         -Wall -Wextra -Werror -Wno-unused-parameter -g
LDLIBS =

SRCS = $(wildcard *.c)

mastermind: $(SRCS)
ifneq ($(strip $(SRCS)),)
	$(CC) $(CFLAGS) -o mastermind $(SRCS) $(LDLIBS)
endif

clean:
	rm -f mastermind

.PHONY: clean
