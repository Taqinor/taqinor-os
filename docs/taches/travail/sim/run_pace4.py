import statistics
from collections import Counter
from sim import *
from run_pace import SEEDS
P = ((0, 'POUSSER'),)
Tn = ((0, 'TENIR'),)

print("### anchoring feedback: user does ~ target+offset (sd .8, capacity 9), 120 d, 30 seeds; target at d30/60/90/119 (mean)")
for off in (-0.7, -0.3, 0.0, 0.3):
    for lab, ru in [('as written', Rules()), ('median+1', Rules(pousser_median_plus1=True))]:
        pts = {30: [], 60: [], 90: [], 119: []}
        for sd in SEEDS:
            rows, al = simulate(anchored(off), 120, sd, ru, P)
            for k in pts:
                pts[k].append(rows[k]['T'])
        print(f"  offset {off:+.1f} {lab:11s}: T d30 {statistics.mean(pts[30]):.1f}  d60 {statistics.mean(pts[60]):.1f}  d90 {statistics.mean(pts[90]):.1f}  d119 {statistics.mean(pts[119]):.1f}")

print("\n### POUSSER window size: 9 (as written) vs 14, 30 seeds")
for nw in (9, 14):
    ru = Rules(n_win=nw)
    bu = [summary(*simulate(burst_crash(), 90, sd, ru, P), '') for sd in SEEDS]
    st = [summary(*simulate(steady(c=0.5), 90, sd, ru, P), '') for sd in SEEDS]
    lag = []
    for sd in SEEDS:
        rows, al = simulate(shift_user(5.0, 8.0, 20, sd=0.5), 90, sd, ru, P)
        sday = [r['i'] for r in rows if r['working']][20]
        lag.append(next((r['i'] - sday for r in rows if r['i'] >= sday and r['T'] >= 8), 99))
    print(f"  n={nw}: burst maxDown {min(x['maxDown'] for x in bu)} meanT {statistics.mean(x['meanT'] for x in bu):.2f} succ {statistics.mean(x['succ'] for x in bu):.0f}% | steady succ {statistics.mean(x['succ'] for x in st):.0f}% | 5->8 tracking lag {statistics.mean(lag):.1f} d")

print("\n### gamer that declares micro tasks at 12 min (escapes the <=10 min test), POUSSER 120d")
for lab, ru in [('as written', Rules()), ('small_ratio', Rules(small_ratio=True))]:
    ss = [simulate(gamer('micro12'), 120, sd, ru, P)[0] for sd in SEEDS]
    print(f"  {lab:12s} endT {statistics.mean(r[-1]['T'] for r in ss):.1f}  success {100*statistics.mean(statistics.mean(x['succ'] for x in r if x['working']) for r in ss):.0f}%")

print("\n### g. cold start (3/day user, and enthusiastic first 3 days at 8 then 3/day), working days only")
for lab, pf in [('steady 3/day', lambda: cold_user(3.0)), ('enthusiastic 8,8,8 then 3', lambda: cold_user(3.0, enthusiastic=3))]:
    for mn in ('POUSSER', 'TENIR'):
        rows, al = simulate(pf(), 21, 4, Rules(), ((0, mn),))
        w = [r for r in rows if r['working']][:14]
        print(f"  {lab:26s} {mn:8s} T : {' '.join(str(r['T']) for r in w)}")
        print(f"  {'':26s} {'':8s} nb: {' '.join(str(r['nb']) for r in w)}  src: {''.join(r['src'][0] for r in w)}")
    for mn in ('POUSSER', 'TENIR'):
        succ = []
        defaults = []
        for sd in SEEDS:
            rows, al = simulate(pf(), 21, sd, Rules(), ((0, mn),))
            w = [r for r in rows if r['working']][:14]
            succ.append(statistics.mean(r['succ'] for r in w))
            defaults.append(sum(r['src'] == 'defaut' for r in w))
        print(f"  {lab:26s} {mn:8s} 30 seeds: success first 14 wd {100*statistics.mean(succ):.0f}% ; days shown as valeur par defaut {statistics.mean(defaults):.1f}")
