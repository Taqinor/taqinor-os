import random, statistics, math
from rythme import *
from collections import Counter
rng=random.Random(1)
for mu,sd in ((5,1.2),(3,1.0),(8,1.5),(5,2.0),(2,1.0)):
    c=Counter(); 
    N=20000
    for _ in range(N):
        cs=[max(0,arrondi(rng.gauss(mu,sd))) for _ in range(10)]
        c[journee_type(cs)]+=1
    m=sum(k*v for k,v in c.items())/N
    print(f"vrai {mu}+-{sd}: journee type moyenne {m:.2f} ; distribution", {k:round(v/N,2) for k,v in sorted(c.items())})
# variante arrondi (round) au lieu de plancher
for mu,sd in ((5,1.2),(3,1.0)):
    t=[];
    for _ in range(20000):
        cs=[max(0,arrondi(rng.gauss(mu,sd))) for _ in range(10)]
        t.append(max(1,arrondi(min(statistics.median(cs),statistics.mean(cs)))))
    print("variante round:",mu,sd,round(statistics.mean(t),2))
# bursts
t=Counter()
for s in range(2000):
    r=random.Random(s)
    cs=[]
    for blk in range(2):
        hi=r.random()<0.5
        cs+= [r.choice([9,10]) if hi else r.choice([1,2]) for _ in range(5)]
    t[journee_type(cs)]+=1
print("rafales type", sorted(t.items()))
