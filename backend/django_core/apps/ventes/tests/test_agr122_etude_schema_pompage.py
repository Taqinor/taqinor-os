"""AGR122 — les clés ``etude_params`` pompage v2 déclarées au schéma.

Le contrat partagé ``contract_samples/etude_pompage_preview.json`` (AGR2,
``cles_etude_params_v2``) est la seule source : chaque clé y est déclarée au
schéma avec SON propriétaire ; les DÉRIVÉES ``moteur_pompage`` sont exclusives
(un navigateur ne les écrit jamais) et ne sont jamais recopiées par une copie
ou une V2 (``CLES_DERIVEES_NON_COPIEES``, QJR117) ; les clés v1 du bloc
agricole hors contrat ont quitté le schéma (D-AGR-13).

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_agr122_etude_schema_pompage -v 2
"""
import json
from pathlib import Path

from django.test import SimpleTestCase
from rest_framework.test import APIClient, APITestCase

from apps.ventes.domain import etude_schema as S
from apps.ventes.domain.etudes import (
    CLES_DERIVEES_NON_COPIEES, etude_params_pour_copie)
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'etude_pompage_preview.json')
LIGNES = [('Pompe immergée 7,5 CV', '1', '9000')]


def _cles_v2():
    with open(CONTRAT, encoding='utf-8') as f:
        return json.load(f)['cles_etude_params_v2']


class ContratDeclareAuSchemaTests(SimpleTestCase):

    def test_le_contrat_porte_les_trois_familles(self):
        cles = _cles_v2()
        self.assertTrue(cles['entrees'])
        self.assertTrue(cles['derivees'])
        self.assertEqual(len(cles['derivees_v1_lues_par_le_rendu']), 7)

    def test_chaque_cle_est_declaree_avec_le_bon_proprietaire(self):
        cles = _cles_v2()
        for famille in ('entrees', 'derivees',
                        'derivees_v1_lues_par_le_rendu'):
            for item in cles[famille]:
                with self.subTest(cle=item['cle']):
                    self.assertIn(item['cle'], S.SCHEMA)
                    self.assertEqual(S.SCHEMA[item['cle']]['proprietaire'],
                                     item['proprietaire'])

    def test_les_entrees_sont_des_entrees_les_derivees_des_derivees(self):
        cles = _cles_v2()
        for item in cles['entrees']:
            with self.subTest(cle=item['cle']):
                self.assertEqual(S.SCHEMA[item['cle']]['nature'], S.ENTREE)
        for item in (cles['derivees']
                     + cles['derivees_v1_lues_par_le_rendu']):
            with self.subTest(cle=item['cle']):
                self.assertEqual(S.SCHEMA[item['cle']]['nature'], S.DERIVEE)
                self.assertEqual(S.SCHEMA[item['cle']]['proprietaire'],
                                 S.MOTEUR_POMPAGE)

    def test_les_cles_v1_hors_contrat_ont_quitte_le_schema(self):
        """D-AGR-13 : aucune relecture d'un ancien devis agricole."""
        for cle in ('current_fuel', 'fuel_spend_current', 'distance_m',
                    'hmt_static', 'hmt_drawdown', 'region', 'crop',
                    'surface_ha', 'profondeur_m', 'debit_souhaite_m3h',
                    'irrigation_method'):
            with self.subTest(cle=cle):
                self.assertNotIn(cle, S.SCHEMA)

    def test_une_cle_v1_retiree_est_refusee_et_nommee(self):
        reproches = S.valider({'distance_m': 20})
        self.assertEqual(len(reproches), 1)
        self.assertIn('distance_m', reproches[0])

    def test_l_ecran_ne_peut_ecrire_aucune_derivee_pompage(self):
        cles = _cles_v2()
        derivees = [i['cle'] for i in cles['derivees']
                    + cles['derivees_v1_lues_par_le_rendu']]
        self.assertEqual(sorted(S.cles_refusees_pour(S.ECRAN, derivees)),
                         sorted(derivees))
        self.assertEqual(S.cles_refusees_pour(S.MOTEUR_POMPAGE, derivees), [])

    def test_l_ecran_ecrit_toutes_les_entrees(self):
        entrees = [i['cle'] for i in _cles_v2()['entrees']]
        self.assertEqual(S.cles_refusees_pour(S.ECRAN, entrees), [])

    def test_chaque_derivee_pompage_n_est_jamais_recopiee(self):
        cles = _cles_v2()
        for item in (cles['derivees']
                     + cles['derivees_v1_lues_par_le_rendu']):
            with self.subTest(cle=item['cle']):
                self.assertIn(item['cle'], CLES_DERIVEES_NON_COPIEES)

    def test_qjr117_chaque_cle_non_copiee_reste_derivee_au_schema(self):
        for cle in CLES_DERIVEES_NON_COPIEES:
            with self.subTest(cle=cle):
                self.assertEqual(S.SCHEMA[cle]['nature'], S.DERIVEE)

    def test_la_copie_garde_les_entrees_et_purge_les_derivees(self):
        source = {'mode_pompe': 'neuve', 'besoin': {'volume_m3_jour': 135},
                  'pompe_kw': 4.41, 'm3_jour': 120.0, 'champ': {'kwc': 6.4}}
        self.assertEqual(etude_params_pour_copie(source),
                         {'mode_pompe': 'neuve',
                          'besoin': {'volume_m3_jour': 135}})

    def test_les_entrees_v2_nourrissent_le_moteur(self):
        """Un PATCH qui touche une entrée v2 relance les études (AGR123)."""
        for cle in ('besoin', 'source', 'hmt_entrees', 'plaque', 'mode_pompe',
                    'localisation', 'options_cochees', 'taille'):
            with self.subTest(cle=cle):
                self.assertIn(cle, S.entrees_du_moteur())


class EndpointEtudeParamsPompageTests(APITestCase):
    """Le refus tel que le navigateur le reçoit : 400 FR, aucune écriture."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), LIGNES,
            reference='DEV-AGR122-0010')
        self.devis.mode_installation = 'agricole'
        self.devis.save(update_fields=['mode_installation'])
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.url = ('/api/django/ventes/devis/%s/etude-params/'
                    % self.devis.id)

    def test_une_derivee_envoyee_par_le_navigateur_est_refusee(self):
        resp = self.api.patch(self.url, {'pompe_kw': 4.41}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('pompe_kw', resp.data['detail'])
        self.devis.refresh_from_db()
        self.assertNotIn('pompe_kw', self.devis.etude_params or {})

    def test_une_cle_inconnue_est_refusee_en_400_qui_la_nomme(self):
        resp = self.api.patch(self.url, {'crop': 'agrumes'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('crop', resp.data['detail'])

    def test_une_entree_v2_est_acceptee_et_fusionnee(self):
        resp = self.api.patch(
            self.url, {'besoin': {'mode': 'volume_declare',
                                  'volume_m3_jour': 135}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.etude_params['besoin']['volume_m3_jour'],
                         135)
