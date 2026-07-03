"""
XFAC1 — Avances client (paiement sans facture) + affectation multi-factures.

On enregistre une avance sans facture, on la ventile ensuite sur 2 factures,
chaque ``montant_du`` baisse du montant affecté, un paiement ne peut jamais
être sur-affecté (>montant), tests multi-tenant (cross-company 404).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_xfac1_avances -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='xfac1-co', nom='XFAC1 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, email='xfac1@example.com'):
    return Client.objects.create(
        company=company, nom='Avance', prenom='Client',
        email=email, telephone='+212600000051', adresse='Casablanca',
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XFAC1AvancesTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.admin = User.objects.create_user(
            username='xfac1_admin', password='x', role_legacy='admin',
            company=self.company,
        )
        self.api = auth(self.admin)

    def _facture(self, ttc='3000'):
        return Facture.objects.create(
            company=self.company,
            reference=f'FAC-{MONTH}-{Facture.objects.count() + 1:04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal(ttc) / Decimal('1.20') * Decimal('1'),
            montant_tva=Decimal('0'), montant_ttc=Decimal(ttc),
            created_by=self.admin,
        )

    # ── 1. Enregistrer une avance sans facture ──
    def test_enregistrer_avance_creates_unaffected_payment(self):
        r = self.api.post(
            '/api/django/ventes/paiements/enregistrer-avance/', {
                'client': self.client_obj.id, 'montant': '5000',
                'date_paiement': timezone.now().date().isoformat(),
                'mode': 'virement',
            }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut_affectation'], 'non_affecte')
        self.assertIsNone(r.data['facture'])
        paiement = Paiement.objects.get(pk=r.data['id'])
        self.assertEqual(paiement.montant_disponible, Decimal('5000'))

    def test_enregistrer_avance_requires_positive_montant(self):
        r = self.api.post(
            '/api/django/ventes/paiements/enregistrer-avance/', {
                'client': self.client_obj.id, 'montant': '0',
                'date_paiement': timezone.now().date().isoformat(),
                'mode': 'virement',
            }, format='json')
        self.assertEqual(r.status_code, 400)

    # ── 2. Ventiler une avance sur 2 factures ──
    def test_ventiler_avance_across_two_factures(self):
        avance = Paiement.objects.create(
            company=self.company, client=self.client_obj, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('5000'), date_paiement=timezone.now().date(),
            mode='virement', created_by=self.admin,
        )
        f1 = self._facture('2000')
        f2 = self._facture('2500')
        self.assertEqual(f1.montant_du, Decimal('2000'))
        self.assertEqual(f2.montant_du, Decimal('2500'))

        r1 = self.api.post(
            f'/api/django/ventes/paiements/{avance.id}/ventiler/',
            {'facture': f1.id, 'montant': '2000'}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        f1.refresh_from_db()
        self.assertEqual(f1.montant_du, Decimal('0'))
        self.assertEqual(f1.statut, Facture.Statut.PAYEE)

        r2 = self.api.post(
            f'/api/django/ventes/paiements/{avance.id}/ventiler/',
            {'facture': f2.id, 'montant': '2500'}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        f2.refresh_from_db()
        self.assertEqual(f2.montant_du, Decimal('0'))

        avance.refresh_from_db()
        self.assertEqual(avance.statut_affectation, 'affecte')
        self.assertEqual(avance.montant_disponible, Decimal('0'))

    # ── 3. Jamais de sur-affectation ──
    def test_ventiler_cannot_exceed_montant_disponible(self):
        avance = Paiement.objects.create(
            company=self.company, client=self.client_obj, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('1000'), date_paiement=timezone.now().date(),
            mode='virement', created_by=self.admin,
        )
        f1 = self._facture('5000')
        r = self.api.post(
            f'/api/django/ventes/paiements/{avance.id}/ventiler/',
            {'facture': f1.id, 'montant': '1500'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_ventiler_cannot_exceed_facture_montant_du(self):
        avance = Paiement.objects.create(
            company=self.company, client=self.client_obj, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('10000'), date_paiement=timezone.now().date(),
            mode='virement', created_by=self.admin,
        )
        f1 = self._facture('2000')
        r = self.api.post(
            f'/api/django/ventes/paiements/{avance.id}/ventiler/',
            {'facture': f1.id, 'montant': '3000'}, format='json')
        self.assertEqual(r.status_code, 400)

    # ── 4. Multi-tenant : cross-company 404 ──
    def test_ventiler_cross_company_facture_404(self):
        avance = Paiement.objects.create(
            company=self.company, client=self.client_obj, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('1000'), date_paiement=timezone.now().date(),
            mode='virement', created_by=self.admin,
        )
        other_company = make_company(slug='xfac1-other', nom='Other Co')
        other_client = make_client(other_company, email='other@example.com')
        other_facture = Facture.objects.create(
            company=other_company,
            reference=f'FAC-{MONTH}-OTH-0001',
            client=other_client, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('1000'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('1000'),
        )
        r = self.api.post(
            f'/api/django/ventes/paiements/{avance.id}/ventiler/',
            {'facture': other_facture.id, 'montant': '500'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_ventiler_cross_company_paiement_404(self):
        other_company = make_company(slug='xfac1-other2', nom='Other Co 2')
        other_client = make_client(other_company, email='other2@example.com')
        other_avance = Paiement.objects.create(
            company=other_company, client=other_client, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('1000'), date_paiement=timezone.now().date(),
            mode='virement',
        )
        f1 = self._facture('2000')
        r = self.api.post(
            f'/api/django/ventes/paiements/{other_avance.id}/ventiler/',
            {'facture': f1.id, 'montant': '500'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_avances_non_affectees_list_scoped_by_company(self):
        Paiement.objects.create(
            company=self.company, client=self.client_obj, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('1000'), date_paiement=timezone.now().date(),
            mode='virement',
        )
        other_company = make_company(slug='xfac1-other3', nom='Other Co 3')
        other_client = make_client(other_company, email='other3@example.com')
        Paiement.objects.create(
            company=other_company, client=other_client, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('2000'), date_paiement=timezone.now().date(),
            mode='virement',
        )
        r = self.api.get('/api/django/ventes/paiements/avances-non-affectees/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
