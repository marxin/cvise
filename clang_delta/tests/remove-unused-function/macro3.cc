# define BEGIN_NAMESPACE_STD namespace std {
# define END_NAMESPACE_STD }
# define __THROW throw ()
# define __nonnull(params)

BEGIN_NAMESPACE_STD
extern void *foo(void *__restrict p1,
                 unsigned p2) __THROW __nonnull ((1, 2));
END_NAMESPACE_STD
