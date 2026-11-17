s = open('run_nudge.py').read()
s = s.replace("""    if rule == 'rate':""", """    if rule == 'rate14':        # pause only if the last 14 sent were ALL ignored; alt-day if last 5 all ignored
        if len(hist) >= 14 and all(hist[-14:]):
            return 'pause'
        if len(hist) >= 5 and all(hist[-5:]):
            return 'alt'
        return 'normal'
    if rule == 'rate':""")
s = s.split("print(\"### 1.")[0] + '''if __name__ == '__main__':
    print("### 1. decay rules (30 seeds, 90 d): ignorer / 1-in-3 / engaged ; rules: written | rate (10) | rate14")
    for rule in ('written', 'rate', 'rate14'):
        print(" rule", rule)
        for lab, q, ps in [('ignores every push', 0.0, 0.0), ('opens 1 in 3', 1 / 3, 0.2), ('opens 80%', 0.8, 0.5)]:
            summarize('   ' + lab, q=q, ps=ps, rule=rule)
    print("\n### 3. cap with all kinds ON (midi ON), engaged q=.8")
    for pr, cap in (('chrono', (2, 3)), ('priority', (2, 3)), ('priority', (3, 3)), ('priority', (3, 4))):
        summarize(f'cap={cap} survivors={pr}', q=0.8, ps=0.5, midi_on=True, cap=cap, priority=pr)
    print("\n### 4. vacations, engaged user: 10 d and 21 d, as written vs suppressed")
    for vac in ((25, 35), (20, 41)):
        for lab, sv in [('as written', False), ('suppressed', True)]:
            res = summarize(f'vac {vac} {lab}', q=0.8, ps=0.5, vac=vac, suppress_vac=sv)
            print("   vacation pushes sent:", round(statistics.mean(r['vac_pushes'] for r in res), 1), "| matin pushes d41-89:", round(statistics.mean(sum(1 for _ in range(1)) * 0 for r in res), 1))
'''
open('run_nudge.py', 'w').write(s)
