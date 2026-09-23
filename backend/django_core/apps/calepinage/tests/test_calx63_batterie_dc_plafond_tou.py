"""CALX63 — écrêtage récupéré en couplage DC, plafond d'injection, heures du
tarif, vieillissement par cycles.

Ce qui est tenu (le « Done = » de la tâche, en tests de propriété) :

* en couplage DC avec un écrêtage non nul, ``ecretage_recupere_kwh > 0`` et
  l'énergie livrée totale est STRICTEMENT supérieure au cas AC ;
* la stratégie ``plafond_injection`` rend une injection jamais supérieure au
  plafond, et une énergie écrêtée STRICTEMENT inférieure à celle de CALX190
  seul (``autoconsommation.plafond_injection`` sur le surplus brut) ;
* ``heures_tarif`` sans grille société ⇒
  ``StrategieInvalide.champ == 'parametres.tou_heures'`` — et jamais la grille
  de référence du dépôt en repli ;
* la capacité de l'année N décroît de façon monotone avec les cycles ;
  cycles ou rétention de fin de vie absents de la fiche ⇒ OMIS en nommant le
  champ, jamais un 80 % supposé.

Courbes et fiches SYNTHÉTIQUES, fabriquées pour le test : aucune ne décrit
une installation réelle, aucune grille horaire n'est celle d'un distributeur.
Tests PURS : aucune base, aucun réseau.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services import batterie as service
from apps.calepinage.services.autoconsommation import plafond_injection
from apps.calepinage.services.batterie import (
    CHAMP_CYCLES_FICHE, CHAMP_EOL_FICHE, CHAMP_TOU_HEURES, STRATEGIES,
    StrategieInvalide, capacite_batterie_par_annee, heures_tarif_societe,
    simuler_batterie, simuler_groupes, specs_batterie, vieillissement_batterie,
)

#: Une journée : consommation à plat ; 8 h de production excédentaire côté
#: ALTERNATIF (déjà plafonnée par l'onduleur), avec de l'écrêtage à midi.
CONSO = [1.0] * 24
PROD_AC = [0.0] * 8 + [4.0] * 8 + [0.0] * 8
ECRETAGE = [0.0] * 10 + [1.5] * 4 + [0.0] * 10

PARC = dict(capacite_utile_kwh=10.0, puissance_charge_kw=5.0,
            puissance_decharge_kw=5.0, rendement_ar_pct=90.0)


def energie_livree(resultat):
    """L'énergie livrée au point de livraison : consommée sans le réseau +
    injectée."""
    return (sum(CONSO) - resultat['import_reseau_kwh']
            + resultat['surplus_injecte_kwh'])


# ── (1) couplage DC : l'écrêtage offert à la charge ─────────────────────

class CouplageDcTest(unittest.TestCase):

    def _deux(self, **parc):
        parametres = dict(PARC, **parc)
        ac = simuler_batterie(CONSO, PROD_AC, strategie='autoconso',
                              couplage='ac', ecretage_horaire=ECRETAGE,
                              **parametres)
        dc = simuler_batterie(CONSO, PROD_AC, strategie='autoconso',
                              couplage='dc', ecretage_horaire=ECRETAGE,
                              **parametres)
        return ac, dc

    def test_en_dc_l_ecretage_est_recupere(self):
        _ac, dc = self._deux()
        self.assertGreater(dc['ecretage_recupere_kwh'], 0.0)

    def test_en_dc_l_energie_livree_depasse_strictement_le_cas_ac(self):
        ac, dc = self._deux()
        self.assertGreater(energie_livree(dc), energie_livree(ac) + 1e-6)

    def test_en_ac_l_ecretage_n_atteint_jamais_la_batterie(self):
        ac, _dc = self._deux()
        self.assertIsNone(ac['ecretage_recupere_kwh'])

    def test_la_recuperation_est_bornee_par_la_puissance_de_charge(self):
        trace = {}
        simuler_batterie(CONSO, PROD_AC, strategie='autoconso', couplage='dc',
                         ecretage_horaire=ECRETAGE, _trace=trace,
                         **dict(PARC, puissance_charge_kw=1.0))
        for rang, (ecretage, solaire) in enumerate(
                zip(trace['entree_ecretage'], trace['entree'])):
            with self.subTest(pas=rang):
                self.assertLessEqual(ecretage, 1.0 + 1e-9)
                self.assertLessEqual(ecretage + solaire, 1.0 + 1e-9)
                self.assertLessEqual(ecretage, ECRETAGE[rang] + 1e-9)

    def test_sans_serie_d_ecretage_rien_n_est_publie_comme_recupere(self):
        resultat = simuler_batterie(CONSO, PROD_AC, strategie='autoconso',
                                    couplage='dc', **PARC)
        self.assertIsNone(resultat['ecretage_recupere_kwh'])

    def test_le_bilan_de_la_batterie_compte_l_ecretage_en_entree(self):
        _ac, dc = self._deux()
        variation = dc['etat_de_charge_kwh'][-1]
        self.assertAlmostEqual(
            dc['charge_batterie_kwh'],
            dc['decharge_batterie_kwh'] + dc['pertes_stockage_kwh']
            + variation, delta=0.002)

    def test_un_couplage_inconnu_est_refuse_en_le_nommant(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD_AC, strategie='autoconso',
                             couplage='triphase', **PARC)
        self.assertEqual(refus.exception.champ, 'couplage')

    def test_une_serie_d_ecretage_d_une_autre_periode_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD_AC, strategie='autoconso',
                             couplage='dc', ecretage_horaire=[1.0] * 5,
                             **PARC)
        self.assertEqual(refus.exception.champ, 'ecretage')

    def test_le_couplage_est_publie_dans_les_parametres(self):
        ac, dc = self._deux()
        self.assertEqual(ac['parametres']['couplage'], 'ac')
        self.assertEqual(dc['parametres']['couplage'], 'dc')


class GroupesDcTest(unittest.TestCase):
    """CALX267 porte les groupes ; CALX63 dit ce que le couplage DC change."""

    def _groupe(self, nom, couplage, **parametres):
        return dict(PARC, strategie='autoconso', groupe=nom,
                    couplage=couplage,
                    onduleur_ref='OND-TEST-1' if couplage == 'dc' else None,
                    modele='PACK-TEST', **parametres)

    def test_seul_le_groupe_dc_recupere_l_ecretage(self):
        resultat = simuler_groupes(
            CONSO, PROD_AC,
            [self._groupe('DC', 'dc'), self._groupe('AC', 'ac')],
            ecretage_horaire=ECRETAGE)
        dc, ac = resultat['groupes']
        self.assertGreater(dc['resultat']['ecretage_recupere_kwh'], 0.0)
        self.assertIsNone(ac['resultat']['ecretage_recupere_kwh'])
        self.assertEqual(resultat['agregat']['ecretage_recupere_kwh'],
                         dc['resultat']['ecretage_recupere_kwh'])

    def test_deux_groupes_dc_se_partagent_l_ecretage_sans_le_compter_deux_fois(
            self):
        petit = dict(capacite_utile_kwh=2.0, puissance_charge_kw=5.0,
                     puissance_decharge_kw=5.0, rendement_ar_pct=90.0)
        resultat = simuler_groupes(
            CONSO, [0.0] * 24,
            [dict(self._groupe('DC1', 'dc'), **petit),
             dict(self._groupe('DC2', 'dc'), **petit)],
            ecretage_horaire=ECRETAGE)
        recuperes = [ligne['resultat']['ecretage_recupere_kwh']
                     for ligne in resultat['groupes']]
        self.assertTrue(all(valeur > 0 for valeur in recuperes), recuperes)
        self.assertLessEqual(sum(recuperes), sum(ECRETAGE) + 1e-6)

    def test_le_groupe_dc_livre_plus_que_le_meme_groupe_en_ac(self):
        dc = simuler_groupes(CONSO, PROD_AC, [self._groupe('G', 'dc')],
                             ecretage_horaire=ECRETAGE)['agregat']
        ac = simuler_groupes(CONSO, PROD_AC, [self._groupe('G', 'ac')],
                             ecretage_horaire=ECRETAGE)['agregat']
        self.assertGreater(energie_livree(dc), energie_livree(ac) + 1e-6)


# ── (2) stratégie « plafond d'injection » ───────────────────────────────

#: Surplus de 5 kWh/h pendant 7 h, pour un plafond SAISI de 3 kW.
PROD_PLAFOND = [0.0] * 9 + [6.0] * 7 + [0.0] * 8
PLAFOND = dict(plafond_injection_kw=3.0,
               plafond_injection_justification='Contrat de raccordement TEST')


class PlafondInjectionTest(unittest.TestCase):

    def setUp(self):
        self.trace = {}
        self.resultat = simuler_batterie(
            CONSO, PROD_PLAFOND, strategie='plafond_injection',
            _trace=self.trace, **PARC, **PLAFOND)
        brut = [max(0.0, prod - conso)
                for conso, prod in zip(CONSO, PROD_PLAFOND)]
        self.seul = plafond_injection(
            brut, plafond_kw=3.0,
            justification='Contrat de raccordement TEST')

    def test_l_injection_ne_depasse_jamais_le_plafond(self):
        for rang, injection in enumerate(self.trace['injection']):
            with self.subTest(pas=rang):
                self.assertLessEqual(injection, 3.0 + 1e-9)
        bloc = self.resultat['ecretage_injection']
        self.assertLessEqual(bloc['injection_max_kw'], 3.0 + 1e-9)
        self.assertLessEqual(self.resultat['surplus_injecte_kwh'],
                             3.0 * 7 + 1e-6)

    def test_l_ecretage_est_strictement_inferieur_a_calx190_seul(self):
        bloc = self.resultat['ecretage_injection']
        self.assertGreater(self.seul['energie_ecretee_kwh'], 0.0)
        self.assertLess(bloc['energie_ecretee_kwh'],
                        self.seul['energie_ecretee_kwh'])
        # Le « sans batterie » publié EST le chiffre de CALX190 seul.
        self.assertEqual(bloc['energie_ecretee_sans_batterie_kwh'],
                         self.seul['energie_ecretee_kwh'])

    def test_seul_le_surplus_au_dessus_du_plafond_est_stocke(self):
        for rang, entree in enumerate(self.trace['entree']):
            au_dessus = max(0.0, PROD_PLAFOND[rang] - CONSO[rang] - 3.0)
            with self.subTest(pas=rang):
                self.assertLessEqual(entree, au_dessus + 1e-9)

    def test_ce_qui_est_stocke_est_restitue_a_la_consommation(self):
        self.assertGreater(self.resultat['decharge_batterie_kwh'], 0.0)
        # Sans batterie, les 17 heures sans surplus seraient importées.
        self.assertLess(self.resultat['import_reseau_kwh'], 17.0)

    def test_la_justification_reste_obligatoire(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD_PLAFOND,
                             strategie='plafond_injection',
                             plafond_injection_kw=3.0, **PARC)
        self.assertEqual(refus.exception.champ,
                         'plafond_injection_justification')

    def test_sans_plafond_saisi_la_strategie_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD_PLAFOND,
                             strategie='plafond_injection', **PARC)
        self.assertEqual(refus.exception.champ, 'plafond_injection_kw')

    def test_un_plafond_negatif_est_refuse_par_la_regle_de_calx190(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(
                CONSO, PROD_PLAFOND, strategie='plafond_injection',
                plafond_injection_kw=-1.0,
                plafond_injection_justification='Contrat TEST', **PARC)
        self.assertEqual(refus.exception.champ, 'plafond_injection_kw')

    def test_le_plafond_ne_pilote_pas_une_autre_strategie(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD_PLAFOND, strategie='autoconso',
                             **PARC, **PLAFOND)
        self.assertEqual(refus.exception.champ, 'plafond_injection_kw')

    def test_le_plafond_et_sa_justification_sont_publies(self):
        parametres = self.resultat['parametres']
        self.assertEqual(parametres['plafond_injection_kw'], 3.0)
        self.assertEqual(parametres['plafond_injection_justification'],
                         'Contrat de raccordement TEST')

    def test_deux_groupes_ecretent_au_point_de_livraison(self):
        groupe = dict(PARC, strategie='plafond_injection', couplage='ac',
                      modele='PACK-TEST', **PLAFOND)
        resultat = simuler_groupes(
            CONSO, PROD_PLAFOND,
            [dict(groupe, groupe='G1', capacite_utile_kwh=3.0),
             dict(groupe, groupe='G2', capacite_utile_kwh=3.0)])
        agregat = resultat['agregat']
        self.assertLessEqual(agregat['ecretage_injection']['injection_max_kw'],
                             3.0 + 1e-9)
        self.assertLess(agregat['ecretage_injection']['energie_ecretee_kwh'],
                        self.seul['energie_ecretee_kwh'])

    def test_deux_plafonds_differents_sont_refuses(self):
        groupe = dict(PARC, strategie='plafond_injection', couplage='ac',
                      modele='PACK-TEST', **PLAFOND)
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD_PLAFOND, [
                dict(groupe, groupe='G1'),
                dict(groupe, groupe='G2', plafond_injection_kw=4.0)])
        self.assertEqual(refus.exception.champ,
                         'groupes[1].plafond_injection_kw')


# ── (3) stratégie « heures du tarif » ───────────────────────────────────

#: Une grille SYNTHÉTIQUE (libellés seulement), fabriquée pour le test.
GRILLE = (['creuse'] * 6 + ['pleine'] * 12 + ['pointe'] * 4
          + ['pleine', 'creuse'])
HEURES_CREUSES = {heure for heure, tranche in enumerate(GRILLE)
                  if tranche == 'creuse'}
HEURES_POINTE = {heure for heure, tranche in enumerate(GRILLE)
                 if tranche == 'pointe'}
SANS_SOLEIL = [0.0] * 24
PARC_TOU = dict(capacite_utile_kwh=4.0, puissance_charge_kw=2.0,
                puissance_decharge_kw=2.0, rendement_ar_pct=90.0)


class HeuresTarifTest(unittest.TestCase):

    def test_sans_grille_societe_la_strategie_est_refusee(self):
        for vide in (None, '', [], {}):
            with self.subTest(grille=vide):
                with self.assertRaises(StrategieInvalide) as refus:
                    simuler_batterie(CONSO, SANS_SOLEIL,
                                     strategie='heures_tarif',
                                     tou_heures=vide, **PARC_TOU)
                self.assertEqual(refus.exception.champ,
                                 'parametres.tou_heures')
                self.assertEqual(refus.exception.champ, CHAMP_TOU_HEURES)

    def test_la_grille_de_reference_du_depot_n_est_jamais_un_repli(self):
        with mock.patch.object(service, 'tranches_horaires',
                               side_effect=AssertionError('repli interdit')):
            with self.assertRaises(StrategieInvalide) as refus:
                simuler_batterie(CONSO, SANS_SOLEIL, strategie='heures_tarif',
                                 **PARC_TOU)
        self.assertEqual(refus.exception.champ, 'parametres.tou_heures')
        with open(service.__file__, encoding='utf-8') as source:
            texte = source.read()
        # Le module NOMME la constante pour dire qu'elle n'est jamais un
        # repli ; il ne la lit que dans ``tranches_horaires`` (CAL152).
        self.assertEqual(texte.count('import DEFAULT_HOUR_TRANCHES'), 1)

    def test_charge_reseau_en_creuse_decharge_en_pointe(self):
        trace = {}
        resultat = simuler_batterie(CONSO, SANS_SOLEIL,
                                    strategie='heures_tarif',
                                    tou_heures=GRILLE, _trace=trace,
                                    **PARC_TOU)
        self.assertGreater(resultat['charge_reseau_kwh'], 0.0)
        self.assertGreater(resultat['decharge_batterie_kwh'], 0.0)
        for heure in range(24):
            with self.subTest(heure=heure):
                if trace['entree_reseau'][heure] > 0:
                    self.assertIn(heure, HEURES_CREUSES)
                if trace['sortie'][heure] > 0:
                    self.assertIn(heure, HEURES_POINTE)

    def test_la_charge_reseau_est_un_soutirage(self):
        resultat = simuler_batterie(CONSO, SANS_SOLEIL,
                                    strategie='heures_tarif',
                                    tou_heures=GRILLE, **PARC_TOU)
        self.assertAlmostEqual(
            resultat['import_reseau_kwh'],
            sum(CONSO) - resultat['decharge_batterie_kwh']
            + resultat['charge_reseau_kwh'], delta=0.002)
        self.assertAlmostEqual(resultat['charge_batterie_kwh'],
                               resultat['charge_reseau_kwh'], delta=0.002)

    def test_la_puissance_de_charge_borne_la_charge_reseau(self):
        trace = {}
        simuler_batterie(CONSO, SANS_SOLEIL, strategie='heures_tarif',
                         tou_heures=GRILLE, _trace=trace, **PARC_TOU)
        self.assertTrue(all(valeur <= 2.0 + 1e-9
                            for valeur in trace['entree_reseau']))

    def test_les_tranches_employees_sont_publiees(self):
        resultat = simuler_batterie(CONSO, SANS_SOLEIL,
                                    strategie='heures_tarif',
                                    tou_heures=GRILLE, **PARC_TOU)
        tranches = resultat['tranches_horaires']
        self.assertEqual(tranches['heures_creuses'], len(HEURES_CREUSES))
        self.assertEqual(tranches['heures_pointe'], len(HEURES_POINTE))
        self.assertEqual(tranches['heures_sans_tranche'], 0)
        self.assertEqual(tranches['source'], 'parametres.tou_heures')

    def test_une_saison_non_saisie_ne_charge_ni_ne_decharge(self):
        """48 pas : un jour de juillet (été saisi), un jour de janvier (hiver
        NON saisi, aucun « annuel ») — rien n'est supposé pour janvier."""
        trace = {}
        resultat = simuler_batterie(
            CONSO * 2, SANS_SOLEIL * 2, strategie='heures_tarif',
            tou_heures={'ete': GRILLE}, mois_des_heures=[7] * 24 + [1] * 24,
            _trace=trace, **PARC_TOU)
        self.assertTrue(all(valeur == 0.0
                            for valeur in trace['entree_reseau'][24:]))
        self.assertTrue(all(valeur == 0.0 for valeur in trace['sortie'][24:]))
        tranches = resultat['tranches_horaires']
        self.assertEqual(tranches['heures_sans_tranche'], 24)
        self.assertTrue(any('hiver' in motif
                            for motif in tranches['motifs_sans_tranche']))

    def test_une_grille_sans_heure_de_pointe_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, SANS_SOLEIL, strategie='heures_tarif',
                             tou_heures=['creuse'] * 12 + ['pleine'] * 12,
                             **PARC_TOU)
        self.assertEqual(refus.exception.champ, 'parametres.tou_heures')

    def test_une_grille_mal_formee_est_refusee(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, SANS_SOLEIL, strategie='heures_tarif',
                             tou_heures=['pointe'] * 5, **PARC_TOU)
        self.assertEqual(refus.exception.champ, 'parametres.tou_heures')

    def test_hors_de_sa_strategie_la_grille_ne_change_rien(self):
        sans = simuler_batterie(CONSO, PROD_AC, strategie='autoconso',
                                **PARC)
        avec = simuler_batterie(CONSO, PROD_AC, strategie='autoconso',
                                tou_heures=GRILLE, **PARC)
        self.assertEqual(sans, avec)
        self.assertIsNone(avec['charge_reseau_kwh'])
        self.assertIsNone(avec['tranches_horaires'])

    def test_un_groupe_sans_grille_est_refuse_sans_prefixe_de_groupe(self):
        groupe = dict(PARC_TOU, strategie='heures_tarif', couplage='ac',
                      groupe='G1', modele='PACK-TEST')
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, SANS_SOLEIL, [groupe])
        self.assertEqual(refus.exception.champ, 'parametres.tou_heures')

    def test_la_charge_reseau_d_un_groupe_precedent_reste_importee(self):
        premier = dict(PARC_TOU, strategie='heures_tarif', couplage='ac',
                       groupe='TOU', modele='PACK-TEST')
        second = dict(PARC_TOU, strategie='autoconso', couplage='ac',
                      groupe='AUTO', modele='PACK-TEST')
        resultat = simuler_groupes(CONSO, SANS_SOLEIL, [premier, second],
                                   tou_heures=GRILLE)
        tou, auto = (ligne['resultat'] for ligne in resultat['groupes'])
        agregat = resultat['agregat']
        self.assertAlmostEqual(
            agregat['import_reseau_kwh'],
            auto['import_reseau_kwh'] + tou['charge_reseau_kwh'], delta=0.002)
        self.assertEqual(agregat['charge_reseau_kwh'],
                         tou['charge_reseau_kwh'])


