"""Reimplementation independante des regles de spec-5a-rythme.md (lue seule, code de l'auteur non consulte).

Interpretations prises (voir verif-spec-5a.md §1) :
 - bloc = 10 jours evalues CONSECUTIFS, sans recouvrement, remis a zero a chaque cloture / bascule / reponse.
 - arrondi d'affichage = demi vers le haut ; seuils 6/10 et 3/10 inclus (>= 6, <= 3).
 - zone TENIR : hors zone = strictement dehors.
"""
import math
import statistics
from datetime import date

DEFAUT = 5
PLAFOND = 12
BLOC = 10
SEUIL_HAUT = 6
SEUIL_BAS = 3


def arrondi(x):
    return int(math.floor(x + 0.5))


# ---------------------------------------------------------------- fonctions pures (spec §7)
def compte_du_jour(taches, activites=0):
    """taches : liste de dict(kind in own|sub|routine, est=min|None). -> (compte, detail)"""
    n = 0
    micro_vues = 0
    micro_comptees = 0
    for t in taches:
        k = t.get("kind", "own")
        if k in ("sub", "routine"):
            continue
        est = t.get("est")
        if est is not None and est <= 10:
            micro_vues += 1
            if micro_comptees < 2:
                micro_comptees += 1
                n += 1
        else:
            n += 1
    n += activites
    return n, {"micro_comptees": micro_comptees, "micro_vues": micro_vues}


def statut_jour(ouvre, conge, compte, plan, app):
    if conge:
        return "conge"
    if not ouvre:
        return "non_ouvre"
    if compte == 0 and not plan and not app:
        return "sans_donnees"
    return "evalue"


def journee_reussie(compte, objectif, k, e):
    if objectif is None:
        return None
    ok = compte >= objectif
    if 1 <= k <= 3:
        ok = ok and e >= 1
    return ok


def journee_type(comptes):
    return max(1, int(math.floor(min(statistics.median(comptes), statistics.mean(comptes)))))


def palier_initial(comptes10, dit):
    typ = journee_type(comptes10)
    return (dit if dit else typ), typ


def mediane_tailles(t):
    return statistics.median(t) if t else None


def garde_taille_ok(ref, ref_n, bloc_tailles):
    """True = passe (ou inapplicable)."""
    if ref is None or ref_n < 10 or len(bloc_tailles) < 10:
        return True
    return statistics.median(bloc_tailles) >= 0.7 * ref


def echec_bloque(N, jour, echec, meilleur):
    """echec = (niveau, jour, n) ; bloque la montee vers N+1."""
    if not echec:
        return False
    niv, le, n = echec
    if niv != N + 1:
        return False
    if meilleur >= N + 1:
        return False
    return jour < le + 42 * n


def evaluer_bloc(etat, jour, seuils=(SEUIL_HAUT, SEUIL_BAS)):
    """etat : dict(N, comptes[10] (deja contre l'objectif du jour: liste de bool tenu), essai, skip,
    baisse_refusee, echec, meilleur, ref, ref_n, tailles). -> 'monter'|'baisser'|'taille'|None"""
    N = etat["N"]
    tenus = sum(etat["tenus"])
    if tenus >= seuils[0] and N < PLAFOND:
        if etat.get("skip", 0) > 0:
            return None
        if echec_bloque(N, jour, etat.get("echec"), etat.get("meilleur", 0)):
            return None
        if not garde_taille_ok(etat.get("ref"), etat.get("ref_n", 0), etat.get("tailles", [])):
            return "taille"
        return "monter"
    if tenus <= seuils[1] and N > 1:
        if etat.get("baisse_refusee"):
            return None
        if etat.get("essai") and tenus > 1:
            return None
        return "baisser"
    return None


