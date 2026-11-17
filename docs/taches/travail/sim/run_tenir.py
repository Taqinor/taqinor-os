import statistics
from sim import *
from run_pace import agg, line, SEEDS
P = (('0', 'POUSSER'),); T = (('0', 'TENIR'),); F = (('0', 'FIXE'),)

print("### b2. learner (habit 4.5, +0.1 per day he meets a target above habit, c=0.6), 112 days, 30 seeds")
def run_learner(sched, rules, label, c=0.6):
    hs = []; done = []
    reach = {5.5: [], 6.5: []}
    for sd in SEEDS:
        rows, al = simulate(learner(c=c), 112, sd, rules, sched)
        hs.append(rows[-1]['K'])
        done.append([statistics.mean(r['nb'] for r in rows[b*14:(b+1)*14] if r['working']) for b in range(8)])
        for lvl in reach:
            k = next((r['i'] for r in rows if r['K'] is not None and r['K'] >= lvl), None)
            reach[lvl].append(k)
    dm = [round(statistics.mean(x[b] for x in done), 2) for b in range(8)]
    rr = {l: (round(statistics.mean(v for v in vs if v is not None), 0) if any(v is not None for v in vs) else None,
              sum(v is not None for v in vs)) for l, vs in reach.items()}
    print(f"{label:34s} final habit {statistics.mean(hs):.2f} | done/14d: {dm} | days to habit>=5.5: {rr[5.5]} , >=6.5: {rr[6.5]} (mean day, #seeds reaching)")
run_learner(P, Rules(), 'POUSSER as written')
run_learner(F, Rules(), 'FIXE 5 (no engine)')
run_learner(T, Rules(), 'TENIR')
run_learner(P, Rules(pousser_median_plus1=True), 'POUSSER median+1 floor')
run_learner(P, Rules(), 'POUSSER c=0.9', c=0.9)

print("\n### TENIR false alarms / R freeze on steady c=0 (sd 1.2), TENIR from day 0, 30 seeds, 90 days")
Rs = []
for sd in SEEDS:
    rows, al = simulate(steady(c=0), 90, sd, Rules(), T)
    Rs.append(next(r['T'] for r in rows if r['src'] == 'calcule'))
from collections import Counter
print("R frozen at first computable day (5 non-missing days), true level 5:", sorted(Counter(Rs).items()))
for lab, ru in [('as written', Rules()), ('R frozen only with >=9 days', Rules(tenir_min_days=9)),
                ('mean10 (R & drift)', Rules(tenir_mean10=True, tenir_min_days=9))]:
    n_al = []; wk = []
    for sd in SEEDS:
        rows, al = simulate(steady(c=0), 90, sd, ru, T)
        n_al.append(len(al))
    print(f"  {lab:32s} alerts/90d: mean {statistics.mean(n_al):.2f}  seeds with >=1 alert: {sum(x>0 for x in n_al)}/30")
print("  steady c=0, sd 2.0 (more variable honest user):")
for lab, ru in [('as written', Rules()), ('mean10', Rules(tenir_mean10=True, tenir_min_days=9))]:
    n_al = []
    for sd in SEEDS:
        rows, al = simulate(steady(c=0, sd=2.0), 90, sd, ru, T)
        n_al.append(len(al))
    print(f"  {lab:32s} alerts/90d: mean {statistics.mean(n_al):.2f}")

print("\n### TENIR switched ON at day 25 (R from 9 days), then behaviour shifts at working-day 20 after switch")
def lat(h2, ru, label, extra=''):
    lats = []; nal = []
    for sd in SEEDS:
        # shift at working-day 40 ~ calendar day ~56 ; TENIR from day 28
        rows, al = simulate(shift_user(5.0, h2, 40), 120, sd, ru, ((0, 'POUSSER'), (28, 'TENIR')))
        shift_day = [r['i'] for r in rows if r['working']][40]
        a = [x for x in al if x[0] >= shift_day]
        lats.append(a[0][0] - shift_day if a else None)
        nal.append(len(a))
    ok = [x for x in lats if x is not None]
    print(f"  5 -> {h2} {label:26s} first alert after shift: mean {statistics.mean(ok):.1f} cal. days (found {len(ok)}/30) ; alerts over remaining ~60 days: mean {statistics.mean(nal):.1f}")
for h2 in (3.0, 8.0):
    lat(h2, Rules(), 'as written')
    lat(h2, Rules(tenir_mean10=True, tenir_min_days=9), 'mean10')
print("  new normal 5->8, rebase on alert (user taps 'passer à X'):")
lat(8.0, Rules(tenir_rebase_on_alert=True), 'as written + rebase')
print("  Alerts if user taps 'garder' every time (cooldown 7 vs 28):")
for cd in (7, 28):
    nal = []
    for sd in SEEDS:
        rows, al = simulate(shift_user(5.0, 8.0, 10), 120, sd, Rules(), ((0, 'POUSSER'), (28, 'TENIR')), alert_cooldown=cd)
        nal.append(len(al))
    print(f"   cooldown {cd}: mean alerts in 92 days after TENIR switch (user permanently at 8, R=5): {statistics.mean(nal):.1f}")

print("\n### c. burst-crash TENIR: R and alerts, as written vs mean10 (switch day 28 after 4 weeks POUSSER)")
for lab, ru in [('as written', Rules()), ('mean10', Rules(tenir_mean10=True, tenir_min_days=9))]:
    Rv = []; nal = []
    for sd in SEEDS:
        rows, al = simulate(burst_crash(), 90, sd, ru, ((0, 'POUSSER'), (28, 'TENIR')))
        Rv.append(rows[40]['T']); nal.append(len(al))
    print(f"  {lab:12s} R distribution {sorted(Counter(Rv).items())}  alerts/62d mean {statistics.mean(nal):.1f}")
