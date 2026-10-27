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

    def test_bi_horaire_hp_a_la_pointe_publiee_hn_ailleurs(self):
        tarif = tc.tarif_applicable({'contrat': 'bt_force_motrice',
                                     'option_bi_horaire': True})
        self.assertEqual([p['poste'] for p in tarif['tarifs_par_poste']],
                         ['pointe', 'normales'])
        # CEC5 — midi = heures normales ; 18 h GMT en hiver = pointe.
        self.assertEqual(tc.tarif_du_poste(tarif, 6, 12)['poste'], 'normales')
        self.assertEqual(tc.tarif_du_poste(tarif, 12, 18)['poste'], 'pointe')

    def test_cec4_prix_declares_sans_contrat_valorises(self):
        mt = tc.tarif_applicable({'base_tarifs': 'ht', 'mt': {
            'tarif_pointe': 1.2, 'tarif_pleines': 0.9, 'tarif_creuses': 0.6}})
        self.assertEqual((mt['contrat'], mt['origine']),
                         ('mt_general', 'declare_facture'))
        bt = tc.tarif_applicable({'base_tarifs': 'ttc', 'bt': {'tranches': [
            {'tarif_kwh': 1.7}]}})
        self.assertEqual(bt['origine'], 'declare_facture')
        self.assertIsNone(bt['contrat'])
        self.assertEqual(tc.tarif_applicable({})['origine'], 'omis')


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

    def test_cec2_tranches_sans_seuils_refusees_nommees(self):
        reproches = es.valider({'tarif_declare': {
            'contrat': 'bt_patente', 'bt': {'tranches': [
                {'tarif_kwh': 1.5}, {'tarif_kwh': 1.7}]}}})
        self.assertTrue(any('etude_params.tarif_declare.bt.tranches' in r
                            for r in reproches))

    def test_cec2_lecture_101_500_ramenee_au_plafond_precedent(self):
        tranches = [{'tarif_kwh': 1.0, 'seuil_min_kwh': 0, 'seuil_max_kwh': 100},
                    {'tarif_kwh': 1.2, 'seuil_min_kwh': 101,
                     'seuil_max_kwh': 500},
                    {'tarif_kwh': 1.4, 'seuil_min_kwh': 501}]
        self.assertEqual(tc.seuils_contigus(tranches),
                         [(0.0, 100.0), (100.0, 500.0), (500.0, None)])
        self.assertEqual(es.valider({'tarif_declare': {
            'contrat': 'bt_force_motrice', 'bt': {'tranches': tranches}}}), [])

    def test_cec4_cec5_devis_envoye_garde_les_regles_d_origine(self):
        mt = {'tarif_pointe': 1.2, 'tarif_pleines': 0.9, 'tarif_creuses': 0.6}
        self.assertEqual(tc.tarif_applicable(
            {'mt': mt}, regles_origine=True)['origine'], 'omis')
        # Bi-horaire : la grille comme hier (aucune alerte nouvelle), c'est la
        # valorisation qui omet (test_ciq204).
        self.assertEqual(tc.tarif_applicable(
            {'contrat': 'bt_force_motrice', 'option_bi_horaire': True},
            regles_origine=True)['origine'], 'grille_officielle')
        # Tranches déclarées sans seuils : lues brutes, comme avant CEC2.
        declare = {'bt': {'tranches': [{'tarif_kwh': 1.4}, {'tarif_kwh': 1.5}]}}
        self.assertEqual(tc._seuils_bt({'origine': 'declare_facture'}, declare,
                                       origine=True),
                         [(None, None), (None, None)])

    def test_cec2_derniere_tranche_plafonnee_refusee(self):
        tranches = [{'tarif_kwh': 1.0, 'seuil_min_kwh': 0, 'seuil_max_kwh': 100},
                    {'tarif_kwh': 1.2, 'seuil_min_kwh': 100,
                     'seuil_max_kwh': 500}]
        self.assertIsNone(tc.seuils_contigus(tranches))
        self.assertTrue(any('bt.tranches' in r for r in es.valider(
            {'tarif_declare': {'contrat': 'bt_patente',
                               'bt': {'tranches': tranches}}})))

    def test_cec8_facture_2025_ht_a_la_tva_de_son_annee(self):
        declare = {'contrat': 'bt_patente', 'base_tarifs': 'ttc',
                   'date_facture': '2025-12-15',
                   'bt': {'tranches': [{'tarif_kwh': 1.18}]}}
        poste = tc.tarif_applicable(declare)['tarifs_par_poste'][0]
        # Facture de 2025 (TVA 18 %, bareme.TVA_PAR_MILLESIME) : HT 1,00.
        self.assertEqual(poste['tarif_kwh_ht'], 1.0)
        self.assertEqual(poste['tarif_kwh_ttc'], 1.2)
        self.assertIn('2025', tc.tarif_applicable(declare)['mention'])
        origine = tc.tarif_applicable(declare, regles_origine=True)
        self.assertEqual(origine['tarifs_par_poste'][0]['tarif_kwh_ttc'], 1.18)

    def test_cec13_regles_du_devis(self):
        from types import SimpleNamespace
        self.assertEqual(tc.regles_du(None), {'regles_origine': False})
        self.assertEqual(tc.regles_du(SimpleNamespace(regles_calcul=2)),
                         {'regles_origine': True})
        self.assertEqual(tc.regles_du(SimpleNamespace(regles_calcul=3)),
                         {'regles_origine': False})
