"""CIQ122 — cas de référence C&I sur ``etudier_ci`` (comportement, pas parité).

Aucune assertion de parité JS : chaque cas pose un COMPORTEMENT attendu du
moteur serveur, avec sa source.

Fixtures :
* PVGIS FIGÉ — ``fixtures/ciq122_pvgis_casablanca.json`` (table vendorisée de
  Casablanca, ``apps.parametres.pvgis_profils``, figée le 2026-10-05) ;
* catalogue de TEST — onduleurs réseau Huawei SEEDÉS
  (``seed_catalogue.CATALOGUE``, prix TTC du fondateur → HT 20 %), panneau
  Jinko 710 W seedé (fiche 2 384 × 1 303 mm), structure bac acier de test ;
* profils de charge — archétypes sourcés CIQ107 (bureau = BDEW G1, hôtel et
  école = NREL ComStock AMY2018, fichier ``moteur_ci/donnees/
  archetypes_charge.json``) ou profil DÉCLARÉ (plages, équipes, fermetures) ;
* tarif — grille officielle ONEE (BT patenté / MT général) par
  ``tarif_ci.tarif_applicable`` (CIQ203), jamais un prix plat.

Module pur côté base : le catalogue, les réglages société et la date sont
injectés (aucune requête), PVGIS est lu du fichier figé.
"""
import datetime
import json
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from apps.stock.management.commands.seed_catalogue import CATALOGUE, ht_at
from apps.ventes.domain import etude_ci
from apps.ventes.quote_engine.constants_82_21 import PLAFOND_INJECTION_PCT
from apps.ventes.tests.test_ciq111_combinaison_onduleurs import _catalogue_huawei
from core.electrique.onduleurs import bornes_dc_ac

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'ciq122_pvgis_casablanca.json'
PVGIS = json.loads(FIXTURE.read_text(encoding='utf-8'))


def _prix_seed(sku):
    for _nom, s, _cat, ttc, *_r in CATALOGUE:
        if s == sku:
            return ht_at(ttc, Decimal('20'))
    raise KeyError(sku)


MODULE = {'produit': 9001, 'designation': 'Panneau Jinko 710W', 'pmax_wc': 710,
          'prix_connu': True, 'prix_vente_ht': _prix_seed('PAN-JK-710'),
          'longueur_mm': 2384, 'largeur_mm': 1303, 'poids_kg': 38}
STRUCTURE = {'id': 9002, 'nom': 'Structure bac acier (test)', 'role_ci': 'structure_ci',
             'role_devis': '', 'type_pose': 'bac_acier', 'fiche': {}, 'prix_connu': True,
             'eligible_ci': True, 'prix_vente_ht': _prix_seed('STR-ACIER')}
CATALOGUE_TEST = {
    'elements': [STRUCTURE],
    'onduleurs': _catalogue_huawei(),
    'module': MODULE,
    'prix_par_id': {MODULE['produit']: MODULE['prix_vente_ht'],
                    STRUCTURE['id']: STRUCTURE['prix_vente_ht']},
}


def _corps(**extra):
    corps = {
        'mode': 'commercial', 'tension': 'bt', 'phases': 'tri',
        'site': {'ville': 'Casablanca', 'lat': 33.57, 'lon': -7.59},
        'tarif': {'contrat': 'bt_patente'},
        'consommation': {'kwh_mensuels': [6000] * 12},
        'contraintes': {'revente_choisie': False, 'nb_points_raccordement': 1,
                        'longueur_dc_m': None, 'longueur_ac_m': None},
        'toit': {'type_pose': None, 'surface_utile_m2': None},
    }
    corps.update(extra)
    return corps


def _etudier(**extra):
    with mock.patch.object(etude_ci, 'lire_catalogue_ci', return_value=CATALOGUE_TEST), \
            mock.patch.object(etude_ci, '_reglages_societe', return_value=None), \
            mock.patch.object(etude_ci, '_aujourdhui', return_value=datetime.date(2026, 10, 5)), \
            mock.patch.object(etude_ci, 'lire_production', return_value=(
                PVGIS['productible_mensuel'], PVGIS['formes_saison'], PVGIS['source'])):
        return etude_ci.etudier_ci(None, _corps(**extra))


