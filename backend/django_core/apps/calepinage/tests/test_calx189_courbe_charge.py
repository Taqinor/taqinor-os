"""CALX189 — la courbe de charge horaire assemblée, VE et PAC compris.

Ce qui est tenu ici :

* **aucune source saisie ⇒ le bloc « consommation » est OMIS**, et avec lui la
  batterie et l'autoconsommation, CHACUN avec son propre motif (le motif de
  l'autoconsommation est celui de son module, pas une reformulation) ;
* le total de la courbe assemblée égale EXACTEMENT la somme des totaux de ses
  composantes (base + chaque charge) ;
* une charge de véhicule sans ``km_par_jour`` est REFUSÉE en NOMMANT le champ
  (``charges.ChargeInvalide``) ;
* l'ordre de priorité des sources est tenu (atelier > import > mensuel >
  profil type), et la provenance retenue est PUBLIÉE ;
* les décisions fondateur du 21/09 sont appliquées : Q2 (véhicule prévu),
  Q3 (énergie de recharge hors production chiffrée), Q11 (plafond annoncé),
  Q12 (climatisation de mai à octobre), Q24 (facture bimestrielle ramenée au
  mois) ;
* le COP de la PAC suit la température de CHAQUE heure de la série (CALX264).

Série de test : une année 2021 SYNTHÉTIQUE (8 760 points), clairement
fabriquée pour le test et jamais présentée comme une mesure. Test PUR : aucune
base, aucun réseau.
"""
from __future__ import annotations

import datetime
import unittest

from apps.calepinage.services import courbe_charge
from apps.calepinage.services.autoconsommation import MOTIF_SANS_COURBE
from apps.calepinage.services.charges import ChargeInvalide
from apps.calepinage.services.courbe_charge import (
    CourbeChargeInvalide, construire_courbe_charge)

#: Les heures de la journée où la série de test porte de l'irradiance.
HEURES_DE_SOLEIL = range(7, 19)

#: Mai à octobre 2021 compte 184 jours (31+30+31+31+30+31) — la saison de
#: la décision fondateur Q12.
JOURS_DE_SAISON_CHAUDE = 184


def serie_de_test(*, annee=2021, t2m=20.0):
    """Une année horaire SYNTHÉTIQUE au format CALX142 (8 760 points)."""
    depart = datetime.datetime(annee, 1, 1)
    points = []
    for rang in range(8760):
        moment = depart + datetime.timedelta(hours=rang)
        points.append({
            'annee': moment.year,
            'mois': moment.month,
            'jour': moment.day,
            'heure': moment.hour,
            'gi_w_m2': 700.0 if moment.hour in HEURES_DE_SOLEIL else 0.0,
            't2m_c': t2m,
        })
    return {'points': points, 'pas_minutes': 60}


def layout_de_test(valeur_horaire=1.0):
    """Un document ATELIER minimal portant une courbe 24 h saisie (CALX255)."""
    return {'consumption': {'courbe24': [valeur_horaire] * 24,
                            'methode': 'courbe'}}


