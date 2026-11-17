import statistics
from collections import Counter
from sim import *
from run_pace import agg, line, SEEDS
P = ((0, 'POUSSER'),); Tn = ((0, 'TENIR'),); F = ((0, 'FIXE'),)
agg_P = (('0', 'POUSSER'),)

def L(pf, days, sched, ru, label):
    ss = [summary(*simulate(pf(), days, sd, ru, sched), label) for sd in SEEDS]
    return {k: statistics.mean(x[k] for x in ss) for k in ('meanT','meanNb','succ','cnt','realmin')}

print("### b. learner: pace and success, POUSSER as written vs median+1 (112 d)")
for lab, ru, sc in [('POUSSER as written', Rules(), P), ('POUSSER median+1', Rules(pousser_median_plus1=True), P), ('FIXE 5', Rules(), F)]:
    o = L(lambda: learner(c=0.6), 112, sc, ru, lab)
    print(f"  {lab:22s} meanT={o['meanT']:.2f} meanDone={o['meanNb']:.2f} success={o['succ']:.0f}% countOnly={o['cnt']:.0f}%")

print("\n### tracking lag: user steps 5->6 (and 5->8) by himself at working-day 20; days until displayed target reaches new level (POUSSER as written)")
for h2 in (6.0, 8.0):
    lag = []
    for sd in SEEDS:
        rows, al = simulate(shift_user(5.0, h2, 20, sd=0.5), 90, sd, Rules(), P)
        sday = [r['i'] for r in rows if r['working']][20]
        k = next((r['i'] - sday for r in rows if r['i'] >= sday and r['T'] >= h2), None)
        lag.append(k)
    ok = [x for x in lag if x is not None]
    print(f"  5->{int(h2)}: target reaches {int(h2)} after {statistics.mean(ok):.1f} calendar days (found {len(ok)}/30)")

print("\n### f. collapse before/after (bad fortnight d30-43; 30 seeds, 110 d, POUSSER)")
def collapse_stats(ru):
    res = []
    for sd in SEEDS:
        rows, al = simulate(collapse(), 110, sd, ru, P)
        mn = min(r['T'] for r in rows[30:60])
        rec = next((r['i'] - 44 for r in rows[44:] if r['T'] >= 5), None)
        ev = [r for r in rows[30:44] if r['working']]
        succ = statistics.mean(r['succ'] for r in rows[30:80] if r['working'])
        res.append((mn, rec, succ))
    ok = [x[1] for x in res if x[1] is not None]
    return "min T %.1f | days after recovery start to T>=5: %.1f (max %d, found %d/30) | success d30-80 %.0f%%" % (
        statistics.mean(x[0] for x in res), statistics.mean(ok), max(ok), len(ok), 100*statistics.mean(x[2] for x in res))
print("  as written          :", collapse_stats(Rules()))
print("  floor_frac28=0.6    :", collapse_stats(Rules(floor_frac28=0.6)))
print("  floor_frac28=0.75   :", collapse_stats(Rules(floor_frac28=0.75)))
print("  max_drop=1          :", collapse_stats(Rules(max_drop=1)))
print("  target_floor=2      :", collapse_stats(Rules(target_floor=2)))
print("  rise_cap=2          :", collapse_stats(Rules(rise_cap=2)))
print("  floor28 0.6+rise2   :", collapse_stats(Rules(floor_frac28=0.6, rise_cap=2)))
print("  effect of floor28 on a steady user (success/mean target):")
for ru in (Rules(), Rules(floor_frac28=0.6), Rules(floor_frac28=0.75)):
    o = L(lambda: steady(c=0.5), 90, P, ru, '')
    print(f"    {ru.floor_frac28}: meanT={o['meanT']:.2f} succ={o['succ']:.0f}%")

print("\n### burst-crash POUSSER: day-to-day jumps (30 seeds) as written vs max_drop=1, vs a 7-day-window variant not tested")
for lab, ru in [('as written', Rules()), ('max_drop=1', Rules(max_drop=1))]:
    o = [summary(*simulate(burst_crash(), 90, sd, ru, P), lab) for sd in SEEDS]
    print(f"  {lab:12s} maxDown {min(x['maxDown'] for x in o)}  maxUp {max(x['maxUp'] for x in o)}  success {statistics.mean(x['succ'] for x in o):.0f}%  meanT {statistics.mean(x['meanT'] for x in o):.2f}  meanDone {statistics.mean(x['meanNb'] for x in o):.2f}")
# correlation between target and next-day done
import math
def corr(a, b):
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x-ma)*(y-mb) for x, y in zip(a, b)); den = math.sqrt(sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))
    return num/den if den else 0
cs = []
for sd in SEEDS:
    rows, al = simulate(burst_crash(), 90, sd, Rules(), P)
    w = [r for r in rows if r['working']]
    cs.append(corr([r['T'] for r in w], [r['nb'] for r in w]))
print("  corr(target shown, done that day) burst-crash POUSSER: mean %.2f" % statistics.mean(cs))

print("\n### d. gamer before/after (POUSSER, 30 seeds, 120 d), honest = steady c=0.5 with 30% small tasks / 50% small")
def G(pf, ru, lab, days=120):
    ss = [summary(*simulate(pf(), days, sd, ru, P), lab) for sd in SEEDS]
    endT = statistics.mean(simulate(pf(), days, sd, ru, P)[0][-1]['T'] for sd in SEEDS)
    return f"{lab:34s} meanT={statistics.mean(x['meanT'] for x in ss):5.2f} endT={endT:5.1f} meanCount={statistics.mean(x['meanNb'] for x in ss):5.2f} success={statistics.mean(x['succ'] for x in ss):3.0f}% realMin={statistics.mean(x['realmin'] for x in ss):4.0f}"
rules_list = [('as written', Rules()), ('small_ratio', Rules(small_ratio=True)), ('small_ratio+imp>=15min', Rules(small_ratio=True, imp_min_est=15))]
for lab, ru in rules_list:
    print(" RULE", lab)
    for v in ('naive', 'cheapest_real', 'microflag'):
        print("   ", G(lambda v=v: gamer(v), ru, f'gamer {v}'))
    print("   ", G(lambda: steady(c=0.5, small_share=0.3), ru, 'honest small_share=30%'))
    print("   ", G(lambda: steady(c=0.5, small_share=0.5), ru, 'honest small_share=50%'))
    print("   ", G(lambda: steady(c=0.5, small_share=0.7), ru, 'honest small_share=70%'))