class CasReferenceTests(unittest.TestCase):

    def test_definitions_iea_pvps_t1_28(self):
        # IEA PVPS T1-28:2016 : autoconsommation = autoconsommé ÷ production ;
        # couverture (autoproduction) = autoconsommé ÷ consommation.
        b = _etudier(rythme={'categorie_commerciale': 'bureau'})['bilan']
        conso = sum(m['consommation_kwh'] for m in b['par_mois'])
        self.assertAlmostEqual(b['taux_autoconso'], b['autoconso_kwh'] / b['production_kwh'],
                               delta=0.001)
        self.assertAlmostEqual(b['taux_couverture'], b['autoconso_kwh'] / conso, delta=0.001)

    def test_bureau_g1_et_hotel_comstock_meme_facture(self):
        # BDEW G1 (demandlib) contre NREL ComStock small hotel, même kWh.
        bureau = _etudier(rythme={'categorie_commerciale': 'bureau'})
        hotel = _etudier(rythme={'categorie_commerciale': 'hotel'})
        self.assertNotEqual(bureau['taille']['retenue_kwc'], hotel['taille']['retenue_kwc'])
        self.assertNotEqual(bureau['bilan']['taux_couverture'], hotel['bilan']['taux_couverture'])

    def test_bureau_ferme_le_week_end_surplus_non_valorise(self):
        # Profil DÉCLARÉ : lundi-vendredi 8 h-18 h, samedi et dimanche fermés.
        e = _etudier(rythme={'jours_ouverts': [True] * 5 + [False, False],
                             'plages': {'ouvre': [[8, 18]]}, 'talon': {'kw': 1}},
                     taille_explicite_kwc=40)
        week_end = [h for h in e['bilan']['horaire'] if h['type_jour'] == 'ferme']
        self.assertTrue(week_end)
        self.assertGreater(sum(h['nb_jours'] * sum(h['surplus_kwh']) for h in week_end), 0)
        self.assertEqual(e['bilan']['injecte_valorise_kwh'], 0)

    def test_ecole_fermee_juillet_aout_non_valorises(self):
        # NREL ComStock primary school + fermeture déclarée 01/07 → 31/08 ; les
        # factures de juillet-août ne portent que le talon (1 kW × 744 h).
        e = _etudier(consommation={'kwh_mensuels': [6000] * 6 + [744, 744] + [6000] * 4},
                     rythme={'categorie_commerciale': 'ecole', 'talon': {'kw': 1},
                             'fermetures': [{'du': '07-01', 'au': '08-31',
                                             'motif': 'vacances scolaires'}]},
                     taille_explicite_kwc=30)
        par_mois = {m['mois']: m for m in e['bilan']['par_mois']}
        for mois in (7, 8):
            self.assertGreater(par_mois[mois]['surplus_kwh'], par_mois[mois]['autoconso_kwh'])
            self.assertGreater(par_mois[mois]['surplus_kwh'], par_mois[6]['surplus_kwh'])
        self.assertEqual(e['bilan']['injecte_valorise_kwh'], 0)

    def test_atelier_3x8_autoconsomme_au_moins_autant_que_1x8(self):
        # Même PUISSANCE appelée pendant les équipes : le 3x8 consomme 3 × l'énergie
        # du 1x8 (24 h au lieu de 8 h) — à taille égale, il absorbe au moins autant.
        un = _etudier(mode='industriel', consommation={'kwh_mensuels': [4000] * 12},
                      rythme={'jours_ouverts': [True] * 6 + [False], 'equipes': '1x8',
                              'debut_equipe_h': 6, 'talon': {'kw': 0}},
                      taille_explicite_kwc=60)
        trois = _etudier(mode='industriel', consommation={'kwh_mensuels': [12000] * 12},
                         rythme={'jours_ouverts': [True] * 6 + [False], 'equipes': '3x8',
                                 'debut_equipe_h': 6, 'talon': {'kw': 0}},
                         taille_explicite_kwc=60)
        self.assertGreaterEqual(trois['bilan']['autoconso_kwh'], un['bilan']['autoconso_kwh'])

    def test_300_kwc_onduleurs_dans_les_bornes_dc_ac(self):
        e = _etudier(consommation={'kwh_mensuels': [60000] * 12},
                     rythme={'categorie_commerciale': 'commerce'}, taille_explicite_kwc=300)
        ond = e['composition']['onduleurs']
        ac = sum(i['kw_ac'] * i['quantite'] for i in ond['combinaison'])
        self.assertLessEqual(300 / ac, bornes_dc_ac().borne_usuelle.valeur + 1e-9)

    def test_toit_declare_plafonnant(self):
        e = _etudier(consommation={'kwh_mensuels': [30000] * 12},
                     rythme={'categorie_commerciale': 'bureau'},
                     toit={'type_pose': 'bac_acier', 'surface_utile_m2': 300})
        self.assertEqual(e['taille']['raison_arret'], 'toit')
        self.assertLessEqual(e['taille']['retenue_kwc'], e['taille']['bornes']['toit']['kwc'])

    def test_mt_avec_revente_injection_plafonnee(self):
        # Loi 82-21 art. 12 + ANRE 04/26 : 20 % de la production annuelle.
        e = _etudier(mode='industriel', tension='mt', tarif={'contrat': 'mt_general'},
                     consommation={'kwh_mensuels': [3000] * 12},
                     rythme={'jours_ouverts': [True] * 5 + [False, False],
                             'plages': {'ouvre': [[8, 17]]}, 'talon': {'kw': 0}},
                     contraintes={'revente_choisie': True, 'longueur_dc_m': None,
                                  'longueur_ac_m': None, 'nb_points_raccordement': 1},
                     taille_explicite_kwc=80)
        b = e['bilan']
        self.assertLessEqual(b['injecte_valorise_kwh'],
                             b['production_kwh'] * PLAFOND_INJECTION_PCT / 100 + 1)
        self.assertGreater(b['injecte_valorise_kwh'], 0)

    def test_bt_aucun_surplus_valorise(self):
        e = _etudier(rythme={'categorie_commerciale': 'bureau'},
                     contraintes={'revente_choisie': True, 'longueur_dc_m': None,
                                  'longueur_ac_m': None, 'nb_points_raccordement': 1},
                     taille_explicite_kwc=80)
        self.assertGreater(e['bilan']['surplus_kwh'], 0)
        self.assertEqual(e['bilan']['injecte_valorise_kwh'], 0)


if __name__ == '__main__':
    unittest.main()