class OmissionTests(unittest.TestCase):
    """Aucune courbe ⇒ trois blocs omis, trois motifs distincts."""

    def test_serie_vide_omet_les_trois_blocs(self):
        resultat = construire_courbe_charge({'points': []}, consommation={})

        self.assertIsNone(resultat['courbe'])
        self.assertIsNone(resultat['consommation'])
        self.assertTrue(resultat['omissions']['consommation'])
        self.assertTrue(resultat['omissions']['batterie'])
        self.assertTrue(resultat['omissions']['autoconsommation'])

    def test_sans_aucune_source_saisie_le_bloc_est_omis(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={})

        self.assertIsNone(resultat['consommation'])
        self.assertEqual(resultat['omissions']['consommation'],
                         courbe_charge.MOTIF_CONSOMMATION)

    def test_chaque_bloc_dependant_porte_son_propre_motif(self):
        omissions = construire_courbe_charge(
            serie_de_test(), consommation={})['omissions']

        self.assertEqual(omissions['batterie'], courbe_charge.MOTIF_BATTERIE)
        # Le motif publié est CELUI du module d'autoconsommation : une
        # reformulation locale finirait par diverger de ce que l'écran dit.
        self.assertEqual(omissions['autoconsommation'], MOTIF_SANS_COURBE)
        self.assertNotEqual(omissions['batterie'],
                            omissions['autoconsommation'])

    def test_un_profil_type_seul_ne_suffit_pas(self):
        # Une FORME sans énergie ne porte aucun kWh : elle ne fait pas une
        # courbe de charge, et le bloc reste omis.
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'profil_type': {'cle': 'residentiel',
                            'courbes': {'annuel': [1.0 / 24] * 24},
                            'source': 'societe'},
        })

        self.assertIsNone(resultat['consommation'])


class TotauxTests(unittest.TestCase):
    """Le total assemblé = la somme de ses composantes, au kWh près."""

    def resultat(self):
        return construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(1.5),
            'charges': [
                {'type': 'vehicule', 'km_par_jour': 40,
                 'kwh_par_100km': 18, 'fenetre_recharge': [22, 23]},
                {'type': 'chauffe_eau', 'puissance_kw': 2.0,
                 'heures_fonctionnement': [5, 6]},
            ],
        })

    def test_total_egale_base_plus_charges(self):
        bloc = self.resultat()['consommation']

        self.assertAlmostEqual(
            bloc['total_kwh'],
            bloc['total_base_kwh'] + bloc['total_charges_kwh'], delta=0.05)

    def test_total_des_charges_egale_la_somme_de_chaque_charge(self):
        bloc = self.resultat()['consommation']

        self.assertAlmostEqual(
            bloc['total_charges_kwh'],
            sum(charge['kwh_an'] for charge in bloc['charges']), delta=0.05)

    def test_la_courbe_rendue_somme_bien_le_total_publie(self):
        resultat = self.resultat()

        self.assertEqual(len(resultat['courbe']), 8760)
        self.assertAlmostEqual(sum(resultat['courbe']),
                               resultat['consommation']['total_kwh'],
                               delta=0.05)

    def test_le_profil_mensuel_publie_somme_la_courbe(self):
        bloc = self.resultat()['consommation']

        self.assertEqual(len(bloc['profil_mensuel']), 12)
        self.assertAlmostEqual(
            sum(mois['kwh'] for mois in bloc['profil_mensuel']),
            bloc['total_kwh'], delta=0.5)

    def test_chaque_charge_reste_visible_separement(self):
        charges = self.resultat()['consommation']['charges']

        self.assertEqual([charge['code'] for charge in charges],
                         ['vehicule', 'chauffe_eau'])
        for charge in charges:
            self.assertEqual(charge['source'], 'saisie')
            self.assertTrue(charge['methode'])
            self.assertGreater(charge['kwh_an'], 0)

    def test_le_chauffe_eau_vaut_sa_puissance_sur_sa_plage(self):
        # Q10 : (kW, plage horaire). 2 kW pendant 2 h, 365 jours.
        charges = self.resultat()['consommation']['charges']
        chauffe_eau = charges[1]

        self.assertAlmostEqual(chauffe_eau['kwh_an'], 2.0 * 2 * 365,
                               delta=0.05)


