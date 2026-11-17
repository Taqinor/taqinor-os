import statistics
from sim import *
from run_pace import agg, line, SEEDS

P = ((0, 'POUSSER'),)
T = ((0, 'TENIR'),)
F = ((0, 'FIXE'),)


def blocks(persona_f, sched, days=112, rules=None, block=14):
    """mean done per 14-day block, mean over seeds; also final K"""
    acc = [[] for _ in range(days // block)]
    Ks = []
    tk = [[] for _ in range(days // block)]
    for sd in SEEDS:
        pf = persona_f()
        rows, al = simulate(pf, days, sd, rules, sched)
        for b in range(days // block):
            seg = [r for r in rows[b * block:(b + 1) * block] if r['working']]
            acc[b].append(statistics.mean(r['nb'] for r in seg))
            tk[b].append(statistics.mean(r['T'] for r in seg))
    return [round(statistics.mean(a), 2) for a in acc], [round(statistics.mean(a), 2) for a in tk]


print("### b. slow grower (capacity K0=6, habit 4.5, c=0.6; K+1 per 14d only if mean(last10)>=K-1)")
for mn, sc in [('POUSSER', P), ('TENIR', T), ('FIXE5', F)]:
    d, t = blocks(slow_grower, sc, 112)
    print(f"{mn:8s} done/14d-block: {d}")
    print(f"{'':8s} target/block : {t}")
print("Variant: stronger responder c=0.9")
for mn, sc in [('POUSSER', P), ('FIXE5', F)]:
    d, t = blocks(lambda: slow_grower(c=0.9), sc, 112)
    print(f"{mn:8s} done: {d}  target: {t}")
print("Rule fix pousser_median_plus1:")
d, t = blocks(slow_grower, P, 112, Rules(pousser_median_plus1=True))
print(f"POUSSER+  done: {d}  target: {t}")

print("\n### f. collapse (bad fortnight days 30-43) POUSSER")
rows, al = simulate(collapse(), 100, 1, Rules(), ((0, 'POUSSER'),))
for a, b in [(25, 45), (45, 75)]:
    print(f"d{a}-{b} T :", series(rows, a, b, 'T'))
    print(f"d{a}-{b} nb:", series(rows, a, b, 'nb'))
    print(f"d{a}-{b} miss:", ''.join('M' if r['missing'] else '.' for r in rows[a:b]))
res = []
for sd in SEEDS:
    rows, al = simulate(collapse(), 110, sd, Rules(), ((0, 'POUSSER'),))
    pre = statistics.mean(r['T'] for r in rows[20:30] if r['working'])
    mn = min(r['T'] for r in rows[30:60])
    rec = next((r['i'] for r in rows[44:] if r['working'] and r['T'] >= 5 and r['nb'] >= 4), None)
    rec_T = next((r['i'] - 44 for r in rows[44:] if r['T'] >= 5), None)
    z = sum(1 for r in rows[30:44] if r['working'] and r['nb'] == 0 and r['missing'])
    z_all = sum(1 for r in rows[30:44] if r['working'] and r['nb'] == 0)
    res.append((pre, mn, rec_T, z, z_all))
print("collapse x30 seeds: pre-T mean %.1f | min T during/after %s (mean %.1f) | days after recovery start until T>=5 : mean %.1f max %s | zero-days excluded as missing %.1f of %.1f zero days" % (
    statistics.mean(x[0] for x in res), sorted(set(x[1] for x in res)), statistics.mean(x[1] for x in res),
    statistics.mean(x[2] for x in res if x[2] is not None), max(x[2] for x in res if x[2] is not None),
    statistics.mean(x[3] for x in res), statistics.mean(x[4] for x in res)))
print("Collapse w/ TENIR from day 0:")
rows, al = simulate(collapse(), 100, 1, Rules(), ((0, 'TENIR'),))
print("R=", rows[10]['T'], "alerts:", al)

print("\n### d. gamer (target-following splitter) vs honest, POUSSER 90d, 30 seeds")
for v in ('naive', 'cheapest_real', 'microflag'):
    print(line(agg(lambda v=v: gamer(v), 90, P, label=f'gamer {v}')))
print(line(agg(lambda: steady(c=0.5), 90, (('0','POUSSER'),), label='honest steady c=.5')))
rows, al = simulate(gamer('cheapest_real', gain=1.0), 90, 1, Rules(), ((0, 'POUSSER'),))
print("gamer gain=+1/day trend T:", series(rows, 0, 90, 'T'))
for g in (0.5, 1.0, 1.5):
    r = []
    for sd in SEEDS:
        rows, al = simulate(gamer('cheapest_real', gain=g), 120, sd, Rules(), ((0, 'POUSSER'),))
        r.append(rows[-1]['T'])
    print(f"gamer gain={g}: end-of-120d target mean {statistics.mean(r):.1f} max {max(r)}")
print("-- split detector (median est of done tasks, window 9d vs previous 9d, both n>=10) on an onset at day 30")
# honest 40-min tasks until day 30, then gamer micro tasks 8 min: estimate fires when?
est_hist = []
for i in range(60):
    est_hist.append((40, 5) if i < 30 else (8, 9))  # (median est, count)
first = None
for i in range(18, 60):
    cur = [e for e, n in est_hist[i - 8:i + 1] for _ in range(n)]
    prev = [e for e, n in est_hist[i - 17:i - 8] for _ in range(n)]
    if len(cur) >= 10 and len(prev) >= 10 and statistics.median(cur) < 0.5 * statistics.median(prev):
        first = i
        break
print("onset day 30 -> detector first fires day", first, "(only an informational line, no effect on target/success)")
gamer_from_start = [8] * 9
print("gamer from day 1: previous window is also micro -> median ratio 1.0 -> never fires")

print("\n### e. interrupted (10-day holiday d25-34, Sat 40%/Sun 15% worked, 4 public holidays)")
for decl in (True, False):
    print(line(agg(lambda decl=decl: interrupted(declared=decl), 90, P, label=f'vacation declared={decl} POUSSER')))
rows, al = simulate(interrupted(), 60, 3, Rules(), ((0, 'POUSSER'),))
print("T :", series(rows, 20, 50, 'T'))
print("nb:", series(rows, 20, 50, 'nb'))
print("miss:", ''.join('M' if r['missing'] else '.' for r in rows[20:50]))
print("-- weekend asymmetry (paired seeds): same weekday behaviour; Saturday worked (2 tasks) vs never")
for wf in (False, True):
    d_no, d_yes = [], []
    for sd in SEEDS:
        for sat_p, store in ((0.0, d_no), (1.0, d_yes)):
            rows, al = simulate(interrupted(vac=(0, 0), sat_p=sat_p, sun_p=0.0), 70, sd, Rules(weekend_floor=wf),
                                ((0, 'POUSSER'),))
            store.append(statistics.mean(r['T'] for r in rows[20:] if r['wd'] == 0 and r['working']))
    print(f"weekend_floor={wf}: mean Monday target  no-weekend-work={statistics.mean(d_no):.2f}  works-Saturday-2-tasks={statistics.mean(d_yes):.2f}")
print("-- 4-week vacation (d20-48) then back: target on return")
rows, al = simulate(interrupted(vac=(20, 48), declared=True), 70, 1, Rules(), ((0, 'POUSSER'),))
print("T d44-60:", series(rows, 44, 60, 'T'), "src:", ' '.join(r['src'][0] for r in rows[44:60]))
