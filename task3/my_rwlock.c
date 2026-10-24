#include "my_rwlock.h"

int my_rwlock_init(my_rwlock_t *lock, const void *attr) {
    (void)attr;
    pthread_mutex_init(&lock->mutex, NULL);
    pthread_cond_init(&lock->readers_ok, NULL);
    pthread_cond_init(&lock->writers_ok, NULL);
    lock->readers = lock->readers_waiting = lock->writers_waiting = lock->writer = 0;
    return 0;
}

int my_rwlock_destroy(my_rwlock_t *lock) {
    pthread_mutex_destroy(&lock->mutex);
    pthread_cond_destroy(&lock->readers_ok);
    pthread_cond_destroy(&lock->writers_ok);
    return 0;
}

int my_rwlock_rdlock(my_rwlock_t *lock) {
    pthread_mutex_lock(&lock->mutex);
    lock->readers_waiting++;
    while (lock->writer || lock->writers_waiting > 0)
        pthread_cond_wait(&lock->readers_ok, &lock->mutex);
    lock->readers_waiting--;
    lock->readers++;
    pthread_mutex_unlock(&lock->mutex);
    return 0;
}

int my_rwlock_wrlock(my_rwlock_t *lock) {
    pthread_mutex_lock(&lock->mutex);
    lock->writers_waiting++;
    while (lock->writer || lock->readers > 0)
        pthread_cond_wait(&lock->writers_ok, &lock->mutex);
    lock->writers_waiting--;
    lock->writer = 1;
    pthread_mutex_unlock(&lock->mutex);
    return 0;
}

int my_rwlock_unlock(my_rwlock_t *lock) {
    pthread_mutex_lock(&lock->mutex);
    if (lock->writer)
        lock->writer = 0;
    else
        lock->readers--;
    if (lock->writers_waiting > 0) {
        if (lock->readers == 0)
            pthread_cond_signal(&lock->writers_ok);
    } else if (lock->readers_waiting > 0) {
        pthread_cond_broadcast(&lock->readers_ok);
    }
    pthread_mutex_unlock(&lock->mutex);
    return 0;
}
