"""Banc AVANT (design-s2-moteur.md §3 tel qu'écrit, via ../sim/engine.py) / APRÈS (regles.py).
Données synthétiques : tout chiffre produit ici est une propriété de la RÈGLE, jamais un fait sur des
utilisateurs réels."""
import os
import sys
import random
import statistics
import datetime as dt

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'sim'))
import engine as av            # noqa: E402  règle AVANT (banc existant réutilisé)
import regles as R             # noqa: E402
import personas as P           # noqa: E402

START = dt.date(2026, 6, 1)    # un lundi
HOL = {dt.date(2026, 7, 30), dt.date(2026, 8, 14), dt.date(2026, 8, 20), dt.date(2026, 8, 21)}
GRAINES = range(1, 31)


def ouvre(d):
    return d.weekday() < 5 and d not in HOL


def mode_du_jour(schedule, i, courant):
    for (di, m) in schedule:
        if i == di:
            return m
    return courant


# ---------------------------------------------------------------- AVANT
def avant(persona, jours, graine, schedule=((0, 'pousser'),), cooldown=7):
    rng = random.Random(graine)
    rules = av.Rules()
    stats, rows, alertes = {}, [], []
    st = dict(prev=None, R=None, last=None)
    mode, etat = None, {}
    for i in range(jours):
        d = START + dt.timedelta(days=i)
        m = mode_du_jour(schedule, i, mode)
        if m != mode and m == 'tenir':
            st['R'] = None
        mode = m
        c9, n28, nm = av.fenetre_non_manquante(stats, d, rules)
        c9 = [s.nb for s in c9]
        if mode == 'libre':
            T = None
        elif n28 < av.MIN_HIST:
            T = av.DEFAULT_NB
        elif mode == 'pousser':
            T = av.cible_pousser(c9, st['prev'], rules)
        else:
            if st['R'] is None and len(nm) >= 5:
                st['R'] = av.reference_tenir(c9)
            T = st['R'] if st['R'] is not None else av.DEFAULT_NB
        alerte = None
        if mode == 'tenir' and st['R'] is not None and len(nm) >= 5 and ouvre(d):
            dv = av.derive_tenir(st['R'], [s.nb for s in nm[-5:]])
            if dv != 'dans' and (st['last'] is None or i - st['last'] >= cooldown):
                alerte, st['last'] = dv, i
                alertes.append((i, dv, etat.get('h')))
        o = persona(dict(i=i, date=d, ouvre=ouvre(d), T=T, rng=rng, etat=etat))
        s = av.Stat(date=d, nb=o['nb'], nb_imp=o['e'], plan=o['plan'], touched=o['ouvert'] or o['nb'] > 0,
                    off=o['conge'], working=ouvre(d), imp_open=1 if o['k'] else 0)
        stats[d] = s
        manquant = av.est_jour_manquant(s, ouvre(d), s.off)
        tenu = av.jour_atteint(s.nb, T, o['e'], 1 if o['k'] else 0) if T is not None else None
        rows.append(dict(i=i, T=T, nb=o['nb'], evalue=(ouvre(d) and not manquant and not o['conge']),
                         tenu=tenu, h=etat.get('h'), prop=None, mode=mode))
        if T is not None:
            st['prev'] = T
    return rows, alertes


# ---------------------------------------------------------------- APRÈS
def apres(persona, jours, graine, schedule=((0, 'pousser'),), rep='raisonnable', objectif_dit=None):
    rng = random.Random(graine)
    rrep = random.Random(graine + 1000)
    e = R.Etat(mode=schedule[0][1], objectif_dit=objectif_dit)
    rows, alertes, props = [], [], []
    etat = {}
    for i in range(jours):
        d = START + dt.timedelta(days=i)
        m = mode_du_jour(schedule, i, e.mode)
        if i > 0 and m != e.mode:
            e = R.basculer(e, m, i)
        T, src = R.objectif_affiche(e)
        o = persona(dict(i=i, date=d, ouvre=ouvre(d), T=T, rng=rng, etat=etat))
        compte = o['nb'] - max(0, o['micro'] - R.MICRO_COMPTEES)
        statut = R.statut_jour(ouvre(d), o['conge'], compte, o['plan'], o['ouvert'])
        tenu, prop = None, None
        if statut == 'evalue':
            e.historique.append((i, compte))
            if e.mode == 'pousser' and T is not None:
                tenu = R.jour_tenu(compte, T, o['k'], o['e'])
                if e.palier is None:
                    e.initiaux.append(compte)
                    e.tailles_bloc += [o['taille']] * compte
                    if len(e.initiaux) >= R.JOURS_INITIAUX:
                        e.palier, _ = R.palier_initial(e.initiaux, e.objectif_dit)
                        e.ref_taille = R.reference_taille(e.tailles_bloc)
                        e.tailles_bloc = []
                        prop = ('initial', e.palier)
                else:
                    e.bloc.append((compte, tenu, o['taille']))
                    e.tailles_bloc += [o['taille']] * compte
                    if len(e.bloc) >= R.BLOC:
                        N = e.palier
                        dec, ch = R.evaluer_bloc(e, i)
                        reponse = P.repondeur(rep, rrep, dec) if dec in ('monter', 'baisser') else None
                        if dec:
                            props.append(dict(i=i, dec=dec, N=N, rep=reponse, h=etat.get('h'), **ch))
                            prop = (dec, reponse)
                        e = R.clore_bloc(e, i, dec, reponse)
            elif e.mode == 'tenir':
                lo, _ = R.bande_tenir(e.R) if e.R is not None else (T, None)
                tenu = compte >= lo
                e, a, moy = R.jour_tenir(e, compte, i)
                if a:
                    alertes.append((i, a, etat.get('h')))
                    e = R.repondre_tenir(e, 'garder', moy)
        rows.append(dict(i=i, T=T, src=src, nb=o['nb'], compte=compte, evalue=(statut == 'evalue'),
                         tenu=tenu, h=etat.get('h'), prop=prop, mode=e.mode, statut=statut))
    return rows, alertes, props


