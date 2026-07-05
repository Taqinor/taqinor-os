"""ZSAV2 — Types de ticket configurables (au-delà de correctif/préventif).

Couvre :
  * CRUD `CategorieTicket` scopé société (lecture tout rôle, écriture
    responsable/admin) ;
  * un ticket porte une catégorie optionnelle sans toucher `type` ;
  * filtre `?categorie=` sur la liste des tickets ;
  * migration additive : un ticket sans catégorie reste valide (comportement
    correctif/préventif inchangé).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_zsav2 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import CategorieTicket, Ticket

User = get_user_model()


def make_company(slug='sav-zsav2', nom='Sav Co ZSAV2'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ZSAV2CategorieTicketTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='zsav2_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='zsav2_normal', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='zsav2-client@example.invalid')

    def test_crud_scoped_admin(self):
        api = auth(self.admin)
        resp = api.post('/api/django/sav/categories-ticket/', {
            'libelle': 'Réclamation', 'ordre': 1,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        cat = CategorieTicket.objects.get(pk=resp.data['id'])
        self.assertEqual(cat.company_id, self.company.id)

    def test_lecture_ouverte_a_tout_role(self):
        CategorieTicket.objects.create(
            company=self.company, libelle='Question', ordre=1)
        api = auth(self.normal)
        resp = api.get('/api/django/sav/categories-ticket/')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_ecriture_refusee_role_normal(self):
        api = auth(self.normal)
        resp = api.post('/api/django/sav/categories-ticket/', {
            'libelle': 'Question', 'ordre': 1,
        })
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_ticket_porte_categorie_optionnelle_sans_toucher_type(self):
        cat = CategorieTicket.objects.create(
            company=self.company, libelle='Demande information', ordre=1)
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'type': Ticket.Type.CORRECTIF,
            'categorie': cat.id,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(pk=resp.data['id'])
        self.assertEqual(ticket.categorie_id, cat.id)
        self.assertEqual(ticket.type, Ticket.Type.CORRECTIF)

    def test_ticket_sans_categorie_reste_valide(self):
        api = auth(self.admin)
        resp = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'type': Ticket.Type.PREVENTIF,
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get(pk=resp.data['id'])
        self.assertIsNone(ticket.categorie_id)

    def test_filtre_categorie_sur_liste_tickets(self):
        cat_a = CategorieTicket.objects.create(
            company=self.company, libelle='Cat A', ordre=1)
        cat_b = CategorieTicket.objects.create(
            company=self.company, libelle='Cat B', ordre=2)
        Ticket.objects.create(
            company=self.company, reference='SAV-ZSAV2-1',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            categorie=cat_a, created_by=self.admin)
        Ticket.objects.create(
            company=self.company, reference='SAV-ZSAV2-2',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            categorie=cat_b, created_by=self.admin)

        api = auth(self.admin)
        resp = api.get(f'/api/django/sav/tickets/?categorie={cat_a.id}')
        self.assertEqual(resp.status_code, 200, resp.content)
        refs = {t['reference'] for t in resp.data['results']}
        self.assertEqual(refs, {'SAV-ZSAV2-1'})
