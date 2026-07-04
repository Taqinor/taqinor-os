"""XPUR18 — Révision de BCF tracée + ré-approbation.

Couvre :
  * modifier un BCF envoyé directement (PATCH) est refusé — seul `reviser`
    peut le faire ;
  * `reviser` journalise les changements (records.Comment ancien→nouveau) et
    incrémente `revision` (imprimé « Rév. N » sur le PDF) ;
  * une hausse de montant au-dessus du seuil FG312 invalide l'approbation
    existante (ré-exige une nouvelle approbation) ;
  * une hausse sous le seuil ou une baisse ne touche pas une approbation
    existante ;
  * sans approbation existante (société sans seuil configuré), reviser reste
    un no-op sur ce plan (comportement historique).

Run:
    python manage.py test apps.stock.test_xpur18_revision_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
from apps.stock.services import reviser_bcf
from apps.stock.utils.pdf_fournisseur import build_bcf_context
from apps.installations.models_approbation_bcf import (
    ApprobationBCF, SeuilApprobationBCF, PALIER_RESPONSABLE, PALIER_ADMIN,
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


class Xpur18Base(TestCase):
    def setUp(self):
        self.company = _company('xpur18-co')
        self.user = _user(
            self.company, 'xpur18-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Révision X18')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X18', sku='OND-XPUR18',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf_envoye(self, prix_unitaire=Decimal('1000'), quantite=2):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X18-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=prix_unitaire)
        return bc


class TestEditionDirecteRefusee(Xpur18Base):
    def test_patch_direct_refuse_sur_bcf_envoye(self):
        bc = self._bcf_envoye()
        resp = self.api.patch(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/',
            {'note': 'Modif directe'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_patch_direct_toujours_permis_en_brouillon(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X18-BROUILLON',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        bc.lignes.create(
            produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1000'))
        resp = self.api.patch(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/',
            {'fournisseur': self.fournisseur.id, 'note': 'Modif brouillon',
             'lignes': [{'produit': self.produit.id, 'quantite': 1,
                         'prix_achat_unitaire': '1000'}]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class TestReviserTraceEtIncremente(Xpur18Base):
    def test_reviser_incremente_revision(self):
        bc = self._bcf_envoye()
        bc, _ = reviser_bcf(
            self.company, self.user, bc, note='Note modifiée par le fournisseur')
        self.assertEqual(bc.revision, 1)

    def test_reviser_journalise_le_changement(self):
        bc = self._bcf_envoye()
        reviser_bcf(self.company, self.user, bc, note='Nouvelle note')
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Comment
        ct = ContentType.objects.get_for_model(BonCommandeFournisseur)
        comments = Comment.objects.filter(
            content_type=ct, object_id=bc.id, company=self.company)
        self.assertEqual(comments.count(), 1)
        self.assertIn('note', comments.first().body)

    def test_reviser_sans_changement_ne_journalise_rien(self):
        bc = self._bcf_envoye()
        bc, changed = reviser_bcf(self.company, self.user, bc)
        self.assertFalse(changed)
        self.assertEqual(bc.revision, 0)

    def test_revision_imprimee_sur_pdf(self):
        bc = self._bcf_envoye()
        reviser_bcf(self.company, self.user, bc, note='v2')
        bc.refresh_from_db()
        context = build_bcf_context(bc)
        self.assertEqual(context['bc'].revision, 1)

    def test_endpoint_reviser(self):
        bc = self._bcf_envoye()
        resp = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bc.id}/reviser/',
            {'note': 'Révisé via API'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['revision'], 1)

    def test_reviser_bcf_brouillon_refuse(self):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-X18-BR2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        with self.assertRaises(ValueError):
            reviser_bcf(self.company, self.user, bc, note='x')


class TestHausseInvalideApprobation(Xpur18Base):
    def test_hausse_au_dessus_du_seuil_invalide_approbation(self):
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=Decimal('1500'),
            actif=True)
        bc = self._bcf_envoye(prix_unitaire=Decimal('700'), quantite=2)  # 1400
        ApprobationBCF.objects.create(
            company=self.company, bcf=bc, palier=PALIER_RESPONSABLE,
            montant_approuve=Decimal('1400'), approuve_par=self.user)

        ligne = bc.lignes.first()
        bc, reapprobation_requise = reviser_bcf(
            self.company, self.user, bc,
            lignes=[{'id': ligne.id, 'quantite': 3,
                     'prix_achat_unitaire': Decimal('700')}])  # 2100 > seuil
        self.assertTrue(reapprobation_requise)
        self.assertFalse(
            ApprobationBCF.objects.filter(company=self.company, bcf=bc)
            .exists())

    def test_hausse_sous_le_seuil_ne_touche_pas_approbation(self):
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=Decimal('5000'),
            actif=True)
        bc = self._bcf_envoye(prix_unitaire=Decimal('700'), quantite=2)  # 1400
        ApprobationBCF.objects.create(
            company=self.company, bcf=bc, palier=PALIER_RESPONSABLE,
            montant_approuve=Decimal('1400'), approuve_par=self.user)

        ligne = bc.lignes.first()
        bc, reapprobation_requise = reviser_bcf(
            self.company, self.user, bc,
            lignes=[{'id': ligne.id, 'quantite': 3,
                     'prix_achat_unitaire': Decimal('700')}])  # 2100, seuil 5000
        self.assertFalse(reapprobation_requise)
        self.assertTrue(
            ApprobationBCF.objects.filter(company=self.company, bcf=bc)
            .exists())

    def test_baisse_de_montant_ne_touche_pas_approbation(self):
        SeuilApprobationBCF.objects.create(
            company=self.company, seuil_responsable=Decimal('1000'),
            actif=True)
        bc = self._bcf_envoye(prix_unitaire=Decimal('700'), quantite=3)  # 2100
        ApprobationBCF.objects.create(
            company=self.company, bcf=bc, palier=PALIER_ADMIN,
            montant_approuve=Decimal('2100'), approuve_par=self.user)

        ligne = bc.lignes.first()
        bc, reapprobation_requise = reviser_bcf(
            self.company, self.user, bc,
            lignes=[{'id': ligne.id, 'quantite': 1,
                     'prix_achat_unitaire': Decimal('700')}])  # 700 < 2100
        self.assertFalse(reapprobation_requise)
        self.assertTrue(
            ApprobationBCF.objects.filter(company=self.company, bcf=bc)
            .exists())

    def test_sans_seuil_configure_reste_no_op(self):
        # Société sans SeuilApprobationBCF actif — comportement historique :
        # aucune invalidation possible (rien à invalider de toute façon).
        bc = self._bcf_envoye(prix_unitaire=Decimal('700'), quantite=2)
        ligne = bc.lignes.first()
        bc, reapprobation_requise = reviser_bcf(
            self.company, self.user, bc,
            lignes=[{'id': ligne.id, 'quantite': 10,
                     'prix_achat_unitaire': Decimal('700')}])
        self.assertFalse(reapprobation_requise)
