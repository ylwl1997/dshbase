CC = gcc
CFLAGS = -Wall -O2
API_DIR = ../api

all: test_glink_api test_glink_dual test_smart_nc1_nt1

test_glink_api: test_glink_api.c $(API_DIR)/libglink_api.a
	$(CC) $(CFLAGS) $< -o $@ -L$(API_DIR) -lglink_api -I$(API_DIR)

test_glink_dual: test_glink_dual.c $(API_DIR)/glink_api.c $(API_DIR)/glink_api.h
	$(CC) $(CFLAGS) -I$(API_DIR) -o $@ test_glink_dual.c $(API_DIR)/glink_api.c

test_smart_nc1_nt1: test_smart_nc1_nt1.c $(API_DIR)/glink_api.c $(API_DIR)/glink_api.h $(API_DIR)/glink_regs.h
	$(CC) $(CFLAGS) -I$(API_DIR) -o $@ test_smart_nc1_nt1.c $(API_DIR)/glink_api.c

$(API_DIR)/libglink_api.a:
	$(MAKE) -C $(API_DIR)

clean:
	rm -f test_glink_api test_glink_dual test_smart_nc1_nt1
	$(MAKE) -C $(API_DIR) clean
