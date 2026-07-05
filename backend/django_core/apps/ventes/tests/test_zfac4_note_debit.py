"""
ZFAC4 — Note de débit (majoration d'une facture émise) — pendant de l'avoir.

Une note de débit émise sur une facture augmente son reste à payer du
montant TTC, la référence suit ``ND-`` sans collision, PDF rendu, scoping
cross-company, tests (reste à payer, numérotation, isolation).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_zfac4_note_debit -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Facture, LigneFacture, NoteDebit

User = get_user_model()


def make_company(slug='nd-co', nom='ND Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class TestNoteDebit(TestCase):
    def setUp(self):
        from apps.roles.models import Role, ALL_PERMISSIONS
        self.company = make_company()
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='nd_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ND',
            telephone='+212600000002')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PVND1',
            prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('20.00'))
        # Facture émise : 10 × 1000 HT (TVA 20 %) = 10000 HT, TVA 2000,
        # TTC 12000.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-ND-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20.00'))

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_facture_baseline_due(self):
        self.assertEqual(self.facture.total_ttc, Decimal('12000.00'))
        self.assertEqual(self.facture.montant_du, Decimal('12000.00'))

    def test_note_debit_increases_montant_du(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Complément non prévu',
             'lignes': [{'produit': self.panneau.id, 'designation': 'Frais complémentaires',
                         'quantite': '1', 'prix_unitaire': '1000',
                         'taux_tva': '20'}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteDebit.objects.get(id=resp.data['id'])
        self.assertEqual(note.total_ttc, Decimal('1200.00'))
        self.assertTrue(note.reference.startswith('ND-'))
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_du, Decimal('13200.00'))

    def test_reference_no_collision_across_two_notes(self):
        api = self._api(self.admin)
        r1 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Première majoration'}, format='json')
        r2 = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Deuxième majoration'}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201, r2.data)
        self.assertNotEqual(r1.data['reference'], r2.data['reference'])

    def test_note_debit_pdf_renders(self):
        api = self._api(self.admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Complément'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        note = NoteDebit.objects.get(id=resp.data['id'])
        self.assertTrue(note.fichier_pdf)

    def test_note_debit_scoping_cross_company_404(self):
        other_company = make_company(slug='nd-other', nom='Other Co')
        from apps.roles.models import Role, ALL_PERMISSIONS
        other_role = Role.objects.create(
            company=other_company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        other_admin = User.objects.create_user(
            username='nd_other_admin', password='x', role=other_role,
            role_legacy='admin', company=other_company)
        api = self._api(other_admin)
        resp = api.post(
            f'/api/django/ventes/factures/{self.facture.id}/creer-note-debit/',
            {'motif': 'Tentative cross-company'}, format='json')
        self.assertEqual(resp.status_code, 404)
