"""Recalcul jetable de l'annexe B (spec 2 §3.5), règles TELLES QU'ÉCRITES."""
import calendar
from datetime import date, timedelta
F = {date(2026, 11, 18), date(2027, 1, 1)}
def ouvre(d): return d.weekday() < 5 and d not in F
JS = ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim']
def fmt(d): return f"{JS[d.weekday()]} {d:%d/%m/%Y}" if d else "None"

def borne(y, m, j):
    last = calendar.monthrange(y, m)[1]
    return date(y, m, last if j == -1 else min(j, last))
def add_mois(d, n, j=None):
    y, m = divmod(d.month - 1 + n, 12)
    return borne(d.year + y, m + 1, j if j is not None else d.day)
def nieme(y, m, wd, rang):
    jours = [date(y, m, k) for k in range(1, calendar.monthrange(y, m)[1] + 1) if date(y, m, k).weekday() == wd]
    return jours[-1] if rang == -1 else jours[rang - 1]

def serie(r, debut, jusqua):
    """Génère la série calendrier (dates >= debut) jusqu'à `jusqua`."""
    t, n = r['type'], r.get('n', 1)
    d = debut
    if t == 'quotidien':
        k = 0
        while debut + timedelta(k * n) <= jusqua:
            yield debut + timedelta(k * n); k += 1
    elif t == 'jours_ouvres':
        while d <= jusqua:
            if ouvre(d): yield d
            d += timedelta(1)
    elif t == 'hebdo':
        lundi0 = debut - timedelta(debut.weekday())
        while d <= jusqua:
            sem = (d - lundi0).days // 7
            if d.weekday() in r['masque'] and sem % n == 0: yield d
            d += timedelta(1)
    elif t == 'mensuel':
        y, m, k = debut.year, debut.month, 0
        while True:
            yy, mm = divmod(m - 1 + k * n, 12); yy += y; mm += 1
            c = nieme(yy, mm, r['wd'], r['rang']) if 'rang' in r else borne(yy, mm, r['j'])
            if c > jusqua: return
            if c >= debut: yield c
            k += 1
    elif t == 'annuel':
        for y in range(debut.year, jusqua.year + 1):
            c = borne(y, debut.month, debut.day)  # 29/02 -> 28/02
            if debut <= c <= jusqua: yield c

def premiere(r, debut):
    if r.get('apres_fait'): return debut
    return next(serie(r, debut, debut + timedelta(800)), None)

def suivante(r, debut, occ, auj, fait):
    if r.get('apres_fait'):
        f, n, t = fait, r.get('n', 1), r['type']
        if t == 'quotidien': c = f + timedelta(n)
        elif t == 'jours_ouvres':
            c, k = f, 0
            while k < n:
                c += timedelta(1); k += ouvre(c)
        elif t == 'hebdo': c = f + timedelta(7 * n)
        elif t == 'mensuel': c = add_mois(f, n)
        elif t == 'annuel': c = borne(f.year + n, f.month, f.day)
    else:
        seuil = max(occ, auj)
        c = next((x for x in serie(r, debut, seuil + timedelta(800)) if x > seuil), None)
    if c and r.get('date_fin') and c > r['date_fin']: return None
    return c

