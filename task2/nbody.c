#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "timer.h"

#define G 6.67430e-11

typedef enum { MODE_NAIVE, MODE_LOCAL } mode_e;

static long n;
static double *m, *x, *y, *vx, *vy;
static double *fx, *fy;
static long stride;

static int nthreads;
static mode_e mode = MODE_LOCAL;
static double t_end, dt = 0.0, eps2 = 0.0;
static long nsteps, every = 1;

static FILE *out;
static double write_time = 0.0;
static pthread_barrier_t barrier;

static int read_input(const char *path) {
    FILE *f = fopen(path, "r");
    char line[1024];
    if (!f) {
        perror(path);
        return -1;
    }
    if (!fgets(line, sizeof line, f) || sscanf(line, "%ld", &n) != 1 || n < 1) {
        fprintf(stderr, "%s: bad body count\n", path);
        fclose(f);
        return -1;
    }
    m = malloc(5 * n * sizeof *m);
    if (!m) {
        perror("malloc");
        fclose(f);
        return -1;
    }
    x = m + n;
    y = x + n;
    vx = y + n;
    vy = vx + n;
    for (long i = 0; i < n;) {
        double v[7];
        if (!fgets(line, sizeof line, f)) {
            fprintf(stderr, "%s: expected %ld bodies, got %ld\n", path, n, i);
            fclose(f);
            return -1;
        }
        int k = sscanf(line, "%lf %lf %lf %lf %lf %lf %lf", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5], &v[6]);
        if (k <= 0)
            continue;
        if (k != 5 && k != 7) {
            fprintf(stderr, "%s: body %ld: expected 5 or 7 numbers, got %d\n", path, i + 1, k);
            fclose(f);
            return -1;
        }
        m[i] = v[0];
        x[i] = v[1];
        y[i] = v[2];
        vx[i] = k == 7 ? v[4] : v[3];
        vy[i] = k == 7 ? v[5] : v[4];
        i++;
    }
    fclose(f);
    return 0;
}

static void row_sum(long i, long j0, long j1, double *sx, double *sy) {
    double xi = x[i], yi = y[i], gmi = G * m[i];
    for (long j = j0; j < j1; j++) {
        double dx = x[j] - xi, dy = y[j] - yi;
        double r2 = dx * dx + dy * dy + eps2;
        double s = gmi * m[j] / (r2 * sqrt(r2));
        *sx += s * dx;
        *sy += s * dy;
    }
}

static void forces_naive(long first, long last) {
    for (long i = first; i < last; i++) {
        double sx = 0.0, sy = 0.0;
        row_sum(i, 0, i, &sx, &sy);
        row_sum(i, i + 1, n, &sx, &sy);
        fx[i] = sx;
        fy[i] = sy;
    }
}

static void corner(long i, double *restrict rfx, double *restrict rfy) {
    double xi = x[i], yi = y[i], gmi = G * m[i], sx = 0.0, sy = 0.0;
    for (long j = i + 1; j < n; j++) {
        double dx = x[j] - xi, dy = y[j] - yi;
        double r2 = dx * dx + dy * dy + eps2;
        double s = gmi * m[j] / (r2 * sqrt(r2));
        sx += s * dx;
        sy += s * dy;
        rfx[j] -= s * dx;
        rfy[j] -= s * dy;
    }
    rfx[i] += sx;
    rfy[i] += sy;
}

static void forces_local(long rank) {
    double *rfx = fx + rank * stride, *rfy = fy + rank * stride;
    long pairs = (n + 1) / 2;
    memset(rfx, 0, n * sizeof *rfx);
    memset(rfy, 0, n * sizeof *rfy);
    for (long p = pairs * rank / nthreads; p < pairs * (rank + 1) / nthreads; p++) {
        corner(p, rfx, rfy);
        if (n - 1 - p != p)
            corner(n - 1 - p, rfx, rfy);
    }
}

static void update(long first, long last, double h) {
    int rows = mode == MODE_LOCAL ? nthreads : 1;
    for (long i = first; i < last; i++) {
        double sx = 0.0, sy = 0.0;
        for (int t = 0; t < rows; t++) {
            sx += fx[t * stride + i];
            sy += fy[t * stride + i];
        }
        x[i] += vx[i] * h;
        y[i] += vy[i] * h;
        vx[i] += sx / m[i] * h;
        vy[i] += sy / m[i] * h;
    }
}

