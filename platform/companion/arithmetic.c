/* SPDX-License-Identifier: MIT
 * Freestanding compiler ABI helpers for the original Xeno engine's signed
 * 64-bit divisions. Fixed 64 iterations; no allocator, floating point or I/O.
 * Compiler builtins libraries vary between pi32v2 distributions. */
#include <stdint.h>
static uint64_t divide(uint64_t a,uint64_t b,uint64_t *remainder) {
    uint64_t q=0,r=0;
    if(!b){*remainder=a;return 0;}
    for(unsigned i=0;i<64;i++) {
        unsigned carry=(unsigned)(r>>63);
        r=(r<<1)|(a>>63);a<<=1;q<<=1;
        if(carry||r>=b){r-=b;q|=1;}
    }
    *remainder=r;return q;
}
uint64_t __udivdi3(uint64_t a,uint64_t b) {uint64_t r;return divide(a,b,&r);}
uint64_t __umoddi3(uint64_t a,uint64_t b) {uint64_t r;divide(a,b,&r);return r;}
int64_t __divdi3(int64_t a,int64_t b) {
    uint64_t r,ua=(uint64_t)a,ub=(uint64_t)b;
    if(a<0)ua=0u-ua;
    if(b<0)ub=0u-ub;
    uint64_t q=divide(ua,ub,&r);if((a<0)!=(b<0))q=0u-q;return (int64_t)q;
}
int64_t __moddi3(int64_t a,int64_t b) {
    uint64_t r,ua=(uint64_t)a,ub=(uint64_t)b;
    if(a<0)ua=0u-ua;
    if(b<0)ub=0u-ub;
    divide(ua,ub,&r);if(a<0)r=0u-r;return (int64_t)r;
}
