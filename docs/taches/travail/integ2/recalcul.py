"""Script JETABLE du second intégrateur (règles et textes).

Recalcule, avec les règles FINALES de `reference/regles.md` (spec-5a + verif-spec-5a + arbitrage A2) :
  - les 49 exemples chiffrés de spec-5a §7 (liste de verif5a/exemples.py), mis à jour ;
  - 12 exemples ajoutés par A2 (seuil 5/10, demie vers le bas, plafonnement, objectif dit) ;
  - les exemples de santé de projet (spec-4 §E-F corrigée) ;
  - les dates et jours de semaine de la table de l'analyseur.
Bibliothèque standard seule. Aucune donnée réelle.
"""
import math
import statistics
from datetime import date, timedelta

DEFAUT, PLAFOND, SEUIL_MONTER, SEUIL_BAISSER = 5, 12, 5, 3
ATTENTE_REFUS = (0, 1, 2, 4)
ATTENTE_ECHEC = 42


def arrondir(x):
    """Au plus proche, la demie vers le bas."""
    return int(math.ceil(x - 0.5))


def compte_du_jour(taches, activites=0):
    normales = micro = 0
    for t in taches:
        if t.get("sous_tache") or t.get("routine"):
            continue
        if t.get("estimation") is not None and t["estimation"] <= 10:
            micro += 1
        else:
            normales += 1
    return normales + min(micro, 2) + activites


def statut_jour(ouvre, conge, compte, plan, app):
    if conge:
        return "conge"
    if not ouvre:
        return "non_ouvre"
    if compte == 0 and not plan and not app:
        return "sans_donnees"
    return "evalue"


def journee_reussie(compte, objectif, choisis, faits):
    if objectif is None:
        return None
    return compte >= objectif and (choisis == 0 or faits >= 1)


def journee_type(comptes):
    return max(1, arrondir(min(statistics.median(comptes), statistics.mean(comptes))))


def palier_initial(comptes10, dit):
    """Rév. 2 : rien n'est imposé. -> (palier appliqué, journée type, carte proposée)."""
    t = journee_type(comptes10)
    if dit:
        return dit, t, ("journee_type" if t != dit else None)
    return None, t, ("premier" if t != DEFAUT else None)


def repondre_premier(reponse, type_):
    return (type_, "accepte") if reponse == "oui" else (DEFAUT, "accepte")


def semaine_courte(statuts):
    return sum(1 for s in statuts if s == "sans_donnees") >= 3


def plafonner_jours(comptes):
    cap = 2 * statistics.median(comptes) + 1
    return [min(c, cap) for c in comptes]


def evaluer_bloc(e, jour):
    N, tenus = e["N"], sum(e["tenus"])
    if tenus >= SEUIL_MONTER and N < PLAFOND:
        if e.get("skip", 0) > 0:
            return None
        ech = e.get("echec")
        if ech and ech[0] == N + 1 and e.get("meilleur", 0) < N + 1 and jour < ech[1] + ATTENTE_ECHEC * ech[2]:
            return None
        ref, tailles = e.get("ref"), e.get("tailles", [])
        if ref is not None and e.get("ref_n", 0) >= 10 and len(tailles) >= 10 and statistics.median(tailles) < 0.7 * ref:
            return "taille"
        return "monter"
    if tenus <= SEUIL_BAISSER and N > 1 and not e.get("baisse_refusee") and not (e.get("essai") and tenus > 1):
        return "baisser"
    return None


def clore_bloc(e, jour, decision, reponse):
    e2, N, tenus = dict(e), e["N"], sum(e["tenus"])
    if tenus >= SEUIL_MONTER:
        e2["meilleur"] = max(e.get("meilleur", 0), N)
    e2["skip"] = max(0, e.get("skip", 0) - 1)
    e2["baisse_refusee"] = False
    e2["essai"] = False
    if decision == "monter":
        if reponse == "oui":
            e2.update(N=N + 1, refus=0, skip=0, essai=True)
        else:
            e2["refus"] = e.get("refus", 0) + 1
            e2["skip"] = ATTENTE_REFUS[min(e2["refus"], 3)]
    elif decision == "baisser":
        if reponse == "oui":
            e2["N"] = max(1, N - 1)
            if N > e2.get("meilleur", 0):
                old = e.get("echec")
                e2["echec"] = (N, jour, old[2] + 1 if old and old[0] == N else 1)
        else:
            e2["baisse_refusee"] = True
    e2["tenus"] = []
    return e2


def reference_tenir(comptes):
    if len(comptes) < 14:
        return None
    w = plafonner_jours(comptes[-14:])
    return sum(w) / 14.0


