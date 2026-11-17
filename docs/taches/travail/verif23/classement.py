"""Recalcul jetable du jeu §3.3 de la spec 3 (cle_tri telle qu'écrite).
Hypothèses NON écrites dans la spec, rendues explicites ici :
  H1 activité ERP : pmax = priorite = 0, rang_jour nul ;
  H2 rang_jour nul pour toutes les tâches du jeu (la table ne le donne pas) ;
  H3 created_at de 7, 12, 20, 21, 30, 31, 40 : quelconque (inutile si l'ordre est décidé avant k6)."""
import random
from datetime import date, datetime, timedelta
J = date(2026, 11, 17); INF = date.max
OUVRES = {d for d in (J + timedelta(k) for k in range(1, 400)) if d.weekday() < 5 and d != date(2026, 11, 18)}
def n_ouvres(ech): return sum(1 for d in OUVRES if J < d <= ech)
T = [  # id, act, ech, prio, prio_projet, jour_prevu, created
 (7, 0, date(2026,11,16), 3, 2, None, datetime(2026,11,1)),
 (12, 0, date(2026,11,17), 1, 2, None, datetime(2026,11,1)),
 (101, 1, date(2026,11,17), 0, 0, None, datetime(2026,11,10)),
 (15, 0, date(2026,11,17), 0, 0, None, datetime(2026,11,14)),
 (20, 0, date(2026,11,19), 2, 3, None, datetime(2026,11,1)),
 (21, 0, date(2026,11,20), 3, 0, None, datetime(2026,11,1)),
 (30, 0, None, 0, 3, None, datetime(2026,11,1)),
 (40, 0, date(2026,11,7), 1, 0, None, datetime(2026,11,1)),
 (31, 0, date(2027,4,15), 3, 0, None, datetime(2026,11,1)),
 (41, 0, None, 0, 0, date(2026,11,12), datetime(2026,11,5)),
 (42, 0, None, 0, 0, J, datetime(2026,11,16,8)),
 (43, 0, None, 0, 0, J, datetime(2026,11,16,9)),
 (44, 0, None, 0, 0, J, datetime(2026,11,16,9)),
]
def bande(t):
    i, act, ech, p, pp, jp, cr = t; pmax = max(p, pp)
    if act or ech == J or (ech and ech < J and pmax == 3): return 1
    if (ech and ech > J and n_ouvres(ech) <= 3) or (pmax == 3 and not (ech and ech > J + timedelta(14))): return 2
    return 3
def cle(t):
    i, act, ech, p, pp, jp, cr = t
    return (bande(t), ech or INF, -max(p, pp), -p, (1, 0), cr, (act, i))  # k5 : rang_jour nul partout (H2)
attendu = [7, 12, 101, 15, 20, 21, 30, 40, 31, 41, 42, 43, 44]
ok = 0
for _ in range(300):
    l = T[:]; random.shuffle(l)
    ok += [t[0] for t in sorted(l, key=cle)] == attendu
print('ordre :', [t[0] for t in sorted(T, key=cle)], '| bandes :', {t[0]: bande(t) for t in T})
print('permutations conformes :', ok, '/ 300')
cles = [cle(t) for t in T]; print('clés toutes distinctes (ordre total) :', len(set(cles)) == len(cles))
