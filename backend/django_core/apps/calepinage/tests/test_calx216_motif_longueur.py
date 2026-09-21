# -*- coding: utf-8 -*-
"""CALX216 — DIRE pourquoi cette longueur de chaîne a été retenue.

``_choisir_longueur`` choisissait sur deux critères ordonnés et rendait un
simple couple ``(longueur, nb_chaines)`` : le motif du choix était perdu, et la
règle fondateur du 24/08/2026 (suppression du critère « nombre de chaînes
multiple des entrées MPPT ») ne vivait que dans un commentaire.

Ce module arme trois choses :

1. le CHOIX NUMÉRIQUE ne bouge pas — un oracle rejoue à l'identique
   l'algorithme d'avant CALX216 sur douze configurations ;
2. le résultat reste un 2-uplet (déballage, égalité, re-export de
   ``apps.ventes.solar_design._choose_string_layout``) ;
3. le motif est rendu : 8 modules sur un onduleur à 2 MPPT donnent « une chaîne
   de 8 », et « 2 × 4 écartée : chaîne plus courte à critère de courant égal ».

``SimpleTestCase`` : aucune base de données.
"""

from django.test import SimpleTestCase

from core.electrique.chaines import (
    CRITERE_AUCUNE_PARTITION,
    CRITERE_CHAINE_LA_PLUS_LONGUE,
    CRITERE_COURANT_ENTREE,
    CRITERE_SEULE_PARTITION,
    MOTIF_CHAINE_PLUS_COURTE,
    MOTIF_HORS_FENETRE_BASSE,
    MOTIF_HORS_FENETRE_HAUTE,
    MOTIF_PARTITION_NON_EGALE,
    MOTIF_SURCHARGE_MPPT,
    MOTIFS_ECARTEMENT,
    _choisir_longueur,
    concevoir_chaines,
)
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)

#: Douze configurations ``(nb_modules, n_mppt, longueur_min, longueur_max,
#: imp_a, i_max_mppt_a)`` couvrant : répartition nominale, fenêtre fermée en
#: haut comme en bas, aucune partition égale, entrée MPPT saturée, plafond non
#: borné, champ d'un seul module.
CONFIGURATIONS = (
    (24, 2, 5, 22, 13.0, 26.0),
    (8, 2, 2, 22, 13.0, 26.0),
    (8, 1, 1, 22, 13.0, 26.0),
    (23, 2, 5, 22, 13.0, 26.0),
    (20, 1, 5, 22, 17.59, 26.0),
    (50, 1, 5, 22, 17.59, 17.0),
    (12, 2, 1, 10 ** 6, 13.0, 26.0),
    (5, 1, 1, 1, 13.0, 26.0),
    (30, 3, 5, 15, 9.0, 20.0),
    (16, 4, 4, 8, 6.0, 12.0),
    (36, 2, 6, 18, 11.0, 22.0),
    (1, 1, 1, 1, 0.0, 0.0),
)

#: Les trois jeux d'arguments que ``apps.ventes.tests.test_pv83_shims_electrique``
#: fait déjà traverser le ré-export — ils passent par le même oracle.
CONFIGURATIONS_SHIM = ((24, 2, 6, 20), (23, 2, 6, 20), (30, 3, 5, 15))


def _surcharge_oracle(nb_chaines, n_mppt, imp_a, i_max_mppt_a):
    """Copie VERBATIM de ``_surcharge_mppt`` d'avant CALX216."""
    if i_max_mppt_a <= 0 or imp_a <= 0:
        return False
    par_entree = -(-nb_chaines // max(1, n_mppt))
    return par_entree * imp_a > i_max_mppt_a + 1e-9


def _oracle(nb_modules, n_mppt, longueur_min, longueur_max, imp_a=0.0,
            i_max_mppt_a=0.0):
    """L'algorithme d'AVANT CALX216, recopié tel quel — la référence."""
    meilleur = (0, 0)
    meilleur_score = None
    for nb_chaines in range(1, nb_modules + 1):
        if nb_modules % nb_chaines != 0:
            continue
        longueur = nb_modules // nb_chaines
        if longueur < longueur_min or longueur > longueur_max:
            continue
        surcharge = 1 if _surcharge_oracle(nb_chaines, n_mppt, imp_a,
                                           i_max_mppt_a) else 0
        score = (surcharge, -longueur)
        if meilleur_score is None or score < meilleur_score:
            meilleur_score = score
            meilleur = (longueur, nb_chaines)
    return meilleur


def _entree_huit_modules():
    """8 modules, onduleur 2 MPPT, fenêtre ouverte à partir de 2 modules."""
    return EntreeElectrique(
        module=SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                          pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                          temp_coeff_pmax_pct_c=-0.35),
        onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=50.0, mppt_v_max=850.0,
                              v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=5.0,
                              v_demarrage_v=50.0),
        groupes=(GroupePan('Sud', 8, 180.0, 15.0),))


def _ecartee(choix, longueur):
    for partition in choix.partitions_ecartees:
        if partition.longueur == longueur:
            return partition
    return None