class GrilleSocieteTest(unittest.TestCase):
    """``heures_tarif_societe`` : les LIBELLÉS seulement — D5."""

    GRILLE_SAISIE = {'heures': GRILLE,
                     'tarifs': {'creuse': 0.5, 'pleine': 1.0, 'pointe': 2.0},
                     'source': 'Facture TEST', 'date_source': '2026-01-01'}

    def test_seuls_les_libelles_d_heures_sortent_de_la_grille(self):
        with mock.patch('apps.parametres.selectors.tou_pour',
                        return_value=self.GRILLE_SAISIE):
            heures = heures_tarif_societe(object())
        self.assertEqual(heures, GRILLE)
        self.assertNotIn('tarifs', json.dumps(heures))

    def test_une_societe_sans_grille_rend_none_donc_un_refus(self):
        with mock.patch('apps.parametres.selectors.tou_pour',
                        return_value=None):
            heures = heures_tarif_societe(object())
        self.assertIsNone(heures)
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, SANS_SOLEIL, strategie='heures_tarif',
                             tou_heures=heures, **PARC_TOU)
        self.assertEqual(refus.exception.champ, 'parametres.tou_heures')

    def test_sans_societe_rien_n_est_lu(self):
        with mock.patch('apps.parametres.selectors.tou_pour') as lecture:
            self.assertIsNone(heures_tarif_societe(None))
        lecture.assert_not_called()

    def test_aucun_prix_ne_sort_du_dispatch(self):
        resultat = simuler_batterie(CONSO, SANS_SOLEIL,
                                    strategie='heures_tarif',
                                    tou_heures=GRILLE, **PARC_TOU)
        texte = json.dumps(resultat).lower()
        for interdit in ('prix', 'achat', 'marge', 'cout', 'mad'):
            self.assertNotIn(interdit, texte)

    def test_les_deux_strategies_sont_nommees(self):
        self.assertIn('plafond_injection', STRATEGIES)
        self.assertIn('heures_tarif', STRATEGIES)


