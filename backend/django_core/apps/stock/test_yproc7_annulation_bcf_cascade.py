"""YPROC7 — Annulation d'un BCF : cascade sur les réceptions ouvertes + garde
à la confirmation.

Couvre :
  * confirmer une réception dont le BCF est ANNULE est refusé (ValueError) ;
  * annuler un BCF annule en cascade ses réceptions BROUILLON (idempotent,
    jamais une réception déjà CONFIRME/ANNULE) et notifie le créateur ;
  * un BCF entièrement reçu reste inannulable (comportement inchangé) ;
  * un BCF partiellement reçu reste annulable, avec le détail des quantités
    déjà entrées en stock dans la réponse.

Run:
    python manage.py test apps.stock.test_yproc7_annulation_bcf_cascade -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur

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


class Yproc7Base(TestCase):
    def setUp(self):
        self.company = _company('yproc7-co')
        self.user = _user(
            self.company, 'yproc7-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YPROC7')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur YPROC7', sku='OND-YPROC7',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf(self, statut=BonCommandeFournisseur.Statut.ENVOYE, quantite=10):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC7-1',
            fournisseur=self.fournisseur, statut=statut,
            created_by=self.user)
        bc.ligne = bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('100'))
        return bc

    def _reception_brouillon(self, bc, quantite=5):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-YPROC7-1',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(
            ligne_commande=bc.ligne, produit=self.produit, quantite=quantite)
        return rec


class TestGardeConfirmationBcfAnnule(Yproc7Base):
    def test_confirmer_reception_bcf_annule_refuse(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ANNULE)
        rec = self._reception_brouillon(bc)
        with self.assertRaises(ValueError):
            confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.BROUILLON)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)

    def test_confirmer_reception_bcf_actif_toujours_permis(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        rec = self._reception_brouillon(bc)
        confirm_reception_fournisseur(rec, self.user)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.CONFIRME)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)


class TestCascadeAnnulationBcf(Yproc7Base):
    def test_annuler_bcf_annule_receptions_brouillon(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        rec = self._reception_brouillon(bc)
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/')
        self.assertEqual(resp.status_code, 200)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ANNULE)
        rec.refresh_from_db()
        self.assertEqual(rec.statut, ReceptionFournisseur.Statut.ANNULE)
        self.assertIn('cascade', resp.data)
        self.assertEqual(resp.data['cascade']['receptions_annulees'], 1)

    def test_annuler_bcf_ne_touche_pas_reception_deja_confirmee(self):
        bc = self._bcf(
            statut=BonCommandeFournisseur.Statut.ENVOYE, quantite=10)
        rec_confirmee = self._reception_brouillon(bc, quantite=3)
        confirm_reception_fournisseur(rec_confirmee, self.user)
        rec_brouillon = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-YPROC7-2',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec_brouillon.lignes.create(
            ligne_commande=bc.ligne, produit=self.produit, quantite=2)

        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/')
        self.assertEqual(resp.status_code, 200)
        rec_confirmee.refresh_from_db()
        rec_brouillon.refresh_from_db()
        self.assertEqual(
            rec_confirmee.statut, ReceptionFournisseur.Statut.CONFIRME)
        self.assertEqual(
            rec_brouillon.statut, ReceptionFournisseur.Statut.ANNULE)
        # Le détail des quantités déjà en stock est renvoyé (décision retour).
        self.assertEqual(
            resp.data['cascade']['quantites_deja_recues'][0]['quantite_recue'],
            3)

    def test_bcf_entierement_recu_reste_inannulable(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.RECU)
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/')
        self.assertEqual(resp.status_code, 400)

    def test_annuler_deux_fois_idempotent_sur_receptions(self):
        bc = self._bcf(statut=BonCommandeFournisseur.Statut.ENVOYE)
        self._reception_brouillon(bc)
        resp1 = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/')
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.data['cascade']['receptions_annulees'], 1)
        # Ré-annuler un BCF déjà annulé : aucune réception brouillon restante
        # à annuler (idempotence sur la cascade — le service ne recompte pas
        # une réception déjà ANNULE).
        resp2 = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/')
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data['cascade']['receptions_annulees'], 0)
