CC = gcc
CFLAGS = -Wall -O2

all: libglink_api.a

libglink_api.a: glink_api.o
	ar rcs $@ $^

glink_api.o: glink_api.c glink_api.h glink_regs.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f *.o *.a
