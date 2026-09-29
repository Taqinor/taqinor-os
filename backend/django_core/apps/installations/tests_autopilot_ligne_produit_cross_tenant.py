"""error-autopilot — cross-tenant ``produit`` sur les lignes de retour de
livraison / démontage (multi-tenant rule, CLAUDE.md).

``RetourLivraisonLigneSerializer`` expose ``produit`` en PK writable sans
queryset scopé société, et ``RetourLivraisonLigneViewSet`` ne vérifie que le
``retour`` parent (jamais ``produit``) — un responsable société A peut donc
PATCHer (ou POSTer) une ligne avec le ``produit`` d'une société B : à la
validation, ``valider_retour_livraison`` verrouille ce produit
(``lock_produit``, sans filtre société) et crédite le stock de la société B.
Même trou côté ``OrdreDemontageLigneSerializer``/``OrdreDemontageLigneViewSet``
(XMFG12).

Couvre :
  * PATCH ``produit`` cross-société sur une ligne de retour de livraison
    existante → 400 nommant ``produit`` (actuellement 200) ;
  * POST direct d'une ligne de retour de livraison avec un ``produit`` d'une
    autre société → 400 (actuellement 201, aucun ``perform_create`` sur
    ``main``) ;
  * mêmes deux cas sur les lignes de démontage (XMFG12) ;
  * contrôle : un ``produit`` de la même société reste accepté (200/201).

Run :
    python manage.py test \
        apps.installations.tests_autopilot_ligne_produit_cross_tenant -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit, EmplacementStock
from apps.installations.models import (
    Installation, Kit, KitComposant, Livraison, LivraisonLigne,
    OrdreDemontage,
)
from apps.installations.services import generer_retour_livraison

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'autopilot-lpc-{n}', defaults={'nom': f'Autopilot LPC {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'autopilot-lpc-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit', stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=Decimal('100'),
        prix_achat=Decimal('0'), quantite_stock=Decimal(stock))


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='LPC',
        email=f'lpc-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-LPC-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)


def make_livraison_livree(company, installation, quantite=10):
    depot = EmplacementStock.objects.create(
        company=company, nom='Dépôt principal', is_principal=True)
    produit = make_produit(company, nom='Batterie LPC', stock=0)
    liv = Livraison.objects.create(
        company=company, reference=f'LIV-LPC-{next(_seq)}',
        installation=installation, depot=depot,
        statut=Livraison.Statut.LIVREE)
    LivraisonLigne.objects.create(
        livraison=liv, produit=produit, designation=produit.nom,
        quantite=quantite)
    return liv, produit, depot


class TestRetourLivraisonLigneProduitCrossTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.liv, self.produit, self.depot = make_livraison_livree(
            self.company, self.inst, quantite=10)
        self.retour = generer_retour_livraison(self.liv, self.user)
        self.ligne = self.retour.lignes.first()

        self.other_company = make_company()
        self.other_produit = make_produit(
            self.other_company, nom='Produit société B')

    def test_patch_produit_cross_tenant_refuse(self):
        """PATCH produit d'une autre société → 400 nommant `produit`."""
        r = self.api.patch(
            f'{BASE}/retour-livraison-lignes/{self.ligne.id}/',
            {'produit': self.other_produit.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('produit', r.data)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.produit_id, self.produit.id)

    def test_patch_produit_meme_societe_accepte(self):
        """Contrôle : produit de la MÊME société reste acceptable."""
        autre_produit_meme_societe = make_produit(
            self.company, nom='Autre produit société A')
        r = self.api.patch(
            f'{BASE}/retour-livraison-lignes/{self.ligne.id}/',
            {'produit': autre_produit_meme_societe.id}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_post_ligne_produit_cross_tenant_refuse(self):
        """POST direct d'une ligne avec un produit d'une autre société →
        400 (pas de `perform_create` sur `main` : aujourd'hui 201)."""
        r = self.api.post(
            f'{BASE}/retour-livraison-lignes/',
            {
                'retour': self.retour.id,
                'produit': self.other_produit.id,
                'designation': 'Ligne malveillante',
                'quantite_retournee': 0,
            }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('produit', r.data)

    def test_post_ligne_produit_meme_societe_accepte(self):
        """Contrôle : POST avec un produit de la même société → 201."""
        r = self.api.post(
            f'{BASE}/retour-livraison-lignes/',
            {
                'retour': self.retour.id,
                'produit': self.produit.id,
                'designation': 'Ligne légitime',
                'quantite_retournee': 0,
            }, format='json')
        self.assertEqual(r.status_code, 201, r.data)


class TestOrdreDemontageLigneProduitCrossTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=5)
        self.comp1 = make_produit(self.company, nom='Onduleur', stock=0)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret',
            produit_compose=self.composite)
        KitComposant.objects.create(
            kit=self.kit, produit=self.comp1, quantite=1)
        resp = self.api.post(f'{BASE}/ordres-demontage/', {
            'kit': self.kit.id, 'quantite': 1,
        }, format='json')
        assert resp.status_code == 201, resp.content
        self.ordre = OrdreDemontage.objects.get(pk=resp.data['id'])
        self.ligne = self.ordre.lignes.first()

        self.other_company = make_company()
        self.other_produit = make_produit(
            self.other_company, nom='Produit société B')

    def test_patch_produit_cross_tenant_refuse(self):
        r = self.api.patch(
            f'{BASE}/ordre-demontage-lignes/{self.ligne.id}/',
            {'produit': self.other_produit.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('produit', r.data)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.produit_id, self.comp1.id)

    def test_post_ligne_produit_cross_tenant_refuse(self):
        r = self.api.post(
            f'{BASE}/ordre-demontage-lignes/',
            {
                'ordre': self.ordre.id,
                'produit': self.other_produit.id,
                'designation': 'Ligne malveillante',
                'quantite_recuperee': 0,
            }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('produit', r.data)
