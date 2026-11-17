"""Exemples chiffrés des fonctions pures (spec-5a-rythme.md §7) — python exemples.py. Chaque assert est un
critère d'acceptation recalculable ; le script s'arrête au premier écart."""
import regles as R

# compte_du_jour
assert R.compte_du_jour([{'estimation': 30}] * 4 + [{'estimation': 5}] * 3)[0] == 6          # 4 + 2 micro
assert R.compte_du_jour([{'estimation': 40, 'sous_tache': True}] * 3 + [{'estimation': None}])[0] == 1
assert R.compte_du_jour([{'estimation': 15, 'routine': True}, {'estimation': 20}], activites_closes=2)[0] == 3

# statut_jour
assert R.statut_jour(True, False, 0, False, False) == 'sans_donnees'
assert R.statut_jour(False, False, 2, False, True) == 'non_ouvre'       # samedi travaillé : jamais évalué
assert R.statut_jour(True, False, 0, True, True) == 'evalue'            # plan validé, 0 fait : compte 0

# journee_reussie
assert R.journee_reussie(6, 5, 1, 1) is True
assert R.journee_reussie(6, 5, 2, 0) is False
assert R.journee_reussie(4, 5, 0, 0) is False

# palier_initial (journée type = min(médiane, moyenne) arrondie à l'inférieur)
assert R.palier_initial([5, 4, 6, 5, 3, 7, 5, 6, 4, 5]) == (5, 5)
assert R.palier_initial([9, 10, 9, 1, 2, 1, 2, 9, 10, 9]) == (6, 6)     # rafales : médiane 9, moyenne 6,2
assert R.palier_initial([3, 3, 2, 4, 3, 3, 2, 3, 4, 3], objectif_dit=5) == (5, 3)

# evaluer_bloc
e = R.Etat(palier=5, bloc=[(c, c >= 5, 40) for c in (5, 6, 5, 4, 7, 5, 3, 6, 5, 4)])
assert R.evaluer_bloc(e, 30)[0] == 'monter'                              # 7 jours sur 10 à 5 ou plus
e = R.Etat(palier=6, bloc=[(c, c >= 6, 40) for c in (5, 4, 6, 5, 3, 5, 6, 4, 5, 4)])
assert R.evaluer_bloc(e, 30)[0] == 'baisser'                             # 2 jours sur 10
e = R.Etat(palier=5, ref_taille=40, bloc=[(6, True, 20)] * 10, tailles_bloc=[20] * 60)
assert R.evaluer_bloc(e, 30)[0] == 'taille'                              # 20 min < 70 % de 40

# clore_bloc : refus -> blocs sautés 1, 2, 4 ; échec -> 42 j
e = R.Etat(palier=5, bloc=[(6, True, 40)] * 10)
e1 = R.clore_bloc(e, 30, 'monter', 'pas_maintenant')
assert (e1.palier, e1.blocs_a_sauter) == (5, 1)
e2 = R.clore_bloc(R.Etat(palier=7, meilleur_tenu=6, bloc=[(4, False, 40)] * 10), 60, 'baisser', 'oui')
assert (e2.palier, e2.echec) == (6, (7, 60, 1))
assert R.evaluer_bloc(R.Etat(palier=6, meilleur_tenu=6, echec=(7, 60, 1), bloc=[(7, True, 40)] * 10), 90)[0] is None
assert R.evaluer_bloc(R.Etat(palier=6, meilleur_tenu=6, echec=(7, 60, 1), bloc=[(7, True, 40)] * 10), 102)[0] == 'monter'

# TENIR
assert R.reference_tenir([5, 6, 4, 5, 9, 5, 4, 6, 5, 1, 5, 6, 5, 4]) == 5.0     # 70 / 14
assert R.reference_tenir([5] * 13) is None                                       # moins de 14 jours
assert R.bande_tenir(5.0) == (4.0, 6.0) and R.bande_tenir(8.0) == (6.4, 9.6)
assert R.derive_tenir(5.0, [3, 4, 3, 2, 4, 3, 3, 4, 2, 3, 4, 3, 3, 4], 80, -1) == 'sous'
assert R.derive_tenir(5.0, [7, 7, 6, 8, 7, 7, 6, 7, 8, 7, 7, 6, 7, 7], 80, -1) == 'au_dessus'
assert R.derive_tenir(5.0, [3] * 14, 80, 90) is None                     # silence de 28 jours en cours
assert R.reference_tenir([7] * 14) == 7.0
assert R.bande_tenir(2.0) == (1.0, 3.0)
assert R.derive_tenir(5.0, [5, 4, 6, 5, 5, 4, 6, 5, 5, 4, 6, 5, 5, 6], 80, -1) is None

# objectif_affiche / basculer
assert R.objectif_affiche(R.Etat()) == (5, 'defaut')
assert R.objectif_affiche(R.Etat(objectif_dit=4)) == (4, 'dit')
assert R.objectif_affiche(R.Etat(mode='libre', palier=6)) == (None, 'libre')
assert R.basculer(R.Etat(mode='tenir', R=5.6), 'pousser', 100).palier == 6
assert R.basculer(R.Etat(mode='tenir', R=5.5), 'pousser', 100).palier == 5
h = [(j, c) for j, c in zip(range(80, 100), [5, 6, 5, 4, 6, 5, 5, 6, 4, 5, 6, 5, 5, 6, 4, 5, 6, 5, 5, 6])]
assert abs(R.basculer(R.Etat(palier=6, historique=h), 'tenir', 100).R - 73 / 14) < 1e-9   # 14 derniers : 73/14 = 5,21

# sollicitations
assert R.choisir_relance({'projet_neglige', 'echeance_du_jour'}) == 'echeance_du_jour'
assert R.choisir_relance({'projet_neglige', 'derive_rythme'}) == 'derive_rythme'
assert R.choisir_relance(set()) is None
assert R.etat_decroissance([True] * 14) == 'pause'
assert R.etat_decroissance([True] * 13) == 'normal'
assert R.etat_decroissance([True] * 20 + [False]) == 'normal'
assert R.derive_pousser_journee(2, 5, False) is True
assert R.derive_pousser_journee(3, 5, False) is False
assert R.derive_pousser_journee(1, 5, True) is False
assert R.surchauffe_tenir_journee(6, 5.0) is True and R.surchauffe_tenir_journee(5, 5.0) is False
assert [R.variante(n) for n in (739572, 739573, 739574)] == [0, 1, 2]
print('exemples : tous les asserts passent')
