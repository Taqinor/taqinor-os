"""Tests XFAC14 — Compensation AR/AP (netting) pour un tiers à la fois client
et fournisseur.

Couvre : 10 000 dus par le client et 6 000 dus au fournisseur se compensent
à 6 000 (les deux soldes baissent, écriture équilibrée) ; sur-compensation
refusée ; audit trail (statut/ecriture_id) ; scoping société.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import Compensation, EcritureComptable
from apps.crm.models import Client
from apps.stock.models import FactureFournisseur, Fournisseur
from apps.ventes.models import Facture

User = get_user_model()


def make_company(slug='xfac14-co', nom='XFAC14 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        compta_services.seed_plan_comptable(self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XFAC14',
            telephone='+212600001401')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur XFAC14')
        self.facture_ar = Facture.objects.create(
            company=self.company, reference='FAC-XFAC14-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ht=Decimal('8333.33'),
            montant_tva=Decimal('1666.67'), montant_ttc=Decimal('10000'))
        self.facture_ap = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XFAC14-0001',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('5000'), montant_tva=Decimal('1000'),
            montant_ttc=Decimal('6000'))


class TestCreerCompensation(_Base):
    def test_compensation_au_plus_petit_solde(self):
        compensation = compta_services.creer_compensation(
            self.company, client_id=self.client_obj.id,
            fournisseur_id=self.fournisseur.id,
            lignes=[
                {'type': 'ar', 'facture_id': self.facture_ar.id,
                 'montant': Decimal('10000')},
                {'type': 'ap', 'facture_id': self.facture_ap.id,
                 'montant': Decimal('6000')},
            ])
        self.assertEqual(compensation.montant_compense, Decimal('6000'))
        self.assertEqual(compensation.statut, Compensation.Statut.BROUILLON)
        self.assertTrue(compensation.reference.startswith('CMP-'))
        self.assertEqual(compensation.lignes.count(), 2)

    def test_sur_compensation_refusee(self):
        with self.assertRaises(compta_services.CompensationError):
            compta_services.creer_compensation(
                self.company, client_id=self.client_obj.id,
                fournisseur_id=self.fournisseur.id,
                lignes=[
                    {'type': 'ar', 'facture_id': self.facture_ar.id,
                     'montant': Decimal('15000')},
                    {'type': 'ap', 'facture_id': self.facture_ap.id,
                     'montant': Decimal('6000')},
                ])
        # Rien n'a été créé (atomicité).
        self.assertEqual(Compensation.objects.count(), 0)

    def test_facture_autre_client_refusee(self):
        autre_client = Client.objects.create(
            company=self.company, nom='Autre', prenom='Client',
            telephone='+212600001402')
        autre_facture = Facture.objects.create(
            company=self.company, reference='FAC-XFAC14-0002',
            client=autre_client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), montant_ttc=Decimal('5000'))
        with self.assertRaises(compta_services.CompensationError):
            compta_services.creer_compensation(
                self.company, client_id=self.client_obj.id,
                fournisseur_id=self.fournisseur.id,
                lignes=[
                    {'type': 'ar', 'facture_id': autre_facture.id,
                     'montant': Decimal('5000')},
                    {'type': 'ap', 'facture_id': self.facture_ap.id,
                     'montant': Decimal('6000')},
                ])

    def test_sans_facture_ap_refusee(self):
        with self.assertRaises(compta_services.CompensationError):
            compta_services.creer_compensation(
                self.company, client_id=self.client_obj.id,
                fournisseur_id=self.fournisseur.id,
                lignes=[
                    {'type': 'ar', 'facture_id': self.facture_ar.id,
                     'montant': Decimal('1000')},
                ])


class TestValiderCompensation(_Base):
    def _compensation(self):
        return compta_services.creer_compensation(
            self.company, client_id=self.client_obj.id,
            fournisseur_id=self.fournisseur.id,
            lignes=[
                {'type': 'ar', 'facture_id': self.facture_ar.id,
                 'montant': Decimal('10000')},
                {'type': 'ap', 'facture_id': self.facture_ap.id,
                 'montant': Decimal('6000')},
            ])

    def test_validation_poste_ecriture_equilibree_et_regle(self):
        compensation = self._compensation()
        compta_services.valider_compensation(compensation)
        compensation.refresh_from_db()
        self.assertEqual(compensation.statut, Compensation.Statut.VALIDEE)
        self.assertIsNotNone(compensation.ecriture_id)

        ecriture = EcritureComptable.objects.get(id=compensation.ecriture_id)
        total_debit = sum(
            (ligne.debit for ligne in ecriture.lignes.all()), Decimal('0'))
        total_credit = sum(
            (ligne.credit for ligne in ecriture.lignes.all()), Decimal('0'))
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('6000'))

        self.facture_ar.refresh_from_db()
        self.facture_ap.refresh_from_db()
        self.assertEqual(self.facture_ar.montant_du, Decimal('4000'))
        self.assertEqual(self.facture_ap.solde_du, Decimal('0'))

    def test_validation_idempotente(self):
        compensation = self._compensation()
        compta_services.valider_compensation(compensation)
        premiere_ecriture_id = compensation.ecriture_id
        compta_services.valider_compensation(compensation)
        compensation.refresh_from_db()
        self.assertEqual(compensation.ecriture_id, premiere_ecriture_id)
        self.assertEqual(
            EcritureComptable.objects.filter(
                reference=compensation.reference).count(), 1)


class TestEndpoint(_Base):
    def setUp(self):
        super().setUp()
        self.user = make_user(self.company, 'xfac14-admin', role='admin')
        self.api = auth(self.user)

    def test_creer_et_valider_via_api(self):
        resp = self.api.post('/api/django/compta/compensations/', {
            'client_id': self.client_obj.id,
            'fournisseur_id': self.fournisseur.id,
            'lignes': [
                {'type': 'ar', 'facture_id': self.facture_ar.id,
                 'montant': '10000'},
                {'type': 'ap', 'facture_id': self.facture_ap.id,
                 'montant': '6000'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_compense'], '6000.00')
        comp_id = resp.data['id']

        resp2 = self.api.post(
            f'/api/django/compta/compensations/{comp_id}/valider/')
        self.assertEqual(resp2.status_code, 200, resp2.data)
        self.assertEqual(resp2.data['statut'], 'validee')

    def test_scoping_societe(self):
        autre = make_company('xfac14-autre', 'Autre Co XFAC14')
        autre_user = make_user(autre, 'xfac14-autre-admin', role='admin')
        api_autre = auth(autre_user)
        resp = api_autre.post('/api/django/compta/compensations/', {
            'client_id': self.client_obj.id,
            'fournisseur_id': self.fournisseur.id,
            'lignes': [
                {'type': 'ar', 'facture_id': self.facture_ar.id,
                 'montant': '10000'},
                {'type': 'ap', 'facture_id': self.facture_ap.id,
                 'montant': '6000'},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