# ── (4) vieillissement par cycles ────────────────────────────────────────

class VieillissementTest(unittest.TestCase):

    def test_la_capacite_decroit_de_facon_monotone_avec_les_annees(self):
        resultat = vieillissement_batterie(300.0, 6000, 70.0)
        capacites = [ligne['capacite_batterie_pct']
                     for ligne in resultat['annees']]
        self.assertEqual(capacites[0], 100.0)
        self.assertTrue(all(suivante < precedente for precedente, suivante
                            in zip(capacites, capacites[1:])), capacites)
        # À 6 000 cycles, la rétention PUBLIÉE — ni plus, ni moins.
        self.assertEqual(resultat['annees'][-1]['cycles_cumules'], 6000.0)
        self.assertEqual(capacites[-1], 70.0)
        self.assertEqual(resultat['annee_fin_de_vie'], 21)

    def test_plus_de_cycles_par_an_use_plus_vite(self):
        for annee in (2, 5, 10):
            valeurs = [
                vieillissement_batterie(cycles, 6000, 70.0,
                                        horizon_annees=10)['annees'][annee - 1]
                ['capacite_batterie_pct'] for cycles in (100, 250, 400)]
            with self.subTest(annee=annee):
                self.assertTrue(valeurs[0] > valeurs[1] > valeurs[2], valeurs)

    def test_au_dela_des_cycles_publies_rien_n_est_extrapole(self):
        resultat = vieillissement_batterie(300.0, 6000, 70.0,
                                           horizon_annees=25)
        self.assertEqual(len(resultat['annees']), 25)
        for ligne in resultat['annees'][21:]:
            with self.subTest(annee=ligne['annee']):
                self.assertIsNone(ligne['capacite_batterie_pct'])
                self.assertTrue(ligne['au_dela_fiche'])

    def test_cycles_absents_de_la_fiche_omis_en_nommant_le_champ(self):
        resultat = vieillissement_batterie(300.0, None, 70.0)
        self.assertEqual(resultat['annees'], [])
        self.assertEqual(resultat['champ'], CHAMP_CYCLES_FICHE)
        self.assertEqual(resultat['champ'], 'fiche_batterie.cycles_publies')
        self.assertIn('fiche_batterie.cycles_publies',
                      resultat['motif_absence'])

    def test_retention_absente_omise_jamais_80_pourcent_suppose(self):
        resultat = vieillissement_batterie(300.0, 6000, None)
        self.assertEqual(resultat['annees'], [])
        self.assertEqual(resultat['champ'], CHAMP_EOL_FICHE)
        self.assertIn('fiche_batterie.eol_pct', resultat['motif_absence'])
        self.assertIsNone(resultat['eol_pct_fiche'])
        self.assertNotIn('80', json.dumps(resultat))

    def test_sans_cycles_annuels_omis_en_nommant_le_champ(self):
        resultat = vieillissement_batterie(None, 6000, 70.0)
        self.assertEqual(resultat['annees'], [])
        self.assertEqual(resultat['champ'], 'cycles_annuels')

    def test_la_capacite_se_pose_sur_les_lignes_annuelles(self):
        lignes = [{'annee': rang, 'p50_kwh': 1000.0 - rang}
                  for rang in range(1, 4)]
        publiees = capacite_batterie_par_annee(
            lignes, vieillissement_batterie(300.0, 6000, 70.0))
        self.assertEqual([ligne['capacite_batterie_pct'] for ligne in publiees],
                         [100.0, 98.5, 97.0])
        self.assertEqual(publiees[0]['p50_kwh'], 999.0)
        # Les lignes reçues ne sont jamais modifiées.
        self.assertNotIn('capacite_batterie_pct', lignes[0])

    def test_un_vieillissement_omis_pose_none_jamais_un_chiffre(self):
        publiees = capacite_batterie_par_annee(
            [{'annee': 1}, {'annee': 2}],
            vieillissement_batterie(300.0, None, None))
        self.assertEqual([ligne['capacite_batterie_pct'] for ligne in publiees],
                         [None, None])

    def test_la_retention_de_fin_de_vie_est_lue_sur_la_fiche(self):
        from apps.calepinage.tests.test_conso_batterie_fiche import (
            FICHE_COMPLETE, batterie,
        )

        avec = specs_batterie(batterie(**FICHE_COMPLETE,
                                       bat_retention_fin_de_vie_pct=70.0))
        self.assertEqual(avec['grandeurs']['eol_pct']['valeur'], 70.0)
        self.assertEqual(avec['grandeurs']['eol_pct']['source'], 'fiche')
        sans = specs_batterie(batterie(**FICHE_COMPLETE))
        self.assertIsNone(sans['grandeurs']['eol_pct']['valeur'])
        self.assertIsNone(sans['grandeurs']['eol_pct']['source'])
        self.assertEqual(sans['avertissements'], [])