def bande_tenir(R):
    b = max(1.0, 0.2 * R)
    return (R - b, R + b)


def derive_tenir(R, comptes, jour, silence):
    if silence is not None and jour < silence:
        return None
    m = reference_tenir(comptes)
    if m is None:
        return None
    lo, hi = bande_tenir(R)
    return "sous" if m < lo else ("au_dessus" if m > hi else None)


def objectif_affiche(e):
    if e.get("mode") == "libre":
        return (None, "libre")
    if e.get("mode") == "tenir" and e.get("R") is not None:
        return (max(1, arrondir(e["R"])), "calcule")
    if e.get("palier") is None:
        return (DEFAUT, "defaut")
    return (e["palier"], e.get("source", "accepte"))


def basculer_vers_pousser_depuis_tenir(R):
    return max(1, arrondir(R))


def objectif_dit(e, nombre=None, sens=None):
    actuel = objectif_affiche(e)[0] or DEFAUT
    if nombre is not None:
        if not 1 <= nombre <= PLAFOND:
            return "400"
        cible = nombre
    else:
        cible = min(PLAFOND, actuel + 1) if sens == "plus" else max(1, actuel - 1)
    froid = e.get("bloc_debut") is None
    return dict(mode="pousser", palier=cible, source="dit", refus=0, skip=0, essai=False,
                baisse_refusee=False, bloc_debut=None if froid else "J+1", froid=froid)


def choisir_relance(c):
    for k in ("echeance", "derive", "neglige"):
        if k in c:
            return k
    return None


def etat_decroissance(ign):
    run = 0
    for x in reversed(ign):
        if not x:
            break
        run += 1
    return "pause" if run >= 14 else "normal"


def derive_pousser_journee(c15, N, ess):
    return c15 < N / 2.0 and not ess


def variante(o):
    return o % 3


RES = []


def chk(n, got, want):
    ok = got == want
    RES.append(ok)
    print(("OK   " if ok else "ECART"), f"{len(RES):>2}", n, "->", got, "" if ok else f"(attendu {want})")


def tenus(c, N):
    return [x >= N for x in c]


