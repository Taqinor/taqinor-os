"""Profils synthétiques — comportements écrits noir sur blanc (hypothèses de simulation, pas des faits).
Chaque profil est une fonction f(ctx) -> dict du jour. ctx : i (jour calendaire), date, ouvre (jour ouvré
société), T (objectif affiché, None en LIBRE), rng, etat (dict partagé : 'h' = habitude vraie du jour).
Sortie : nb (tâches faites, avant règles de comptage), micro (dont micro-tâches <= 10 min),
taille (minutes médianes des tâches faites), k (essentiels choisis), e (essentiels faits),
plan (plan validé), ouvert (app ouverte), conge (congé déclaré), travaille (a travaillé un jour non ouvré)."""
import math


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def jour(rng, nb, ouvre=True, p_plan=0.85, p_ouvre=0.95, p_ess=0.85, taille=40, part_micro=0.15):
    plan = rng.random() < p_plan if ouvre else False
    ouvert = plan or rng.random() < p_ouvre
    k = (2 if rng.random() < 0.3 else 1) if plan else 0
    e = 0
    if k:
        p = p_ess if nb >= 2 else 0.3
        e = sum(1 for _ in range(k) if rng.random() < p)
        e = min(e, nb)
    micro = sum(1 for _ in range(nb) if rng.random() < part_micro)
    return dict(nb=nb, micro=micro, taille=taille, k=k, e=e, plan=plan, ouvert=ouvert, conge=False,
                travaille=(nb > 0 and not ouvre))


def repos(rng):
    return dict(nb=0, micro=0, taille=40, k=0, e=0, plan=False, ouvert=False, conge=False, travaille=False)


def pousse(T, h, c):
    """Réaction à l'objectif : il fait c × (écart au-dessus de son habitude) de plus. T None = LIBRE."""
    return 0.0 if T is None else c * max(T - h, 0)


# 1. Régulier : habitude 5, écart-type 1,2, réactivité 0,3, ne progresse pas.
def regulier(h=5.0, sd=1.2, c=0.3, K=9):
    def f(ctx):
        ctx['etat']['h'] = h
        if not ctx['ouvre']:
            return repos(ctx['rng'])
        r = ctx['rng']
        return jour(r, clip(round(h + pousse(ctx['T'], h, c) + r.gauss(0, sd)), 0, K))
    return f


# 2. Progresse s'il est poussé : habitude 4,5 ; +0,1 par jour ouvré où l'objectif dépasse son habitude
#    d'au moins 0,5 (≈ +1 toutes les deux semaines tant qu'il est poussé) ; réactivité 0,5 ; plafond 10.
def progresse(h0=4.5, c=0.5, sd=0.9, gain=0.1, Kmax=10):
    st = dict(h=h0)

    def f(ctx):
        ctx['etat']['h'] = st['h']
        if not ctx['ouvre']:
            return repos(ctx['rng'])
        r, h, T = ctx['rng'], st['h'], ctx['T']
        nb = clip(round(h + pousse(T, h, c) + r.gauss(0, sd)), 0, Kmax)
        if T is not None and T >= h + 0.5:
            st['h'] = min(Kmax, h + gain)
        return jour(r, nb)
    return f


# 3. Rafales puis creux : cycle de 7 jours ouvrés, 3 jours à 9-10 tâches puis 4 jours à 1-2.
def rafales():
    st = dict(k=0)

    def f(ctx):
        ctx['etat']['h'] = 5.1
        if not ctx['ouvre']:
            return repos(ctx['rng'])
        r = ctx['rng']
        ph = st['k'] % 7
        st['k'] += 1
        return jour(r, r.choice((9, 10)) if ph < 3 else r.choice((1, 2)), p_plan=0.8)
    return f


# 4. Tricheur : effort réel constant (200 min/jour) ; fait toujours objectif + 1 tâches en découpant
#    (taille = 200 / nb) ; fait toujours un essentiel. Ne clique jamais « mes tâches ont changé ».
def tricheur(effort=200):
    def f(ctx):
        ctx['etat']['h'] = 5.0
        if not ctx['ouvre']:
            return repos(ctx['rng'])
        r = ctx['rng']
        T = ctx['T'] or 5
        nb = max(2, T + 1)
        taille = effort / nb
        o = jour(r, nb, p_ess=1.0, taille=taille)
        o['micro'] = nb if taille <= 10 else 0
        o['e'] = max(o['e'], 1 if o['k'] else 0)
        return o
    return f


