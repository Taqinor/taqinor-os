"""XPUR16 — Lignes libres / services sur le BCF (achats hors stock).

Couvre :
  * une ligne sans produit doit porter une désignation libre (validation) ;
  * `sans_stock` est posé automatiquement quand produit est vide ;
  * un BCF mixte (produit + ligne libre) compte les deux dans le total ;
  * la réception d'un BCF mixte NE crée aucun MouvementStock pour la ligne
    libre, mais incrémente sa quantité reçue (participe à
    est_entierement_recu) ;
  * la facturation depuis réception (FG56) reprend la ligne libre avec sa
    désignation.

Run:
    python manage.py test apps.stock.test_xpur16_lignes_libres_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, MouvementStock, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur, facturer_reception

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


class Xpur16Base(TestCase):
    def setUp(self):
        self.company = _company('xpur16-co')
        self.user = _user(
            self.company, 'xpur16-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Transporteur X16')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X16', sku='OND-XPUR16',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=0)


class TestSansStockAuto(Xpur16Base):
    def test_sans_stock_pose_automatiquement_sans_produit(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X16-1',
            fournisseur=self.fournisseur)
        ligne = bc.lignes.create(
            produit=None, designation='Transport Casablanca', quantite=1,
            prix_achat_unitaire=Decimal('500'))
        self.assertTrue(ligne.sans_stock)

    def test_ligne_catalogue_normale_reste_sans_stock_false(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X16-2',
            fournisseur=self.fournisseur)
        ligne = bc.lignes.create(
            produit=self.produit, quantite=3,
            prix_achat_unitaire=Decimal('1200'))
        self.assertFalse(ligne.sans_stock)


class TestCreationBcfMixte(Xpur16Base):
    def test_creation_bcf_mixte_via_api(self):
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [
                {'produit': self.produit.id, 'quantite': 5,
                 'prix_achat_unitaire': '1200'},
                {'produit': None, 'designation': 'Transport Casablanca',
                 'quantite': 1, 'prix_achat_unitaire': '500'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        lignes = resp.data['lignes']
        self.assertEqual(len(lignes), 2)
        libre = next(ln for ln in lignes if ln['produit'] is None)
        self.assertTrue(libre['sans_stock'])
        self.assertEqual(libre['designation'], 'Transport Casablanca')
        # Le total compte les deux lignes : 5*1200 + 1*500 = 6500.
        self.assertEqual(Decimal(resp.data['total_achat']), Decimal('6500'))

    def test_ligne_sans_produit_ni_designation_refusee(self):
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [
                {'produit': None, 'quantite': 1, 'prix_achat_unitaire': '100'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class TestReceptionLigneLibre(Xpur16Base):
    def _bcf_mixte(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X16-MIX',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_produit = bc.lignes.create(
            produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'))
        ligne_libre = bc.lignes.create(
            produit=None, designation='Transport Casablanca', quantite=1,
            prix_achat_unitaire=Decimal('500'))
        return bc, ligne_produit, ligne_libre

    def test_recevoir_ligne_libre_ne_cree_pas_de_mouvement(self):
        bc, ligne_produit, ligne_libre = self._bcf_mixte()
        before = MouvementStock.objects.count()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/recevoir/',
            {'receptions': [
                {'ligne': ligne_produit.id, 'quantite': 5},
                {'ligne': ligne_libre.id, 'quantite': 1},
            ]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        after = MouvementStock.objects.count()
        # Un seul mouvement créé (la ligne produit) — la ligne libre n'en crée
        # aucun.
        self.assertEqual(after - before, 1)
        ligne_libre.refresh_from_db()
        self.assertEqual(ligne_libre.quantite_recue, 1)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.RECU)

    def test_produit_stock_incremente_seulement_pour_ligne_catalogue(self):
        bc, ligne_produit, ligne_libre = self._bcf_mixte()
        self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/recevoir/',
            {'receptions': [
                {'ligne': ligne_produit.id, 'quantite': 5},
                {'ligne': ligne_libre.id, 'quantite': 1},
            ]}, format='json')
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)


class TestFacturationLigneLibre(Xpur16Base):
    def test_facturation_reprend_designation_ligne_libre(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X16-FACT',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_libre = bc.lignes.create(
            produit=None, designation='Transport Casablanca', quantite=1,
            prix_achat_unitaire=Decimal('500'))

        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X16-1', bon_commande=bc)
        reception.lignes.create(
            ligne_commande=ligne_libre, produit=None, quantite=1)
        confirm_reception_fournisseur(reception, self.user)

        facture = facturer_reception(self.company, self.user, reception)
        lignes_facture = list(facture.lignes.all())
        self.assertEqual(len(lignes_facture), 1)
        self.assertEqual(lignes_facture[0].designation, 'Transport Casablanca')
        self.assertEqual(lignes_facture[0].prix_unitaire_ht, Decimal('500'))
