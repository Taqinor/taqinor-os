import sys, statistics
from sim import *

SEEDS = range(1, 31)


def agg(persona_f, days=90, schedule=(('0', 'POUSSER'),), rules=None, label='', hol=HOL):
    sch = tuple((int(a), b) for a, b in schedule)
    ss = []
    al = []
    for sd in SEEDS:
        rows, alerts = simulate(persona_f(), days, sd, rules, sch, hol)
        s = summary(rows, alerts, label)
        ss.append(s)
    m = lambda k: round(statistics.mean(x[k] for x in ss), 2)
    out = dict(label=label)
    for k in ('meanT', 'meanNb', 'succ', 'cnt', 'alerts', 'zero_excl', 'realmin'):
        out[k] = m(k)
    out['maxUp'] = max(x['maxUp'] for x in ss)
    out['maxDown'] = min(x['maxDown'] for x in ss)
    out['minT'] = min(x['minT'] for x in ss)
    out['maxT'] = max(x['maxT'] for x in ss)
    out['endT'] = m('endT')
    return out


def line(o):
    return fmt(o)


if __name__ == '__main__':
    P = (('0', 'POUSSER'),)
    T = (('0', 'TENIR'),)
    F = (('0', 'FIXE'),)
    print("### Multi-seed (30 seeds) means; maxUp/maxDown = extreme over seeds; 90 days")
    for nm, pf in [
        ('a steady c=0 (ignores target)', lambda: steady(c=0.0)),
        ('a steady c=0.5 (responsive)', lambda: steady(c=0.5)),
        ('c burst-crash', lambda: burst_crash()),
        ('h ceiling K=6', lambda: ceiling_user()),
    ]:
        for mn, sc in [('POUSSER', P), ('TENIR', T), ('FIXE5', F)]:
            print(line(agg(pf, 90, sc, label=f'{nm} {mn}')))
        print()
    # one detailed seed
    print("### seed-1 target series, steady c=0.5 POUSSER, working days only")
    rows, al = simulate(steady(c=0.5), 90, 1, Rules(), ((0, 'POUSSER'),))
    print('T :', ' '.join(str(r['T']) for r in rows if r['working']))
    print('nb:', ' '.join(str(r['nb']) for r in rows if r['working']))
    print("\n### burst-crash seed 1 POUSSER: T/nb per working day")
    rows, al = simulate(burst_crash(), 60, 1, Rules(), ((0, 'POUSSER'),))
    print('T :', ' '.join(str(r['T']) for r in rows if r['working']))
    print('nb:', ' '.join(str(r['nb']) for r in rows if r['working']))
    print("\n### burst-crash TENIR: R by switch day (phase dependence of R=median9)")
    Rs = {}
    for sw in range(14, 21):
        rows, al = simulate(burst_crash(), 40, 1, Rules(), ((0, 'POUSSER'), (sw, 'TENIR')))
        Rs[sw] = rows[sw]['T']
    print(Rs)
