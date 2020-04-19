#define __LEAF, __leaf__
#define __THROW __attribute__((__nothrow__ __LEAF))
# define __nonnull(params) __attribute__ ((__nonnull__ params))

extern void *foo(void* __restrict p1, const void* __restrict p2,
                 int p3, unsigned p4)
     __THROW __nonnull ((1, 2));
