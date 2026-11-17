"""Simulation harness: personas + loop. Synthetic data; properties of the RULE only."""
import random, statistics, datetime as dt
from engine import *

START = dt.date(2026, 6, 1)  # a Monday
HOL = {dt.date(2026, 7, 30), dt.date(2026, 8, 14), dt.date(2026, 8, 20), dt.date(2026, 8, 21)}


def is_working(d, hol=HOL):
    return d.weekday() < 5 and d not in hol


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def finalize(rng, nb, working, p_plan=0.85, p_imp_open=0.9, p_reserved=0.7,
             small_share=0.3, est_med=40, imp_est=40):
    plan = (rng.random() < p_plan) if working else (rng.random() < 0.1)
    imp_open = 1 if rng.random() < p_imp_open else 0
    imp = 0
    if nb > 0 and imp_open:
        if plan and rng.random() < p_reserved:
            imp = 1
        imp += sum(rng.random() < 0.08 for _ in range(max(nb - 1, 0)))
    n_small = sum(rng.random() < small_share for _ in range(nb))
    minutes = n_small * 8 + (nb - n_small) * est_med
    touched = nb > 0 or plan or rng.random() < 0.3
    return dict(nb=nb, nb_imp=imp, nb_small=n_small, minutes=minutes, real_min=minutes,
                plan=plan, touched=touched, off=False, imp_open=imp_open, imp_est=imp_est)


# ---------------------------------------------------------------- personas
def steady(h=5.0, sd=1.2, c=0.0, K=9, **kw):
    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False, **kw)
        nb = clip(round(h + c * max(ctx['T'] - h, 0) + rng.gauss(0, sd)), 0, K)
        return finalize(rng, nb, True, **kw)
    return f


def slow_grower(h=4.5, K0=6, c=0.6, sd=0.9, grow_every=14, need=1.0):
    st = dict(K=K0, hist=[], last=0)

    def f(ctx):
        rng = ctx['rng']
        ctx['state']['K'] = st['K']
        if not ctx['working']:
            return finalize(rng, 0, False)
        K = st['K']
        nb = clip(round(h + c * max(ctx['T'] - h, 0) + rng.gauss(0, sd)), 0, K)
        st['hist'].append(nb)
        if ctx['i'] - st['last'] >= grow_every and len(st['hist']) >= 10:
            if statistics.mean(st['hist'][-10:]) >= K - need:
                st['K'] += 1
                st['last'] = ctx['i']
        return finalize(rng, nb, True)
    return f


def burst_crash(hi=(9, 10), lo=(1, 2), c=0.0):
    st = dict(k=0)

    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False)
        ph = st['k'] % 7
        st['k'] += 1
        nb = rng.choice(hi) if ph < 3 else rng.choice(lo)
        return finalize(rng, nb, True, p_plan=0.8)
    return f


def collapse(bad_from=30, bad_to=44, ramp=10):
    st = dict(k=0)

    def f(ctx):
        rng = ctx['rng']
        i = ctx['i']
        if not ctx['working']:
            return finalize(rng, 0, False)
        if bad_from <= i < bad_to:
            nb = rng.choice([0, 0, 1, 1, 2])
            return finalize(rng, nb, True, p_plan=0.3)
        if i >= bad_to:
            st['k'] += 1
            h = min(5.0, 2.0 + 3.0 * st['k'] / ramp)
            nb = clip(round(h + rng.gauss(0, 1.0)), 0, 9)
            return finalize(rng, nb, True, p_plan=0.7)
        nb = clip(round(5 + rng.gauss(0, 1.2)), 0, 9)
        return finalize(rng, nb, True)
    return f


def gamer(variant='cheapest_real', real_min=25, gain=0.5):
    """Does exactly the displayed target (+noise) by splitting. variant:
    naive (never touches important), cheapest_real (1 real important task of real_min),
    microflag (flags own 2-min task as important)."""
    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False)
        nb = max(2, round(ctx['T'] + rng.gauss(gain, 1.0)))
        o = finalize(rng, nb, True, small_share=0.0)
        n_micro = nb - (1 if variant == 'cheapest_real' else 0)
        o['nb_small'] = n_micro
        o['imp_open'] = 1
        if variant == 'naive':
            o['nb_imp'] = 0
            o['nb_small'] = nb
            o['real_min'] = nb * 5
        elif variant == 'cheapest_real':
            o['nb_imp'] = 1
            o['imp_est'] = real_min
            o['real_min'] = real_min + (nb - 1) * 5
        elif variant == 'micro12':   # micro tasks declared at 12 min (not small), 1 real important
            o['nb_small'] = 0
            o['nb_imp'] = 1
            o['imp_est'] = real_min
            o['real_min'] = real_min + (nb - 1) * 5
        else:  # microflag
            o['nb_imp'] = 1
            o['imp_est'] = 2
            o['nb_small'] = nb
            o['real_min'] = nb * 5
        o['minutes'] = o['real_min']
        return o
    return f


