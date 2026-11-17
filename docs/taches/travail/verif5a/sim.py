"""Banc de simulation independant. Modeles de comportement ECRITS ICI (voir verif-spec-5a.md §3).

Hypotheses communes (arbitraires, a lire comme un jeu de donnees synthetiques) :
 - jour 0 = lundi 16/11/2026 ; ouvre = lundi-vendredi hors feries {23, 72} ;
 - chaque jour ouvre, l'utilisateur n'utilise pas l'appli avec proba 0,08 (alors 0 compte, pas de plan -> sans_donnees) ;
 - sinon plan valide avec proba 0,85 ; essentiel choisi avec proba 0,70 (k=1), fait avec proba 0,85 s'il a fait >=1 tache ;
 - proposition repondue le 1er jour ouvre suivant, sauf 'ignore' (expire apres 7 j) ;
 - taille d'une tache = lognormale mediane 30 min, sigma 0,5 (estimation = taille).
"""
import math
import random
import statistics
from datetime import date, timedelta

from rythme import *

START = date(2026, 11, 16)
FERIES = {23, 72}


class P:
    def __init__(self, name, **kw):
        self.name = name
        self.C = 5.0             # niveau courant (moyenne vraie)
        self.sd = 1.2
        self.grow = 0.0          # gain par jour ouvre quand pousse (objectif >= round(C))
        self.cap = 99
        self.p_yes_up = 1.0
        self.p_yes_down = 1.0
        self.p_ignore = 0.0
        self.est = True
        self.conge = None        # (debut, fin) calendaires
        self.sat = 0.0
        self.cheat = False
        self.burst = False
        self.collapse = None     # (debut, fin)
        self.ceiling = None      # plafond dur : le niveau suit l'objectif jusqu'a ce plafond
        self.follow = False      # niveau = objectif - 0.3 (capable) borne par potentiel
        self.potential = 9
        self.p_skip = 0.08
        self.p_notif = 0.5
        self.short_days = ()
        self.size_med = 30.0
        self.size_drift = None   # fonction(d)->facteur de taille
        self.press_changed = 0.5
        self.step = None         # (jour, nouveau_niveau)
        self.mean_fn = None      # fonction(d)->moyenne vraie
        self.conge_after_accept = None  # duree du conge pris le lendemain de la 1re montee acceptee
        self.reentry = 1.0       # facteur de niveau les 5 jours ouvres apres un conge
        self.outliers = {}       # jour -> nombre de taches cochees (cochage en masse)
        self.week_short = ()     # semaines (numero) ou il ne travaille que 2 jours
        self.ess_prob = 0.70
        self.open_on_idle = False  # ouvre l'appli (plan valide) meme les jours sans travail
        self.__dict__.update(kw)
        self.burst_phase = None

    # niveau vrai espere ce jour (pour juger fausses alertes / fausses baisses)
    def true_mean(self, d, obj):
        if self.mean_fn:
            return self.mean_fn(d)
        if self.collapse and self.collapse[0] <= d < self.collapse[1]:
            return 1.0
        if self.burst:
            return 5.5
        if self.follow and obj is not None:
            return min(self.potential, obj - 0.3)
        if self.ceiling and obj is not None:
            return min(obj, self.ceiling) - 0.3
        if self.step and d >= self.step[0]:
            return self.step[1]
        return self.C

    def draw_count(self, d, obj, rng):
        if self.burst:
            blk = d // 5
            r = random.Random(blk * 7919 + 13)
            hi = r.random() < 0.5
            return rng.choice([9, 10]) if hi else rng.choice([1, 2])
        m = self.true_mean(d, obj)
        if self.conge and self.reentry != 1.0 and self.conge[1] < d <= self.conge[1] + 7:
            m *= self.reentry
        sd = self.sd
        if self.ceiling:
            sd = 1.0
        n = max(0, arrondi(rng.gauss(m, sd)))
        if self.ceiling:
            n = min(n, self.ceiling + 1)
        return n

    def make_tasks(self, d, obj, rng):
        n = self.draw_count(d, obj, rng)
        f = self.size_drift(d) if self.size_drift else 1.0
        sizes = [self.size_med * f * math.exp(rng.gauss(0, 0.5)) for _ in range(n)]
        if d in self.outliers:
            n2 = self.outliers[d]
            sizes = [self.size_med * math.exp(rng.gauss(0, 0.5)) for _ in range(n2)]
            tasks = [dict(kind="own", size=s, est=None) for s in sizes]
            return tasks
        tasks = [dict(kind="own", size=s, est=(s if self.est else None)) for s in sizes]
        if self.cheat and obj is not None:
            target = obj + 1
            guard = 0
            while compte_du_jour(tasks)[0] < target and guard < 30 and tasks:
                guard += 1
                tasks.sort(key=lambda t: -t["size"])
                big = tasks.pop(0)
                h = big["size"] / 2
                for _ in range(2):
                    tasks.append(dict(kind="own", size=h, est=(h if self.est else None)))
        return tasks

    def answer(self, typ, rng):
        if rng.random() < self.p_ignore:
            return "ignore"
        if typ == "monter":
            return "oui" if rng.random() < self.p_yes_up else "non"
        if typ == "baisser":
            return "oui" if rng.random() < self.p_yes_down else "non"
        if typ == "type":
            return "oui"
        if typ == "derive":
            return "non"  # "garder" ; cf. persona.derive_pass
        if typ == "garde_taille":
            return "oui" if rng.random() < self.press_changed else "non"
        return "non"

    def post_day(self, d, obj):
        if self.grow and obj is not None and obj >= arrondi(self.C) and self.C < self.cap:
            self.C = min(self.cap, self.C + self.grow)


