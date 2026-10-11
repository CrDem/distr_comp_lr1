CC     = gcc
CFLAGS = -O2 -std=gnu11 -Wall -Wextra -pthread -I..
SRC    = mandelbrot.c ../my_rand.c
DEPS   = $(SRC) ../my_rand.h ../timer.h
MODES  = static mutex spin atomic dynamic

mandelbrot: $(DEPS)
	$(CC) $(CFLAGS) -o $@ $(SRC)

mandelbrot_tsan: $(DEPS)
	$(CC) -O1 -g -std=gnu11 -fsanitize=thread -pthread -I.. -o $@ $(SRC)

test: mandelbrot
	python3 check.py

tsan: mandelbrot_tsan
	for m in $(MODES); do setarch -R ./mandelbrot_tsan 8 20000 -m $$m -i 100 -b 7 -n || exit 1; done

bench: mandelbrot
	python3 bench.py

plot:
	python3 plot.py

clean:
	rm -f mandelbrot mandelbrot_tsan *.csv

.PHONY: test tsan bench plot clean