class ChargeRefuseeTests(unittest.TestCase):
    """Une charge incomplète est refusée en NOMMANT le champ."""

    def test_vehicule_sans_km_par_jour_est_refuse(self):
        with self.assertRaises(ChargeInvalide) as refus:
            construire_courbe_charge(serie_de_test(), consommation={
                'layout': layout_de_test(),
                'charges': [{'type': 'vehicule', 'kwh_par_100km': 18,
                             'fenetre_recharge': [22, 23]}],
            })

        self.assertEqual(refus.exception.champ, 'vehicule.km_par_jour')
        self.assertIn('kilométrage quotidien', refus.exception.motif.lower())

    def test_chauffe_eau_sans_puissance_est_refuse(self):
        with self.assertRaises(ChargeInvalide) as refus:
            construire_courbe_charge(serie_de_test(), consommation={
                'layout': layout_de_test(),
                'charges': [{'type': 'chauffe_eau',
                             'heures_fonctionnement': [5, 6]}],
            })

        self.assertEqual(refus.exception.champ, 'chauffe_eau.puissance_kw')

    def test_type_de_charge_inconnu_est_refuse(self):
        with self.assertRaises(CourbeChargeInvalide) as refus:
            construire_courbe_charge(serie_de_test(), consommation={
                'layout': layout_de_test(),
                'charges': [{'type': 'sauna', 'puissance_kw': 3}],
            })

        self.assertEqual(refus.exception.champ, 'charges.type')
        self.assertIn('sauna', refus.exception.motif)


class PrioriteDesSourcesTests(unittest.TestCase):
    """La saisie la plus proche du client gagne (Q14), et se PUBLIE."""

    def test_le_layout_prime_sur_import_et_mensuel(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(2.0),
            'import_intervalle': {'valeurs': [0.5] * 8760, 'origine': 'ONEE'},
            'profil_mensuel': [{'mois': 1, 'kwh': 900}],
        })

        self.assertEqual(resultat['consommation']['courbe_origine'], 'layout')
        self.assertAlmostEqual(resultat['consommation']['total_kwh'],
                               2.0 * 8760, delta=0.05)

    def test_import_prime_sur_le_mensuel(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'import_intervalle': {'valeurs': [0.5] * 8760, 'origine': 'ONEE'},
            'profil_mensuel': [{'mois': 1, 'kwh': 900}],
        })

        self.assertEqual(resultat['consommation']['courbe_origine'],
                         'import_intervalle')
        self.assertAlmostEqual(resultat['consommation']['total_kwh'],
                               0.5 * 8760, delta=0.05)

    def test_le_mensuel_prime_sur_lannuel(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'profil_mensuel': [{'mois': 1, 'kwh': 900}],
            'annuel_kwh': 10000,
        })

        self.assertEqual(resultat['consommation']['courbe_origine'],
                         'profil_mensuel')
        self.assertAlmostEqual(resultat['consommation']['total_kwh'], 900,
                               delta=0.05)

    def test_lannuel_saisi_cale_le_profil_type(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'annuel_kwh': 9600,
            'profil_type': {'cle': 'residentiel',
                            'courbes': {'annuel': [1.0 / 24] * 24},
                            'source': 'societe'},
        })

        self.assertEqual(resultat['consommation']['courbe_origine'],
                         'profil_type')
        self.assertAlmostEqual(resultat['consommation']['total_kwh'], 9600,
                               delta=0.05)

    def test_un_import_dune_autre_annee_est_refuse_en_nommant_le_champ(self):
        with self.assertRaises(CourbeChargeInvalide) as refus:
            construire_courbe_charge(serie_de_test(), consommation={
                'import_intervalle': {'valeurs': [0.5] * 8784},
            })

        self.assertEqual(refus.exception.champ,
                         'consommation.import_intervalle.valeurs')