def honest_equiv(minutes=200):
    """Honest user with same effort as the gamer: ~5 tasks of 40 min."""
    return steady(h=5.0, sd=0.0)


def interrupted(vac=(25, 35), declared=True, sat_p=0.4, sun_p=0.15, c=0.0):
    rng_wk = random.Random(777)

    def f(ctx):
        rng = ctx['rng']
        i = ctx['i']
        d = ctx['date']
        sat = rng_wk.random() < sat_p
        sun = rng_wk.random() < sun_p
        if vac[0] <= i < vac[1]:
            o = finalize(rng, 0, False, p_plan=0.0)
            o['touched'] = False
            o['off'] = declared
            return o
        if d.weekday() == 5:
            return finalize(rng, 2 if sat else 0, False, p_plan=0.5 if sat else 0.0)
        if d.weekday() == 6:
            return finalize(rng, 1 if sun else 0, False, p_plan=0.3 if sun else 0.0)
        if not ctx['working']:  # public holiday
            return finalize(rng, 0, False, p_plan=0.0)
        nb = clip(round(5 + c * max(ctx['T'] - 5, 0) + rng.gauss(0, 1.2)), 0, 9)
        return finalize(rng, nb, True)
    return f


def cold_user(h=3.0, enthusiastic=0, sd=1.0):
    st = dict(k=0)

    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False)
        st['k'] += 1
        base = 8.0 if st['k'] <= enthusiastic else h
        nb = clip(round(base + rng.gauss(0, sd)), 0, 12)
        return finalize(rng, nb, True, p_plan=0.7)
    return f


def ceiling_user(K=6, h=5, sd=0.8, shortfall=0.4):
    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False)
        nb = clip(round(max(h, min(ctx['T'], K)) - shortfall + rng.gauss(0, sd)), 0, K)
        return finalize(rng, nb, True)
    return f


# ---------------------------------------------------------------- loop
def simulate(persona, days=90, seed=1, rules=None, schedule=((0, 'POUSSER'),),
             hol=HOL, alert_cooldown=7):
    rules = rules or Rules()
    rng = random.Random(seed)
    stats, rows, alerts = {}, [], []
    state = dict(prev_T=None, R=None, last_alert=None, K=None)
    mode = None
    for i in range(days):
        d = START + dt.timedelta(days=i)
        for (di, m) in schedule:
            if i == int(di):
                if m != mode and m == 'TENIR':
                    state['R'] = None
                mode = m
        working = is_working(d, hol)
        c9, n28, nm = fenetre_non_manquante(stats, d, rules)
        c9 = [s.nb for s in c9]
        src = 'calcule'
        if mode == 'FIXE' or n28 < MIN_HIST:
            T = DEFAULT_NB
            src = 'defaut'
        elif mode == 'POUSSER':
            T = cible_pousser(c9, state['prev_T'], rules, [s.nb for s in nm])
            if rules.rise_every and state['prev_T'] is not None and T > state['prev_T']:
                lr = state.get('last_rise', -999)
                if i - lr < rules.rise_every:
                    T = state['prev_T']
                else:
                    state['last_rise'] = i
        else:
            if state['R'] is None:
                if len(nm) >= rules.tenir_min_days:
                    if rules.tenir_mean10:
                        state['Rr'] = statistics.mean([s.nb for s in nm[-rules.tenir_win:]])
                        state['R'] = round_half_up(state['Rr'])
                    else:
                        state['R'] = reference_tenir(c9)
            T = state['R'] if state['R'] is not None else DEFAULT_NB
            if state['R'] is None:
                src = 'defaut'
        alert = None
        if mode == 'TENIR' and state['R'] is not None and len(nm) >= (rules.tenir_win if rules.tenir_mean10 else 5) and working:
            if rules.tenir_mean10:
                mm = statistics.mean([s.nb for s in nm[-rules.tenir_win:]])
                lo_, hi_ = bande_tenir(state['R'])
                if rules.tenir_real:
                    b_ = hi_ - state['R']
                    lo_, hi_ = state['Rr'] - b_, state['Rr'] + b_
                dv = 'sous' if mm < lo_ else ('au-dessus' if mm > hi_ else 'dans')
            else:
                dv = derive_tenir(state['R'], [s.nb for s in nm[-5:]])
            if dv != 'dans' and (state['last_alert'] is None or i - state['last_alert'] >= alert_cooldown):
                alert = dv
                state['last_alert'] = i
                alerts.append((i, dv, state['R']))
                if rules.tenir_rebase_on_alert:
                    if rules.tenir_mean10:
                        state['Rr'] = statistics.mean([s.nb for s in nm[-rules.tenir_win:]])
                        state['R'] = round_half_up(state['Rr'])
                    else:
                        state['R'] = reference_tenir([s.nb for s in nm[-5:]])
        ctx = dict(i=i, date=d, working=working, T=T, mode=mode, rng=rng, state=state)
        o = persona(ctx)
        st = Stat(date=d, nb=o['nb'], nb_imp=o['nb_imp'], nb_small=o['nb_small'], minutes=o['minutes'],
                  plan=o['plan'], touched=o['touched'], off=o['off'], working=working, imp_open=o['imp_open'])
        raw = st.nb
        st.nb = effective_count(st, T, rules)
        imp_ok = st.nb_imp
        if rules.imp_min_est and o.get('imp_est', 99) < rules.imp_min_est:
            imp_ok = 0
        succ = jour_atteint(st.nb, T, imp_ok, st.imp_open)
        stats[d] = st
        missing = est_jour_manquant(st, working, st.off)
        rows.append(dict(i=i, date=d, wd=d.weekday(), working=working, mode=mode, T=T, src=src,
                         nb=st.nb, raw=raw, imp=st.nb_imp, succ=succ, cnt_ok=st.nb >= T, missing=missing,
                         off=st.off, alert=alert, real_min=o['real_min'], K=state.get('K')))
        state['prev_T'] = T
    return rows, alerts


