"""XSAV15 — MTBF / MTTR / coût cumulé par équipement et par modèle.

Couvre :
  * MTBF = écart moyen entre tickets correctifs successifs du même équipement ;
  * MTTR = écart moyen ouverture -> résolution ;
  * coût cumulé (Ticket.cout + pièces valorisées prix d'achat) gated
    `prix_achat_voir` — jamais renvoyé sans la permission ;
  * indicateur réparer-vs-remplacer ;
  * vue d'ensemble parc triée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav15 -v 2
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
from apps.sav.models import Equipement, PieceConsommee, Ticket

User = get_user_model()


def make_company(slug='sav-xsav15', nom='Sav Co XSAV15'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV15FiabiliteTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user_no_cout = User.objects.create_user(
            username='xsav15_tech', password='x', role_legacy='technicien',
            company=self.company)
        self.admin = User.objects.create_user(
            username='xsav15_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav15-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV15', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur MTBF', sku='OND-MTBF-XSAV15',
            prix_achat=Decimal('300'), prix_vente=Decimal('600'))
        self.equip = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            created_by=self.admin)

    def _ticket(self, date_ouverture, date_resolution=None, cout=None):
        t = Ticket.objects.create(
            company=self.company, reference=f'SAV-XSAV15-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            equipement=self.equip, type=Ticket.Type.CORRECTIF,
            statut=Ticket.Statut.RESOLU if date_resolution else Ticket.Statut.NOUVEAU,
            date_ouverture=date_ouverture, date_resolution=date_resolution,
            cout=cout, created_by=self.admin)
        return t

    def test_mtbf_mttr_corrects_sur_fixtures(self):
        # Tickets ouverts à J0, J+10, J+30 -> écarts 10, 20 -> MTBF = 15.
        self._ticket(date(2026, 1, 1), date(2026, 1, 3))
        self._ticket(date(2026, 1, 11), date(2026, 1, 14))
        self._ticket(date(2026, 1, 31), date(2026, 2, 2))

        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/equipements/{self.equip.id}/fiabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['mtbf_jours'], 15.0)
        # MTTR : (2,3,2) jours -> moyenne = 2.33
        self.assertAlmostEqual(resp.data['mttr_jours'], 2.33, places=1)
        self.assertEqual(resp.data['nb_tickets_correctifs'], 3)

    def test_mtbf_none_si_moins_de_deux_tickets(self):
        self._ticket(date(2026, 1, 1), date(2026, 1, 3))
        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/equipements/{self.equip.id}/fiabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIsNone(resp.data['mtbf_jours'])

    def test_cout_gated_prix_achat_voir(self):
        self._ticket(date(2026, 1, 1), date(2026, 1, 3), cout=Decimal('200'))
        t2 = self._ticket(date(2026, 1, 11), date(2026, 1, 14), cout=Decimal('100'))
        PieceConsommee.objects.create(
            company=self.company, ticket=t2, produit=self.produit,
            quantite=2, created_by=self.admin)

        api_tech = auth(self.user_no_cout)
        resp = api_tech.get(
            f'/api/django/sav/equipements/{self.equip.id}/fiabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn('cout_cumule', resp.data)

        api_admin = auth(self.admin)
        resp = api_admin.get(
            f'/api/django/sav/equipements/{self.equip.id}/fiabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        # coût = 200 + 100 (tickets) + 2*300 (pièces au prix d'achat) = 900.
        self.assertEqual(resp.data['cout_cumule'], 900.0)
        # prix catalogue = 600 < coût cumulé -> remplacer.
        self.assertEqual(resp.data['reparer_vs_remplacer'], 'remplacer')

    def test_reparer_si_cout_sous_prix_catalogue(self):
        self._ticket(date(2026, 1, 1), date(2026, 1, 3), cout=Decimal('50'))
        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/equipements/{self.equip.id}/fiabilite/')
        self.assertEqual(resp.data['reparer_vs_remplacer'], 'reparer')

    def test_insight_vue_ensemble_triee(self):
        produit2 = Produit.objects.create(
            company=self.company, nom='Onduleur MTBF 2', sku='OND-MTBF2-XSAV15',
            prix_achat=Decimal('100'), prix_vente=Decimal('200'))
        equip2 = Equipement.objects.create(
            company=self.company, produit=produit2, installation=self.inst,
            created_by=self.admin)
        self._ticket(date(2026, 1, 1), date(2026, 1, 3), cout=Decimal('50'))
        Ticket.objects.create(
            company=self.company, reference='SAV-XSAV15-EQ2',
            client=self.client_obj, installation=self.inst,
            equipement=equip2, type=Ticket.Type.CORRECTIF,
            statut=Ticket.Statut.RESOLU,
            date_ouverture=date(2026, 1, 1), date_resolution=date(2026, 1, 2),
            cout=Decimal('900'), created_by=self.admin)

        api = auth(self.admin)
        resp = api.get('/api/django/sav/insights/sav-fiabilite/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['couts_inclus'])
        results = resp.data['results']
        self.assertEqual(len(results), 2)
        # Trié par coût cumulé décroissant -> équipement 2 (900) en premier.
        self.assertEqual(results[0]['equipement_id'], equip2.id)