D = date
J = D(2026, 11, 17)
cas = [  # (n°, règle, début, occ, fait/sauté, attendu)
 (1, {'type': 'hebdo', 'masque': {0}}, J, None, None, D(2026,11,23)),
 (2, {'type': 'hebdo', 'masque': {0}}, J, D(2026,11,23), D(2026,11,23), D(2026,11,30)),
 (3, {'type': 'hebdo', 'masque': {0}}, J, D(2026,11,23), D(2026,11,21), D(2026,11,30)),
 (4, {'type': 'hebdo', 'masque': {0}}, J, D(2026,11,23), D(2026,12,2), D(2026,12,7)),
 (5, {'type': 'hebdo', 'masque': {0}}, J, D(2026,11,23), D(2026,11,17), D(2026,11,30)),
 (6, {'type': 'mensuel', 'j': 31}, J, None, None, D(2026,11,30)),
 (7, {'type': 'mensuel', 'j': 31}, J, D(2027,1,31), D(2027,1,31), D(2027,2,28)),
 (8, {'type': 'mensuel', 'j': 31}, J, D(2027,2,28), D(2027,2,28), D(2027,3,31)),
 (9, {'type': 'mensuel', 'j': -1}, J, D(2026,11,30), D(2026,11,30), D(2026,12,31)),
 (10, {'type': 'jours_ouvres'}, J, J, J, D(2026,11,19)),
 (11, {'type': 'jours_ouvres'}, J, D(2026,11,20), D(2026,11,20), D(2026,11,23)),
 (12, {'type': 'jours_ouvres'}, J, D(2026,12,31), D(2026,12,31), D(2027,1,4)),
 (13, {'type': 'quotidien', 'n': 2}, J, J, D(2026,11,18), D(2026,11,19)),
 (14, {'type': 'quotidien', 'n': 3, 'apres_fait': 1}, J, J, D(2026,11,20), D(2026,11,23)),
 (15, {'type': 'mensuel', 'n': 3, 'j': 20, 'apres_fait': 1}, J, J, D(2027,1,20), D(2027,4,20)),
 (16, {'type': 'mensuel', 'n': 1, 'j': 31, 'apres_fait': 1}, J, J, D(2027,1,31), D(2027,2,28)),
 (17, {'type': 'jours_ouvres', 'n': 2, 'apres_fait': 1}, J, J, J, D(2026,11,20)),
 (18, {'type': 'hebdo', 'n': 2, 'masque': {0, 3}}, J, None, None, D(2026,11,19)),
 (19, {'type': 'hebdo', 'n': 2, 'masque': {0, 3}}, J, D(2026,11,19), D(2026,11,19), D(2026,11,30)),
 (20, {'type': 'hebdo', 'n': 2, 'masque': {0, 3}}, J, D(2026,11,30), D(2026,11,30), D(2026,12,3)),
 (21, {'type': 'annuel'}, D(2028,2,29), D(2028,2,29), D(2028,2,29), D(2029,2,28)),
 (22, {'type': 'hebdo', 'masque': {0}, 'date_fin': D(2026,11,25)}, J, D(2026,11,23), D(2026,11,23), None),
 (23, {'type': 'mensuel', 'wd': 4, 'rang': 1}, J, None, None, D(2026,12,4)),
 (24, {'type': 'mensuel', 'wd': 4, 'rang': 1}, J, D(2026,12,4), D(2026,12,4), D(2027,1,1)),
 (25, {'type': 'mensuel', 'wd': 4, 'rang': -1}, J, None, None, D(2026,11,27)),
]
ko = 0
for n, r, debut, occ, fait, att in cas:
    got = premiere(r, debut) if occ is None and fait is None else suivante(r, debut, occ, fait, fait)
    ok = got == att
    ko += not ok
    print(f"B{n:<2} attendu {fmt(att):<16} obtenu {fmt(got):<16} {'OK' if ok else 'ECART'}")
print("écarts:", ko)
# Cas hors annexe : annuel 29/02 sur plusieurs années (série ancrée sur le début)
r = {'type': 'annuel'}
print("annuel 29/02/2028 x4 :", [fmt(x) for x in serie(r, D(2028,2,29), D(2032,12,31))])
# après_fait mensuel dérive : 31/01 -> 28/02 -> 28/03
print("mensuel apres_fait 31/01 puis 28/02 :", fmt(add_mois(D(2027,2,28), 1)))
# Weekday affiché « 5/6 »
print("5/6/2027 =", fmt(D(2027,6,5)), "; 17/11/2026 =", fmt(J))
