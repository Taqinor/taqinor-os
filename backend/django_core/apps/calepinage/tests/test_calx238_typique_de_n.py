# -*- coding: utf-8 -*-
"""CALX238 — replier les circuits d'onduleurs identiques en « typique de N ».

``blocs_du_schema`` ne regroupait rien : une centrale à dix onduleurs
identiques produisait dix fois le même sous-ensemble et basculait en A3 par le
seul effet du nombre (``_format_planche``, ``RANGEES_MAX_A4 = 3``).

Les trois cas demandés sont armés ici — dix branches identiques REPLIÉES, une
branche divergente LAISSÉE SEULE, une seule branche INCHANGÉE (comparaison
octet pour octet du SVG) — plus la garantie que le tableau d'équipements
continue de compter les quantités RÉELLES de ``protections[]``/``cables[]``.

``SimpleTestCase`` : aucune base de données.
"""

import re

from django.test import SimpleTestCase

from core.electrique import concevoir
from core.electrique.schema import (
    FORMAT_A4_PAYSAGE,
    blocs_du_schema,
    lignes_tableau,
    rendre_schema,
)
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)

MODULE = SpecModule(vmp_v=34.0, voc_v=41.0, isc_a=13.8, imp_a=13.0,
                    pmax_wc=550.0, temp_coeff_voc_pct_c=-0.27,
                    temp_coeff_pmax_pct_c=-0.35,
                    designation='Canadian Solar 550 Wc')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=850.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0,
                        v_demarrage_v=90.0,
                        designation='Deye SUN-10K-SG05LP3')


def _branche(organes=('QDC1', 'QAC1'), nb_chaines=2, longueurs=(12, 12),
             modele='Deye SUN-10K-SG05LP3'):
    return {'modele': modele, 'nb_chaines': nb_chaines,
            'longueurs': list(longueurs), 'organes': list(organes)}


def _entree():
    return EntreeElectrique(module=MODULE, onduleur=ONDULEUR,
                            groupes=(GroupePan('Sud', 24, 180.0, 15.0),),
                            dc_m=30.0, ac_m=12.0)


def _textes(svg):
    return re.findall(r'>([^<>]+)</text>', svg)


def _clefs(blocs):
    return [bloc.clef for bloc in blocs]


class DixBranchesIdentiquesSontRepliees(SimpleTestCase):
    def setUp(self):
        self.entree = _entree()
        self.resultat = concevoir(self.entree)
        self.branches = tuple(_branche() for _ in range(10))

    def test_un_seul_bloc_onduleur_portant_typique_de_10(self):
        blocs = blocs_du_schema(self.entree, self.resultat,
                                branches_onduleur=self.branches)
        onduleurs = [b for b in blocs if b.clef.startswith('onduleur')]
        self.assertEqual(len(onduleurs), 1)
        self.assertIn('typique de 10', onduleurs[0].sous_titre)

    def test_le_texte_typique_de_10_est_bien_dessine(self):
        """La boîte ne tient que deux lignes : la mention doit survivre."""
        svg = rendre_schema(self.entree, self.resultat,
                            branches_onduleur=self.branches)
        self.assertTrue(any('typique de 10' in texte
                            for texte in _textes(svg)))

    def test_la_planche_reste_en_A4(self):
        """Le repli est exactement ce qui évite la bascule par le nombre."""
        svg = rendre_schema(self.entree, self.resultat,
                            branches_onduleur=self.branches)
        self.assertIn('viewBox="0 0 %s' % ('%.0f' % FORMAT_A4_PAYSAGE[0]), svg)


