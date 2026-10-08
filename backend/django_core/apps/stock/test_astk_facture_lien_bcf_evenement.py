"""ASTK99 — une facture fournisseur qui ACQUIERT un BCF (PATCH bon_commande
None → X, flux OCR) émet `facture_fournisseur_creee` : la provision GR/IR
ouverte du BCF est lettrée comme pour une facture née d'une réception.

Run:
    python manage.py test apps.stock.test_astk_facture_lien_bcf_evenement
"""
import datetime
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur, Produit,
    ReceptionFournisseur,
)
from core.events import facture_fournisseur_creee

User = get_user_model()


class LienBcfEvenementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk99-co', slug='astk99-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk99',
            permissions=['stock_voir', 'stock_modifier',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.user = User.objects.create_user(
            username='astk99-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK99')
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK99', sku='OND-ASTK99',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK99-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=produit, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK99-0001',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=produit,
            quantite=10)
        # Provision GR/IR ouverte, posée par le service réel d'installations.
        from apps.installations.services import provisionner_gr_ir_reception
        self.provision = provisionner_gr_ir_reception(
            reception=rec, company=self.company, user=self.user)
        self.Provision = django_apps.get_model(
            'installations', 'ReceptionNonFacturee')
        # Facture née sans BCF (flux OCR).
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK99-0001',
            fournisseur=self.fournisseur, montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))
        self.recus = []

        def _capte(sender, instance, company, user=None, **kwargs):
            self.recus.append((sender, instance.pk, company, user))
        facture_fournisseur_creee.connect(
            _capte, dispatch_uid='astk99-capte', weak=False)
        self.addCleanup(
            facture_fournisseur_creee.disconnect,
            dispatch_uid='astk99-capte')

    def _patch(self, data):
        return self.api.patch(
            f'/api/django/stock/factures-fournisseur/{self.facture.id}/',
            data, format='json')

    def test_patch_lien_bcf_lettre_la_provision(self):
        prov = self.Provision.objects.get(pk=self.provision.pk)
        self.assertFalse(prov.lettre)
        resp = self._patch({'bon_commande': self.bcf.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        prov = self.Provision.objects.get(pk=self.provision.pk)
        self.assertTrue(prov.lettre)
        self.assertEqual(prov.facture_id, self.facture.id)
        self.assertEqual(len(self.recus), 1)
        sender, pk, company, user = self.recus[0]
        self.assertIs(sender, FactureFournisseur)
        self.assertEqual(pk, self.facture.id)
        self.assertEqual(company, self.company)
        self.assertEqual(user, self.user)

    def test_patch_sans_changement_de_bcf_n_emet_rien(self):
        self._patch({'bon_commande': self.bcf.id})
        self.recus.clear()
        resp = self._patch({'note': 'commentaire', 'bon_commande': self.bcf.id})
        self.assertEqual(resp.status_code, 200, resp.data)
        resp = self._patch({'note': 'autre'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.recus, [])