class DecisionsFondateurTests(unittest.TestCase):
    """Les décisions tranchées le 21/09, appliquées et annoncées."""

    def test_q24_une_facture_bimestrielle_est_ramenee_au_mois(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'profil_mensuel': [{'mois': 3, 'kwh': 600,
                                'periodicite': 'bimestrielle'}],
        })
        bloc = resultat['consommation']

        self.assertAlmostEqual(bloc['total_kwh'], 300, delta=0.05)
        self.assertTrue(any('bimestrielle' in mention
                            for mention in bloc['avertissements']))

    def test_q24_une_periodicite_inconnue_est_refusee(self):
        with self.assertRaises(CourbeChargeInvalide) as refus:
            construire_courbe_charge(serie_de_test(), consommation={
                'profil_mensuel': [{'mois': 3, 'kwh': 600,
                                    'periodicite': 'hebdomadaire'}],
            })

        self.assertIn('periodicite', refus.exception.champ)

    def test_q12_la_climatisation_ne_tourne_que_de_mai_a_octobre(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'clim', 'puissance_kw': 2.0,
                         'heures_fonctionnement': [13, 14, 15]}],
        })
        bloc = resultat['consommation']
        par_mois = {mois['mois']: mois['kwh'] for mois in
                    bloc['profil_mensuel']}

        self.assertAlmostEqual(bloc['charges'][0]['kwh_an'],
                               2.0 * 3 * JOURS_DE_SAISON_CHAUDE, delta=0.05)
        for hors_saison in (1, 2, 3, 4, 11, 12):
            self.assertEqual(par_mois.get(hors_saison, 0.0), 0.0)
        for en_saison in (5, 6, 7, 8, 9, 10):
            self.assertGreater(par_mois[en_saison], 0.0)

    def test_q12_une_saison_saisie_remplace_la_decision_par_defaut(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'piscine', 'puissance_kw': 1.0,
                         'heures_fonctionnement': [10],
                         'mois_actifs': [7, 8]}],
        })

        self.assertAlmostEqual(
            resultat['consommation']['charges'][0]['kwh_an'],
            1.0 * (31 + 31), delta=0.05)

    def test_q2_un_vehicule_seulement_prevu_est_compte_et_annonce(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'vehicule', 'km_par_jour': 40,
                         'kwh_par_100km': 18, 'fenetre_recharge': [22, 23],
                         'planifie': True}],
        })
        charge = resultat['consommation']['charges'][0]

        self.assertTrue(charge['planifie'])
        self.assertAlmostEqual(charge['kwh_an'], 40 / 100 * 18 * 365,
                               delta=0.05)
        self.assertTrue(any('future voiture' in hypothese
                            for hypothese in charge['hypotheses']))

    def test_q11_une_recharge_qui_deborde_est_plafonnee_et_le_dit(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'vehicule', 'km_par_jour': 1000,
                         'kwh_par_100km': 20, 'fenetre_recharge': [22, 23],
                         'puissance_borne_kw': 7.0}],
        })
        charge = resultat['consommation']['charges'][0]

        self.assertTrue(charge['plafonnee'])
        self.assertAlmostEqual(charge['kwh_an'], 7.0 * 2 * 365, delta=0.05)
        self.assertTrue(any('PLAFONNÉE' in hypothese
                            for hypothese in charge['hypotheses']))

    def test_q4_sans_puissance_de_borne_rien_nest_plafonne(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'vehicule', 'km_par_jour': 1000,
                         'kwh_par_100km': 20, 'fenetre_recharge': [22, 23]}],
        })
        charge = resultat['consommation']['charges'][0]

        self.assertFalse(charge['plafonnee'])
        self.assertAlmostEqual(charge['kwh_an'], 200 * 365, delta=0.5)

    def test_q3_lenergie_de_recharge_hors_production_est_chiffree(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'vehicule', 'km_par_jour': 40,
                         'kwh_par_100km': 18, 'fenetre_recharge': [1, 2]}],
        })
        charge = resultat['consommation']['charges'][0]

        # 1 h et 2 h du matin : la série n'y porte aucune irradiance, donc
        # TOUTE l'énergie de recharge devra venir de la batterie ou du réseau.
        self.assertAlmostEqual(charge['kwh_hors_production_an'],
                               charge['kwh_an'], delta=0.05)

    def test_q3_une_recharge_en_plein_jour_ne_compte_pas_hors_production(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'vehicule', 'km_par_jour': 40,
                         'kwh_par_100km': 18, 'fenetre_recharge': [12, 13]}],
        })
        charge = resultat['consommation']['charges'][0]

        self.assertAlmostEqual(charge['kwh_hors_production_an'], 0.0,
                               delta=0.05)


