import statistics
from sim import *
from run_pace import SEEDS
P = ((0, 'POUSSER'),)
SW = ((0, 'POUSSER'), (30, 'TENIR'), (60, 'POUSSER'))

AW = Rules()
REC = Rules(target_floor=1, weekend_floor=True, small_ratio=True, imp_min_est=15, max_drop=2)
RECP = Rules(target_floor=1, weekend_floor=True, small_ratio=True, imp_min_est=15, max_drop=2, pousser_median_plus1=True)
rules = [('as written', AW), ('RECOMMENDED (floor1, weekend_floor, small_ratio, imp>=15min, max_drop=2)', REC), ('REC + median+1 (ambition option)', RECP)]


def block(lab, pf, days=90, sched=P):
    print(f"-- {lab}")
    for rl, ru in rules:
        ss = [summary(*simulate(pf(), days, sd, ru, sched), '') for sd in SEEDS]
        print(f"   {rl[:44]:44s} meanT {statistics.mean(x['meanT'] for x in ss):5.2f} meanDone {statistics.mean(x['meanNb'] for x in ss):5.2f} success {statistics.mean(x['succ'] for x in ss):3.0f}% maxUp {max(x['maxUp'] for x in ss):+d} maxDown {min(x['maxDown'] for x in ss):+d} minT {min(x['minT'] for x in ss)} maxT {max(x['maxT'] for x in ss)}")


block('a steady c=0.5', lambda: steady(c=0.5))
block('c burst-crash', lambda: burst_crash())
block('f collapse (d30-43)', lambda: collapse(), 110)
block('anchored offset -0.7 (120d)', lambda: anchored(-0.7), 120)
block('anchored offset 0.0 (120d)', lambda: anchored(0.0), 120)
block('learner c=0.6 (112d)', lambda: learner(c=0.6), 112)
block('h ceiling K=6', lambda: ceiling_user())
block('d gamer cheapest_real (120d)', lambda: gamer('cheapest_real'), 120)
block('d gamer microflag (120d)', lambda: gamer('microflag'), 120)
block('e interrupted (vac declared)', lambda: interrupted())

print("\n-- weekend asymmetry: Monday target, never works weekend vs works Saturday (2 tasks)")
for rl, ru in rules:
    a, b = [], []
    for sd in SEEDS:
        for sat_p, store in ((0.0, a), (1.0, b)):
            rows, al = simulate(interrupted(vac=(0, 0), sat_p=sat_p, sun_p=0.0), 70, sd, ru, P)
            store.append(statistics.mean(r['T'] for r in rows[20:] if r['wd'] == 0 and r['working']))
    print(f"   {rl[:44]:44s} no-weekend {statistics.mean(a):.2f}  Saturday-worked {statistics.mean(b):.2f}  diff {statistics.mean(b)-statistics.mean(a):+.2f}")

print("\n-- switcher (30 seeds): per-phase mean target / mean done / success")
for lab, pf in [('steady c=0.5', lambda: steady(c=0.5))]:
    for md, a, b in (('POUSSER', 0, 30), ('TENIR', 30, 60), ('POUSSER2', 60, 90)):
        accT, accN, accS = [], [], []
        for sd in SEEDS:
            rows, al = simulate(pf(), 90, sd, AW, SW)
            seg = [r for r in rows[a:b] if r['working']]
            accT.append(statistics.mean(r['T'] for r in seg)); accN.append(statistics.mean(r['nb'] for r in seg)); accS.append(statistics.mean(r['succ'] for r in seg))
        print(f"   {md:9s} meanT {statistics.mean(accT):.2f} meanDone {statistics.mean(accN):.2f} success {100*statistics.mean(accS):.0f}%")
rs = []
for sd in SEEDS:
    rows, al = simulate(steady(c=0.5), 90, sd, AW, SW)
    rs.append((rows[30]['T'], rows[29]['T'], rows[60]['T']))
print("   R at switch vs last POUSSER target vs first POUSSER2 target (means):", [round(statistics.mean(x[k] for x in rs), 2) for k in range(3)])

print("\n-- TENIR recommended (mean14, unrounded, freeze>=14 d) vs written: steady false alarms + burst + enthusiastic onboarding")
TR = Rules(tenir_mean10=True, tenir_win=14, tenir_real=True, tenir_min_days=14)
for lab, ru in (('as written', AW), ('mean14/unrounded/freeze14', TR)):
    fa = statistics.mean(len(simulate(steady(c=0, sd=1.2), 90, sd, ru, ((0, 'TENIR'),))[1]) for sd in SEEDS)
    fa2 = statistics.mean(len(simulate(steady(c=0, sd=2.0), 90, sd, ru, ((0, 'TENIR'),))[1]) for sd in SEEDS)
    bu = statistics.mean(len(simulate(burst_crash(), 90, sd, ru, ((0, 'TENIR'),))[1]) for sd in SEEDS)
    en = statistics.mean(len(simulate(cold_user(3.0, enthusiastic=3), 90, sd, ru, ((0, 'TENIR'),))[1]) for sd in SEEDS)
    Rn = statistics.mean(simulate(cold_user(3.0, enthusiastic=3), 40, sd, ru, ((0, 'TENIR'),))[0][30]['T'] for sd in SEEDS)
    print(f"   {lab:28s} false alarms steady sd1.2: {fa:.2f}/90d, sd2.0: {fa2:.2f}/90d | burst-crash alerts {bu:.1f}/90d | onboarding-burst user (true 3/day): alerts {en:.1f}/90d, R at d30 = {Rn:.1f}")
