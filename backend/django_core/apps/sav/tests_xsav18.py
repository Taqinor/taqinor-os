"""XSAV18 — Rentabilité par contrat de maintenance.

Couvre :
  * calcul correct (revenu FG40 par libellé vs coût tickets+pièces) sur
    fixtures ;
  * permission gated (`prix_achat_voir`) — 403 explicite sans elle ;
  * classement par marge croissante (contrats à perte en premier).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav18 -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import ContratMaintenance, PieceConsommee, Ticket
from apps.ventes.models import Facture

User = get_user_model()


def make_company(slug='sav-xsav18', nom='Sav Co XSAV18'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV18RentabiliteTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav18_admin', password='x', role_legacy='admin',
            company=self.company)
        self.tech = User.objects.create_user(
            username='xsav18_tech', password='x', role_legacy='technicien',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav18-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV18', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Pièce X', sku='PIECE-X-XSAV18',
            prix_achat=Decimal('50'), prix_vente=Decimal('100'))
        self.contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj, installation=self.inst,
            periodicite='annuel', date_debut=date(2026, 1, 1),
            prix=Decimal('1200'), facturation_active=True)

    def _facture(self, montant_ttc, libelle=None):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-XSAV18-{Facture.objects.count()}',
            client=self.client_obj,
            statut=Facture.Statut.EMISE,
            montant_ht=montant_ttc, montant_tva=Decimal('0'),
            montant_ttc=montant_ttc,
            libelle=libelle or f'Maintenance — contrat #{self.contrat.pk} (Annuel)')

    def _ticket(self, cout=None, ticket_type=Ticket.Type.PREVENTIF):
        t = Ticket.objects.create(
            company=self.company, reference=f'SAV-XSAV18-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            type=ticket_type, cout=cout, created_by=self.admin)
        return t

    def test_calcul_correct_sur_fixtures(self):
        self._facture(Decimal('1200'))
        t1 = self._ticket(cout=Decimal('100'))
        PieceConsommee.objects.create(
            company=self.company, ticket=t1, produit=self.produit,
            quantite=2, created_by=self.admin)
        # revenu=1200, coût = 100 + 2*50 = 200 -> marge=1000, 1 visite (t1 préventif).

        api = auth(self.admin)
        resp = api.get(
            f'/api/django/sav/contrats-maintenance/{self.contrat.id}/rentabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['revenu'], 1200.0)
        self.assertEqual(resp.data['cout'], 200.0)
        self.assertEqual(resp.data['marge'], 1000.0)
        self.assertEqual(resp.data['nb_visites'], 1)
        self.assertEqual(resp.data['marge_par_visite'], 1000.0)

    def test_permission_gated_403_sans_prix_achat_voir(self):
        api = auth(self.tech)
        resp = api.get(
            f'/api/django/sav/contrats-maintenance/{self.contrat.id}/rentabilite/')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_ignore_facture_autre_contrat(self):
        autre_contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date(2026, 1, 1))
        self._facture(Decimal('1200'))
        self._facture(Decimal('500'), libelle=f'Maintenance — contrat #{autre_contrat.pk} (Annuel)')

        api = auth(self.admin)
        resp = api.get(
            f'/api/django/sav/contrats-maintenance/{self.contrat.id}/rentabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['revenu'], 1200.0)

    def test_classement_marge_croissante(self):
        # Contrat perdant (self.contrat) : coût > revenu.
        self._facture(Decimal('100'))
        self._ticket(cout=Decimal('900'))

        contrat_gagnant = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date(2026, 1, 1))
        Facture.objects.create(
            company=self.company, reference='FAC-XSAV18-GAGNANT',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('2000'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('2000'),
            libelle=f'Maintenance — contrat #{contrat_gagnant.pk} (Annuel)')

        api = auth(self.admin)
        resp = api.get('/api/django/sav/contrats-maintenance/rentabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data['results']
        self.assertEqual(len(results), 2)
        # Le contrat perdant (marge négative) doit apparaître en premier.
        self.assertEqual(results[0]['contrat_id'], self.contrat.id)
        self.assertLess(results[0]['marge'], results[1]['marge'])
