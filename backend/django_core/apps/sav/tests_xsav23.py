"""XSAV23 — Réponses types (macros) SAV.

Couvre :
  * CRUD company-scoped ;
  * insertion en un clic rend les placeholders whitelistés ;
  * le changement de statut optionnel est appliqué ;
  * un placeholder non whitelisté / un `{` isolé ne casse jamais le rendu.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav23 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import ReponseType, Ticket

User = get_user_model()


def make_company(slug='sav-xsav23', nom='Sav Co XSAV23'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV23ReponseTypeTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav23_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav23-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV23', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV23-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)

    def test_crud_company_scoped(self):
        api = auth(self.admin)
        resp = api.post(
            '/api/django/sav/reponses-type/',
            {'titre': 'Confirmation RDV',
             'corps': 'Bonjour {client}, votre ticket {reference} est planifié.'})
        self.assertEqual(resp.status_code, 201, resp.content)
        rt = ReponseType.objects.get(pk=resp.data['id'])
        self.assertEqual(rt.company_id, self.company.id)

        resp = api.get('/api/django/sav/reponses-type/')
        self.assertEqual(resp.status_code, 200, resp.content)
        titres = [r['titre'] for r in resp.data.get(
            'results', resp.data if isinstance(resp.data, list) else [])]
        self.assertIn('Confirmation RDV', titres)

    def test_insertion_rend_placeholders(self):
        macro = ReponseType.objects.create(
            company=self.company, titre='RDV',
            corps='Bonjour {client}, ticket {reference}, le {date}.')
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/noter/',
            {'reponse_type_id': macro.id})
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.data['body']
        self.assertIn('Client Test', body)
        self.assertIn('SAV-XSAV23-1', body)
        self.assertNotIn('{client}', body)
        self.assertNotIn('{reference}', body)

    def test_changement_statut_applique(self):
        macro = ReponseType.objects.create(
            company=self.company, titre='Planification',
            corps='Ticket planifié.', nouveau_statut=Ticket.Statut.PLANIFIE)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/noter/',
            {'reponse_type_id': macro.id})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.PLANIFIE)

    def test_statut_idempotent_deja_dans_ce_statut(self):
        self.ticket.statut = Ticket.Statut.PLANIFIE
        self.ticket.save(update_fields=['statut'])
        macro = ReponseType.objects.create(
            company=self.company, titre='Planification 2',
            corps='Déjà planifié.', nouveau_statut=Ticket.Statut.PLANIFIE)
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/noter/',
            {'reponse_type_id': macro.id})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.PLANIFIE)

    def test_placeholder_non_whiteliste_ne_casse_pas(self):
        macro = ReponseType.objects.create(
            company=self.company, titre='Étrange',
            corps='Bonjour {client}, code {inconnu} et accolade { seule.')
        rendu = macro.rendu(client='X', reference='R1')
        self.assertIn('X', rendu)
        self.assertIn('{inconnu}', rendu)
        self.assertIn('{ seule.', rendu)

    def test_body_explicite_prioritaire_sur_macro(self):
        macro = ReponseType.objects.create(
            company=self.company, titre='Macro Test',
            corps='Corps de la macro.')
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/noter/',
            {'reponse_type_id': macro.id, 'body': 'Note manuelle explicite'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['body'], 'Note manuelle explicite')
