"""ZPUR3 — Modèle de BCF réutilisable (purchase template) pour commandes
récurrentes.

Couvre :
  * créer un modèle « Kit consommables mensuel » puis « générer » produit un
    BCF brouillon avec les bonnes lignes et le prix auto-rempli
    (PrixFournisseur si connu, sinon prix_achat catalogue) ;
  * le modèle est company-scopé (404 cross-company) ;
  * générer sans fournisseur (ni sur le modèle, ni fourni) est refusé ;
  * un modèle vide (aucune ligne) est refusé à la génération.

Run:
    python manage.py test apps.stock.test_zpur3_modele_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, ModeleBonCommandeFournisseur,
    PrixFournisseur, Produit,
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


class Zpur3Base(TestCase):
    def setUp(self):
        self.company = _company('zpur3-co')
        self.user = _user(
            self.company, 'zpur3-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR3')
        self.mc4 = Produit.objects.create(
            company=self.company, nom='Connecteur MC4', sku='MC4-ZPUR3',
            prix_vente=Decimal('20'), prix_achat=Decimal('5'))
        self.visserie = Produit.objects.create(
            company=self.company, nom='Visserie inox', sku='VIS-ZPUR3',
            prix_vente=Decimal('10'), prix_achat=Decimal('2'))


class TestCreationEtGeneration(Zpur3Base):
    def test_creer_modele_puis_generer_produit_bcf_brouillon(self):
        resp = self.api.post('/api/django/stock/modeles-bcf/', {
            'nom': 'Kit consommables mensuel',
            'fournisseur': self.fournisseur.id,
            'lignes': [
                {'produit': self.mc4.id, 'quantite': 100},
                {'produit': self.visserie.id, 'quantite': 50},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        modele_id = resp.data['id']

        resp2 = self.api.post(
            f'/api/django/stock/modeles-bcf/{modele_id}/generer/')
        self.assertEqual(resp2.status_code, 201, resp2.data)
        bc = BonCommandeFournisseur.objects.get(id=resp2.data['id'])
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.BROUILLON)
        self.assertEqual(bc.lignes.count(), 2)
        ligne_mc4 = bc.lignes.get(produit=self.mc4)
        self.assertEqual(ligne_mc4.quantite, 100)
        # Sans PrixFournisseur enregistré : repli sur prix_achat catalogue.
        self.assertEqual(ligne_mc4.prix_achat_unitaire, Decimal('5'))

    def test_generer_utilise_prix_fournisseur_si_connu(self):
        PrixFournisseur.objects.create(
            company=self.company, produit=self.mc4,
            fournisseur=self.fournisseur, prix_achat=Decimal('4.50'))
        modele = ModeleBonCommandeFournisseur.objects.create(
            company=self.company, nom='Kit MC4', fournisseur=self.fournisseur)
        modele.lignes.create(produit=self.mc4, quantite=200)

        resp = self.api.post(
            f'/api/django/stock/modeles-bcf/{modele.id}/generer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        bc = BonCommandeFournisseur.objects.get(id=resp.data['id'])
        ligne = bc.lignes.get(produit=self.mc4)
        self.assertEqual(ligne.prix_achat_unitaire, Decimal('4.50'))


class TestGardes(Zpur3Base):
    def test_generer_sans_fournisseur_refuse(self):
        modele = ModeleBonCommandeFournisseur.objects.create(
            company=self.company, nom='Sans fournisseur')
        modele.lignes.create(produit=self.mc4, quantite=10)
        resp = self.api.post(
            f'/api/django/stock/modeles-bcf/{modele.id}/generer/')
        self.assertEqual(resp.status_code, 400)

    def test_generer_modele_vide_refuse(self):
        modele = ModeleBonCommandeFournisseur.objects.create(
            company=self.company, nom='Vide', fournisseur=self.fournisseur)
        resp = self.api.post(
            f'/api/django/stock/modeles-bcf/{modele.id}/generer/')
        self.assertEqual(resp.status_code, 400)


class TestMultiTenant(Zpur3Base):
    def test_modele_autre_societe_404(self):
        autre = _company('zpur3-autre')
        autre_user = _user(
            autre, 'zpur3-autre-user',
            permissions=['stock_modifier', 'stock_voir'])
        autre_api = _api(autre_user)
        modele = ModeleBonCommandeFournisseur.objects.create(
            company=self.company, nom='Modèle privé',
            fournisseur=self.fournisseur)
        resp = autre_api.get(f'/api/django/stock/modeles-bcf/{modele.id}/')
        self.assertEqual(resp.status_code, 404)
