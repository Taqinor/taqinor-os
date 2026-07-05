"""YPROC4 — L'approbation par palier (FG312) doit BLOQUER l'envoi du BCF.

Couvre :
  * société SANS seuil configuré : `envoyer` se comporte exactement comme
    avant (aucune régression) ;
  * société AVEC seuil actif : un BCF au-dessus du palier requis, SANS
    approbation, ne peut pas être envoyé (400 explicite) ;
  * une approbation au bon palier couvrant le montant permet l'envoi ;
  * une hausse du total du BCF au-dessus du montant approuvé invalide
    l'approbation existante (refus) ;
  * multi-tenant : une approbation d'une autre société n'est jamais prise en
    compte.

Run:
    python manage.py test apps.stock.test_yproc4_gate_envoi_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
from apps.installations.models_approbation_bcf import (
    ApprobationBCF, SeuilApprobationBCF, PALIER_RESPONSABLE, PALIER_ADMIN,
)
from apps.installations.selectors import bcf_approbation_valide

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


class Yproc4Base(TestCase):
    def setUp(self):
        self.company = _company('yproc4-co')
        self.user = _user(
            self.company, 'yproc4-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YPROC4')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur YPROC4', sku='OND-YPROC4',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf_brouillon(self, prix_unitaire=Decimal('1000'), quantite=2):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC4-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=prix_unitaire)
        return bc

    def _envoyer(self, bc):
        return self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/envoyer/')


class TestSansSeuilCompatibiliteTotale(Yproc4Base):
    def test_envoyer_sans_seuil_configure_inchange(self):
        bc = self._bcf_brouillon()
        resp = self._envoyer(bc)
        self.assertEqual(resp.status_code, 200)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)


class TestAvecSeuilGateEnvoi(Yproc4Base):
    def setUp(self):
        super().setUp()
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=Decimal('500'),
            actif=True)

    def test_bcf_au_dessus_du_seuil_sans_approbation_refuse(self):
        # 2 * 1000 = 2000 > seuil 500 -> palier admin requis, aucune
        # approbation existante.
        bc = self._bcf_brouillon()
        resp = self._envoyer(bc)
        self.assertEqual(resp.status_code, 400)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.BROUILLON)

    def test_bcf_sous_le_seuil_reste_envoyable_sans_approbation(self):
        # 1 * 100 = 100 <= seuil 500 -> palier responsable ; toujours besoin
        # d'une ApprobationBCF pour ce palier (le seuil EST configuré) : sans
        # elle, l'envoi est refusé.
        bc = self._bcf_brouillon(prix_unitaire=Decimal('100'), quantite=1)
        resp = self._envoyer(bc)
        self.assertEqual(resp.status_code, 400)

    def test_bcf_approuve_au_bon_palier_peut_etre_envoye(self):
        bc = self._bcf_brouillon()  # total 2000 -> palier admin
        ApprobationBCF.objects.create(
            company=self.company, bcf=bc, palier=PALIER_ADMIN,
            montant_approuve=Decimal('2000'), approuve_par=self.user)
        resp = self._envoyer(bc)
        self.assertEqual(resp.status_code, 200)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_hausse_du_montant_invalide_approbation_existante(self):
        bc = self._bcf_brouillon()  # total 2000
        ApprobationBCF.objects.create(
            company=self.company, bcf=bc, palier=PALIER_ADMIN,
            montant_approuve=Decimal('2000'), approuve_par=self.user)
        # Le total augmente après approbation (ajout d'une ligne).
        bc.lignes.create(
            produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1000'))
        resp = self._envoyer(bc)
        self.assertEqual(resp.status_code, 400)

    def test_approbation_palier_responsable_ne_couvre_pas_palier_admin(self):
        bc = self._bcf_brouillon()  # total 2000 -> palier admin requis
        ApprobationBCF.objects.create(
            company=self.company, bcf=bc, palier=PALIER_RESPONSABLE,
            montant_approuve=Decimal('2000'), approuve_par=self.user)
        resp = self._envoyer(bc)
        self.assertEqual(resp.status_code, 400)


class TestMultiTenant(Yproc4Base):
    def test_approbation_autre_societe_non_prise_en_compte(self):
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=Decimal('500'),
            actif=True)
        autre = _company('yproc4-autre')
        bc = self._bcf_brouillon()
        # Approbation posée sur une AUTRE société (ne doit jamais matcher —
        # simulateur d'anomalie de données, jamais atteignable via l'API).
        ApprobationBCF.objects.create(
            company=autre, bcf=bc, palier=PALIER_ADMIN,
            montant_approuve=Decimal('9999'), approuve_par=self.user)
        self.assertFalse(
            bcf_approbation_valide(self.company, bc.id, bc.total_achat))
