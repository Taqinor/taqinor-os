"""CALX268 — la commande horaire à SOC cible, par groupe.

Ce qui est tenu ici (le « Done » de la tâche) :

* une fenêtre de charge 01 h–05 h à 80 % sur une batterie de 10 kWh ⇒
  ``etat_de_charge_kwh[5] == 8.0`` (± 0,001) et AUCUNE charge en 06 h ;
* deux fenêtres de charge qui se recouvrent (01–05 et 04–07) ⇒ refus
  nommant ``fenetres.charge[1]`` ;
* l'entrée d'aujourd'hui (``heures_charge`` / ``heures_decharge``) ⇒ le
  résultat terme à terme INCHANGÉ (instantané figé ci-dessous, relevé sur le
  code d'avant CALX268) ; elle vaut une fenêtre unique sans cible.

Tests PURS : aucune base, aucun réseau. Séries SYNTHÉTIQUES (la production
de nuit de la première série est fabriquée pour le test : la charge d'une
fenêtre reste celle du SURPLUS solaire).
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.batterie import (
    FENETRES_MAX, StrategieInvalide, simuler_batterie, simuler_groupes,
)

#: Consommation à plat ; 2 kWh de surplus par heure de 01 h à 06 h.
CONSO = [1.0] * 24
PROD_NUIT = [0.0] + [3.0] * 6 + [0.0] * 17

PARC = dict(capacite_utile_kwh=10.0, puissance_charge_kw=2.0,
            puissance_decharge_kw=2.0, rendement_ar_pct=100.0)

H_01_05 = [1, 2, 3, 4, 5]
DECHARGE_SOIR = [19, 20, 21, 22, 23]


def decalage(fenetres, conso=CONSO, prod=PROD_NUIT, **extra):
    parametres = dict(PARC, strategie='decalage', fenetres=fenetres)
    parametres.update(extra)
    return simuler_batterie(conso, prod, **parametres)


class SocCibleTest(unittest.TestCase):

    def test_la_charge_s_arrete_au_soc_vise_de_la_fenetre(self):
        resultat = decalage({
            'charge': [{'heures': H_01_05, 'soc_cible_pct': 80}],
            'decharge': [{'heures': DECHARGE_SOIR, 'soc_cible_pct': None}],
        })
        etats = resultat['etat_de_charge_kwh']
        self.assertAlmostEqual(etats[5], 8.0, delta=0.001)
        # 06 h est HORS fenêtre : aucune charge, alors que le surplus existe.
        self.assertAlmostEqual(etats[6], etats[5], delta=0.001)
        self.assertAlmostEqual(resultat['charge_batterie_kwh'], 8.0,
                               delta=0.001)

    def test_sans_cible_la_meme_fenetre_charge_jusqu_au_plein(self):
        resultat = decalage({
            'charge': [{'heures': H_01_05, 'soc_cible_pct': None}],
            'decharge': [{'heures': DECHARGE_SOIR}],
        })
        self.assertAlmostEqual(resultat['etat_de_charge_kwh'][5], 10.0,
                               delta=0.001)

    def test_la_cible_tient_aussi_avec_un_rendement_publie(self):
        resultat = decalage({
            'charge': [{'heures': H_01_05, 'soc_cible_pct': 80}],
            'decharge': [{'heures': DECHARGE_SOIR}],
        }, rendement_ar_pct=90.0)
        self.assertAlmostEqual(resultat['etat_de_charge_kwh'][5], 8.0,
                               delta=0.001)

    def test_la_decharge_ne_descend_pas_sous_son_soc_vise(self):
        resultat = decalage({
            'charge': [{'heures': H_01_05, 'soc_cible_pct': None}],
            'decharge': [{'heures': DECHARGE_SOIR, 'soc_cible_pct': 50}],
        })
        etats = resultat['etat_de_charge_kwh']
        for heure in DECHARGE_SOIR:
            self.assertGreaterEqual(etats[heure], 5.0 - 0.001)
        self.assertAlmostEqual(etats[23], 5.0, delta=0.001)

    def test_trois_fenetres_de_chaque_sorte_sont_admises(self):
        resultat = decalage({
            'charge': [{'heures': [1], 'soc_cible_pct': 20},
                       {'heures': [2], 'soc_cible_pct': 40},
                       {'heures': [3], 'soc_cible_pct': 60}],
            'decharge': [{'heures': [19]}, {'heures': [20]},
                         {'heures': [21], 'soc_cible_pct': 10}],
        })
        etats = resultat['etat_de_charge_kwh']
        self.assertAlmostEqual(etats[1], 2.0, delta=0.001)
        self.assertAlmostEqual(etats[2], 4.0, delta=0.001)
        self.assertAlmostEqual(etats[3], 6.0, delta=0.001)
        self.assertEqual(len(resultat['parametres']['fenetres']['charge']), 3)


class RefusTest(unittest.TestCase):

    def test_deux_fenetres_de_charge_qui_se_recouvrent(self):
        with self.assertRaises(StrategieInvalide) as refus:
            decalage({
                'charge': [{'heures': H_01_05, 'soc_cible_pct': 80},
                           {'heures': [4, 5, 6, 7], 'soc_cible_pct': 90}],
                'decharge': [{'heures': DECHARGE_SOIR}],
            })
        self.assertEqual(refus.exception.champ, 'fenetres.charge[1]')

    def test_une_decharge_qui_recouvre_une_charge(self):
        with self.assertRaises(StrategieInvalide) as refus:
            decalage({'charge': [{'heures': H_01_05}],
                      'decharge': [{'heures': [5, 6]}]})
        self.assertEqual(refus.exception.champ, 'fenetres.decharge[0]')

    def test_au_plus_trois_fenetres(self):
        with self.assertRaises(StrategieInvalide) as refus:
            decalage({'charge': [{'heures': [h]} for h in range(4)],
                      'decharge': [{'heures': [20]}]})
        self.assertEqual(refus.exception.champ,
                         f'fenetres.charge[{FENETRES_MAX}]')

    def test_un_soc_hors_bornes(self):
        with self.assertRaises(StrategieInvalide) as refus:
            decalage({'charge': [{'heures': H_01_05, 'soc_cible_pct': 120}],
                      'decharge': [{'heures': [20]}]})
        self.assertEqual(refus.exception.champ,
                         'fenetres.charge[0].soc_cible_pct')

    def test_une_fenetre_sans_heures(self):
        with self.assertRaises(StrategieInvalide) as refus:
            decalage({'charge': [{'soc_cible_pct': 80}],
                      'decharge': [{'heures': [20]}]})
        self.assertEqual(refus.exception.champ, 'fenetres.charge[0].heures')

    def test_aucune_fenetre_de_decharge(self):
        with self.assertRaises(StrategieInvalide) as refus:
            decalage({'charge': [{'heures': H_01_05}]})
        self.assertEqual(refus.exception.champ, 'fenetres.decharge')

    def test_des_fenetres_et_des_heures_a_la_fois(self):
        with self.assertRaises(StrategieInvalide) as refus:
            decalage({'charge': [{'heures': H_01_05}],
                      'decharge': [{'heures': [20]}]}, heures_charge=[1])
        self.assertEqual(refus.exception.champ, 'fenetres')

    def test_des_fenetres_hors_strategie_de_decalage(self):
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(CONSO, PROD_NUIT, strategie='autoconso',
                             fenetres={'charge': [{'heures': [1]}]}, **PARC)
        self.assertEqual(refus.exception.champ, 'fenetres')


class EntreeDAujourdHuiTest(unittest.TestCase):
    """``heures_charge``/``heures_decharge`` : le résultat terme à terme."""

    CONSO = [1.0] * 24
    PROD = [0.0] * 6 + [2.0] * 12 + [0.0] * 6
    ENTREE = dict(strategie='decalage', heures_charge=[10, 11, 12],
                  heures_decharge=[19, 20, 21], capacite_utile_kwh=10.0,
                  puissance_charge_kw=5.0, puissance_decharge_kw=5.0,
                  rendement_ar_pct=90.0)

    #: Instantané relevé sur le code d'AVANT CALX268 (même entrée).
    AVANT = {
        'strategie': 'decalage',
        'heures': 24,
        'charge_batterie_kwh': 3.0,
        'decharge_batterie_kwh': 2.7,
        'import_reseau_kwh': 9.3,
        'surplus_injecte_kwh': 9.0,
        'pertes_stockage_kwh': 0.3,
        'etat_de_charge_kwh': [0.0] * 10 + [0.9487, 1.8974] + [2.846] * 7
        + [1.792, 0.7379, 0.0, 0.0, 0.0],
        'energie_effacee_kwh': None,
    }

    def test_le_resultat_d_aujourd_hui_est_inchange_terme_a_terme(self):
        resultat = simuler_batterie(self.CONSO, self.PROD, **self.ENTREE)
        for cle, valeur in self.AVANT.items():
            with self.subTest(cle=cle):
                self.assertEqual(resultat[cle], valeur)
        parametres = resultat['parametres']
        self.assertEqual(parametres['heures_charge'], [10, 11, 12])
        self.assertEqual(parametres['heures_decharge'], [19, 20, 21])

    def test_les_listes_d_heures_valent_une_fenetre_unique_sans_cible(self):
        legacy = simuler_batterie(self.CONSO, self.PROD, **self.ENTREE)
        entree = dict(self.ENTREE)
        entree.pop('heures_charge')
        entree.pop('heures_decharge')
        fenetres = simuler_batterie(self.CONSO, self.PROD, fenetres={
            'charge': [{'heures': [10, 11, 12], 'soc_cible_pct': None}],
            'decharge': [{'heures': [19, 20, 21], 'soc_cible_pct': None}],
        }, **entree)
        self.assertEqual(legacy, fenetres)
        self.assertEqual(legacy['parametres']['fenetres'], {
            'charge': [{'heures': [10, 11, 12], 'soc_cible_pct': None}],
            'decharge': [{'heures': [19, 20, 21], 'soc_cible_pct': None}],
        })

    def test_les_refus_d_aujourd_hui_sont_inchanges(self):
        entree = dict(self.ENTREE, heures_charge=None)
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(self.CONSO, self.PROD, **entree)
        self.assertEqual(refus.exception.champ, 'heures_charge')
        entree = dict(self.ENTREE, heures_decharge=[12])
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_batterie(self.CONSO, self.PROD, **entree)
        self.assertEqual(refus.exception.champ, 'heures_decharge')

    def test_hors_decalage_les_fenetres_publiees_valent_none(self):
        resultat = simuler_batterie(self.CONSO, self.PROD,
                                    strategie='autoconso',
                                    capacite_utile_kwh=10.0,
                                    puissance_charge_kw=5.0,
                                    puissance_decharge_kw=5.0,
                                    rendement_ar_pct=90.0)
        self.assertIsNone(resultat['parametres']['fenetres'])


class ParGroupeTest(unittest.TestCase):
    """Chaque groupe (CALX267) porte SES fenêtres."""

    def test_chaque_groupe_suit_sa_propre_cible(self):
        commun = dict(PARC, strategie='decalage', couplage='ac',
                      modele='PACK-X')
        resultat = simuler_groupes(CONSO, PROD_NUIT, [
            dict(commun, groupe='G1', fenetres={
                'charge': [{'heures': H_01_05, 'soc_cible_pct': 50}],
                'decharge': [{'heures': DECHARGE_SOIR}]}),
            dict(commun, groupe='G2', fenetres={
                'charge': [{'heures': H_01_05, 'soc_cible_pct': 30}],
                'decharge': [{'heures': DECHARGE_SOIR}]}),
        ])
        premier, second = (ligne['resultat'] for ligne in resultat['groupes'])
        self.assertAlmostEqual(premier['etat_de_charge_kwh'][5], 5.0,
                               delta=0.001)
        self.assertAlmostEqual(second['etat_de_charge_kwh'][5], 3.0,
                               delta=0.001)
        self.assertEqual(
            second['parametres']['fenetres']['charge'][0]['soc_cible_pct'],
            30)

    def test_un_recouvrement_dans_le_second_groupe_est_nomme(self):
        commun = dict(PARC, strategie='decalage', couplage='ac')
        with self.assertRaises(StrategieInvalide) as refus:
            simuler_groupes(CONSO, PROD_NUIT, [
                dict(commun, groupe='G1', fenetres={
                    'charge': [{'heures': H_01_05}],
                    'decharge': [{'heures': DECHARGE_SOIR}]}),
                dict(commun, groupe='G2', fenetres={
                    'charge': [{'heures': H_01_05},
                               {'heures': [4, 5, 6, 7]}],
                    'decharge': [{'heures': DECHARGE_SOIR}]}),
            ])
        self.assertEqual(refus.exception.champ,
                         'groupes[1].fenetres.charge[1]')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
