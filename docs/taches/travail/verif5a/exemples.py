from rythme import *

res = []


def chk(nom, got, want):
    ok = (got == want)
    res.append(ok)
    print(("OK   " if ok else "ECART"), nom, "->", got, "" if ok else f"(attendu {want})")


def tenus(counts, N):
    return [c >= N for c in counts]


# compte_du_jour
chk("4x30 + 3x5", compte_du_jour([dict(est=30)] * 4 + [dict(est=5)] * 3)[0], 6)
chk("3 sous + parent", compte_du_jour([dict(kind="sub")] * 3 + [dict(est=30)])[0], 1)
chk("routine + tache + 2 act", compte_du_jour([dict(kind="routine"), dict(est=30)], 2)[0], 3)
# statut_jour
chk("statut sans_donnees", statut_jour(True, False, 0, False, False), "sans_donnees")
chk("statut samedi 2 faites", statut_jour(False, False, 2, False, False), "non_ouvre")
chk("statut evalue", statut_jour(True, False, 0, True, True), "evalue")
# journee_reussie
chk("jr (6,5,1,1)", journee_reussie(6, 5, 1, 1), True)
chk("jr (6,5,2,0)", journee_reussie(6, 5, 2, 0), False)
chk("jr (4,5,0,0)", journee_reussie(4, 5, 0, 0), False)
# palier_initial
chk("pi 1", palier_initial([5, 4, 6, 5, 3, 7, 5, 6, 4, 5], None), (5, 5))
chk("pi rafales", palier_initial([9, 10, 9, 1, 2, 1, 2, 9, 10, 9], None), (6, 6))
chk("pi dit 5", palier_initial([3, 3, 2, 4, 3, 3, 2, 3, 4, 3], 5), (5, 3))
# evaluer_bloc
b1 = dict(N=5, tenus=tenus((5, 6, 5, 4, 7, 5, 3, 6, 5, 4), 5))
chk("bloc monter", evaluer_bloc(b1, 30), "monter")
b2 = dict(N=6, tenus=tenus((5, 4, 6, 5, 3, 5, 6, 4, 5, 4), 6))
chk("bloc baisser", evaluer_bloc(b2, 30), "baisser")
b3 = dict(N=5, tenus=[True] * 7 + [False] * 3, ref=40, ref_n=40, tailles=[20] * 40)
chk("bloc taille", evaluer_bloc(b3, 30), "taille")
# clore_bloc
e = clore_bloc(dict(N=5, tenus=[True] * 7 + [False] * 3), 30, "monter", "non")
chk("refus -> 1 bloc saute", e["skip"], 1)
e = clore_bloc(dict(N=7, tenus=[True] * 2 + [False] * 8), 60, "baisser", "oui")
chk("baisse 7->6 j60 echec", (e["N"], e["echec"]), (6, (7, 60, 1)))
e6 = dict(N=6, tenus=[True] * 7 + [False] * 3, echec=(7, 60, 1))
chk("montee 7 j90", evaluer_bloc(e6, 90), None)
chk("montee 7 j101", evaluer_bloc(e6, 101), None)
chk("montee 7 j102", evaluer_bloc(e6, 102), "monter")
# TENIR
chk("ref 14 x 5", reference_tenir([5] * 14), 5.0)
chk("ref 13", reference_tenir([5] * 13), None)
chk("ref 14x7", reference_tenir([7] * 14), 7.0)
chk("bande 5", bande_tenir(5), (4.0, 6.0))
chk("bande 8", tuple(round(x, 4) for x in bande_tenir(8)), (6.4, 9.6))
chk("bande 2", bande_tenir(2), (1.0, 3.0))
# derive : moyenne 3,2 (14 jours) -> 3.2*14 = 44.8 non entier ; on utilise 3,2 en construisant 14 jours de somme 45 = 3.214
chk("derive sous", derive_tenir(5, [3] * 8 + [4] * 6 if False else [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4], 50, None), "sous")
chk("derive au_dessus", derive_tenir(5, [7] * 13 + [6], 50, None), "au_dessus")
chk("derive silence", derive_tenir(5, [3] * 14, 50, 70), None)
# objectif_affiche
chk("obj froid", objectif_affiche(dict(mode="pousser", palier=None)), (5, "defaut"))
chk("obj dit 4", objectif_affiche(dict(mode="pousser", dit=4)), (4, "dit"))
chk("obj libre", objectif_affiche(dict(mode="libre")), (None, "libre"))
# basculer
def tenir_to_pousser(R, rond):
    e = Etat(arrondi_bascule=rond)
    e.mode = "tenir"; e.R = R; e.R_fixe = 1; e.froid = False
    e.basculer("pousser", 100)
    return e.palier
chk("TENIR R5,6 -> palier (floor)", tenir_to_pousser(5.6, "floor"), 6)
chk("TENIR R5,5 -> palier (floor)", tenir_to_pousser(5.5, "floor"), 5)
chk("TENIR R5,6 -> palier (demi-bas)", tenir_to_pousser(5.6, "bas"), 6)
chk("TENIR R5,5 -> palier (demi-bas)", tenir_to_pousser(5.5, "bas"), 5)
e = Etat(); e.froid = False; e.palier = 5
for i in range(14):
    e.hist.append(dict(jour=i, compte=5, obj=5, tenu=True, est=[]))
e.hist[0]["compte"] = 5; e.hist[1]["compte"] = 5
# somme 73 : 13 jours à 5 (65) + 8
e.hist = [dict(jour=i, compte=5, obj=5, tenu=True, est=[]) for i in range(13)] + [dict(jour=13, compte=8, obj=5, tenu=True, est=[])]
e.basculer("tenir", 14)
chk("vers TENIR 73 -> R 5,21", round(e.R, 2), 5.21)
# relance
chk("relance neglige+echeance", choisir_relance({"negligé", "echeance"}), "echeance")
chk("relance neglige+derive", choisir_relance({"negligé", "derive"}), "derive")
chk("relance vide", choisir_relance(set()), None)
# decroissance
chk("14 ignorees", etat_decroissance([True] * 14), "pause")
chk("13 ignorees", etat_decroissance([True] * 13), "normal")
chk("20 puis ouverte", etat_decroissance([True] * 20 + [False]), "normal")
# derive pousser
chk("dp (2,5,non)", derive_pousser_journee(2, 5, False), True)
chk("dp (3,5,non)", derive_pousser_journee(3, 5, False), False)
chk("dp (1,5,oui)", derive_pousser_journee(1, 5, True), False)
# variante
chk("var 739572", variante(739572), 0)
chk("var 739573", variante(739573), 1)
chk("var 739574", variante(739574), 2)
print(sum(res), "/", len(res), "OK")