class LeChoixNumeriqueNeBougePas(SimpleTestCase):
    def test_douze_configurations_rendent_le_couple_d_avant(self):
        for configuration in CONFIGURATIONS:
            with self.subTest(configuration=configuration):
                self.assertEqual(tuple(_choisir_longueur(*configuration)),
                                 _oracle(*configuration))

    def test_les_arguments_du_re_export_historique_aussi(self):
        for configuration in CONFIGURATIONS_SHIM:
            with self.subTest(configuration=configuration):
                self.assertEqual(tuple(_choisir_longueur(*configuration)),
                                 _oracle(*configuration))

    def test_le_resultat_reste_un_2_uplet(self):
        """Déballage et égalité : les appelants historiques ne voient rien."""
        choix = _choisir_longueur(24, 2, 5, 22, 13.0, 26.0)
        longueur, nb_chaines = choix
        self.assertEqual((longueur, nb_chaines), (12, 2))
        self.assertEqual(choix, (12, 2))
        self.assertEqual(len(choix), 2)
        self.assertEqual(choix.longueur, 12)
        self.assertEqual(choix.nb_chaines, 2)

    def test_aucune_partition_rend_toujours_zero_zero(self):
        choix = _choisir_longueur(23, 2, 5, 22, 13.0, 26.0)
        self.assertEqual(choix, (0, 0))
        self.assertEqual(choix.critere_retenu, CRITERE_AUCUNE_PARTITION)


class LeMotifDuChoixEstRendu(SimpleTestCase):
    def test_huit_modules_sur_deux_mppt_disent_pourquoi(self):
        choix = _choisir_longueur(8, 2, 2, 22, 13.0, 26.0)
        self.assertEqual(choix, (8, 1))
        self.assertEqual(choix.critere_retenu, CRITERE_CHAINE_LA_PLUS_LONGUE)
        ecartee = _ecartee(choix, 4)
        self.assertIsNotNone(ecartee)
        self.assertEqual(ecartee.nb_chaines, 2)
        self.assertEqual(ecartee.motif, MOTIF_CHAINE_PLUS_COURTE)
        self.assertEqual(
            "%d × %d écartée : %s" % (ecartee.nb_chaines, ecartee.longueur,
                                      ecartee.motif),
            "2 × 4 écartée : chaîne plus courte à critère de courant égal")

    def test_les_quatre_motifs_de_fenetre_et_d_egalite(self):
        choix = _choisir_longueur(8, 2, 2, 6, 13.0, 26.0)
        self.assertEqual(choix, (4, 2))
        self.assertEqual(_ecartee(choix, 1).motif, MOTIF_HORS_FENETRE_BASSE)
        self.assertEqual(_ecartee(choix, 8).motif, MOTIF_HORS_FENETRE_HAUTE)
        self.assertEqual(_ecartee(choix, 3).motif, MOTIF_PARTITION_NON_EGALE)
        self.assertEqual(_ecartee(choix, 3).nb_chaines, 0)
        self.assertEqual(_ecartee(choix, 2).motif, MOTIF_CHAINE_PLUS_COURTE)

    def test_la_surcharge_d_entree_mppt_est_nommee(self):
        """Une chaîne par entrée : la partition qui empile deux chaînes de
        CS7N-710 sur une entrée à 26 A est écartée POUR CE MOTIF."""
        choix = _choisir_longueur(8, 1, 1, 22, 17.59, 26.0)
        self.assertEqual(choix, (8, 1))
        self.assertEqual(_ecartee(choix, 4).motif, MOTIF_SURCHARGE_MPPT)
        self.assertEqual(choix.critere_retenu, CRITERE_COURANT_ENTREE)

    def test_une_seule_partition_admissible_le_dit(self):
        choix = _choisir_longueur(5, 1, 5, 5, 13.0, 26.0)
        self.assertEqual(choix, (5, 1))
        self.assertEqual(choix.critere_retenu, CRITERE_SEULE_PARTITION)

    def test_aucun_motif_hors_de_la_liste_fermee(self):
        for configuration in CONFIGURATIONS:
            with self.subTest(configuration=configuration):
                choix = _choisir_longueur(*configuration)
                for partition in choix.partitions_ecartees:
                    self.assertIn(partition.motif, MOTIFS_ECARTEMENT)

    def test_toutes_les_longueurs_sont_expliquees(self):
        """Le balayage couvre 1 → nb_modules : aucune longueur sans réponse."""
        choix = _choisir_longueur(8, 2, 2, 22, 13.0, 26.0)
        self.assertEqual(
            sorted(p.longueur for p in choix.partitions_ecartees),
            [1, 2, 3, 4, 5, 6, 7])


class LeMotifRemonteDansLaRepartition(SimpleTestCase):
    def test_une_chaine_de_huit_et_son_motif(self):
        resultat = concevoir_chaines(_entree_huit_modules())
        self.assertEqual(resultat.bloquants, ())
        repartition = resultat.repartitions[0]
        self.assertEqual(repartition.longueur_chaine, 8)
        self.assertEqual(repartition.nb_chaines, 1)
        self.assertEqual(repartition.critere_longueur,
                         CRITERE_CHAINE_LA_PLUS_LONGUE)
        motifs = {p.longueur: p.motif for p in repartition.partitions_ecartees}
        self.assertEqual(motifs[4], MOTIF_CHAINE_PLUS_COURTE)
        self.assertEqual(motifs[1], MOTIF_HORS_FENETRE_BASSE)

    def test_une_longueur_imposee_ne_fabrique_aucun_motif(self):
        """L'utilisateur a tranché : publier un critère serait un motif
        inventé."""
        entree = _entree_huit_modules()
        entree = EntreeElectrique(
            module=entree.module, onduleur=entree.onduleur,
            groupes=entree.groupes, longueur_chaine_forcee=4)
        repartition = concevoir_chaines(entree).repartitions[0]
        self.assertEqual(repartition.longueur_chaine, 4)
        self.assertEqual(repartition.critere_longueur, '')
        self.assertEqual(repartition.partitions_ecartees, ())