static void write_frame(double t) {
    double start, finish;
    GET_TIME(start);
    fprintf(out, "%.12g", t);
    for (long i = 0; i < n; i++)
        fprintf(out, ",%.12g,%.12g", x[i], y[i]);
    fputc('\n', out);
    GET_TIME(finish);
    write_time += finish - start;
}

static void *worker(void *arg) {
    long rank = (long)arg;
    long first = n * rank / nthreads, last = n * (rank + 1) / nthreads;
    for (long k = 1; k <= nsteps; k++) {
        double t_prev = (k - 1) * dt, t = k == nsteps ? t_end : k * dt;
        if (mode == MODE_LOCAL)
            forces_local(rank);
        else
            forces_naive(first, last);
        pthread_barrier_wait(&barrier);
        update(first, last, t - t_prev);
        pthread_barrier_wait(&barrier);
        if (rank == 0 && out && (k % every == 0 || k == nsteps))
            write_frame(t);
    }
    return NULL;
}

static void usage(const char *prog) {
    fprintf(stderr,
            "usage: %s t_end input.txt [-t nthreads] [-d dt] [-m naive|local]\n"
            "       [-e eps] [-k every] [-o out.csv] [-n]\n",
            prog);
    exit(1);
}

int main(int argc, char *argv[]) {
    const char *out_path = "nbody.csv";
    const char *mode_name = "local";
    double eps = 0.0;
    int opt;

    nthreads = (int)sysconf(_SC_NPROCESSORS_ONLN);
    while ((opt = getopt(argc, argv, "t:d:m:e:k:o:n")) != -1) {
        switch (opt) {
        case 't': nthreads = atoi(optarg); break;
        case 'd': dt = atof(optarg); break;
        case 'm': mode_name = optarg; break;
        case 'e': eps = atof(optarg); break;
        case 'k': every = atol(optarg); break;
        case 'o': out_path = optarg; break;
        case 'n': out_path = NULL; break;
        default: usage(argv[0]);
        }
    }
    if (argc - optind != 2)
        usage(argv[0]);
    t_end = atof(argv[optind]);
    if (strcmp(mode_name, "naive") == 0)
        mode = MODE_NAIVE;
    else if (strcmp(mode_name, "local") != 0)
        usage(argv[0]);
    if (dt <= 0.0)
        dt = t_end > 0.0 ? t_end / 1000.0 : 1.0;
    if (nthreads < 1 || t_end < 0.0 || every < 1 || eps < 0.0)
        usage(argv[0]);
    eps2 = eps * eps;
    nsteps = (long)ceil(t_end / dt - 1e-9);

    if (read_input(argv[optind + 1]) != 0)
        return 1;
    stride = (n + 7) & ~7L;
    size_t rows = mode == MODE_LOCAL ? (size_t)nthreads : 1;
    fx = aligned_alloc(64, rows * stride * sizeof *fx);
    fy = aligned_alloc(64, rows * stride * sizeof *fy);
    if (!fx || !fy) {
        perror("aligned_alloc");
        return 1;
    }

    if (out_path) {
        out = fopen(out_path, "w");
        if (!out) {
            perror(out_path);
            return 1;
        }
        setvbuf(out, NULL, _IOFBF, 1 << 20);
        fputc('t', out);
        for (long i = 1; i <= n; i++)
            fprintf(out, ",x%ld,y%ld", i, i);
        fputc('\n', out);
        write_frame(0.0);
    }

    pthread_t *threads = malloc(nthreads * sizeof *threads);
    pthread_barrier_init(&barrier, NULL, nthreads);
    double start, finish;
    GET_TIME(start);
    for (long t = 0; t < nthreads; t++)
        pthread_create(&threads[t], NULL, worker, (void *)t);
    for (long t = 0; t < nthreads; t++)
        pthread_join(threads[t], NULL);
    GET_TIME(finish);

    double compute = finish - start - (out ? write_time : 0.0);
    if (out && fclose(out) != 0) {
        perror(out_path);
        return 1;
    }
    printf("mode=%s threads=%d n=%ld steps=%ld compute=%.6f write=%.6f\n",
           mode_name, nthreads, n, nsteps, compute, write_time);

    pthread_barrier_destroy(&barrier);
    free(threads);
    free(fx);
    free(fy);
    free(m);
    return 0;
}
