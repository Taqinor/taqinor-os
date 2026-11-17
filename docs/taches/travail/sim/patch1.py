s = open('engine.py').read()
s = s.replace("    tenir_win: int = 10 ", "    n_win: int = 9                   # POUSSER window size (as written = 9)\n    tenir_win: int = 10 ")
s = s.replace("def fenetre_non_manquante(stats, today, rules, n=N_WIN, horizon=HORIZON):",
              "def fenetre_non_manquante(stats, today, rules, n=None, horizon=HORIZON):\n    n = n or rules.n_win")
open('engine.py', 'w').write(s)
p = open('sim.py').read()
p += '''

def anchored(offset=-0.7, sd=0.8, K=9, floor=0):
    """Goal-as-anchor user: does about target+offset, regardless of habit."""
    def f(ctx):
        rng = ctx['rng']
        if not ctx['working']:
            return finalize(rng, 0, False)
        return finalize(rng, clip(round(ctx['T'] + offset + rng.gauss(0, sd)), floor, K), True)
    return f
'''
p = p.replace("""        else:  # microflag""", """        elif variant == 'micro12':   # micro tasks declared at 12 min (not small), 1 real important
            o['nb_small'] = 0
            o['nb_imp'] = 1
            o['imp_est'] = real_min
            o['real_min'] = real_min + (nb - 1) * 5
        else:  # microflag""")
open('sim.py', 'w').write(p)
