import random, statistics, datetime as dt
from sim import START, HOL, is_working

KINDS = ['matin', 'midi', 'hebdo', 'soir']
TIME = {'matin': 830, 'midi': 1330, 'hebdo': 1600, 'soir': 1800}
PRIO = {'soir': 0, 'matin': 1, 'hebdo': 2, 'midi': 3}   # variant B: which push survives the cap


def decay_state(hist, rule):
    """hist = list of booleans (True = ignored) for SENT pushes of that kind, chronological."""
    if rule == 'written':
        run = 0
        for x in reversed(hist):
            if x:
                run += 1
            else:
                break
        return 'pause' if run >= 6 else ('alt' if run >= 3 else 'normal')
    if rule == 'rate14':        # pause only if the last 14 sent were ALL ignored; alt-day if last 5 all ignored
        if len(hist) >= 14 and all(hist[-14:]):
            return 'pause'
        if len(hist) >= 5 and all(hist[-5:]):
            return 'alt'
        return 'normal'
    if rule == 'rate':          # pause only if the last 10 sent were ALL ignored; alt if last 4 all ignored
        if len(hist) >= 10 and all(hist[-10:]):
            return 'pause'
        if len(hist) >= 4 and all(hist[-4:]):
            return 'alt'
        return 'normal'


def run(q, ps, v=0.0, midi_on=False, cap=(2, 3), priority='chrono', days=90, seed=1, rule='written',
        vac=None, suppress_vac=False, kinds_on=('matin', 'soir', 'hebdo'), vac_q_zero=True, q_after_vac=None):
    """q = P(open a push within 3h); ps = P(self-plans during the day); v = P(visits target screen himself)."""
    rng = random.Random(seed)
    hist = {k: [] for k in KINDS}
    last_sent = {k: None for k in KINDS}
    pause_day = {}
    per_day = []
    kinds_sent = {k: 0 for k in KINDS}
    vac_pushes = 0
    for i in range(days):
        d = START + dt.timedelta(days=i)
        working = is_working(d)
        on_vac = vac and vac[0] <= i < vac[1]
        sent_today = []
        if working and not (on_vac and suppress_vac):
            plan_before = False
            due = []
            # matin: plan not yet accepted at 08:30
            plan_accepted = False
            due.append('matin')
            plan_state = {'plan': False}
            opened = {}
            on = set(kinds_on) | ({'midi'} if midi_on else set())
            # Evaluate in chronological order
            order = sorted([k for k in on if (k != 'hebdo' or d.weekday() == 4)], key=lambda k: TIME[k])
            # cap & priority selection is done on the due set; conditions of soir/midi depend on plan state,
            # approximated: plan accepted by day end with prob ps or if matin opened.
            cand = []
            matin_open = None
            for k in order:
                st = decay_state(hist[k], rule)
                if st == 'pause':
                    pause_day.setdefault(k, i)
                    continue
                if st == 'alt' and last_sent[k] is not None and i - last_sent[k] < 2:
                    continue
                cand.append(k)
            capd = cap[1] if d.weekday() == 4 and 'hebdo' in on else cap[0]
            if len(cand) > capd:
                if priority == 'chrono':
                    cand = cand[:capd]
                else:
                    keep = sorted(cand, key=lambda k: PRIO[k])[:capd]
                    cand = [k for k in cand if k in keep]
            plan_ok = False
            for k in cand:
                if k == 'soir' and not (plan_ok or rng.random() < ps or matin_open):
                    continue
                if k == 'midi' and not ((plan_ok or rng.random() < ps) and rng.random() < 0.5):
                    continue
                sent_today.append(k)
                qq = 0.0 if (on_vac and vac_q_zero) else q
                opened_it = rng.random() < qq
                visited = rng.random() < (0 if on_vac else v)
                hist[k].append(not (opened_it or visited))
                last_sent[k] = i
                kinds_sent[k] += 1
                if k == 'matin':
                    matin_open = opened_it
                    plan_ok = opened_it
                if on_vac:
                    vac_pushes += 1
        per_day.append(len(sent_today))
    return dict(per_day=per_day, kinds=kinds_sent, pause=pause_day, vac_pushes=vac_pushes)


def summarize(label, **kw):
    res = [run(seed=s, **kw) for s in range(1, 31)]
    mx = max(max(r['per_day']) for r in res)
    tot = statistics.mean(sum(r['per_day']) for r in res)
    kinds = {k: statistics.mean(r['kinds'][k] for r in res) for k in KINDS}
    paused = {k: sum(1 for r in res if k in r['pause']) for k in KINDS}
    pd = {k: statistics.mean(r['pause'][k] for r in res if k in r['pause']) if any(k in r['pause'] for r in res) else None for k in KINDS}
    last30 = statistics.mean(sum(r['per_day'][60:]) for r in res)
    print(f"{label:46s} max/day {mx} | total90 {tot:5.1f} | by kind { {k: round(v, 1) for k, v in kinds.items() if v} } | paused (of 30) { {k: v for k, v in paused.items() if v} } | mean pause day { {k: round(v) for k, v in pd.items() if v} } | pushes d60-89 {last30:.1f}")
    return res


if __name__ == '__main__':
    print("### 1. decay rules (30 seeds, 90 d): ignorer / 1-in-3 / engaged ; rules: written | rate (10) | rate14")
    for rule in ('written', 'rate', 'rate14'):
        print(" rule", rule)
        for lab, q, ps in [('ignores every push', 0.0, 0.0), ('opens 1 in 3', 1 / 3, 0.2), ('opens 80%', 0.8, 0.5)]:
            summarize('   ' + lab, q=q, ps=ps, rule=rule)
    print()
    print("### 3. cap with all kinds ON (midi ON), engaged q=.8")
    for pr, cap in (('chrono', (2, 3)), ('priority', (2, 3)), ('priority', (3, 3)), ('priority', (3, 4))):
        summarize(f'cap={cap} survivors={pr}', q=0.8, ps=0.5, midi_on=True, cap=cap, priority=pr)
    print()
    print("### 4. vacations, engaged user: 10 d and 21 d, as written vs suppressed")
    for vac in ((25, 35), (20, 41)):
        for lab, sv in [('as written', False), ('suppressed', True)]:
            res = summarize(f'vac {vac} {lab}', q=0.8, ps=0.5, vac=vac, suppress_vac=sv)
            print("   vacation pushes sent:", round(statistics.mean(r['vac_pushes'] for r in res), 1))
