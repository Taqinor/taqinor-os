"""
XFAC21 — Dossier contentieux / passage en recouvrement externe.

Le pack PDF se télécharge complet, la réclamation contentieux est créée et
visible dans litiges, les relances automatiques de ces factures s'arrêtent
(tests scoping, factures payées refusées).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac21_dossier_contentieux -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.litiges.models import Reclamation
from apps.ventes.models import Facture, RelanceLog

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac21-co', nom='XFAC21 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac21@example.com'):
    return Client.objects.create(
        company=company, nom='Contentieux', prenom='Client',
        email=email, telephone='+212600000066', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC21DossierContentieuxTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac21_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8001',
            client=self.client_obj, statut=Facture.Statut.EN_RETARD,
            montant_ttc=Decimal('5000'), created_by=self.admin,
            date_echeance=timezone.now().date(),
        )
        RelanceLog.objects.create(
            company=self.company, facture=self.facture, niveau=1,
            niveau_nom='Rappel', note='Rappel envoyé', created_by=self.admin,
        )

    def _url(self):
        return (f'/api/django/ventes/clients/{self.client_obj.id}/'
                'dossier-contentieux/')

    def test_generates_pdf_and_opens_litiges_reclamation(self):
        r = self.api.post(self._url(), {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        reclamation_id = r['X-Reclamation-Id']
        reclamation = Reclamation.objects.get(pk=reclamation_id)
        self.assertEqual(reclamation.company, self.company)
        self.assertEqual(
            reclamation.type_reclamation, Reclamation.TypeReclamation.RECOUVREMENT)
        self.assertTrue(reclamation.bloque_relances)

    def test_freezes_relances_on_selected_factures(self):
        self.assertFalse(self.facture.exclu_relances)
        r = self.api.post(self._url(), {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.facture.refresh_from_db()
        self.assertTrue(self.facture.exclu_relances)

    def test_paid_facture_alone_refused_nothing_to_recover(self):
        self.facture.statut = Facture.Statut.PAYEE
        self.facture.save(update_fields=['statut'])
        r = self.api.post(self._url(), {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_no_client_factures_refused(self):
        other_client = make_client(self.company, email='xfac21b@example.com')
        r = self.api.post(
            f'/api/django/ventes/clients/{other_client.id}/'
            'dossier-contentieux/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_client_scoping_other_company_404(self):
        other_company = make_company(slug='xfac21-other', nom='XFAC21 Other')
        other_client = Client.objects.create(
            company=other_company, nom='Autre', email='other@example.com',
        )
        r = self.api.post(
            f'/api/django/ventes/clients/{other_client.id}/'
            'dossier-contentieux/', {}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_selected_factures_only(self):
        facture2 = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-8002',
            client=self.client_obj, statut=Facture.Statut.EN_RETARD,
            montant_ttc=Decimal('2000'), created_by=self.admin,
            date_echeance=timezone.now().date(),
        )
        r = self.api.post(
            self._url(), {'factures': [self.facture.id]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.facture.refresh_from_db()
        facture2.refresh_from_db()
        self.assertTrue(self.facture.exclu_relances)
        self.assertFalse(facture2.exclu_relances)
