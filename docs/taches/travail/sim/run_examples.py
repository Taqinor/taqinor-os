import math, statistics, itertools
from fractions import Fraction
from engine import *

print("== worked examples ==")
c = [2, 3, 4, 4, 5, 6, 6, 7, 8]
p = percentile_lineaire(c, 0.6)
print("P60", p, "ceil", math.ceil(p), "median", statistics.median(c), "max", max(c),
      "-> cible", cible_pousser(c, 5, Rules()))
R = 5
print("TENIR band R=5:", bande_tenir(5), " derive [3,2,4,3,5]:", derive_tenir(5, [3, 2, 4, 3, 5]),
      "median", statistics.median([3, 2, 4, 3, 5]))
mins = [220, 250, 255, 260, 270, 280, 300, 310, 340]
print("budget median:", statistics.median(mins))
est = dict(T1=15, T4=10, T5=120, T2=90 * 1.5, T3=60)
budget = 270
tot = 0
plan = []
for t in ['T5', 'T1', 'T4', 'T2', 'T3']:
    if len(plan) >= 5:
        break
    if tot + est[t] > budget * 1.10:
        print("skip", t, tot + est[t], ">", budget * 1.10)
        continue
    tot += est[t]
    plan.append(t)
    print("add", t, "->", tot)
print("plan", plan, tot, "min = %dh%02d" % divmod(int(tot), 60), "budget %dh%02d" % divmod(budget, 60))
print("90*1.5 =", 90 * 1.5, "= %dh%02d" % divmod(int(90 * 1.5), 60))

print("\n== float ceil(P60) vs exact rational (all windows of n=5..9 over values 0..4 and a few 0..12) ==")
bad = 0
tot_ = 0
for n in range(5, 10):
    for vals in itertools.product(range(0, 5), repeat=n):
        s = sorted(vals)
        if list(vals) != s:
            continue  # sorted multisets only
        tot_ += 1
        pos = Fraction(3, 5) * (n - 1)
        lo = pos.numerator // pos.denominator
        hi = min(lo + 1, n - 1)
        ex = s[lo] + (pos - lo) * (s[hi] - s[lo])
        exact = math.ceil(ex)
        fl = math.ceil(percentile_lineaire(list(vals), 0.6))
        if exact != fl:
            bad += 1
            if bad <= 5:
                print("MISMATCH", vals, float(ex), exact, fl)
print("multisets checked", tot_, "mismatches", bad)

print("\n== bande_tenir b for R=1..20 (python round = banker's) ==")
for R in range(1, 21):
    lo, hi = bande_tenir(R)
    exact_half = (0.2 * R) % 1
    print(R, (lo, hi), "b=%d" % (hi - R), "rel=%.0f%%" % (100 * (hi - R) / R), end=' | ')
print()
print("\n== P60 vs median gap on integer data (how much does ceil(P60) exceed the median?) ==")
import random
rng = random.Random(3)
gaps = []
for _ in range(20000):
    w = [max(0, round(rng.gauss(5, 1.2))) for _ in range(9)]
    gaps.append(math.ceil(percentile_lineaire(w, .6)) - statistics.median(w))
print("steady 5±1.2, window 9: mean(ceil(P60)-median)=%.2f ; share>=+1: %.0f%% ; share 0: %.0f%%" % (
    statistics.mean(gaps), 100 * sum(g >= 1 for g in gaps) / len(gaps), 100 * sum(g == 0 for g in gaps) / len(gaps)))
