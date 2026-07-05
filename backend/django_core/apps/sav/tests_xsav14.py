"""XSAV14 — Taxonomie panne / cause / remède + Pareto des défaillances.

Couvre :
  * CauseDefaillance / RemedeDefaillance CRUD, company-scoped ;
  * codes saisis à la résolution (cause/remede posés sur le ticket) ;
  * Pareto par produit correct sur fixtures (nb, %, %cumulé, causes) ;
  * multi-tenant : un ticket/cause d'une autre société n'apparaît jamais.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav14 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.sav.models import CauseDefaillance, Equipement, RemedeDefaillance, Ticket

User = get_user_model()


def make_company(slug='sav-xsav14', nom='Sav Co XSAV14'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV14TaxonomieTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company(slug='sav-xsav14-other', nom='Autre Co')
        self.user = User.objects.create_user(
            username='xsav14_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav14-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV14', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X', sku='OND-X-XSAV14',
            prix_achat=500, prix_vente=900)
        self.produit2 = Produit.objects.create(
            company=self.company, nom='Onduleur Y', sku='OND-Y-XSAV14',
            prix_achat=500, prix_vente=900)
        self.cause_defaut = CauseDefaillance.objects.create(
            company=self.company, nom='Défaut composant')
        self.cause_install = CauseDefaillance.objects.create(
            company=self.company, nom="Erreur d'installation")
        self.remede = RemedeDefaillance.objects.create(
            company=self.company, nom='Remplacement pièce')

    def _equip(self, produit):
        return Equipement.objects.create(
            company=self.company, produit=produit, installation=self.inst,
            created_by=self.user)

    def _ticket(self, equipement, cause=None, remede=None):
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-XSAV14-{Ticket.objects.count()}',
            client=self.client_obj, installation=self.inst,
            equipement=equipement, type=Ticket.Type.CORRECTIF,
            annule=False, cause=cause, remede=remede, created_by=self.user)

    # ── CRUD référentiels ────────────────────────────────────────────────────

    def test_causes_defaillance_crud_scoped(self):
        resp = self.api.get('/api/django/sav/causes-defaillance/')
        self.assertEqual(resp.status_code, 200, resp.content)
        noms = [c['nom'] for c in resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])]
        self.assertIn('Défaut composant', noms)

        resp = self.api.post(
            '/api/django/sav/causes-defaillance/', {'nom': 'Usure normale'})
        self.assertEqual(resp.status_code, 201, resp.content)
        created = CauseDefaillance.objects.get(pk=resp.data['id'])
        self.assertEqual(created.company_id, self.company.id)

    def test_remedes_defaillance_crud_scoped(self):
        resp = self.api.post(
            '/api/django/sav/remedes-defaillance/', {'nom': 'Nettoyage'})
        self.assertEqual(resp.status_code, 201, resp.content)
        created = RemedeDefaillance.objects.get(pk=resp.data['id'])
        self.assertEqual(created.company_id, self.company.id)

    # ── Codification à la résolution ────────────────────────────────────────

    def test_cause_remede_poses_sur_ticket_via_api(self):
        # YDOCF1 — cause/remède restent PATCHables directement (hors machine
        # d'états) ; la transition de statut passe par l'action guardée.
        ticket = self._ticket(self._equip(self.produit))
        self.api.post(f'/api/django/sav/tickets/{ticket.id}/demarrer/',
                      {}, format='json')
        resp = self.api.patch(
            f'/api/django/sav/tickets/{ticket.id}/',
            {'cause': self.cause_defaut.id, 'remede': self.remede.id},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        resp2 = self.api.post(
            f'/api/django/sav/tickets/{ticket.id}/resoudre/', {}, format='json')
        self.assertEqual(resp2.status_code, 200, resp2.content)
        ticket.refresh_from_db()
        self.assertEqual(ticket.cause_id, self.cause_defaut.id)
        self.assertEqual(ticket.remede_id, self.remede.id)
        self.assertEqual(resp.data['cause_nom'], 'Défaut composant')
        self.assertEqual(resp.data['remede_nom'], 'Remplacement pièce')

    def test_cause_cross_tenant_rejetee(self):
        cause_etrangere = CauseDefaillance.objects.create(
            company=self.other_company, nom='Cause étrangère')
        ticket = self._ticket(self._equip(self.produit))
        resp = self.api.patch(
            f'/api/django/sav/tickets/{ticket.id}/',
            {'cause': cause_etrangere.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    # ── Pareto ───────────────────────────────────────────────────────────────

    def test_pareto_pannes_correct_sur_fixtures(self):
        eq1 = self._equip(self.produit)
        eq2 = self._equip(self.produit2)
        # produit 1 : 3 tickets avec cause codifiée.
        self._ticket(eq1, cause=self.cause_defaut)
        self._ticket(eq1, cause=self.cause_defaut)
        self._ticket(eq1, cause=self.cause_install)
        # produit 2 : 1 ticket.
        self._ticket(eq2, cause=self.cause_defaut)
        # ticket sans cause codifiée — ignoré du Pareto.
        self._ticket(eq1, cause=None)

        resp = self.api.get('/api/django/sav/insights/sav-pannes/')
        self.assertEqual(resp.status_code, 200, resp.content)
        results = resp.data['results']
        self.assertEqual(len(results), 2)
        top = results[0]
        self.assertEqual(top['libelle'], 'Onduleur X')
        self.assertEqual(top['nb_tickets'], 3)
        self.assertEqual(top['pct'], 75.0)
        self.assertEqual(top['pct_cumule'], 75.0)
        causes = {c['cause']: c['nb'] for c in top['causes']}
        self.assertEqual(causes['Défaut composant'], 2)
        self.assertEqual(causes["Erreur d'installation"], 1)

        second = results[1]
        self.assertEqual(second['libelle'], 'Onduleur Y')
        self.assertEqual(second['nb_tickets'], 1)
        self.assertEqual(second['pct_cumule'], 100.0)

    def test_pareto_exclut_autre_societe(self):
        # Ticket d'une autre société ne doit jamais apparaître.
        other_user = User.objects.create_user(
            username='xsav14_other', password='x', role_legacy='admin',
            company=self.other_company)
        other_client = Client.objects.create(
            company=self.other_company, nom='Autre', prenom='Client',
            email='xsav14-other@example.invalid')
        other_inst = Installation.objects.create(
            company=self.other_company, reference='CHT-OTHER', client=other_client)
        other_produit = Produit.objects.create(
            company=self.other_company, nom='Onduleur Étranger',
            sku='OND-OTHER', prix_achat=500, prix_vente=900)
        other_cause = CauseDefaillance.objects.create(
            company=self.other_company, nom='Cause étrangère')
        other_equip = Equipement.objects.create(
            company=self.other_company, produit=other_produit,
            installation=other_inst, created_by=other_user)
        Ticket.objects.create(
            company=self.other_company, reference='SAV-OTHER-1',
            client=other_client, installation=other_inst,
            equipement=other_equip, type=Ticket.Type.CORRECTIF,
            cause=other_cause, created_by=other_user)

        eq1 = self._equip(self.produit)
        self._ticket(eq1, cause=self.cause_defaut)

        resp = self.api.get('/api/django/sav/insights/sav-pannes/')
        self.assertEqual(resp.status_code, 200, resp.content)
        libelles = [r['libelle'] for r in resp.data['results']]
        self.assertNotIn('Onduleur Étranger', libelles)
        self.assertEqual(len(resp.data['results']), 1)