print("=== 49 exemples de spec-5a §7, règles finales ===")
chk("compte 4x30+3x5", compte_du_jour([dict(estimation=30)] * 4 + [dict(estimation=5)] * 3), 6)
chk("compte 3 sous + parent", compte_du_jour([dict(sous_tache=True)] * 3 + [dict(estimation=30)]), 1)
chk("compte routine + tache + 2 act", compte_du_jour([dict(routine=True), dict(estimation=30)], 2), 3)
chk("statut (oui,non,0,non,non)", statut_jour(True, False, 0, False, False), "sans_donnees")
chk("statut samedi 2 faites", statut_jour(False, False, 2, False, False), "non_ouvre")
chk("statut (oui,non,0,oui,oui)", statut_jour(True, False, 0, True, True), "evalue")
chk("reussie (6,5,1,1)", journee_reussie(6, 5, 1, 1), True)
chk("reussie (6,5,2,0)", journee_reussie(6, 5, 2, 0), False)
chk("reussie (4,5,0,0)", journee_reussie(4, 5, 0, 0), False)
chk("palier_initial regulier", palier_initial([5, 4, 6, 5, 3, 7, 5, 6, 4, 5], None), (None, 5, None))
chk("palier_initial rafales", palier_initial([9, 10, 9, 1, 2, 1, 2, 9, 10, 9], None), (None, 6, "premier"))
chk("palier_initial dit 5", palier_initial([3, 3, 2, 4, 3, 3, 2, 3, 4, 3], 5), (5, 3, "journee_type"))
chk("bloc N5 (5,6,5,4,7,5,3,6,5,4)", evaluer_bloc(dict(N=5, tenus=tenus((5, 6, 5, 4, 7, 5, 3, 6, 5, 4), 5)), 30), "monter")
chk("bloc N6 (5,4,6,5,3,5,6,4,5,4)", evaluer_bloc(dict(N=6, tenus=tenus((5, 4, 6, 5, 3, 5, 6, 4, 5, 4), 6)), 30), "baisser")
chk("bloc tailles 20 ref 40", evaluer_bloc(dict(N=5, tenus=[True] * 7 + [False] * 3, ref=40, ref_n=40, tailles=[20] * 40), 30), "taille")
chk("clore refus -> 1 bloc saute", clore_bloc(dict(N=5, tenus=[True] * 7 + [False] * 3), 30, "monter", "pas_maintenant")["skip"], 1)
e = clore_bloc(dict(N=7, tenus=[True] * 2 + [False] * 8), 60, "baisser", "oui")
chk("clore baisse 7->6 j60", (e["N"], e["echec"]), (6, (7, 60, 1)))
e6 = dict(N=6, tenus=[True] * 7 + [False] * 3, echec=(7, 60, 1))
chk("montee vers 7 j90", evaluer_bloc(e6, 90), None)
chk("montee vers 7 j101", evaluer_bloc(e6, 101), None)
chk("montee vers 7 j102", evaluer_bloc(e6, 102), "monter")
chk("ref 14x5", reference_tenir([5] * 14), 5.0)
chk("ref 13 jours", reference_tenir([5] * 13), None)
chk("ref 14x7", reference_tenir([7] * 14), 7.0)
chk("bande 5", bande_tenir(5), (4.0, 6.0))
chk("bande 8", tuple(round(x, 4) for x in bande_tenir(8)), (6.4, 9.6))
chk("bande 2", bande_tenir(2), (1.0, 3.0))
chk("derive R5, 11x3+3x4 (moy 3,21)", derive_tenir(5, [3] * 11 + [4] * 3, 50, None), "sous")
chk("derive R5, 13x7+6 (moy 6,93)", derive_tenir(5, [7] * 13 + [6], 50, None), "au_dessus")
chk("derive silence jusqu'au j70", derive_tenir(5, [3] * 14, 50, 70), None)
chk("objectif froid", objectif_affiche(dict(mode="pousser", palier=None)), (5, "defaut"))
chk("objectif dit 4", objectif_affiche(dict(mode="pousser", palier=4, source="dit")), (4, "dit"))
chk("objectif libre", objectif_affiche(dict(mode="libre")), (None, "libre"))
chk("TENIR R5,6 -> pousser", basculer_vers_pousser_depuis_tenir(5.6), 6)
chk("TENIR R5,5 -> pousser", basculer_vers_pousser_depuis_tenir(5.5), 5)
chk("TENIR R4,5 -> pousser", basculer_vers_pousser_depuis_tenir(4.5), 4)
chk("TENIR R5,51 -> pousser", basculer_vers_pousser_depuis_tenir(5.51), 6)
chk("vers TENIR, 13x5 + 8 -> R", round(reference_tenir([5] * 13 + [8]), 2), 5.21)
chk("relance {neglige, echeance}", choisir_relance({"neglige", "echeance"}), "echeance")
chk("relance {neglige, derive}", choisir_relance({"neglige", "derive"}), "derive")
chk("relance vide", choisir_relance(set()), None)
chk("14 ignorees", etat_decroissance([True] * 14), "pause")
chk("13 ignorees", etat_decroissance([True] * 13), "normal")
chk("20 ignorees puis 1 ouverte", etat_decroissance([True] * 20 + [False]), "normal")
chk("derive pousser (2,5,non)", derive_pousser_journee(2, 5, False), True)
chk("derive pousser (3,5,non)", derive_pousser_journee(3, 5, False), False)
chk("derive pousser (1,5,oui)", derive_pousser_journee(1, 5, True), False)
chk("variante 739572", variante(739572), 0)
chk("variante 739573", variante(739573), 1)
chk("variante 739574", variante(739574), 2)
n49 = sum(RES)
print(n49, "/", len(RES), "OK")

print("=== 12 exemples ajoutés par A2 ===")
chk("A2 bloc N5 5/10 tenus -> monter", evaluer_bloc(dict(N=5, tenus=tenus((5, 5, 5, 5, 5, 4, 4, 4, 4, 4), 5)), 30), "monter")
chk("A2 bloc N5 4/10 tenus -> rien", evaluer_bloc(dict(N=5, tenus=tenus((5, 5, 5, 5, 4, 4, 4, 4, 4, 4), 5)), 30), None)
chk("A2 bloc N5 3/10 tenus -> baisser", evaluer_bloc(dict(N=5, tenus=tenus((5, 5, 5, 4, 4, 4, 4, 4, 4, 4), 5)), 30), "baisser")
chk("A2 essai, 2 tenus -> rien", evaluer_bloc(dict(N=6, essai=True, tenus=[True] * 2 + [False] * 8), 30), None)
chk("A2 essai, 1 tenu -> baisser", evaluer_bloc(dict(N=6, essai=True, tenus=[True] + [False] * 9), 30), "baisser")
chk("A2 meilleur_tenu a 5/10", clore_bloc(dict(N=6, tenus=[True] * 5 + [False] * 5), 30, None, None)["meilleur"], 6)
chk("A2 plafonner 13x5 + 30", plafonner_jours([5] * 13 + [30])[-1], 11)
chk("A2 R avec un jour a 30", round(reference_tenir([5] * 13 + [30]), 2), 5.43)
chk("A2 derive R5 avec un jour a 30", derive_tenir(5, [5] * 13 + [30], 50, None), None)
chk("A2 dit 7 sur palier 5", (objectif_dit(dict(palier=5, source="accepte", bloc_debut="x"), nombre=7)["palier"]), 7)
chk("A2 plus sur palier 5 ; moins sur palier 1", (objectif_dit(dict(palier=5, bloc_debut="x"), sens="plus")["palier"],
                                                  objectif_dit(dict(palier=1, bloc_debut="x"), sens="moins")["palier"]), (6, 1))
