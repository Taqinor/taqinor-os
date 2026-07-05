"""ZPUR11 — Motif d'annulation obligatoire + réouverture d'un BCF annulé.

Couvre :
  * annuler sans motif → 400 (refusé) ;
  * annuler avec motif → tracé (motif_annulation + chatter horodaté/acteur) ;
  * un BCF annulé SANS réception confirmée se rouvre en brouillon ;
  * un BCF ayant des réceptions confirmées refuse la réouverture (400) ;
  * permission : rôle standard reçoit 403 sur annuler/rouvrir.

Run:
    python manage.py test \
        apps.stock.test_zpur11_annulation_reouverture_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.records.models import Comment
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None, role_legacy='responsable'):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Zpur11Base(TestCase):
    def setUp(self):
        self.company = _company('zpur11-co')
        self.user = _user(
            self.company, 'zpur11-resp',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ZPUR11')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ZPUR11', sku='OND-ZPUR11',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))

    def _bcf(self, reference='BCF-ZPUR11-0001',
             statut=BonCommandeFournisseur.Statut.ENVOYE):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=reference,
            fournisseur=self.fournisseur, statut=statut)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))
        return bc


class TestAnnulationMotifObligatoire(Zpur11Base):
    def test_annuler_sans_motif_refuse(self):
        bc = self._bcf()
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/'
        resp = self.api.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 400)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_annuler_motif_vide_refuse(self):
        bc = self._bcf()
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/'
        resp = self.api.post(
            url, {'motif_annulation': '   '}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_annuler_avec_motif_trace(self):
        bc = self._bcf()
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/'
        resp = self.api.post(
            url, {'motif_annulation': 'Fournisseur en rupture'},
            format='json')
        self.assertEqual(resp.status_code, 200)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ANNULE)
        self.assertEqual(bc.motif_annulation, 'Fournisseur en rupture')
        comments = Comment.objects.filter(
            company=self.company, object_id=bc.pk)
        self.assertTrue(
            any('Fournisseur en rupture' in c.body for c in comments))
        self.assertTrue(any(c.author_id == self.user.id for c in comments))


class TestReouverture(Zpur11Base):
    def _annuler(self, bc, motif='motif test'):
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/'
        self.api.post(url, {'motif_annulation': motif}, format='json')
        bc.refresh_from_db()
        return bc

    def test_rouvrir_sans_reception_confirmee_ok(self):
        bc = self._bcf()
        bc = self._annuler(bc)
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/rouvrir/'
        resp = self.api.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 200)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.BROUILLON)

    def test_rouvrir_avec_reception_confirmee_refuse(self):
        bc = self._bcf()
        ligne = bc.lignes.first()
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ZPUR11-0001',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.CONFIRME)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=5)
        bc = self._annuler(bc)
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/rouvrir/'
        resp = self.api.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 400)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ANNULE)

    def test_rouvrir_bcf_non_annule_refuse(self):
        bc = self._bcf()
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/rouvrir/'
        resp = self.api.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 400)


class TestPermissions(Zpur11Base):
    def test_role_standard_403_annuler_et_rouvrir(self):
        bc = self._bcf()
        user_standard = _user(
            self.company, 'zpur11-standard', permissions=['stock_voir'],
            role_legacy='commercial')
        api_standard = _api(user_standard)
        url = f'/api/django/stock/bons-commande-fournisseur/{bc.id}/annuler/'
        resp = api_standard.post(
            url, {'motif_annulation': 'x'}, format='json')
        self.assertEqual(resp.status_code, 403)
        url_rouvrir = (
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/rouvrir/')
        resp2 = api_standard.post(url_rouvrir, {}, format='json')
        self.assertEqual(resp2.status_code, 403)
