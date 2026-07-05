"""Tests YSUBS3/YSUBS4 — AbonnementMonitoring : facturation récurrente
découplée du renouvellement + transitions gardées (suspendre/résilier) avec
événement + motif obligatoire.

Couvre :
  * ``facturer_abonnement_monitoring`` émet une Facture standard (référence
    FAC, client résolu, TTC = montant) pour un abonnement actif ;
  * re-facturer la même période (``derniere_facturation``) refuse ;
  * ``renouveler`` n'émet plus aucune facture (découplage) ;
  * ``suspendre``/``resilier`` bloquent la facturation suivante ;
  * ``resilier`` sans motif refuse, avec motif émet
    ``abonnement_monitoring_resilie`` exactement une fois ;
  * isolation multi-tenant.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import AbonnementMonitoring
from apps.crm.models import Client
from apps.ventes.models import Facture
from core.events import abonnement_monitoring_resilie

User = get_user_model()


def make_company(slug='ysubs34-co', nom='YSUBS3/4 Co'):
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
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YSUBS34',
            telephone='+212600003401')
        self.abonnement = AbonnementMonitoring.objects.create(
            company=self.company, client_id=self.client_obj.id,
            periodicite='mensuel', montant=Decimal('199'),
            date_debut=date(2026, 1, 1),
            prochaine_echeance=date(2026, 2, 1))


class TestFacturerAbonnement(_Base):
    def test_facture_standard_emise(self):
        facture = compta_services.facturer_abonnement_monitoring(
            self.abonnement)
        self.assertEqual(facture.montant_ttc, Decimal('199.00'))
        self.assertEqual(facture.client_id, self.client_obj.id)
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertTrue(facture.reference.startswith('FAC'))
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.derniere_facturation, date(2026, 2, 1))

    def test_refacturer_meme_periode_refuse(self):
        compta_services.facturer_abonnement_monitoring(self.abonnement)
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.facturer_abonnement_monitoring(self.abonnement)
        self.assertEqual(
            Facture.objects.filter(client=self.client_obj).count(), 1)

    def test_abonnement_non_actif_refuse(self):
        compta_services.suspendre_abonnement_monitoring(self.abonnement)
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.facturer_abonnement_monitoring(self.abonnement)

    def test_renouveler_nemet_plus_de_facture(self):
        compta_services.renouveler_abonnement_monitoring(self.abonnement)
        self.assertEqual(
            Facture.objects.filter(client=self.client_obj).count(), 0)


class TestTransitionsGardees(_Base):
    def test_suspendre_bloque_facturation_suivante(self):
        compta_services.suspendre_abonnement_monitoring(self.abonnement)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.SUSPENDU)
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.facturer_abonnement_monitoring(self.abonnement)

    def test_resilier_sans_motif_refuse(self):
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.resilier_abonnement_monitoring(
                self.abonnement, motif='')
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.ACTIF)

    def test_resilier_avec_motif_emet_evenement_une_fois(self):
        recus = []

        def _handler(sender, abonnement, motif, company, **kwargs):
            recus.append((abonnement.id, motif))

        abonnement_monitoring_resilie.connect(_handler)
        try:
            compta_services.resilier_abonnement_monitoring(
                self.abonnement, motif='Client insatisfait')
            # Idempotent : re-résilier un abonnement déjà résilié → no-op,
            # aucune 2e émission.
            compta_services.resilier_abonnement_monitoring(
                self.abonnement, motif='Autre motif')
        finally:
            abonnement_monitoring_resilie.disconnect(_handler)

        self.assertEqual(len(recus), 1)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.RESILIE)
        self.assertEqual(
            self.abonnement.motif_resiliation, 'Client insatisfait')
        with self.assertRaises(compta_services.AbonnementMonitoringError):
            compta_services.facturer_abonnement_monitoring(self.abonnement)


class TestEndpoint(_Base):
    def setUp(self):
        super().setUp()
        self.user = make_user(self.company, 'ysubs34-admin')
        self.api = auth(self.user)

    def test_facturer_endpoint(self):
        resp = self.api.post(
            f'/api/django/compta/abonnements-monitoring/'
            f'{self.abonnement.id}/facturer/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_ttc'], '199.00')

    def test_resilier_endpoint_sans_motif_400(self):
        resp = self.api.post(
            f'/api/django/compta/abonnements-monitoring/'
            f'{self.abonnement.id}/resilier/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_resilier_endpoint_avec_motif_200(self):
        resp = self.api.post(
            f'/api/django/compta/abonnements-monitoring/'
            f'{self.abonnement.id}/resilier/',
            {'motif': 'Non renouvelé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.abonnement.refresh_from_db()
        self.assertEqual(
            self.abonnement.statut, AbonnementMonitoring.Statut.RESILIE)

    def test_isolation_societe(self):
        autre = make_company('ysubs34-autre', 'Autre Co')
        autre_user = make_user(autre, 'ysubs34-autre-admin')
        api_autre = auth(autre_user)
        resp = api_autre.post(
            f'/api/django/compta/abonnements-monitoring/'
            f'{self.abonnement.id}/facturer/')
        self.assertEqual(resp.status_code, 404)