# ---------------------------------------------------------------- mesures
def mesures(rows, alertes, props=None, depart_perso=True):
    Ts = [r['T'] for r in rows]
    sauts = [Ts[k] - Ts[k - 1] for k in range(1, len(Ts)) if Ts[k] is not None and Ts[k - 1] is not None]
    ev = [r for r in rows if r['evalue'] and r['T'] is not None]
    props = props or []
    up = [p for p in props if p['dec'] == 'monter']
    dn = [p for p in props if p['dec'] == 'baisser']
    fausses_baisses = sum(1 for p in dn if p['h'] is not None and p['h'] >= p['N'])
    # AVANT : baisses imposées alors que l'habitude vraie >= objectif de la veille
    imposees = sum(1 for k in range(1, len(rows)) if Ts[k] is not None and Ts[k - 1] is not None
                   and Ts[k] < Ts[k - 1] and rows[k]['h'] is not None and rows[k]['h'] >= Ts[k - 1])
    tv = [t for t in Ts if t is not None]
    return dict(Tmoy=statistics.mean(r['T'] for r in ev) if ev else float('nan'),
                Tmin=min(tv) if tv else None, Tmax=max(tv) if tv else None, Tfin=tv[-1] if tv else None,
                up=max(sauts) if sauts else 0, down=min(sauts) if sauts else 0,
                changements=sum(1 for s in sauts if s != 0),
                p_up=len(up), p_dn=len(dn), acc_up=sum(1 for p in up if p['rep'] == 'oui'),
                acc_dn=sum(1 for p in dn if p['rep'] == 'oui'),
                taille=sum(1 for p in props if p['dec'] == 'taille'),
                fausses=fausses_baisses, imposees=imposees, alertes=len(alertes),
                tenus=100 * statistics.mean(1 if r['tenu'] else 0 for r in ev) if ev else float('nan'),
                fait_fin=statistics.mean([r['nb'] for r in rows if r['evalue']][-20:]),
                h_fin=rows[-1]['h'])


def agreger(liste):
    out = {}
    for k in liste[0]:
        vals = [x[k] for x in liste if x[k] is not None]
        if not vals:
            out[k] = None
        elif k in ('up', 'Tmax'):
            out[k] = max(vals)
        elif k in ('down', 'Tmin'):
            out[k] = min(vals)
        else:
            out[k] = statistics.mean(vals)
    return out


def trajectoire(liste_rows, jours=(14, 30, 45, 60, 90, 119)):
    out = []
    for j in jours:
        v = [rows[j]['T'] for rows in liste_rows if j < len(rows) and rows[j]['T'] is not None]
        out.append('%s' % (statistics.median(v) if v else '—'))
    return '/'.join(out)


def comparer(nom, fab, jours=120, schedule=((0, 'pousser'),), rep='raisonnable', objectif_dit=None):
    A, B, rA, rB = [], [], [], []
    for g in GRAINES:
        rows, al = avant(fab(), jours, g, schedule)
        A.append(mesures(rows, al))
        rA.append(rows)
        rows, al, pr = apres(fab(), jours, g, schedule, rep, objectif_dit)
        B.append(mesures(rows, al, pr))
        rB.append(rows)
    return nom, agreger(A), agreger(B), trajectoire(rA), trajectoire(rB)
