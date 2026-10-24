CC     = gcc
CFLAGS = -O2 -std=gnu11 -Wall -Wno-unused-result -pthread -I..
COMMON = pth_ll_rwl.c ../my_rand.c

all: ll_pthread ll_my

ll_pthread: $(COMMON) ../my_rand.h ../timer.h
	$(CC) $(CFLAGS) -o $@ $(COMMON)

ll_my: $(COMMON) my_rwlock.c my_rwlock.h ../my_rand.h ../timer.h
	$(CC) $(CFLAGS) -DMY_RWLOCK -o $@ $(COMMON) my_rwlock.c

tsan: $(COMMON) my_rwlock.c my_rwlock.h
	$(CC) -O1 -g -std=gnu11 -pthread -fsanitize=thread -I.. -DMY_RWLOCK -o ll_my_tsan $(COMMON) my_rwlock.c
	printf "1000\n20000\n0.8\n0.1\n" | setarch -R ./ll_my_tsan 8

bench: all
	python3 bench.py

clean:
	rm -f ll_pthread ll_my ll_my_tsan

.PHONY: all tsan bench clean