def clore_bloc(etat, jour, decision, reponse):
    """-> nouvel etat (dict copie). reponse in oui|non|None."""
    e = dict(etat)
    N = e["N"]
    # compteurs de cloture
    skip = e.get("skip", 0)
    if skip > 0:
        skip -= 1
    e["skip"] = skip
    e["baisse_refusee"] = False
    e["essai"] = False
    if sum(e["tenus"]) >= SEUIL_HAUT:
        e["meilleur"] = max(e.get("meilleur", 0), N)
    if decision == "monter":
        if reponse == "oui":
            e["N"] = N + 1
            e["essai"] = True
            e["refus"] = 0
            e["skip"] = 0
        elif reponse == "non":
            e["refus"] = e.get("refus", 0) + 1
            e["skip"] = {1: 1, 2: 2}.get(e["refus"], 4)
    elif decision == "baisser":
        if reponse == "oui":
            e["N"] = max(1, N - 1)
            old = e.get("echec")
            n = old[2] + 1 if old and old[0] == N else 1
            e["echec"] = (N, jour, n)
        elif reponse == "non":
            e["baisse_refusee"] = True
    e["tenus"] = []
    e["tailles"] = []
    return e


def rogner(comptes):
    """correction proposee : chaque jour plafonne a 2 x mediane + 1 (fenetre de 14 jours)."""
    w = comptes[-14:]
    if len(w) < 14:
        return comptes
    cap = 2 * statistics.median(w) + 1
    return [min(c, cap) for c in comptes]


def reference_tenir(comptes):
    if len(comptes) < 14:
        return None
    return sum(comptes[-14:]) / 14.0


def bande_tenir(R):
    b = max(1.0, 0.2 * R)
    return (R - b, R + b)


def derive_tenir(R, comptes, jour, silence):
    """silence = jour jusqu'auquel on se tait (None/False = pas de silence). -> 'sous'|'au_dessus'|None"""
    if silence and (silence is True or jour < silence):
        return None
    if len(comptes) < 14:
        return None
    m = sum(comptes[-14:]) / 14.0
    lo, hi = bande_tenir(R)
    if m < lo:
        return "sous"
    if m > hi:
        return "au_dessus"
    return None


def objectif_affiche(etat):
    if etat.get("mode") == "libre":
        return (None, "libre")
    if etat.get("dit"):
        return (etat["dit"], "dit")
    if etat.get("palier") is None:
        return (DEFAUT, "defaut")
    return (etat["palier"], etat.get("source", "accepte"))


def choisir_relance(cands):
    for c in ("echeance", "derive", "negligé"):
        if c in cands:
            return c
    return None


def etat_decroissance(ignorees):
    """ignorees : liste de booleens (True = ignoree), ordre chronologique."""
    run = 0
    for x in reversed(ignorees):
        if x:
            run += 1
        else:
            break
    return "pause" if run >= 14 else "normal"


def derive_pousser_journee(c15h, N, ess_fait):
    return c15h < N / 2.0 and not ess_fait


def variante(ordinal):
    return ordinal % 3


# ---------------------------------------------------------------- machine d'etat
class Proposition:
    def __init__(self, type_, jour, **kw):
        self.type = type_
        self.jour = jour
        self.__dict__.update(kw)


