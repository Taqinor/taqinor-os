import statistics
from sim import *
from run_pace import SEEDS
P = ((0, 'POUSSER'),)
cands = [('as written', Rules()), ('median+1', Rules(pousser_median_plus1=True)),
         ('median+1, rise<=1/14d', Rules(pousser_median_plus1=True, rise_every=14)),
         ('median+1, rise<=1/7d', Rules(pousser_median_plus1=True, rise_every=7)),
         ('as written + floor1', Rules(target_floor=1)),
         ('median+1 rise14 floor1', Rules(pousser_median_plus1=True, rise_every=14, target_floor=1))]
print("learner (can grow): final habit, days to +1 (habit>=5.5), done last block, success; anchored offsets d119 target; steady success; burst maxDown")
for lab, ru in cands:
    hs = []; reach = []; last = []; succ = []
    for sd in SEEDS:
        rows, al = simulate(learner(c=0.6), 112, sd, ru, P)
        hs.append(rows[-1]['K']); reach.append(next((r['i'] for r in rows if r['K'] >= 5.5), None))
        last.append(statistics.mean(r['nb'] for r in rows[98:] if r['working']))
        succ.append(statistics.mean(r['succ'] for r in rows if r['working']))
    ok = [x for x in reach if x is not None]
    anc = {}
    for off in (-0.7, 0.0, 0.3):
        anc[off] = statistics.mean(simulate(anchored(off), 120, sd, ru, P)[0][119]['T'] for sd in SEEDS)
    stsucc = statistics.mean(summary(*simulate(steady(c=0.5), 90, sd, ru, P), '')['succ'] for sd in SEEDS)
    bm = min(summary(*simulate(burst_crash(), 90, sd, ru, P), '')['maxDown'] for sd in SEEDS)
    print(f"{lab:26s} habit {statistics.mean(hs):.2f} | +1 reached d{statistics.mean(ok):.0f} ({len(ok)}/30) | done wk16 {statistics.mean(last):.2f} | learner succ {100*statistics.mean(succ):.0f}% | anchored T119: -0.7={anc[-0.7]:.1f} 0={anc[0.0]:.1f} +0.3={anc[0.3]:.1f} | steady succ {stsucc:.0f}% | burst maxDown {bm}")
