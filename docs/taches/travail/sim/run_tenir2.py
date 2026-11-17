import statistics
from collections import Counter
from sim import *
from run_pace import SEEDS
T = ((0, 'TENIR'),)
variants = [
 ('A as written (median9 / med5, +-1)', Rules()),
 ('B mean10, freeze>=9d', Rules(tenir_mean10=True, tenir_min_days=9, tenir_win=10)),
 ('C B + unrounded R', Rules(tenir_mean10=True, tenir_min_days=9, tenir_win=10, tenir_real=True)),
 ('D mean14 + unrounded R', Rules(tenir_mean10=True, tenir_min_days=9, tenir_win=14, tenir_real=True)),
]
print("false alarms: steady sd1.2 / sd2.0, TENIR from day 0, 90 d, 30 seeds (alerts mean ; seeds with >=1)")
for lab, ru in variants:
    out = []
    for sdv in (1.2, 2.0):
        n = [len(simulate(steady(c=0, sd=sdv), 90, sd, ru, T)[1]) for sd in SEEDS]
        out.append("sd%.1f: %.2f ; %d/30" % (sdv, statistics.mean(n), sum(x > 0 for x in n)))
    print(f"  {lab:36s}", ' | '.join(out))
print("detection: TENIR from day 28 (R from history), shift at working-day 25 (~day 35); first alert delay (cal. days) and alerts in the remaining ~85 d with 'garder' (cooldown 7) ")
for lab, ru in variants:
    out = []
    for h2 in (3.0, 8.0):
        lats = []; nal = []
        for sd in SEEDS:
            rows, al = simulate(shift_user(5.0, h2, 25), 120, sd, ru, ((0, 'POUSSER'), (28, 'TENIR')))
            sday = [r['i'] for r in rows if r['working']][25]
            a = [x for x in al if x[0] >= sday]
            lats.append(a[0][0] - sday if a else None); nal.append(len(a))
        ok = [x for x in lats if x is not None]
        out.append("5->%d: delay %.1f (%d/30 found), alerts %.1f" % (h2, statistics.mean(ok) if ok else -1, len(ok), statistics.mean(nal)))
    print(f"  {lab:36s}", ' | '.join(out))
print("  cooldown 28 (after 'garder'), variant D, 5->3 and 5->8:")
for h2 in (3.0, 8.0):
    nal = [len([x for x in simulate(shift_user(5.0, h2, 25), 120, sd, variants[3][1], ((0, 'POUSSER'), (28, 'TENIR')), alert_cooldown=28)[1]]) for sd in SEEDS]
    print(f"    5->{h2}: alerts over ~85 d: {statistics.mean(nal):.1f}")
print("burst-crash TENIR (switch day 28): R values, alerts in 62 d")
for lab, ru in variants:
    Rv = []; nal = []
    for sd in SEEDS:
        rows, al = simulate(burst_crash(), 90, sd, ru, ((0, 'POUSSER'), (28, 'TENIR')))
        Rv.append(rows[40]['T']); nal.append(len(al))
    print(f"  {lab:36s} R {sorted(Counter(Rv).items())}  alerts {statistics.mean(nal):.1f}")
print("collapse in TENIR (R from first 5 vs 9 days) alerts; steady->collapse d30-44 -> recovery; TENIR from day 0")
for lab, ru in variants:
    nal = []
    for sd in SEEDS:
        rows, al = simulate(collapse(), 110, sd, ru, T)
        nal.append(len(al))
    print(f"  {lab:36s} alerts/110d {statistics.mean(nal):.1f}")
