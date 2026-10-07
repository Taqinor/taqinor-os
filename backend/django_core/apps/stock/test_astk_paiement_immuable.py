"""ASTK27 (C-ASTK-004) — les paiements fournisseur sont immuables par l'API.

Constat FACF-5 : `PaiementFournisseurViewSet` exposait le CRUD complet. Un
PATCH {facture: B} déplaçait un règlement de 1 000 de la facture A vers la
facture B SANS recalcul : A restait « payee » solde dû 1 000, B « a_payer »
avec un total payé de 1 000 ; un PATCH {montant: 300} laissait la RAS-TVA
calculée sur 600 (100,00). Désormais PUT/PATCH répondent 405 : une correction
passe par l'annulation (DELETE admin) et la recréation, qui recalculent le
statut des factures et la RAS.

Run :
    python manage.py test apps.stock.test_astk_paiement_immuable
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, FactureFournisseur, Fournisseur, PaiementFournisseur,
)

User = get_user_model()

URL = '/api/django/stock/paiements-fournisseur/'


class PaiementImmuableTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK27 Co', slug='astk27-co')
        AchatsParametres.objects.create(
            company=self.company, ras_tva_actif=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK27')
        self.facture_a = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK27-A',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ht=Decimal('1000'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('1000'))
        self.facture_b = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK27-B',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ht=Decimal('2000'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('2000'))
        # Facture C (TVA 200, biens sans ARF ⇒ RAS 100 %) : un paiement de
        # 600 retient 100,00.
        self.facture_c = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK27-C',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'))
        self.resp = self._api('responsable', 'astk27-resp')
        self.admin = self._api('admin', 'astk27-admin')

        r = self.resp.post(URL, {
            'facture': self.facture_a.id, 'montant': '1000',
            'date_paiement': '2026-09-10', 'mode': 'virement'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.paiement_a = PaiementFournisseur.objects.get(pk=r.data['id'])
        r = self.resp.post(URL, {
            'facture': self.facture_c.id, 'montant': '600',
            'date_paiement': '2026-09-10', 'mode': 'virement'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.paiement_c = PaiementFournisseur.objects.get(pk=r.data['id'])

    def _api(self, role_legacy, username):
        role = Role.objects.create(
            company=self.company, nom=f'r-{username}',
            permissions=['stock_voir', 'stock_modifier', 'prix_achat_voir',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        user = User.objects.create_user(
            username=username, password='pw-astk27-x', company=self.company,
            role=role, role_legacy=role_legacy)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _etat_initial_intact(self):
        self.facture_a.refresh_from_db()
        self.facture_b.refresh_from_db()
        self.paiement_a.refresh_from_db()
        self.paiement_c.refresh_from_db()
        self.assertEqual(self.paiement_a.facture_id, self.facture_a.id)
        self.assertEqual(
            self.facture_a.statut, FactureFournisseur.Statut.PAYEE)
        self.assertEqual(self.facture_a.solde_du, Decimal('0'))
        self.assertEqual(
            self.facture_b.statut, FactureFournisseur.Statut.A_PAYER)
        self.assertEqual(self.facture_b.total_paye, Decimal('0'))
        self.assertEqual(self.paiement_c.montant, Decimal('600'))
        self.assertEqual(self.paiement_c.montant_ras_tva, Decimal('100.00'))

    def test_patch_405(self):
        r = self.resp.patch(
            f'{URL}{self.paiement_a.id}/', {'facture': self.facture_b.id},
            format='json')
        self.assertEqual(r.status_code, 405, r.content)
        r = self.resp.patch(
            f'{URL}{self.paiement_c.id}/', {'montant': '300'}, format='json')
        self.assertEqual(r.status_code, 405, r.content)
        self._etat_initial_intact()

    def test_put_405(self):
        r = self.admin.put(f'{URL}{self.paiement_a.id}/', {
            'facture': self.facture_b.id, 'montant': '1000',
            'date_paiement': '2026-09-10', 'mode': 'virement'},
            format='json')
        self.assertEqual(r.status_code, 405, r.content)
        self._etat_initial_intact()

    def test_correction_par_annulation_et_recreation(self):
        r = self.admin.delete(f'{URL}{self.paiement_a.id}/')
        self.assertEqual(r.status_code, 204, r.content)
        r = self.resp.post(URL, {
            'facture': self.facture_b.id, 'montant': '1000',
            'date_paiement': '2026-09-11', 'mode': 'virement'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.facture_a.refresh_from_db()
        self.facture_b.refresh_from_db()
        self.assertEqual(
            self.facture_a.statut, FactureFournisseur.Statut.A_PAYER)
        self.assertEqual(self.facture_a.solde_du, Decimal('1000'))
        self.assertEqual(
            self.facture_b.statut,
            FactureFournisseur.Statut.PARTIELLEMENT_PAYEE)
        self.assertEqual(self.facture_b.total_paye, Decimal('1000'))

        # Paiement de 600 corrigé à 300 : annuler puis recréer ⇒ RAS
        # recalculée sur le nouveau montant (50,00), jamais 100 figé.
        r = self.admin.delete(f'{URL}{self.paiement_c.id}/')
        self.assertEqual(r.status_code, 204, r.content)
        r = self.resp.post(URL, {
            'facture': self.facture_c.id, 'montant': '300',
            'date_paiement': '2026-09-11', 'mode': 'virement'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        nouveau = PaiementFournisseur.objects.get(pk=r.data['id'])
        self.assertEqual(nouveau.montant_ras_tva, Decimal('50.00'))
