"""NTP2P18 — Historique de prix négocié par fournisseur/produit.

Couvre : la série temporelle des prix RÉELLEMENT reçus (lignes de BCF
réceptionnées uniquement), l'écart vs le prix catalogue courant
(``PrixFournisseur``), l'alerte de dérive au-delà du seuil configuré
(``AchatsParametres.seuil_deviation_prix_pct``, réutilisé — XPUR13), et
l'endpoint ``produits/{id}/historique-prix/?fournisseur=``.

Run:
    python manage.py test apps.stock.test_ntp2p18_historique_prix_fournisseur -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, PrixFournisseur, Produit,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntp2p18Base(TestCase):
    def setUp(self):
        self.company = _company('ntp2p18-co')
        self.user = _user(
            self.company, 'ntp2p18-user',
            permissions=['stock_modifier', 'stock_voir', 'prix_achat_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P18')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur NTP2P18', sku='OND-NTP2P18',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1000'))

    def _bcf_recu(self, prix, ref):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=ref,
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=1,
            prix_achat_unitaire=prix, quantite_recue=1)
        return bcf


class TestSerieTemporelle(Ntp2p18Base):
    def test_seules_les_lignes_receptionnees_comptent(self):
        self._bcf_recu(Decimal('1000'), 'BCF-NTP2P18-1')
        # Ligne NON reçue (quantite_recue=0) — ne doit PAS apparaître.
        bcf_non_recu = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTP2P18-2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf_non_recu, produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('5000'), quantite_recue=0)

        resultat = stock_selectors.historique_prix_fournisseur(
            self.company, self.produit.id, self.fournisseur.id)
        self.assertEqual(len(resultat['historique']), 1)
        self.assertEqual(
            resultat['historique'][0]['prix_recu'], Decimal('1000'))


class TestAlerteDeviation(Ntp2p18Base):
    def test_ecart_15pct_avec_seuil_10pct_declenche_alerte(self):
        AchatsParametres.objects.create(
            company=self.company, seuil_deviation_prix_pct=Decimal('10'))
        # Catalogue = 1000, reçu = 1150 → +15 %, au-delà du seuil 10 %.
        self._bcf_recu(Decimal('1150'), 'BCF-NTP2P18-3')
        resultat = stock_selectors.historique_prix_fournisseur(
            self.company, self.produit.id, self.fournisseur.id)
        self.assertTrue(resultat['dernier_prix_alerte'])
        self.assertAlmostEqual(
            resultat['historique'][0]['ecart_vs_catalogue_pct'], 15.0,
            places=1)

    def test_ecart_dans_le_seuil_pas_dalerte(self):
        AchatsParametres.objects.create(
            company=self.company, seuil_deviation_prix_pct=Decimal('10'))
        self._bcf_recu(Decimal('1050'), 'BCF-NTP2P18-4')  # +5 %
        resultat = stock_selectors.historique_prix_fournisseur(
            self.company, self.produit.id, self.fournisseur.id)
        self.assertFalse(resultat['dernier_prix_alerte'])

    def test_seuil_zero_desactive_toute_alerte(self):
        # Défaut historique (seuil 0) — jamais d'alerte, même sur un écart
        # énorme.
        self._bcf_recu(Decimal('5000'), 'BCF-NTP2P18-5')
        resultat = stock_selectors.historique_prix_fournisseur(
            self.company, self.produit.id, self.fournisseur.id)
        self.assertFalse(resultat['dernier_prix_alerte'])


class TestEndpoint(Ntp2p18Base):
    def test_badge_alerte_sur_la_ligne_via_api(self):
        AchatsParametres.objects.create(
            company=self.company, seuil_deviation_prix_pct=Decimal('10'))
        self._bcf_recu(Decimal('1150'), 'BCF-NTP2P18-6')
        resp = self.api.get(
            f'/api/django/stock/produits/{self.produit.id}/historique-prix/'
            f'?fournisseur={self.fournisseur.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['dernier_prix_alerte'])

    def test_parametre_fournisseur_requis(self):
        resp = self.api.get(
            f'/api/django/stock/produits/{self.produit.id}/historique-prix/')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_refuse_sans_droit_prix_achat_voir(self):
        viewer = _user(
            self.company, 'ntp2p18-viewer', permissions=['stock_voir'])
        api = _api(viewer)
        resp = api.get(
            f'/api/django/stock/produits/{self.produit.id}/historique-prix/'
            f'?fournisseur={self.fournisseur.id}')
        self.assertEqual(resp.status_code, 403, resp.data)