class PompeAChaleurTests(unittest.TestCase):
    """Le COP suit la température de CHAQUE heure de la série (CALX264)."""

    COP_POINTS = [{'t_ext_c': 0.0, 'cop': 2.0},
                  {'t_ext_c': 20.0, 'cop': 4.0}]

    def test_le_cop_est_lu_a_la_temperature_de_la_serie(self):
        resultat = construire_courbe_charge(
            serie_de_test(t2m=20.0), consommation={
                'layout': layout_de_test(0.0),
                'charges': [{'type': 'pac', 'puissance_kw': 5.0,
                             'cop_points': self.COP_POINTS,
                             'heures_fonctionnement': [6, 7]}],
            })
        charge = resultat['consommation']['charges'][0]

        # 20 °C ⇒ COP 4 ⇒ 5 kW / 4 = 1,25 kWh par heure de marche.
        self.assertAlmostEqual(charge['kwh_an'], 1.25 * 2 * 365, delta=0.5)

    def test_une_temperature_plus_froide_coute_plus_cher(self):
        chaud = construire_courbe_charge(
            serie_de_test(t2m=20.0), consommation={
                'layout': layout_de_test(0.0),
                'charges': [{'type': 'pac', 'puissance_kw': 5.0,
                             'cop_points': self.COP_POINTS,
                             'heures_fonctionnement': [6, 7]}],
            })['consommation']['charges'][0]
        froid = construire_courbe_charge(
            serie_de_test(t2m=0.0), consommation={
                'layout': layout_de_test(0.0),
                'charges': [{'type': 'pac', 'puissance_kw': 5.0,
                             'cop_points': self.COP_POINTS,
                             'heures_fonctionnement': [6, 7]}],
            })['consommation']['charges'][0]

        self.assertGreater(froid['kwh_an'], chaud['kwh_an'])
        self.assertAlmostEqual(froid['kwh_an'], 2 * chaud['kwh_an'], delta=1.0)

    def test_une_serie_sans_temperature_refuse_le_cop_par_temperature(self):
        serie = serie_de_test()
        serie['points'][10]['t2m_c'] = None

        with self.assertRaises(CourbeChargeInvalide) as refus:
            construire_courbe_charge(serie, consommation={
                'layout': layout_de_test(0.0),
                'charges': [{'type': 'pac', 'puissance_kw': 5.0,
                             'cop_points': self.COP_POINTS,
                             'heures_fonctionnement': [6, 7]}],
            })

        self.assertEqual(refus.exception.champ, 'meteo.t2m_c')

    def test_un_cop_constant_saisi_reste_admis(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0),
            'charges': [{'type': 'pac', 'puissance_kw': 6.0, 'cop': 3.0,
                         'heures_fonctionnement': [6, 7, 8]}],
        })
        charge = resultat['consommation']['charges'][0]

        self.assertAlmostEqual(charge['kwh_an'], 6.0 * 3 / 3.0 * 365,
                               delta=0.5)