def run(factory, seed, days=120, modes=None, dit=None, notif=False, trace=False, arrondi_bascule="floor",
        etat_hook=None, rule=None):
    p = factory()
    rng = random.Random(seed * 9973 + 17)
    e = Etat(dit=dit, arrondi_bascule=arrondi_bascule)
    if rule:
        rule(e)
    modes = modes or {}
    out = dict(obj=[], counts=[], ev=[], reussie=[], N_hist=[], alerts=[], fausses_baisses=0, fausses_alertes=0,
               props=dict(monter=0, baisser=0, taille=0, type=0), acc=dict(monter=0, baisser=0), sat_total=0,
               tot=0, statuts={}, log=[], days=[], cards=[], answers=[])
    pending_decision = None
    notif_state = dict(ign=dict(matin=0, relance=0, soir=0), pause=set(), sent=[], per_day=[])
    prevN = None
    jumps = []
    for d in range(days):
        wd = d % 7
        ouvre = wd < 5 and d not in FERIES
        conge = bool(p.conge and p.conge[0] <= d <= p.conge[1])
        skipped = False
        if d in modes:
            e.basculer(modes[d], d)
        e.debut_journee(d)
        # reponse a la carte du matin
        if e.pending and ouvre and not conge:
            if pending_decision is None:
                pending_decision = p.answer(e.pending.type, rng)
            if pending_decision != "ignore":
                typ = e.pending.type
                out["answers"].append((d, typ, pending_decision))
                if typ == "derive":
                    oui = (pending_decision == "oui")
                    pass_ = getattr(p, "derive_pass", False)
                    e.repondre(d, pass_)
                else:
                    e.repondre(d, pending_decision == "oui")
                if typ in ("monter", "baisser") and pending_decision == "oui":
                    out["acc"][typ] += 1
                    if typ == "monter" and p.conge_after_accept and p.conge is None:
                        p.conge = (d + 1, d + p.conge_after_accept)
                        out["accept_day"] = d
                pending_decision = None
        elif e.pending is None:
            pending_decision = None
        court = wd in p.short_days
        week_off = (d // 7) in p.week_short and wd in (2, 3, 4)
        obj = e.objectif_du_jour(court)
        if conge or (not ouvre and not (wd == 5 and rng.random() < p.sat)):
            tasks = []
        elif not ouvre:
            tasks = p.make_tasks(d, obj, rng)
        else:
            skipped = (rng.random() < p.p_skip) or (week_off and not p.open_on_idle)
            tasks = [] if (skipped or week_off) else p.make_tasks(d, obj, rng)
        if conge:
            statut = "conge"
            count, det = 0, {}
        else:
            count, det = compte_du_jour(tasks)
            app = bool(tasks) or (not skipped and rng.random() < 0.97)
            plan = app and rng.random() < 0.85
            statut = statut_jour(ouvre, False, count, plan, app)
            if not ouvre and tasks:
                out["sat_total"] += count
        out["statuts"][statut] = out["statuts"].get(statut, 0) + 1
        est = [t["est"] for t in tasks]
        k = 1 if (statut == "evalue" and rng.random() < p.ess_prob) else 0
        ee = 1 if (k and count >= 1 and rng.random() < 0.85) else 0
        before_N = e.N()
        evs = e.fin_journee(d, statut, count, est, court)
        if e.pending is not None and e.pending.jour == d:
            out["cards"].append(dict(d=d, **{kk: vv for kk, vv in e.pending.__dict__.items() if kk != "jour"}))
        for x in evs:
            out["ev"].append((d, x))
            if x[0] in ("monter", "baisser", "type"):
                out["props"][x[0]] += 1
            if x[0] == "garde_taille":
                out["props"]["taille"] += 1
            if x[0] == "baisser":
                tm = p.true_mean(d, before_N)
                if tm >= x[1] - 0.5:
                    out["fausses_baisses"] += 1
            if x[0] == "derive":
                out["alerts"].append((d, x[1]))
                level_changed = p.step and d >= p.step[0]
                if not level_changed:
                    out["fausses_alertes"] += 1
        if statut == "evalue" and e.mode != "libre":
            jr = journee_reussie(count, obj, k, ee)
            out["reussie"].append(jr)
        if statut == "evalue":
            out["counts"].append((d, count))
        p.post_day(d, e.N() if e.mode == "pousser" else None)
        N = e.N()
        out["N_hist"].append(N)
        if prevN is not None and N is not None and N != prevN and e.mode == "pousser":
            jumps.append(N - prevN)
        prevN = N
        out["days"].append(dict(d=d, ouvre=ouvre, conge=conge, statut=statut, count=count, N=N, mode=e.mode,
                                R=e.R, ee=ee, k=k, court=court))
    out["jumps"] = jumps
    out["etat"] = e
    out["notif"] = notif_state
    out["persona"] = p
    return out
