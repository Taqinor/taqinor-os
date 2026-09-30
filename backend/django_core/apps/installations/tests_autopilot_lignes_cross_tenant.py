"""ERR115 / ERR116 — lignes enfants sans `company` propre : la CRÉATION doit
borner le parent (retour de livraison / ordre de démontage) à la société de
l'appelant, comme la mise à jour le faisait déjà.

Run :
    python manage.py test \
        apps.installations.tests_autopilot_lignes_cross_tenant -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import EmplacementStock, Produit
from apps.installations.models import (
    Installation, Kit, Livraison, OrdreDemontage, OrdreDemontageLigne,
    RetourLivraison, RetourLivraisonLigne,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'errlct-co-{n}', defaults={'nom': f'ERR LCT Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'errlct-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit', stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=Decimal('100'),
        prix_achat=0, quantite_stock=stock)


def make_retour(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='LCT',
        email=f'errlct-{company.id}-{n}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=f'CHT-LCT-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)
    depot = EmplacementStock.objects.create(
        company=company, nom=f'Dépôt {n}', is_principal=True)
    liv = Livraison.objects.create(
        company=company, reference=f'LIV-LCT-{n}', installation=inst,
        depot=depot, statut=Livraison.Statut.LIVREE)
    return RetourLivraison.objects.create(company=company, livraison=liv)


class TestRetourLivraisonLigneCrossTenant(TestCase):
    """ERR115 — POST d'une ligne sur le retour d'une autre société → 400."""

    def setUp(self):
        self.co_a = make_company()
        self.co_b = make_company()
        self.api_a = auth(make_user(self.co_a))
        self.retour_a = make_retour(self.co_a)
        self.retour_b = make_retour(self.co_b)
        self.produit_a = make_produit(self.co_a, nom='Produit A')

    def test_create_sur_retour_autre_societe_refuse(self):
        resp = self.api_a.post(f'{BASE}/retour-livraison-lignes/', {
            'retour': self.retour_b.id, 'produit': self.produit_a.id,
            'designation': 'Intrus', 'quantite_retournee': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('retour', resp.data)
        self.assertFalse(
            RetourLivraisonLigne.objects.filter(retour=self.retour_b).exists())

    def test_create_sur_retour_meme_societe_ok(self):
        resp = self.api_a.post(f'{BASE}/retour-livraison-lignes/', {
            'retour': self.retour_a.id, 'produit': self.produit_a.id,
            'designation': 'Ligne A', 'quantite_retournee': 0,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(
            RetourLivraisonLigne.objects.filter(retour=self.retour_a).exists())


def make_ordre(company, statut=OrdreDemontage.Statut.PLANIFIE):
    n = next(_seq)
    composite = make_produit(company, nom=f'Coffret {n}', stock=5)
    kit = Kit.objects.create(
        company=company, nom=f'Kit {n}', produit_compose=composite)
    return OrdreDemontage.objects.create(
        company=company, reference=f'DSM-LCT-{n}', kit=kit, quantite=1,
        statut=statut)


class TestOrdreDemontageLigneCrossTenant(TestCase):
    """ERR116 — POST d'une ligne sur l'ordre d'une autre société, ou sur un
    ordre qui n'est plus planifié → 400."""

    def setUp(self):
        self.co_a = make_company()
        self.co_b = make_company()
        self.api_a = auth(make_user(self.co_a))
        self.produit_a = make_produit(self.co_a, nom='Composant A')

    def _post(self, ordre):
        return self.api_a.post(f'{BASE}/ordre-demontage-lignes/', {
            'ordre': ordre.id, 'produit': self.produit_a.id,
            'designation': 'Ligne', 'quantite_recuperee': 1,
        }, format='json')

    def test_create_sur_ordre_autre_societe_refuse(self):
        ordre_b = make_ordre(self.co_b)
        resp = self._post(ordre_b)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('ordre', resp.data)
        self.assertFalse(
            OrdreDemontageLigne.objects.filter(ordre=ordre_b).exists())

    def test_create_sur_ordre_termine_refuse(self):
        ordre = make_ordre(self.co_a, statut=OrdreDemontage.Statut.TERMINE)
        resp = self._post(ordre)
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('ordre', resp.data)
        self.assertFalse(
            OrdreDemontageLigne.objects.filter(ordre=ordre).exists())

    def test_create_sur_ordre_planifie_meme_societe_ok(self):
        ordre = make_ordre(self.co_a)
        resp = self._post(ordre)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(
            OrdreDemontageLigne.objects.filter(ordre=ordre).exists())
