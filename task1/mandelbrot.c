#include <pthread.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "my_rand.h"
#include "timer.h" 

#define XMIN -2.0
#define XMAX 0.5
#define YMIN -1.25
#define YMAX 1.25

typedef struct {
    double x, y;
} point_t;

typedef void *(*worker_t)(void *);

static int nthreads;
static long npoints;
static int max_iter = 1000;
static int use_shortcut = 0;
static long chunk = 1024;
static point_t *points;

static long counter = 0;
static atomic_long atomic_counter = 0;
static pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_spinlock_t spin;

static int in_set(double cx, double cy) {
    if (use_shortcut) {
        double xq = cx - 0.25, y2 = cy * cy;
        double q = xq * xq + y2;
        if (q * (q + xq) <= 0.25 * y2)
            return 1;
        if ((cx + 1.0) * (cx + 1.0) + y2 <= 0.0625)
            return 1;
    }
    double x = 0.0, y = 0.0, x2 = 0.0, y2 = 0.0;
    for (int i = 0; i < max_iter; i++) {
        y = 2.0 * x * y + cy;
        x = x2 - y2 + cx;
        x2 = x * x;
        y2 = y * y;
        if (x2 + y2 > 4.0)
            return 0;
    }
    return 1;
}

static point_t next_point(unsigned *seed) {
    point_t c;
    do {
        c.x = XMIN + (XMAX - XMIN) * my_drand(seed);
        c.y = YMIN + (YMAX - YMIN) * my_drand(seed);
    } while (!in_set(c.x, c.y));
    return c;
}

static unsigned thread_seed(long rank) {
    unsigned seed = (unsigned)(rank + 1) * 2654435761u;
    return seed % 4294967291u ? seed : 1;
}

static void *work_static(void *arg) {
    long rank = (long)arg;
    unsigned seed = thread_seed(rank);
    long first = npoints * rank / nthreads;
    long last = npoints * (rank + 1) / nthreads;
    for (long i = first; i < last; i++)
        points[i] = next_point(&seed);
    return NULL;
}

static void *work_mutex(void *arg) {
    unsigned seed = thread_seed((long)arg);
    for (;;) {
        point_t p = next_point(&seed);
        pthread_mutex_lock(&mutex);
        long i = counter < npoints ? counter++ : npoints;
        pthread_mutex_unlock(&mutex);
        if (i >= npoints)
            break;
        points[i] = p;
    }
    return NULL;
}

static void *work_spin(void *arg) {
    unsigned seed = thread_seed((long)arg);
    for (;;) {
        point_t p = next_point(&seed);
        pthread_spin_lock(&spin);
        long i = counter < npoints ? counter++ : npoints;
        pthread_spin_unlock(&spin);
        if (i >= npoints)
            break;
        points[i] = p;
    }
    return NULL;
}

static void *work_atomic(void *arg) {
    unsigned seed = thread_seed((long)arg);
    for (;;) {
        point_t p = next_point(&seed);
        long i = atomic_fetch_add_explicit(&atomic_counter, 1, memory_order_relaxed);
        if (i >= npoints)
            break;
        points[i] = p;
    }
    return NULL;
}

static void *work_dynamic(void *arg) {
    unsigned seed = thread_seed((long)arg);
    for (;;) {
        pthread_mutex_lock(&mutex);
        long first = counter;
        counter += chunk;
        pthread_mutex_unlock(&mutex);
        if (first >= npoints)
            break;
        long last = first + chunk < npoints ? first + chunk : npoints;
        for (long i = first; i < last; i++)
            points[i] = next_point(&seed);
    }
    return NULL;
}

static const struct {
    const char *name;
    worker_t fn;
} modes[] = {
    {"static", work_static},
    {"mutex", work_mutex},
    {"spin", work_spin},
    {"atomic", work_atomic},
    {"dynamic", work_dynamic},
};

static int write_csv(const char *path) {
    FILE *f = fopen(path, "w");
    if (!f) {
        perror(path);
        return -1;
    }
    fputs("x,y\n", f);
    for (long i = 0; i < npoints; i++)
        fprintf(f, "%.12f,%.12f\n", points[i].x, points[i].y);
    return fclose(f);
}

static void usage(const char *prog) {
    fprintf(stderr,
            "usage: %s nthreads npoints [-m static|mutex|spin|atomic|dynamic]\n"
            "       [-i max_iter] [-b chunk] [-s] [-o out.csv] [-n]\n",
            prog);
    exit(1);
}

int main(int argc, char *argv[]) {
    const char *out = "mandelbrot.csv";
    const char *mode_name = "static";
    worker_t worker = NULL;
    int opt;

    while ((opt = getopt(argc, argv, "m:i:b:so:n")) != -1) {
        switch (opt) {
        case 'm': mode_name = optarg; break;
        case 'i': max_iter = atoi(optarg); break;
        case 'b': chunk = atol(optarg); break;
        case 's': use_shortcut = 1; break;
        case 'o': out = optarg; break;
        case 'n': out = NULL; break;
        default: usage(argv[0]);
        }
    }
    if (argc - optind != 2)
        usage(argv[0]);
    nthreads = atoi(argv[optind]);
    npoints = atol(argv[optind + 1]);
    for (size_t k = 0; k < sizeof modes / sizeof modes[0]; k++)
        if (strcmp(mode_name, modes[k].name) == 0)
            worker = modes[k].fn;
    if (nthreads < 1 || npoints < 1 || max_iter < 1 || chunk < 1 || !worker)
        usage(argv[0]);

    points = malloc(npoints * sizeof *points);
    pthread_t *threads = malloc(nthreads * sizeof *threads);
    if (!points || !threads) {
        perror("malloc");
        return 1;
    }
    pthread_spin_init(&spin, PTHREAD_PROCESS_PRIVATE);

    double start, computed, written;
    GET_TIME(start);
    for (long t = 0; t < nthreads; t++)
        pthread_create(&threads[t], NULL, worker, (void *)t);
    for (long t = 0; t < nthreads; t++)
        pthread_join(threads[t], NULL);
    GET_TIME(computed);
    if (out && write_csv(out) != 0)
        return 1;
    GET_TIME(written);

    printf("mode=%s threads=%d points=%ld max_iter=%d shortcut=%d chunk=%ld "
           "compute=%.6f write=%.6f\n",
           mode_name, nthreads, npoints, max_iter, use_shortcut, chunk,
           computed - start, written - computed);

    pthread_spin_destroy(&spin);
    free(threads);
    free(points);
    return 0;
}
