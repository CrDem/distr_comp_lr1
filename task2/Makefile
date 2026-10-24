CC     = gcc
CFLAGS = -O2 -std=gnu11 -Wall -Wextra -pthread -I..
DEPS   = nbody.c ../timer.h

nbody: $(DEPS)
	$(CC) $(CFLAGS) -o $@ nbody.c -lm

nbody_tsan: $(DEPS)
	$(CC) -O1 -g -std=gnu11 -fsanitize=thread -pthread -I.. -o $@ nbody.c -lm

test: nbody
	python3 check.py

tsan: nbody_tsan
	python3 gen.py cloud 300 -o data/tsan.txt > /dev/null
	for m in naive local; do setarch -R ./nbody_tsan 1 data/tsan.txt -d 0.05 -e 0.1 -t 7 -m $$m -n || exit 1; done

bench: nbody
	python3 bench.py

plot:
	python3 plot.py

clean:
	rm -f nbody nbody_tsan *.csv

.PHONY: test tsan bench plot clean