class ContexteTests(unittest.TestCase):
    """L'entrée unique se lit aussi depuis le contexte de simulation."""

    def test_la_declaration_peut_venir_du_contexte(self):
        resultat = construire_courbe_charge(
            serie_de_test(),
            {'consommation': {'layout': layout_de_test(1.0)}})

        self.assertEqual(resultat['consommation']['courbe_origine'], 'layout')

    def test_la_declaration_explicite_prime_sur_le_contexte(self):
        resultat = construire_courbe_charge(
            serie_de_test(),
            {'consommation': {'layout': layout_de_test(1.0)}},
            consommation={'annuel_kwh': 4000})

        self.assertEqual(resultat['consommation']['courbe_origine'],
                         'profil_type')
        self.assertAlmostEqual(resultat['consommation']['total_kwh'], 4000,
                               delta=0.05)

    def test_la_provenance_de_la_courbe_est_toujours_publiee(self):
        bloc = construire_courbe_charge(
            serie_de_test(),
            consommation={'layout': layout_de_test(1.0)})['consommation']

        self.assertIn(bloc['courbe_origine'], courbe_charge.ORIGINES)
        self.assertEqual(bloc['pas_minutes'], 60)
        self.assertTrue(bloc['avertissements'])


def serie_de_deux_ans():
    """DEUX années SYNTHÉTIQUES identiques (2021 puis 2022, 17 520 points)."""
    return {'points': serie_de_test(annee=2021)['points']
            + serie_de_test(annee=2022)['points'], 'pas_minutes': 60}


class AnneeMoyenneTests(unittest.TestCase):
    """ACAL1603 — en météo pluriannuelle, « par an » = une année moyenne.

    Cas chiffré à la main : base saisie 1 kWh/h = 24 kWh/j × 365 = 8 760
    kWh/an ; voiture 30 km/j × 16 kWh/100 km = 4,8 kWh/j × 365 = 1 752
    kWh/an, rechargée de 22 h à 24 h (aucun soleil : tout « hors
    production ») ; total 10 512 kWh/an ; janvier = 31 × (24 + 4,8) = 892,8.
    """

    DECLARATION = {
        'layout': layout_de_test(1.0),
        'charges': [{'type': 'vehicule', 'km_par_jour': 30,
                     'kwh_par_100km': 16, 'fenetre_recharge': [22, 23]}],
    }

    def bloc(self, serie, annees):
        return construire_courbe_charge(
            serie, {'annees_fenetre': annees,
                    'consommation': dict(self.DECLARATION)})['consommation']

    def test_serie_de_deux_ans_total_et_kwh_an_valent_une_annee(self):
        bloc = self.bloc(serie_de_deux_ans(), 2)

        self.assertAlmostEqual(bloc['total_kwh'], 10512.0, delta=0.01)
        self.assertAlmostEqual(bloc['total_base_kwh'], 8760.0, delta=0.01)
        self.assertAlmostEqual(bloc['total_charges_kwh'], 1752.0, delta=0.01)
        self.assertAlmostEqual(bloc['charges'][0]['kwh_an'], 1752.0,
                               delta=0.01)
        self.assertAlmostEqual(bloc['charges'][0]['kwh_hors_production_an'],
                               1752.0, delta=0.01)
        janvier = next(m for m in bloc['profil_mensuel'] if m['mois'] == 1)
        self.assertAlmostEqual(janvier['kwh'], 892.8, delta=0.01)
        self.assertAlmostEqual(sum(m['kwh'] for m in bloc['profil_mensuel']),
                               bloc['total_kwh'], delta=0.05)

    def test_en_annee_type_rien_ne_change(self):
        une = self.bloc(serie_de_test(), 1)
        sans_contexte = construire_courbe_charge(
            serie_de_test(), consommation=dict(self.DECLARATION))
        self.assertEqual(une, sans_contexte['consommation'])
        self.assertAlmostEqual(une['total_kwh'], 10512.0, delta=0.01)

    def test_energie_annuelle_saisie_reste_annuelle_sur_deux_ans(self):
        # Jumeau : une énergie ANNUELLE saisie (profil type) se lit 9 000
        # kWh/an, jamais 4 500 (9 000 étalés sur deux années).
        bloc = construire_courbe_charge(
            serie_de_deux_ans(),
            {'annees_fenetre': 2, 'consommation': {'annuel_kwh': 9000}},
        )['consommation']
        self.assertAlmostEqual(bloc['total_kwh'], 9000.0, delta=0.05)

    def test_kwh_mensuels_saisis_restent_mensuels_sur_deux_ans(self):
        bloc = construire_courbe_charge(
            serie_de_deux_ans(),
            {'annees_fenetre': 2, 'consommation': {
                'profil_mensuel': [{'mois': 1, 'kwh': 520}]}},
        )['consommation']
        janvier = next(m for m in bloc['profil_mensuel'] if m['mois'] == 1)
        self.assertAlmostEqual(janvier['kwh'], 520.0, delta=0.05)