chk("A2 dit 15 -> refus", objectif_dit(dict(palier=5), nombre=15), "400")
print("=== 4 exemples ajoutés par la révision 2 ===")
chk("premier [Oui, 3] sur [3]*10", repondre_premier("oui", palier_initial([3] * 10, None)[1]), (3, "accepte"))
chk("premier [Garder 5]", repondre_premier("garder", 3), (5, "accepte"))
chk("semaine courte : 2 evalues + 3 sans_donnees", semaine_courte(["evalue"] * 2 + ["sans_donnees"] * 3), True)
chk("semaine normale : 3 evalues + 2 sans_donnees", semaine_courte(["evalue"] * 3 + ["sans_donnees"] * 2), False)
print("journee type demi-bas : moyenne 4,5 mediane 5 ->", journee_type([4, 5, 4, 5, 4, 5, 4, 5, 4, 5]),
      "; moyenne 5,5 mediane 5,5 ->", journee_type([5, 6, 5, 6, 5, 6, 5, 6, 5, 6]))
print("sans plafond, R aurait ete", round((65 + 30) / 14, 2))

print("=== sante (spec-4 corrigee) ===")
FER = {date(2026, 11, 6), date(2026, 11, 18)}


def travailles(du_excl, au_incl, feries=(), conges=()):
    j, n = du_excl + timedelta(1), 0
    while j <= au_incl:
        if j.weekday() < 5 and j not in feries and j not in conges:
            n += 1
        j += timedelta(1)
    return n


J = date(2026, 11, 17)
print("a_l_arret ref 03/11, sans ferie :", travailles(date(2026, 11, 3), J))
print("a_l_arret ref 03/11, 06/11 ferie :", travailles(date(2026, 11, 3), J, {date(2026, 11, 6)}))
conge = {date(2026, 11, 2) + timedelta(k) for k in range(12)}
print("retour de conge (ref 30/10, conge 02-13/11, 06/11 ferie) :", travailles(date(2026, 10, 30), J, {date(2026, 11, 6)}, conge))
print("projet neuf cree 03/11, rien fait :", travailles(date(2026, 11, 3), J))
print("echeance menacee d : besoin", math.ceil(12 * 20 / 8), "reste 15")


def neglige(p):
    out = []
    for n, (pr, d, act, anc) in p.items():
        lower = [(q, dq) for q, (pq, dq, _, _) in p.items() if pq < pr and dq >= 1]
        if act >= 1 and anc >= 14 and d == 0 and lower:
            out.append((n, max(lower, key=lambda x: x[1])[0]))
    return out


print("neglige A3/0 B2/4 C1/1 :", neglige({"A": (3, 0, 1, 20), "B": (2, 4, 1, 20), "C": (1, 1, 1, 20)}))
print("neglige A3/0 B2/0 C1/1 :", neglige({"A": (3, 0, 1, 20), "B": (2, 0, 1, 20), "C": (1, 1, 1, 20)}))
print("neglige tous 0 :", neglige({"A": (3, 0, 1, 20), "B": (2, 0, 1, 20), "C": (1, 0, 1, 20)}))

print("=== dates de la table de l'analyseur (repere mar. 17/11/2026 10:00) ===")
NOMS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
for d in [date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21), date(2026, 11, 23),
          date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 30), date(2026, 12, 1), date(2026, 12, 3),
          date(2026, 12, 5), date(2027, 1, 3), date(2027, 6, 5), date(2026, 11, 27)]:
    print(d.strftime("%d/%m/%Y"), NOMS[d.weekday()])
print("in 2 weeks :", J + timedelta(14), "; dans 3 jours :", J + timedelta(3))
print("lundi vu un lundi 23/11 :", date(2026, 11, 23) + timedelta(7))
print("ordinal 17/11/2026 % 3 :", J.toordinal() % 3)