def evaluated(rows):
    return [r for r in rows if r['working'] and not r['off']]


def summary(rows, alerts=None, label=''):
    ev = evaluated(rows)
    ev_nm = [r for r in ev if not r['missing']]
    Ts = [r['T'] for r in rows]
    ups = [Ts[k] - Ts[k - 1] for k in range(1, len(Ts))]
    n = len(ev) or 1
    zero_excl = sum(1 for r in ev if r['missing'] and r['nb'] == 0)
    return dict(label=label, meanT=round(statistics.mean(r['T'] for r in ev), 2),
                meanNb=round(statistics.mean(r['nb'] for r in ev), 2),
                succ=round(100 * sum(r['succ'] for r in ev) / n),
                cnt=round(100 * sum(r['cnt_ok'] for r in ev) / n),
                maxUp=max(ups), maxDown=min(ups), alerts=len(alerts or []), zero_excl=zero_excl,
                minT=min(Ts), maxT=max(Ts), endT=Ts[-1],
                realmin=round(statistics.mean(r['real_min'] for r in ev)))


def fmt(s):
    return ("%-34s meanT=%-5s meanDone=%-5s succ=%3d%% countOnly=%3d%% maxUp=%+d maxDown=%+d minT=%d maxT=%d endT=%d alerts=%d zeroDaysExcl=%d realMin=%d"
            % (s['label'], s['meanT'], s['meanNb'], s['succ'], s['cnt'], s['maxUp'], s['maxDown'],
               s['minT'], s['maxT'], s['endT'], s['alerts'], s['zero_excl'], s['realmin']))


def series(rows, a=0, b=None, key='T'):
    return ' '.join(str(r[key]) for r in rows[a:b])


def learner(h0=4.5, c=0.6, sd=0.9, gain=0.1, Kmax=9):
    """Slow grower v2: habit h rises by `gain` on each day he meets a target that is above his habit."""
    st = dict(h=h0)

    def f(ctx):
        rng = ctx['rng']
        ctx['state']['K'] = round(st['h'], 2)
        if not ctx['working']:
            return finalize(rng, 0, False)
        h = st['h']
        nb = clip(round(h + c * max(ctx['T'] - h, 0) + rng.gauss(0, sd)), 0, Kmax)
        if nb >= ctx['T'] and ctx['T'] > h + 0.4:
            st['h'] = min(Kmax, h + gain)
        return finalize(rng, nb, True)
    return f


def shift_user(h1=5.0, h2=3.0, at=20, sd=1.2):
    st = dict(k=0)

    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False)
        st['k'] += 1
        h = h1 if st['k'] <= at else h2
        return finalize(rng, clip(round(h + rng.gauss(0, sd)), 0, 14), True)
    return f


def anchored(offset=-0.7, sd=0.8, K=9, floor=0):
    """Goal-as-anchor user: does about target+offset, regardless of habit."""
    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False)
        return finalize(rng, clip(round(ctx['T'] + offset + rng.gauss(0, sd)), floor, K), True)
    return f
