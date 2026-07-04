"""XPUR23 — Destination de réception : dépôt/emplacement cible ou chantier
(livraison directe).

Couvre :
  * un BCF « livrer au dépôt B » crédite B (StockEmplacement) à la
    réception ;
  * un BCF « livraison directe chantier X » trace l'affectation (SORTIE
    immédiate après l'ENTREE — n'entre jamais en stock libre) ;
  * sans destination renseignée, comportement historique inchangé (dépôt
    principal implicite, aucune StockEmplacement créée) ;
  * même comportement via le chemin `ReceptionFournisseur` (confirm_reception
    _fournisseur), et via la ligne libre XPUR16 (aucun crash).

Run:
    python manage.py test apps.stock.test_xpur23_destination_reception -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Client
from apps.installations.models_installation import Installation
from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur, MouvementStock,
    Produit, ReceptionFournisseur, StockEmplacement,
)
from apps.stock.services import confirm_reception_fournisseur, ensure_emplacements

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


def _installation(company):
    client = Client.objects.create(
        company=company, nom='Client X23', prenom='Test')
    return Installation.objects.create(
        company=company, reference='CH-X23-1', client=client)


class Xpur23Base(TestCase):
    def setUp(self):
        self.company = _company('xpur23-co')
        self.user = _user(
            self.company, 'xpur23-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur X23')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X23', sku='OND-XPUR23',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=0)
        ensure_emplacements(self.company)
        self.depot_b = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt B', is_principal=False,
            ordre=20)

    def _bcf(self, **extra):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X23-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            **extra)
        bc.lignes.create(
            produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'))
        return bc


class TestDestinationDepot(Xpur23Base):
    def test_livrer_au_depot_b_credite_b(self):
        bc = self._bcf(emplacement_destination=self.depot_b)
        ligne = bc.lignes.first()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 5}]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.depot_b)
        self.assertEqual(se.quantite, 5)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)

    def test_sans_destination_comportement_historique(self):
        bc = self._bcf()
        ligne = bc.lignes.first()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 5}]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # Aucune StockEmplacement créée — le dépôt principal reste dérivé.
        self.assertFalse(
            StockEmplacement.objects.filter(produit=self.produit).exists())
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)


class TestLivraisonDirecteChantier(Xpur23Base):
    def test_livraison_directe_ne_reste_pas_en_stock_libre(self):
        chantier = _installation(self.company)
        bc = self._bcf(chantier_livraison=chantier)
        ligne = bc.lignes.first()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': 5}]},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.produit.refresh_from_db()
        # ENTREE puis SORTIE immédiate : le stock net repasse à 0 (n'entre
        # jamais en stock libre).
        self.assertEqual(self.produit.quantite_stock, 0)
        mouvements = list(MouvementStock.objects.filter(
            produit=self.produit).order_by('date', 'id'))
        types = [m.type_mouvement for m in mouvements]
        self.assertIn(MouvementStock.TypeMouvement.ENTREE, types)
        self.assertIn(MouvementStock.TypeMouvement.SORTIE, types)
        sortie = next(
            m for m in mouvements
            if m.type_mouvement == MouvementStock.TypeMouvement.SORTIE)
        self.assertIn(chantier.reference, sortie.note)


class TestConfirmReceptionFournisseurDestination(Xpur23Base):
    def test_confirm_reception_credite_depot_destination(self):
        bc = self._bcf(emplacement_destination=self.depot_b)
        ligne = bc.lignes.first()
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X23-1', bon_commande=bc)
        reception.lignes.create(
            ligne_commande=ligne, produit=self.produit, quantite=5)
        confirm_reception_fournisseur(reception, self.user)
        se = StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.depot_b)
        self.assertEqual(se.quantite, 5)

    def test_confirm_reception_avec_ligne_libre_ne_plante_pas(self):
        """Régression XPUR16 : une ligne libre (produit=None) sur le chemin
        ReceptionFournisseur ne doit jamais lever d'AttributeError."""
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X23-LIBRE',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_libre = bc.lignes.create(
            produit=None, designation='Transport X23', quantite=1,
            prix_achat_unitaire=Decimal('300'))
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X23-LIBRE',
            bon_commande=bc)
        reception.lignes.create(
            ligne_commande=ligne_libre, produit=None, quantite=1)
        # Ne doit pas lever d'exception.
        confirm_reception_fournisseur(reception, self.user)
        ligne_libre.refresh_from_db()
        self.assertEqual(ligne_libre.quantite_recue, 1)