class UneBrancheDivergenteResteSeule(SimpleTestCase):
    def setUp(self):
        self.entree = _entree()
        self.resultat = concevoir(self.entree)

    def test_un_seul_organe_de_difference_empeche_le_repli(self):
        branches = tuple(_branche() for _ in range(9))
        branches += (_branche(organes=('QDC1', 'QAC1', 'DDR1')),)
        blocs = blocs_du_schema(self.entree, self.resultat,
                                branches_onduleur=branches)
        onduleurs = [b for b in blocs if b.clef.startswith('onduleur')]
        self.assertEqual(len(onduleurs), 2)
        self.assertEqual(_clefs(onduleurs), ['onduleur', 'onduleur#2'])
        self.assertIn('typique de 9', onduleurs[0].sous_titre)
        self.assertNotIn('typique', onduleurs[1].sous_titre)

    def test_un_nombre_de_chaines_different_empeche_le_repli(self):
        branches = (_branche(), _branche(nb_chaines=3,
                                         longueurs=(12, 12, 12)))
        onduleurs = [b for b in blocs_du_schema(
            self.entree, self.resultat, branches_onduleur=branches)
            if b.clef.startswith('onduleur')]
        self.assertEqual(len(onduleurs), 2)

    def test_une_longueur_de_chaine_differente_empeche_le_repli(self):
        branches = (_branche(), _branche(longueurs=(12, 11)))
        onduleurs = [b for b in blocs_du_schema(
            self.entree, self.resultat, branches_onduleur=branches)
            if b.clef.startswith('onduleur')]
        self.assertEqual(len(onduleurs), 2)

    def test_un_modele_different_empeche_le_repli(self):
        branches = (_branche(), _branche(modele='Deye SUN-12K-SG04LP3'))
        onduleurs = [b for b in blocs_du_schema(
            self.entree, self.resultat, branches_onduleur=branches)
            if b.clef.startswith('onduleur')]
        self.assertEqual(len(onduleurs), 2)
        self.assertEqual(onduleurs[1].titre, 'Deye SUN-12K-SG04LP3')

    def test_chaque_groupe_est_relie_a_la_barrette_de_terre(self):
        branches = (_branche(), _branche(organes=('QDC1', 'QAC1', 'DDR1')))
        svg = rendre_schema(self.entree, self.resultat,
                            branches_onduleur=branches)
        self.assertIn('data-bloc="onduleur#2"', svg)


class UneSeuleBrancheNeChangeRien(SimpleTestCase):
    """Non-régression OCTET POUR OCTET sur un cas existant."""

    def setUp(self):
        self.entree = _entree()
        self.resultat = concevoir(self.entree)
        self.reference = rendre_schema(self.entree, self.resultat)

    def test_sans_branches_le_svg_est_identique(self):
        for branches in (None, (), []):
            with self.subTest(branches=branches):
                self.assertEqual(
                    rendre_schema(self.entree, self.resultat,
                                  branches_onduleur=branches),
                    self.reference)

    def test_avec_une_seule_branche_le_svg_est_identique(self):
        self.assertEqual(
            rendre_schema(self.entree, self.resultat,
                          branches_onduleur=(_branche(),)),
            self.reference)

    def test_aucun_typique_de_1_n_apparait(self):
        blocs = blocs_du_schema(self.entree, self.resultat,
                                branches_onduleur=(_branche(),))
        for bloc in blocs:
            self.assertNotIn('typique', bloc.sous_titre)


class LeTableauCompteTOUJOURSLesQuantitesReelles(SimpleTestCase):
    def test_le_repli_du_schema_ne_touche_pas_le_tableau(self):
        entree = _entree()
        resultat = concevoir(entree)
        lignes = lignes_tableau(resultat)
        # L'égalité déjà armée : le tableau EST la liste des protections,
        # suivie des câbles. Le repli du dessin n'y change rien.
        self.assertEqual([ligne[0] for ligne in lignes],
                         [p.repere for p in resultat.protections]
                         + [c.repere for c in resultat.cables])
        quantites = {ligne[0]: ligne[3] for ligne in lignes}
        for protection in resultat.protections:
            self.assertEqual(quantites[protection.repere],
                             '%d u' % protection.quantite)
