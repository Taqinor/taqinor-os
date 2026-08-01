"""AOF158 — la cascade inverse tombe au CENTIME sur le cas réel.

Cas reproduit (dossier FRDISI du 27/07) :
    coût de revient 2 666 600 HT + bénéfice net visé 1 500 000 HT
    → total HT 4 166 600 · TVA 20 % 833 320 · TTC 4 999 920
    → marge 36,0 %, délibérément sous la barre psychologique des 5 000 000.

Le jeu de lignes ci-dessous est une reconstitution à 13 lignes du bordereau
réel (qui en compte 30 sur 4 sections) : les PU y sont ceux du dossier —
modules 2 950/U, onduleurs 78 000/U, batteries 2 600/kWh, coffrets DC 4 500,
AC 8 500, TGPV 15 000, station météo 50 000, afficheur 39 500, EMS 200 000,
génie civil 120 000, essais/DOE 70 000. La ligne d'ajustement désignée est
« Études d'exécution » ; sur cette reconstitution elle se solde à 261 800 (le
bordereau complet la porte à 262 000 — c'est le propre d'une ligne
d'ajustement de recevoir le résidu).

Run :
    python manage.py test apps.ao.tests.test_aof_cascade_solveur -v2
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.ao.fabrique.cascade import (
    CascadeImpossible, arrondir_pu, lignes_du_bordereau, pas_metier,
    resoudre_cascade, total_de_reference,
)
from apps.ao.fabrique.cascade_controles import (
    ALERTE, REFUS, PrixHorsBande, controler_fourchettes, verifier_fourchettes,
)

COUT_REVIENT = Decimal('2666600')
BENEFICE_VISE = Decimal('1500000')
CIBLE_HT = Decimal('4166600')
TVA_ATTENDUE = Decimal('833320')
TTC_ATTENDU = Decimal('4999920')
SEUIL = Decimal('5000000')
LIGNE_AJUSTEMENT = 13


def lignes_reference():
    return [
        {'numero': 1, 'designation': 'Module photovoltaïque 625 Wc',
         'famille': 'module', 'unite': 'U', 'quantite': Decimal('560'),
         'pu_reference': Decimal('2950')},
        {'numero': 2, 'designation': 'Onduleur 110 kW', 'famille': 'onduleur',
         'unite': 'U', 'quantite': Decimal('3'),
         'pu_reference': Decimal('78000')},
        {'numero': 3, 'designation': 'Batterie lithium', 'famille': 'batterie',
         'unite': 'kWh', 'quantite': Decimal('288'),
         'pu_reference': Decimal('2600')},
        {'numero': 4, 'designation': 'Coffret DC', 'famille': 'coffret_dc',
         'unite': 'U', 'quantite': Decimal('6'),
         'pu_reference': Decimal('4500')},
        {'numero': 5, 'designation': 'Coffret AC', 'famille': 'coffret_ac',
         'unite': 'U', 'quantite': Decimal('3'),
         'pu_reference': Decimal('8500')},
        {'numero': 6, 'designation': 'TGPV', 'famille': 'tgpv', 'unite': 'U',
         'quantite': Decimal('1'), 'pu_reference': Decimal('15000')},
        {'numero': 7, 'designation': 'Station météo',
         'famille': 'station_meteo', 'unite': 'U', 'quantite': Decimal('1'),
         'pu_reference': Decimal('50000')},
        {'numero': 8, 'designation': 'Afficheur pédagogique',
         'famille': 'afficheur', 'unite': 'U', 'quantite': Decimal('1'),
         'pu_reference': Decimal('39500')},
        {'numero': 9, 'designation': 'EMS et supervision', 'famille': 'ems',
         'unite': 'Ens.', 'quantite': Decimal('1'),
         'pu_reference': Decimal('200000')},
        {'numero': 10, 'designation': 'Génie civil',
         'famille': 'genie_civil', 'unite': 'Ens.', 'quantite': Decimal('1'),
         'pu_reference': Decimal('120000')},
        {'numero': 11, 'designation': 'Essais et DOE', 'famille': 'essais',
         'unite': 'Ens.', 'quantite': Decimal('1'),
         'pu_reference': Decimal('70000')},
        {'numero': 12, 'designation': 'Structure porteuse et câblage',
         'famille': 'structure', 'unite': 'Ens.', 'quantite': Decimal('1'),
         'pu_reference': Decimal('723000')},
        {'numero': LIGNE_AJUSTEMENT, 'designation': "Études d'exécution",
         'famille': 'etudes', 'unite': 'Ens.', 'quantite': Decimal('1'),
         'pu_reference': Decimal('261800')},
    ]


def cascade(**surcharges):
    parametres = {
        'cout_revient_ht': COUT_REVIENT,
        'benefice_net_vise_ht': BENEFICE_VISE,
        'ligne_ajustement': LIGNE_AJUSTEMENT,
        'seuil_psychologique': SEUIL,
    }
    parametres.update(surcharges)
    lignes = parametres.pop('lignes', None) or lignes_reference()
    return resoudre_cascade(lignes, **parametres)


class CasReelTest(SimpleTestCase):
    def test_le_total_tombe_au_centime_sur_la_cible(self):
        plan = cascade()
        self.assertEqual(plan['cible_ht'], CIBLE_HT)
        self.assertEqual(plan['total_ht'], CIBLE_HT)
        # L'invariant DUR, recalculé indépendamment du solveur :
        somme = sum((Decimal(str(ligne['quantite'])) * ligne['pu']
                     for ligne in plan['lignes']), Decimal('0'))
        self.assertEqual(somme, CIBLE_HT)

    def test_la_tva_et_le_ttc_sont_ceux_du_dossier(self):
        plan = cascade()
        self.assertEqual(plan['tva'], TVA_ATTENDUE)
        self.assertEqual(plan['total_ttc'], TTC_ATTENDU)

    def test_la_marge_est_de_36_pourcent(self):
        self.assertEqual(cascade()['marge_pct'], Decimal('36.0'))

    def test_le_ttc_reste_sous_la_barre_des_cinq_millions(self):
        self.assertLess(cascade()['total_ttc'], SEUIL)

    def test_le_depassement_du_seuil_est_refuse_pas_rabote(self):
        with self.assertRaises(CascadeImpossible) as capture:
            cascade(benefice_net_vise_ht=Decimal('2000000'))
        self.assertIn('seuil', str(capture.exception))
        self.assertIn('jamais raboter', str(capture.exception))


class PrixCrediblesTest(SimpleTestCase):
    def test_les_pas_metier_suivent_l_ordre_de_grandeur(self):
        self.assertEqual(pas_metier(Decimal('900')), Decimal('50'))
        self.assertEqual(pas_metier(Decimal('2950')), Decimal('50'))
        self.assertEqual(pas_metier(Decimal('78000')), Decimal('500'))
        self.assertEqual(pas_metier(Decimal('262000')), Decimal('1000'))

    def test_les_douze_PU_reels_du_dossier_tombent_juste(self):
        """Le pas est calibré sur le dossier, pas l'inverse.

        Un pas de 100 sous 10 000 aurait remonté « modules 2 950 » à 3 000 —
        changer un prix réel pour satisfaire la règle d'arrondi.
        """
        for pu in ('2950', '2600', '4500', '8500', '15000', '39500', '50000',
                   '70000', '78000', '120000', '200000', '262000'):
            valeur = Decimal(pu)
            self.assertEqual(arrondir_pu(valeur), valeur, pu)

    def test_aucun_pu_ne_traine_de_centimes(self):
        """Une homothétie brute sortirait 2 947,33 — pas ce solveur."""
        plan = cascade(benefice_net_vise_ht=Decimal('1437000'))
        for ligne in plan['lignes']:
            if ligne['numero'] == LIGNE_AJUSTEMENT:
                continue
            pas = pas_metier(ligne['pu'])
            self.assertEqual(ligne['pu'] % pas, Decimal('0'),
                             '{} → {}'.format(ligne['designation'],
                                              ligne['pu']))

    def test_un_pu_n_est_jamais_arrondi_a_zero(self):
        self.assertEqual(arrondir_pu(Decimal('3')), Decimal('50'))
        self.assertEqual(arrondir_pu(Decimal('0')), Decimal('0'))

    def test_le_total_de_reference_est_la_base_de_l_homothetie(self):
        self.assertEqual(total_de_reference(lignes_reference()), CIBLE_HT)
        self.assertEqual(cascade()['facteur'], Decimal('1'))


class IdempotenceTest(SimpleTestCase):
    def test_rejouer_la_cascade_ne_change_aucun_pu(self):
        premier = cascade()
        rejouees = [
            dict(ligne, pu_reference=ligne['pu']) for ligne in premier['lignes']
        ]
        second = resoudre_cascade(
            rejouees, cout_revient_ht=COUT_REVIENT,
            benefice_net_vise_ht=BENEFICE_VISE,
            ligne_ajustement=LIGNE_AJUSTEMENT, seuil_psychologique=SEUIL)
        self.assertEqual([ligne['pu'] for ligne in second['lignes']],
                         [ligne['pu'] for ligne in premier['lignes']])
        self.assertEqual(second['total_ht'], premier['total_ht'])

    def test_deux_executions_identiques_donnent_le_meme_plan(self):
        self.assertEqual([ligne['pu'] for ligne in cascade()['lignes']],
                         [ligne['pu'] for ligne in cascade()['lignes']])


class LigneAjustementTest(SimpleTestCase):
    def test_la_ligne_designee_absorbe_le_residu(self):
        plan = cascade()
        ajustement = [ligne for ligne in plan['lignes']
                      if ligne['numero'] == LIGNE_AJUSTEMENT][0]
        self.assertTrue(ajustement.get('ajustement'))
        self.assertEqual(ajustement['pu'], Decimal('261800'))

    def test_une_ligne_d_ajustement_inconnue_est_refusee(self):
        with self.assertRaises(CascadeImpossible) as capture:
            cascade(ligne_ajustement=999)
        self.assertIn('nulle part où aller', str(capture.exception))

    def test_un_residu_non_soldable_est_nomme_pas_masque(self):
        """Une quantité qui ne divise pas le résidu ne solde pas au centime.

        Le résidu vaut ici 261 800 ; réparti sur 3 unités il tombe à
        87 266,666… — donc 0,01 DH d'écart après quantification. Le solveur
        le NOMME au lieu de laisser filer un centime dans l'invariant.
        """
        lignes = lignes_reference()
        lignes[-1]['quantite'] = Decimal('3')
        lignes[-1]['pu_reference'] = Decimal('87267')
        with self.assertRaises(CascadeImpossible) as capture:
            cascade(lignes=lignes)
        self.assertIn('forfait', str(capture.exception))

    def test_une_cible_trop_basse_est_refusee(self):
        with self.assertRaises(CascadeImpossible) as capture:
            cascade(cout_revient_ht=Decimal('100000'),
                    benefice_net_vise_ht=Decimal('0'))
        self.assertIn('trop basse', str(capture.exception))

    def test_un_bordereau_vide_est_refuse(self):
        with self.assertRaises(CascadeImpossible):
            cascade(lignes=[])


class EtancheiteCascadeTest(SimpleTestCase):
    def test_aucune_cle_de_cout_ne_sort_vers_le_bordereau(self):
        lignes = lignes_du_bordereau(cascade())
        interdites = ('cout', 'prix_achat', 'marge', 'benefice',
                      'coefficient')
        for ligne in lignes:
            for cle in ligne:
                for interdite in interdites:
                    self.assertNotIn(interdite, cle)

    def test_la_projection_ferme_la_liste_des_cles(self):
        ligne = lignes_du_bordereau(cascade())[0]
        self.assertEqual(sorted(ligne), ['designation', 'famille', 'numero',
                                         'pu', 'quantite', 'total_ht',
                                         'unite'])
        self.assertNotIn('pu_reference', ligne)


def fourchettes():
    return {
        'module': {'min': Decimal('2500'), 'max': Decimal('3400'),
                   'source': 'AO déposé 2026-05 (bibliothèque de prix)'},
        'onduleur': {'min': Decimal('60000'), 'max': Decimal('95000'),
                     'source': 'devis accepté 2026-03'},
        'batterie': {'min': Decimal('2300'), 'max': Decimal('3000'),
                     'source': 'AO déposé 2026-05'},
    }


class FourchettesTest(SimpleTestCase):
    def test_des_pu_dans_la_bande_ne_produisent_aucun_ecart(self):
        rapport = controler_fourchettes(lignes_du_bordereau(cascade()),
                                        fourchettes())
        self.assertEqual(rapport['ecarts'], [])

    def test_un_pu_hors_bande_est_signale_avec_sa_fourchette_et_sa_source(self):
        lignes = lignes_du_bordereau(cascade())
        lignes[0]['pu'] = Decimal('4200')  # module trop cher
        rapport = controler_fourchettes(lignes, fourchettes())
        ecart = rapport['ecarts'][0]
        self.assertEqual(ecart['famille'], 'module')
        self.assertEqual(ecart['max'], Decimal('3400'))
        self.assertIn('bibliothèque de prix', ecart['source'])
        self.assertEqual(ecart['severite'], ALERTE)

    def test_les_ecarts_sont_tries_par_impact_pas_par_pourcentage(self):
        lignes = lignes_du_bordereau(cascade())
        lignes[0]['pu'] = Decimal('3500')     # +100 × 560 = 56 000 d'impact
        lignes[1]['pu'] = Decimal('120000')   # +25 000 × 3 = 75 000 d'impact
        rapport = controler_fourchettes(lignes, fourchettes())
        self.assertEqual([e['famille'] for e in rapport['ecarts']],
                         ['onduleur', 'module'])

    def test_un_ecart_hors_de_toute_plausibilite_refuse(self):
        lignes = lignes_du_bordereau(cascade())
        lignes[0]['pu'] = Decimal('9000')  # plus du double de la borne haute
        with self.assertRaises(PrixHorsBande) as capture:
            verifier_fourchettes(lignes, fourchettes())
        self.assertEqual(capture.exception.ecarts[0]['severite'], REFUS)
        self.assertIn('bibliothèque de prix', str(capture.exception))

    def test_une_famille_non_couverte_est_dite_non_couverte(self):
        rapport = controler_fourchettes(lignes_du_bordereau(cascade()),
                                        fourchettes())
        familles = {e['famille'] for e in rapport['non_couvertes']}
        self.assertIn('etudes', familles)
        self.assertIn('tgpv', familles)
        # …et surtout : elle n'est pas déclarée conforme.
        self.assertNotIn('etudes', {e['famille'] for e in rapport['ecarts']})

    def test_une_alerte_ne_bloque_pas(self):
        lignes = lignes_du_bordereau(cascade())
        lignes[0]['pu'] = Decimal('3600')
        rapport = verifier_fourchettes(lignes, fourchettes())
        self.assertEqual(len(rapport['ecarts']), 1)
        self.assertEqual(rapport['refus'], [])