class FactureDuLeadTests(unittest.TestCase):
    """ACAL1608 — sans aucune consommation saisie dans l'atelier, la courbe
    de base est celle que ``consommation.py`` propose pour la facture du lead
    (posée dans la déclaration sous ``facture_lead`` par le constructeur du
    contexte), d'origine NOMMÉE ; un lead C&I ou agricole garde l'omission.

    Cas chiffré : la proposition rend une courbe plate de 0,5 kWh/h (12
    kWh/j) sans saisons ⇒ 12 × 365 = 4 380 kWh/an.
    """

    PROPOSITION = {'courbe24': [0.5] * 24, 'methode': 'facture',
                   'source': {'origine': 'lead', 'bareme': 'societe'},
                   'classe': 'residentiel'}

    def test_aucune_saisie_lead_a_facture_courbe_publiee(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': {}, 'facture_lead': dict(self.PROPOSITION)})
        bloc = resultat['consommation']

        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['courbe_origine'], 'facture_lead')
        self.assertIn('facture_lead', courbe_charge.ORIGINES)
        self.assertAlmostEqual(bloc['total_kwh'], 4380.0, delta=0.01)
        self.assertEqual(resultat['omissions']['autoconsommation'], '')
        self.assertTrue(any('facture du lead' in texte
                            for texte in bloc['avertissements']))

    def test_les_saisons_de_la_facture_modulent_la_courbe(self):
        proposition = dict(self.PROPOSITION,
                           saisons={'ete': 1.5, 'hiver': 1.0})
        bloc = construire_courbe_charge(serie_de_test(), consommation={
            'facture_lead': proposition})['consommation']
        juillet = next(m for m in bloc['profil_mensuel'] if m['mois'] == 7)
        janvier = next(m for m in bloc['profil_mensuel'] if m['mois'] == 1)
        self.assertAlmostEqual(juillet['kwh'], 31 * 12 * 1.5, delta=0.01)
        self.assertAlmostEqual(janvier['kwh'], 31 * 12.0, delta=0.01)

    def test_une_saisie_de_l_atelier_prime_sur_la_facture(self):
        bloc = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(1.0),
            'facture_lead': dict(self.PROPOSITION)})['consommation']
        self.assertEqual(bloc['courbe_origine'], 'layout')

    def test_lead_c_et_i_ou_agricole_garde_l_omission_motivee(self):
        for classe in ('force_motrice', 'agricole'):
            resultat = construire_courbe_charge(serie_de_test(), consommation={
                'facture_lead': dict(self.PROPOSITION, classe=classe)})
            self.assertIsNone(resultat['consommation'])
            self.assertTrue(any('profil' in texte
                                for texte in resultat['avertissements']))


