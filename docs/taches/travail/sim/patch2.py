s = open('engine.py').read()
s = s.replace("    n_win: int = 9 ", "    rise_every: int = 0              # POUSSER may rise by +1 at most once every N calendar days (0 = off)\n    n_win: int = 9 ")
open('engine.py', 'w').write(s)
p = open('sim.py').read()
p = p.replace("""            T = cible_pousser(c9, state['prev_T'], rules, [s.nb for s in nm])""", """            T = cible_pousser(c9, state['prev_T'], rules, [s.nb for s in nm])
            if rules.rise_every and state['prev_T'] is not None and T > state['prev_T']:
                lr = state.get('last_rise', -999)
                if i - lr < rules.rise_every:
                    T = state['prev_T']
                else:
                    state['last_rise'] = i""")
open('sim.py', 'w').write(p)
