"""CIQ203 — le tarif du client C&I résolu (facture d'abord, grille en repli
étiqueté, sinon omis) + clés ``tarif_declare`` / ``saisies_economie_ci`` au
schéma.

SimpleTestCase : aucune base. Formes = contrat partagé
``contract_samples/tarifs_ci.json`` (CIQ11).
"""
import json
import os

from django.test import SimpleTestCase

from apps.ventes import tarif_ci as tc
from apps.ventes.domain import etude_schema as es

_CONTRAT = os.path.join(os.path.dirname(__file__), os.pardir,
                        'contract_samples', 'tarifs_ci.json')


def _contrat():
    with open(_CONTRAT, encoding='utf-8') as fh:
        return json.load(fh)


class TarifApplicableTest(SimpleTestCase):
    def test_facture_mt_declaree_prix_du_client(self):
        ex = _contrat()['exemple']
        tarif = tc.tarif_applicable(ex['tarif_declare'], tension='mt')
        self.assertEqual(tarif, ex['tarif'])
        self.assertEqual(tarif['origine'], 'declare_facture')

    def test_patente_sans_prix_repli_grille(self):
        ex = _contrat()['exemple_bt_repli']
        tarif = tc.tarif_applicable(ex['tarif_declare'], tension='bt')
        self.assertEqual(tarif, ex['tarif'])
        t2 = tarif['tarifs_par_poste'][1]
        self.assertEqual(t2['tarif_kwh_ttc'], 1.7090)
        self.assertEqual(t2['tarif_kwh_ht'], 1.4242)
        self.assertTrue(t2['derive_ht_estimation'])
        # au-delà de 150 kWh/mois : la tranche 2, marquée à confirmer
        poste = tc.tarif_du_poste(tarif, 6, 12, kwh_mois=400)
        self.assertEqual(poste['tarif_kwh_ttc'], 1.7090)
        self.assertEqual(poste['etiquette'],
                         'règle de tranche à confirmer sur facture')
        self.assertEqual(
            tc.tarif_du_poste(tarif, 6, 12, kwh_mois=120)['tarif_kwh_ttc'],
            1.5146)

    def test_contrat_inconnu_omis_sans_prix_plat(self):
        ex = _contrat()['exemple_omis']
        tarif = tc.tarif_applicable(None)
        self.assertEqual(tarif, ex['tarif'])
        tarif_bt = tc.tarif_applicable({'contrat': None}, tension='bt')
        blob = json.dumps([tarif, tarif_bt])
        for interdit in ('1.75', '1.2,', '1.20', '0.95', '0.7,'):
            self.assertNotIn(interdit, blob)
        self.assertEqual(tarif_bt['origine'], 'omis')

    def test_repli_mt_21_12_18h_pointe(self):
        tarif = tc.tarif_applicable(None, tension='mt')
        self.assertEqual(tarif['origine'], 'grille_officielle')
        self.assertEqual(tarif['contrat'], 'mt_general')
        poste = tc.tarif_du_poste(tarif, 12, 18)
        self.assertEqual(poste['poste'], 'pointe')
        self.assertEqual(poste['tarif_kwh_ttc'], 1.4157)
        # Jamais une moyenne pondérée : midi d'été = pleines.
        self.assertEqual(tc.tarif_du_poste(tarif, 6, 12)['tarif_kwh_ttc'],
                         1.0101)

    def test_domestique_sans_prix_omis(self):
        tarif = tc.tarif_applicable({'contrat': 'bt_domestique'})
        self.assertEqual(tarif['origine'], 'omis')
        self.assertEqual(tarif['tarifs_par_poste'], [])

    def test_ttc_declare_garde_sa_base(self):
        tarif = tc.tarif_applicable({
            'contrat': 'mt_general', 'base_tarifs': 'ttc',
            'provenance': 'facture', 'date_facture': '2026-08-31',
            'saisi_le': '2026-09-01',
            'mt': {'tarif_pointe': 1.2, 'tarif_pleines': 0.96,
                   'tarif_creuses': 0.6}})
        p = tarif['tarifs_par_poste'][0]
        self.assertEqual(p['tarif_kwh_ttc'], 1.2)
        self.assertEqual(p['tarif_kwh_ht'], 1.0)
        self.assertEqual(p['base_publiee'], 'ttc')

    def test_bi_horaire_heure_omise(self):
        tarif = tc.tarif_applicable({'contrat': 'bt_force_motrice',
                                     'option_bi_horaire': True})
        self.assertEqual([p['poste'] for p in tarif['tarifs_par_poste']],
                         ['pointe', 'normales'])
        self.assertIsNone(tc.tarif_du_poste(tarif, 6, 12, kwh_mois=900))


class SchemaTarifDeclareTest(SimpleTestCase):
    def test_valider_accepte_les_deux_cles(self):
        ex = _contrat()['exemple']
        bloc = {'tarif_declare': ex['tarif_declare'],
                'saisies_economie_ci': {'revente_demandee': False}}
        self.assertEqual(es.valider(bloc), [])
        self.assertEqual(es.cles_refusees_pour(es.ECRAN, bloc), [])

    def test_prix_negatif_nomme_le_champ(self):
        reproches = es.valider({'tarif_declare': {
            'contrat': 'mt_general',
            'mt': {'tarif_pointe': -1, 'tarif_pleines': 1,
                   'tarif_creuses': 1}}})
        self.assertTrue(any('etude_params.tarif_declare.mt.tarif_pointe' in r
                            for r in reproches))

    def test_bi_horaire_patente_nomme_option(self):
        reproches = es.valider({'tarif_declare': {
            'contrat': 'bt_patente', 'option_bi_horaire': True}})
        self.assertTrue(any(
            'etude_params.tarif_declare.option_bi_horaire' in r
            for r in reproches))

    def test_mt_sans_ses_trois_postes(self):
        reproches = es.valider({'tarif_declare': {
            'contrat': 'mt_general', 'mt': {'tarif_pointe': 1.1}}})
        self.assertTrue(any('mt.tarif_pleines' in r for r in reproches))
        self.assertTrue(any('mt.tarif_creuses' in r for r in reproches))

    def test_aller_retour_identique(self):
        ex = _contrat()['exemple']
        saisies = {'revente_demandee': False, 'parcours_aide': 'aucun'}
        bloc = es.fusionner({}, proprietaire=es.ECRAN,
                            tarif_declare=ex['tarif_declare'],
                            saisies_economie_ci=saisies)
        rouvert = json.loads(json.dumps(bloc))
        bloc2 = es.fusionner(rouvert, proprietaire=es.ECRAN,
                             tarif_declare=rouvert['tarif_declare'],
                             saisies_economie_ci=rouvert['saisies_economie_ci'])
        self.assertEqual(bloc2, bloc)
