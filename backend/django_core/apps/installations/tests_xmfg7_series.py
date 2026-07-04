"""
XMFG7 — Capture des numéros de série à l'assemblage + étiquette du composite.

Couvre :
  * clôture avec séries transmises enregistre `SerieAssemblage` (composite +
    composant lié) ;
  * l'action `series` liste les séries de l'ordre ;
  * l'étiquette (`etiquette`) se génère (HTML WeasyPrint-ready, QR) et ne
    contient AUCUN prix ;
  * sans série de composite enregistrée, l'étiquette renvoie 404 proprement.

Run :
    python manage.py test apps.installations.tests_xmfg7_series -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, SerieAssemblage,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg7-co-{n}', defaults={'nom': nom or f'XMFG7 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg7-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100, prix_achat=0):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=prix_achat,
        quantite_stock=stock)


class TestSeriesAssemblage(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(
            self.company, nom='Coffret', stock=0, prix_achat=500)
        self.comp1 = make_produit(
            self.company, nom='Onduleur', stock=10, prix_achat=1000)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=1)
        self.ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-S1', kit=self.kit, quantite=2)

    def test_terminer_avec_series_les_enregistre(self):
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/terminer/', {
                'series_composite': ['SN-COFFRET-001', 'SN-COFFRET-002'],
                'series_composants': [
                    {'produit_id': self.comp1.id, 'numero_serie': 'SN-OND-A',
                     'composite_index': 0},
                    {'produit_id': self.comp1.id, 'numero_serie': 'SN-OND-B',
                     'composite_index': 1},
                ],
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        series = list(SerieAssemblage.objects.filter(ordre=self.ordre))
        self.assertEqual(len(series), 4)
        composites = [s for s in series if s.role == SerieAssemblage.Role.COMPOSITE]
        composants = [s for s in series if s.role == SerieAssemblage.Role.COMPOSANT]
        self.assertEqual(len(composites), 2)
        self.assertEqual(len(composants), 2)
        # le lien composite<->composant est correct
        ond_a = next(s for s in composants if s.numero_serie == 'SN-OND-A')
        self.assertEqual(ond_a.composite_ref.numero_serie, 'SN-COFFRET-001')

    def test_action_series_liste(self):
        self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/terminer/', {
                'series_composite': ['SN-X', 'SN-Y'],
            }, format='json')
        resp = self.api.get(f'{BASE}/ordres-assemblage/{self.ordre.id}/series/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 2)

    def test_etiquette_generee_sans_prix(self):
        self.api.post(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/terminer/', {
                'series_composite': ['SN-LABEL-1'],
            }, format='json')
        resp = self.api.get(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/etiquette/')
        self.assertEqual(resp.status_code, 200, resp.content)
        html = resp.content.decode('utf-8')
        self.assertIn('SN-LABEL-1', html)
        self.assertNotIn('500', html)  # prix_achat composite jamais affiché
        self.assertNotIn('1000', html)  # prix_achat composant jamais affiché

    def test_etiquette_sans_serie_404(self):
        resp = self.api.get(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/etiquette/')
        self.assertEqual(resp.status_code, 404, resp.content)
