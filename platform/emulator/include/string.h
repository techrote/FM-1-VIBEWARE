/* Private freestanding declaration shim for the unmodified portable core.
 * Match Dinghy firmware/src/libc.c at 92f17b28, not the hosted libc ABI:
 * the pi32v2 compiler can spell size_t differently from unsigned.
 * This include directory is target-only (-fno-builtin). */
#ifndef VW_TARGET_STRING_H
#define VW_TARGET_STRING_H
#include <stddef.h>
typedef char vw_target_memset_size_fits_unsigned[
    sizeof(size_t) <= sizeof(unsigned) ? 1 : -1];
void *memset(void *, int, unsigned);
#endif