# ── le câblage dans le bloc « batterie » (etapes/batterie.py) ───────────

class ChaineDeSimulationTest(SimpleTestCase):
    """Les trois apports passent par l'étape, sans seconde arithmétique."""

    def _bloc(self, *, heures=48, serie=None, specs=None, contexte_en_plus=None,
              **declaration):
        from apps.calepinage.services.etapes import batterie as bloc
        from apps.calepinage.tests.test_calx188_batterie import (
            contexte_de_test, serie_de_test,
        )

        contexte = contexte_de_test(heures=heures, **declaration)
        if specs is not None:
            contexte[bloc.CLE_CONTEXTE]['groupes'][0]['specs'] = specs
        contexte.update(contexte_en_plus or {})
        serie = serie if serie is not None else serie_de_test(heures=heures)
        return bloc.bloc_batterie(serie, contexte)

    @staticmethod
    def _serie_ecretee(heures=48):
        from apps.calepinage.tests.test_calx188_batterie import serie_de_test

        serie = serie_de_test(heures=heures)
        for point in serie['points']:
            point['ecretage_kw'] = 1.5 if 10 <= point['heure'] <= 13 else 0.0
        return serie

    def _bilan(self, energie):
        entrees = (energie['production_kwh'] + energie['ecretage_recupere_kwh']
                   + energie['charge_reseau_kwh'])
        sorties = (energie['autoconsomme_kwh'] + energie['export_kwh']
                   + energie['pertes_batterie_kwh']
                   + energie['variation_stock_kwh'])
        self.assertAlmostEqual(entrees, sorties, delta=0.1)

    def test_une_banque_dc_recupere_l_ecretage_de_la_serie(self):
        _suite, resultat = self._bloc(serie=self._serie_ecretee(),
                                      couplage='dc',
                                      onduleur_ref='OND-TEST-1')
        self.assertEqual(resultat['motif_absence'], '')
        energie = resultat['total']['energie']
        self.assertGreater(energie['ecretage_recupere_kwh'], 0.0)
        self._bilan(energie)

    def test_une_banque_ac_ne_recupere_rien(self):
        _suite, resultat = self._bloc(serie=self._serie_ecretee(),
                                      couplage='ac')
        self.assertEqual(resultat['total']['energie']['ecretage_recupere_kwh'],
                         0.0)

    def test_le_plafond_se_lit_sur_le_raccordement(self):
        """Batterie PUIS autoconsommation, comme la chaîne de simulation :
        l'écrêtage au point de livraison reste publié par CALX190 seul, et il
        est strictement inférieur à celui de CALX190 sans batterie."""
        from apps.calepinage.services.etapes.autoconsommation import (
            bloc_autoconsommation,
        )
        from apps.calepinage.tests.test_calx188_batterie import (
            contexte_de_test, serie_de_test,
        )

        raccordement = {'raccordement': {
            'plafond_injection_kw': 1.0,
            'plafond_injection_justification': 'Contrat TEST'}}
        suite, resultat = self._bloc(strategie='plafond_injection',
                                     contexte_en_plus=raccordement)
        self.assertEqual(resultat['motif_absence'], '')
        self._bilan(resultat['total']['energie'])

        contexte = dict(contexte_de_test(heures=48), **raccordement)
        finale, avec = bloc_autoconsommation(suite, contexte)
        sans_batterie = dict(contexte)
        sans_batterie.pop('batterie')
        _serie, sans = bloc_autoconsommation(serie_de_test(heures=48),
                                             sans_batterie)
        for point in finale['points']:
            self.assertLessEqual(point['reseau_export_kwh'], 1.0 + 1e-6)
        self.assertGreater(sans['plafond']['energie_ecretee_kwh'], 0.0)
        self.assertLess(avec['plafond']['energie_ecretee_kwh'],
                        sans['plafond']['energie_ecretee_kwh'])

    def test_un_plafond_sans_justification_nomme_le_raccordement(self):
        suite, resultat = self._bloc(
            strategie='plafond_injection',
            contexte_en_plus={'raccordement': {'plafond_injection_kw': 1.0}})
        self.assertIsNone(resultat['total'])
        self.assertIn('raccordement.plafond_injection_justification',
                      resultat['motif_absence'])
        self.assertNotIn('batterie_soc_pct', suite['points'][0])

    def test_sans_grille_societe_le_bloc_nomme_le_reglage(self):
        _suite, resultat = self._bloc(strategie='heures_tarif')
        self.assertIsNone(resultat['total'])
        self.assertIn('« parametres.tou_heures »', resultat['motif_absence'])

    def test_la_grille_societe_pilote_la_batterie(self):
        from apps.calepinage.services.etapes import batterie as bloc

        _suite, resultat = self._bloc(
            strategie='heures_tarif',
            contexte_en_plus={bloc.CLE_TOU_HEURES: GRILLE})
        self.assertEqual(resultat['motif_absence'], '')
        energie = resultat['total']['energie']
        self.assertGreater(energie['charge_reseau_kwh'], 0.0)
        self._bilan(energie)
        # La provenance de l'énergie servie n'est pas répartie : c'est DIT.
        self.assertTrue(any('chargés sur le réseau' in avis
                            for avis in resultat['avertissements']))

    def test_le_vieillissement_se_publie_sur_une_annee_entiere(self):
        from apps.calepinage.tests.test_calx188_batterie import specs_de_test

        specs = specs_de_test()
        specs['grandeurs']['eol_pct'] = {'valeur': 70.0, 'source': 'fiche',
                                         'mention': 'Lu sur la fiche produit.'}
        _suite, resultat = self._bloc(heures=8760, specs=specs)
        vieillissement = resultat['total']['vieillissement']
        self.assertEqual(vieillissement['motif_absence'], '')
        capacites = [ligne['capacite_batterie_pct']
                     for ligne in vieillissement['annees']
                     if ligne['capacite_batterie_pct'] is not None]
        self.assertEqual(capacites[0], 100.0)
        self.assertTrue(all(suivante < precedente for precedente, suivante
                            in zip(capacites, capacites[1:])))

    def test_une_fiche_sans_retention_omet_le_vieillissement(self):
        _suite, resultat = self._bloc(heures=8760)
        vieillissement = resultat['total']['vieillissement']
        self.assertEqual(vieillissement['annees'], [])
        self.assertEqual(vieillissement['champ'], 'fiche_batterie.eol_pct')

    def test_une_serie_de_deux_jours_ne_donne_pas_de_cycles_annuels(self):
        from apps.calepinage.services.etapes import batterie as bloc
        from apps.calepinage.tests.test_calx188_batterie import specs_de_test

        specs = specs_de_test()
        specs['grandeurs']['eol_pct'] = {'valeur': 70.0, 'source': 'fiche',
                                         'mention': 'Lu sur la fiche produit.'}
        _suite, resultat = self._bloc(heures=48, specs=specs)
        vieillissement = resultat['total']['vieillissement']
        self.assertEqual(vieillissement['annees'], [])
        self.assertEqual(vieillissement['motif_absence'],
                         bloc.MOTIF_VIEILLISSEMENT_PAS_ANNUEL)