rows, al = simulate(cold_user(3.0, enthusiastic=3), 40, 4, Rules(), ((0, 'POUSSER'),))
print("  enthusiastic start: first 25 working days T :", ' '.join(str(r['T']) for r in [r for r in rows if r['working']][:25]))
Rv = []
for sd in SEEDS:
    rows, al = simulate(cold_user(3.0), 30, sd, Rules(), Tn)
    Rv.append(next((r['T'] for r in rows if r['src'] == 'calcule'), None))
print("  steady 3/day, TENIR: R frozen at first computable day (5 days of data):", sorted(Counter(Rv).items()))

print("\n### h. ceiling (real max K), POUSSER, 30 seeds, 90 d")
for K in (5, 6, 7):
    ss = [simulate(ceiling_user(K=K, h=K - 1 if K > 5 else 5), 90, sd, Rules(), P)[0] for sd in SEEDS]
    frac_above = statistics.mean(statistics.mean(r['T'] > K for r in rows if r['working']) for rows in ss)
    succ = statistics.mean(statistics.mean(r['succ'] for r in rows if r['working']) for rows in ss)
    mT = statistics.mean(statistics.mean(r['T'] for r in rows if r['working']) for rows in ss)
    mN = statistics.mean(statistics.mean(r['nb'] for r in rows if r['working']) for rows in ss)
    print(f"  K={K}: mean target {mT:.2f}, mean done {mN:.2f}, days target>K {100*frac_above:.0f}%, success {100*succ:.0f}%, max target {max(r['T'] for rows in ss for r in rows)}")


def lucky():
    base = ceiling_user(K=6)

    def f(ctx):
        o = base(ctx)
        if ctx['working'] and ctx['i'] % 20 == 7:
            o['nb'] = 9
        return o
    return f


ss = [simulate(lucky(), 90, sd, Rules(), P)[0] for sd in SEEDS]
print("  ceiling K=6 with a lucky 9-task day every 20 d: days target > 6:",
      round(100 * statistics.mean(statistics.mean(r['T'] > 6 for r in rows if r['working']) for rows in ss)), "%  max target", max(r['T'] for rows in ss for r in rows))

print("\n### i. switcher: POUSSER d0-29, TENIR d30-59, POUSSER d60-89")
for lab, pf in [('steady c=0.5', lambda: steady(c=0.5)), ('learner c=0.6', lambda: learner(c=0.6))]:
    rows, al = simulate(pf(), 90, 2, Rules(), ((0, 'POUSSER'), (30, 'TENIR'), (60, 'POUSSER')))
    print(f"  {lab}: T d24-36: {series(rows,24,37,'T')} | d54-66: {series(rows,54,67,'T')} | R={rows[30]['T']}")
    for md, a, b in (('POUSSER', 0, 30), ('TENIR', 30, 60), ('POUSSER2', 60, 90)):
        seg = [r for r in rows[a:b] if r['working']]
        print(f"     {md:9s} meanT {statistics.mean(r['T'] for r in seg):.2f} meanDone {statistics.mean(r['nb'] for r in seg):.2f} success {100*statistics.mean(r['succ'] for r in seg):.0f}%")
    print("     alerts:", al)
Rs = []
bests = []
for sd in SEEDS:
    rows, al = simulate(learner(c=0.6), 90, sd, Rules(), ((0, 'POUSSER'), (60, 'TENIR')))
    Rs.append(rows[60]['T'])
    bests.append(statistics.mean(r['nb'] for r in rows[0:20] if r['working']))
print(f"  learner: R frozen at switch (d60) = {statistics.mean(Rs):.1f} vs mean done in first 20 d {statistics.mean(bests):.1f}")
