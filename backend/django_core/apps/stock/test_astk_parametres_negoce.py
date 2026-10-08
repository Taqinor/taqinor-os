"""ASTK201 (C-ASTK-049) — l'API paramètres-négoce n'expose que les réglages
RÉELLEMENT lus (`consignation_activee`, `atp_horizon_jours`) ; un PATCH d'un
réglage sans lecteur répond 400 « Réglage non branché. » (jamais un 200 sans
effet) ; la fonction morte `progression_seuil_rfa` est supprimée.

Sonde WMS-2 d'origine : PATCH ``seuil_alerte_rfa_pct`` 50 → 200 sans effet.

Aucun mock : vue et serializer réels.

Run :
    python manage.py test apps.stock.test_astk_parametres_negoce -v 2
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import services_rfa
from apps.stock.models import ParametresNegoce

User = get_user_model()

URL = '/api/django/stock/parametres-negoce/'
CONTRAT = (Path(__file__).resolve().parent / 'contract_samples'
           / 'negoce_consignation_rfa.json')
NON_BRANCHES = ('van_sales_active', 'seuil_alerte_rfa_pct',
                'heures_tournee_defaut', 'seuil_alerte_marge_pct',
                'cout_rupture_jour_mad')


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ParametresNegoceTests(TestCase):
    def setUp(self):
        self.co = make_company('astk201-co', 'ASTK201 Co')
        self.admin = User.objects.create_user(
            username='astk201_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = auth(self.admin)

    def test_seuls_reglages_lus_exposes(self):
        rep = self.api.get(URL)
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(
            sorted(rep.json()),
            sorted(['id', 'consignation_activee', 'atp_horizon_jours',
                    'updated_at']))

    def test_patch_reglage_non_branche_400(self):
        avant = ParametresNegoce.get(self.co).seuil_alerte_rfa_pct
        for champ, valeur in (('seuil_alerte_rfa_pct', 50),
                              ('van_sales_active', False),
                              ('heures_tournee_defaut', 3),
                              ('seuil_alerte_marge_pct', 10),
                              ('cout_rupture_jour_mad', '100')):
            rep = self.api.patch(URL, {champ: valeur}, format='json')
            self.assertEqual(rep.status_code, 400, (champ, rep.content))
            self.assertEqual(rep.json()[champ], ['Réglage non branché.'])
        self.assertEqual(
            ParametresNegoce.get(self.co).seuil_alerte_rfa_pct, avant)
        # Un réglage vivant passe toujours ; relire GET → identique.
        rep = self.api.patch(URL, {'atp_horizon_jours': 15}, format='json')
        self.assertEqual(rep.status_code, 200, rep.content)
        self.assertEqual(self.api.get(URL).json(), rep.json())
        self.assertEqual(rep.json()['atp_horizon_jours'], 15)

    def test_reponse_conforme_contrat(self):
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        route = contrat['routes']['parametres_negoce']
        rep = self.api.get(URL)
        self.assertEqual(sorted(rep.json()), sorted(route['exemple']))
        rep = self.api.patch(URL, {'seuil_alerte_rfa_pct': 50},
                             format='json')
        self.assertEqual(rep.status_code, 400)
        corps = rep.json()
        self.assertTrue(corps['error']['request_id'])
        corps['error']['request_id'] = (
            route['exemple_erreur_400']['error']['request_id'])
        self.assertEqual(corps, route['exemple_erreur_400'])

    def test_progression_seuil_rfa_supprimee(self):
        self.assertFalse(hasattr(services_rfa, 'progression_seuil_rfa'))
