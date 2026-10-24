#ifndef MY_RWLOCK_H
#define MY_RWLOCK_H

#include <pthread.h>

typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t readers_ok;
    pthread_cond_t writers_ok;
    int readers;
    int readers_waiting;
    int writers_waiting;
    int writer;
} my_rwlock_t;

int my_rwlock_init(my_rwlock_t *lock, const void *attr);
int my_rwlock_destroy(my_rwlock_t *lock);
int my_rwlock_rdlock(my_rwlock_t *lock);
int my_rwlock_wrlock(my_rwlock_t *lock);
int my_rwlock_unlock(my_rwlock_t *lock);

#endif