class CourbeNulleRangeeTests(unittest.TestCase):
    """ACAL1962 (suite lecture) — 24 zéros rangés avant la correction de
    l'atelier ne sont PAS une consommation saisie : la cascade passe à la
    source suivante, comme pour la clé absente."""

    PROPOSITION = FactureDuLeadTests.PROPOSITION
    CHARGE = {'type': 'chauffe_eau', 'puissance_kw': 2.0,
              'heures_fonctionnement': [5, 6]}

    def test_le_predicat_est_unique_et_exact(self):
        from apps.calepinage.services.consommation import (
            _courbe24_est_nulle, profil_depuis_layout)
        self.assertTrue(_courbe24_est_nulle([0.0] * 24))
        self.assertTrue(_courbe24_est_nulle([0] * 24))
        self.assertFalse(_courbe24_est_nulle([0.0] * 23 + [0.01]))
        self.assertFalse(_courbe24_est_nulle(None))
        profil = profil_depuis_layout(layout_de_test(0.0))
        self.assertIsNone(profil['courbe24'])
        self.assertIsNone(profil_depuis_layout({})['courbe24'])

    def test_a_zeros_et_facture_du_lead_la_base_vient_de_la_facture(self):
        for layout in (layout_de_test(0.0), {}):  # (d) clé absente = zéros
            bloc = construire_courbe_charge(serie_de_test(), consommation={
                'layout': layout,
                'facture_lead': dict(self.PROPOSITION)})['consommation']
            self.assertEqual(bloc['courbe_origine'], 'facture_lead')
            self.assertAlmostEqual(bloc['total_base_kwh'], 4380.0, delta=0.01)

    def test_b_zeros_sans_autre_source_avec_charges_meme_chiffres(self):
        resultat = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.0), 'charges': [dict(self.CHARGE)]})
        bloc = resultat['consommation']

        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['courbe_origine'], 'layout')
        self.assertAlmostEqual(bloc['total_base_kwh'], 0.0, delta=0.001)
        self.assertAlmostEqual(bloc['total_kwh'], 2.0 * 2 * 365, delta=0.05)
        self.assertTrue(any("Aucune consommation de base n'est connue" in t
                            for t in bloc['avertissements']))

    def test_c_une_courbe_non_nulle_reste_inchangee(self):
        bloc = construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout_de_test(0.5),
            'facture_lead': dict(self.PROPOSITION)})['consommation']
        self.assertEqual(bloc['courbe_origine'], 'layout')
        self.assertAlmostEqual(bloc['total_base_kwh'], 0.5 * 24 * 365,
                               delta=0.05)
        self.assertFalse(any("Aucune consommation de base" in t
                             for t in bloc['avertissements']))

    def test_d_cle_absente_et_zeros_donnent_le_meme_resultat(self):
        # Une courbe ABSENTE et 24 zéros sont la même chose : avec des
        # charges, jamais perdues en silence (base 0 kWh, dite en clair).
        blocs = [construire_courbe_charge(serie_de_test(), consommation={
            'layout': layout, 'charges': [dict(self.CHARGE)]})['consommation']
            for layout in ({}, layout_de_test(0.0))]
        self.assertEqual(blocs[0], blocs[1])
        self.assertAlmostEqual(blocs[0]['total_kwh'], 2.0 * 2 * 365,
                               delta=0.05)
        self.assertIn(courbe_charge.MOTIF_BASE_NULLE,
                      blocs[0]['avertissements'])

    def test_sans_charge_les_deux_formes_sont_omises_avec_leur_motif(self):
        for layout in ({}, layout_de_test(0.0)):
            resultat = construire_courbe_charge(serie_de_test(), consommation={
                'layout': layout})
            self.assertIsNone(resultat['consommation'])
            self.assertEqual(resultat['omissions']['consommation'],
                             courbe_charge.MOTIF_CONSOMMATION)

    def test_la_phrase_aucun_repli_n_est_emise_que_si_rien_n_est_trouve(self):
        for layout in ({'consumption': {}}, layout_de_test(0.0)):
            trouve = construire_courbe_charge(serie_de_test(), consommation={
                'layout': layout,
                'facture_lead': dict(self.PROPOSITION)})
            self.assertFalse(any("l'atelier" in t and 'VIDE' in t or 'ignorée' in t
                                 for t in trouve['avertissements']))
            rien = construire_courbe_charge(serie_de_test(), consommation={
                'layout': layout})
            self.assertTrue(any("l'atelier" in t and 'VIDE' in t or 'ignorée' in t
                                for t in rien['avertissements']))