# 5. Interrompu : régulier 5 ± 1,2 ; congé déclaré de 10 jours calendaires (j40-49) ; samedi travaillé
#    avec probabilité 0,4 (2 tâches), dimanche 0,15 (1 tâche) ; 4 jours fériés. declare=False : congé
#    NON déclaré (il n'ouvre simplement pas l'app).
def interrompu(conge=(40, 50), declare=True, p_sam=0.4, p_dim=0.15, h=5.0, sd=1.2, c=0.3):
    def f(ctx):
        ctx['etat']['h'] = h
        r, i, d = ctx['rng'], ctx['i'], ctx['date']
        if conge[0] <= i < conge[1]:
            o = repos(r)
            o['conge'] = declare
            return o
        if d.weekday() == 5:
            return jour(r, 2, ouvre=False) if r.random() < p_sam else repos(r)
        if d.weekday() == 6:
            return jour(r, 1, ouvre=False) if r.random() < p_dim else repos(r)
        if not ctx['ouvre']:
            return repos(r)
        return jour(r, clip(round(h + pousse(ctx['T'], h, c) + r.gauss(0, sd)), 0, 9))
    return f


# 6. Effondrement : régulier 5 jusqu'à j30 ; j30-43 : 0-2 tâches, plan 30 %, app ouverte 40 % ;
#    reprise linéaire de 2 à 5 en 10 jours ouvrés ; puis régulier.
def effondrement(de=30, a=44, rampe=10):
    st = dict(k=0)

    def f(ctx):
        r, i = ctx['rng'], ctx['i']
        if de <= i < a:
            ctx['etat']['h'] = 1.0
        elif i >= a:
            ctx['etat']['h'] = min(5.0, 2.0 + 3.0 * st['k'] / rampe)
        else:
            ctx['etat']['h'] = 5.0
        if not ctx['ouvre']:
            return repos(r)
        if de <= i < a:
            return jour(r, r.choice((0, 0, 1, 1, 2)), p_plan=0.3, p_ouvre=0.4, p_ess=0.5)
        if i >= a:
            st['k'] += 1
            h = ctx['etat']['h']
            return jour(r, clip(round(h + r.gauss(0, 1.0)), 0, 9), p_plan=0.7)
        return jour(r, clip(round(5 + pousse(ctx['T'], 5, 0.3) + r.gauss(0, 1.2)), 0, 9))
    return f


# 7. Démarrage à froid : vrai niveau 3 ± 1, dès le premier jour (enthousiaste=3 : 8 tâches les 3
#    premiers jours ouvrés, puis 3).
def froid(h=3.0, sd=1.0, enthousiaste=0, c=0.3):
    st = dict(k=0)

    def f(ctx):
        ctx['etat']['h'] = h
        if not ctx['ouvre']:
            return repos(ctx['rng'])
        st['k'] += 1
        r = ctx['rng']
        base = 8.0 if st['k'] <= enthousiaste else h + pousse(ctx['T'], h, c)
        return jour(r, clip(round(base + r.gauss(0, sd)), 0, 12), p_plan=0.7)
    return f


# 8. Déjà au plafond : capacité dure K = 6, habitude 5,5, réactivité 0,6, écart-type 0,8.
def plafond(K=6, h=5.5, c=0.6, sd=0.8):
    def f(ctx):
        ctx['etat']['h'] = min(h, K)
        if not ctx['ouvre']:
            return repos(ctx['rng'])
        r = ctx['rng']
        return jour(r, clip(round(h + pousse(ctx['T'], h, c) + r.gauss(0, sd)), 0, K))
    return f


# TENIR : changement durable de niveau au jour `a` (5 -> 3 ou 5 -> 7).
def change(h1=5.0, h2=3.0, a=50, sd=1.2):
    def f(ctx):
        h = h1 if ctx['i'] < a else h2
        ctx['etat']['h'] = h
        if not ctx['ouvre']:
            return repos(ctx['rng'])
        r = ctx['rng']
        return jour(r, clip(round(h + r.gauss(0, sd)), 0, 14))
    return f


# Réponses aux propositions (comportement écrit) :
#   'raisonnable' : accepte une montée avec probabilité 0,7, une baisse 0,8 ; en TENIR répond « garder ».
#   'oui' : accepte tout ; 'non' : refuse tout (« pas maintenant ») ; en TENIR, « garder ».
def repondeur(kind, rng, decision):
    if kind == 'oui':
        return 'oui'
    if kind == 'non':
        return 'pas_maintenant'
    p = 0.7 if decision == 'monter' else 0.8
    return 'oui' if rng.random() < p else 'pas_maintenant'