class Etat:
    def __init__(self, mode="pousser", dit=None, arrondi_bascule="floor"):
        self.mode = mode
        self.dit = dit
        self.arrondi_bascule = arrondi_bascule
        self.froid = True
        self.palier = None  # None tant que froid et rien dit
        self.hist = []      # jours evalues : dict(jour, compte, obj, tenu, est)
        self.cold = []
        self.cold_est = []
        self.tenus = []
        self.blocc = []
        self.tailles = []
        self.ref = None
        self.ref_n = 0
        self.ref_attend = False
        self.refus = 0
        self.skip = 0
        self.baisse_refusee = False
        self.essai = False
        self.meilleur = 0
        self.echec = None
        self.pending = None
        self.R = None
        self.R_fixe = None
        self.silence = None
        self.derive_alertes = []
        self.events = []
        self.journal_prop = []  # (jour, type, reponse)
        self.libre_depuis = None
        self.cfg = dict(B=BLOC, haut=SEUIL_HAUT, bas=SEUIL_BAS, double=None, arrondi_type="floor")

    # -- objectif
    def N(self):
        if self.mode == "libre":
            return None
        if self.mode == "tenir":
            return arrondi(self.R) if self.R is not None else (self.palier or self.dit or DEFAUT)
        if self.palier is not None:
            return self.palier
        return self.dit or DEFAUT

    def objectif_du_jour(self, court=False):
        n = self.N()
        if n is None:
            return None
        return max(1, n - 1) if court else n

    # -- debut de journee : expiration
    def debut_journee(self, jour):
        p = self.pending
        if p and jour - p.jour > 7:
            self.journal_prop.append((p.jour, p.type, "expiree"))
            self.pending = None

    # -- reponse a une proposition
    def repondre(self, jour, oui):
        p = self.pending
        if not p:
            return
        self.pending = None
        rep = "oui" if oui else "non"
        self.journal_prop.append((p.jour, p.type, rep))
        if p.type in ("monter", "baisser"):
            self.appliquer_reponse_bloc(jour, oui, p)
        elif p.type == "type":
            if oui:
                self.palier = p.typ
                self.dit = None
                self._reset_bloc()
        elif p.type == "derive":
            if oui:  # "passer a"
                self.R = arrondi(p.moyenne)
                self.R_fixe = jour
            # silence deja pose a la creation
        elif p.type == "garde_taille":
            if oui:  # "Mes taches ont changé"
                self.ref = None
                self.ref_attend = True

    def _reset_bloc(self):
        self.tenus = []
        self.tailles = []

    # -- fin de journee (statut deja calcule)
    def fin_journee(self, jour, statut, compte, est, court=False):
        ev = []
        if statut != "evalue":
            return ev
        obj = self.objectif_du_jour(court)
        tenu = (obj is not None and compte >= obj)
        self.hist.append(dict(jour=jour, compte=compte, obj=obj, tenu=tenu, est=list(est)))
        if self.mode == "libre":
            return ev
        if self.mode == "tenir":
            return self._tenir(jour)
        return self._pousser(jour, compte, est, tenu)

    # -- POUSSER
    def _pousser(self, jour, compte, est, tenu):
        ev = []
        if self.froid:
            self.cold.append(compte)
            self.cold_est += [x for x in est if x is not None]
            if len(self.cold) == 10:
                pal, typ = palier_initial(self.cold, self.dit)
                if self.cfg["arrondi_type"] == "round":
                    typ = max(1, arrondi(min(statistics.median(self.cold), statistics.mean(self.cold))))
                    pal = self.dit if self.dit else typ
                self.froid = False
                if len(self.cold_est) >= 10:
                    self.ref = statistics.median(self.cold_est)
                    self.ref_n = len(self.cold_est)
                if self.dit:
                    self.palier = self.dit
                    if typ != self.dit:
                        self.pending = Proposition("type", jour, typ=typ)
                        ev.append(("type", typ))
                else:
                    self.palier = pal
                    ev.append(("palier_initial", pal))
                self.tenus = []
                self.tailles = []
            return ev
        self.tenus.append(tenu)
        self.blocc.append(compte)
        self.tailles += [x for x in est if x is not None]
        B = self.cfg["B"]
        if len(self.tenus) < B:
            return ev
        # cloture du bloc
        N = self.palier
        if self.ref_attend:
            if len([x for x in self.tailles]) >= 10:
                self.ref = statistics.median(self.tailles)
                self.ref_n = len(self.tailles)
            self.ref_attend = False
            ref_ok_now = False
        st = dict(N=N, tenus=list(self.tenus), essai=self.essai, skip=self.skip,
                  baisse_refusee=self.baisse_refusee, echec=self.echec, meilleur=self.meilleur,
                  ref=self.ref, ref_n=self.ref_n, tailles=list(self.tailles))
        dec = evaluer_bloc(st, jour, (self.cfg["haut"], self.cfg["bas"]))
        if dec in ("monter", "taille") and self.cfg.get("garde_moy") is not None and statistics.mean(self.blocc) < N - self.cfg["garde_moy"]:
            dec = None
        self.blocc = []
        # compteurs de cloture communs
        if self.skip > 0:
            self.skip -= 1
        self.baisse_refusee = False
        self.essai = False
        if sum(self.tenus) >= SEUIL_HAUT:
            self.meilleur = max(self.meilleur, N)
        n_tenus = sum(self.tenus)
        med = statistics.median(self.tailles) if self.tailles else None
        self.tenus = []
        self.tailles = []
        if dec in ("monter", "baisser"):
            step = 2 if (dec == "monter" and self.cfg["double"] and n_tenus >= self.cfg["double"] and N + 2 <= PLAFOND) else 1
            self.pending = Proposition(dec, jour, N=N, n_tenus=n_tenus, step=step, garder=(dec == "monter" and self.refus >= 2))
            ev.append((dec, N))
        elif dec == "taille":
            self.pending = Proposition("garde_taille", jour, med=med, ref=self.ref)
            ev.append(("garde_taille", med))
        return ev

    def appliquer_reponse_bloc(self, jour, oui, p):
        N = self.palier
        if p.type == "monter":
            if oui:
                self.palier = min(PLAFOND, N + getattr(p, "step", 1))
                self.essai = True
                self.refus = 0
                self.skip = 0
                self.baisse_refusee = False
                self.tenus = []
                self.tailles = []
            else:
                self.refus += 1
                self.skip = {1: 1, 2: 2}.get(self.refus, 4)
        elif p.type == "baisser":
            if oui:
                old = self.echec
                n = old[2] + 1 if old and old[0] == N else 1
                self.echec = (N, jour, n)
                self.palier = max(1, N - 1)
                self.essai = False
                self.tenus = []
                self.tailles = []
            else:
                self.baisse_refusee = True

    # -- TENIR
    def _tenir(self, jour):
        ev = []
        last = [h for h in self.hist if jour - h["jour"] <= 42]
        rg = rogner if self.cfg.get("rogner") else (lambda x: x)
        if self.R_fixe is None:
            r = reference_tenir(rg([h["compte"] for h in last]))
            if r is not None:
                self.R = r
                self.R_fixe = jour
            return ev
        since = [h for h in self.hist if h["jour"] > self.R_fixe and jour - h["jour"] <= 42]
        if len(since) < 14:
            return ev
        comptes = rg([h["compte"] for h in since])
        res = derive_tenir(self.R, comptes, jour, self.silence)
        if res:
            m = sum(comptes[-14:]) / 14.0
            self.silence = jour + 28
            self.pending = Proposition("derive", jour, sens=res, moyenne=m)
            self.derive_alertes.append((jour, res))
            ev.append(("derive", res))
        return ev

    # -- bascules
    def basculer(self, mode, jour):
        old = self.mode
        if mode == old:
            return
        last = [h for h in self.hist if jour - h["jour"] <= 42]
        self.pending = None
        if mode == "tenir":
            r = reference_tenir([h["compte"] for h in last])
            if r is not None:
                self.R = r
                self.R_fixe = jour
            else:
                self.R = float(self.palier or self.dit or DEFAUT)
                self.R_fixe = None
            self.silence = None
        elif mode == "pousser":
            if old == "tenir":
                if self.R is not None:
                    if self.arrondi_bascule == "floor":
                        self.palier = max(1, int(math.floor(self.R)))
                    else:  # demi vers le bas
                        self.palier = max(1, int(math.ceil(self.R - 0.5)))
                self.froid = False
            elif old == "libre":
                c = [h["compte"] for h in last[-10:]]
                self.palier = journee_type(c) if len(c) >= 10 else DEFAUT
                self.froid = False
                if self.palier is None:
                    self.palier = DEFAUT
            self.dit = None if old != "pousser" else self.dit
        self.mode = mode
        # une bascule remet blocs, refus et essai a zero ; meilleur et echecs gardes
        self.tenus = []
        self.tailles = []
        self.refus = 0
        self.skip = 0
        self.essai = False
        self.baisse_refusee = False
        self.ref = None
        self.ref_attend = True
