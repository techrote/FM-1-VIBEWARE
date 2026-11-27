/* SPDX-License-Identifier: MIT */
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
uint64_t __udivdi3(uint64_t,uint64_t);
uint64_t __umoddi3(uint64_t,uint64_t);
int64_t __divdi3(int64_t,int64_t);
int64_t __moddi3(int64_t,int64_t);
int main(void) {
    uint64_t rng=0x8b9e725fd35433a1ull;
    for(unsigned n=0;n<20000;n++) {
        rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;uint64_t a=rng;
        rng^=rng<<13;rng^=rng>>7;rng^=rng<<17;uint64_t b=rng|1;
        assert(__udivdi3(a,b)==a/b && __umoddi3(a,b)==a%b);
        int64_t sa=(int64_t)(a>>1),sb=(int64_t)((b>>1)|1);
        if(n&1)sa=-sa;
        if(n&2)sb=-sb;
        assert(__divdi3(sa,sb)==sa/sb && __moddi3(sa,sb)==sa%sb);
    }
    for(int64_t a=-1000000;a<=1000000;a+=7919)
        assert(__divdi3(a*24000,24000+(a<0?-a:a))==a*24000/(24000+(a<0?-a:a)));
    puts("original freestanding 64-bit arithmetic: 20000 randomized divisions/moduli PASS");
}
