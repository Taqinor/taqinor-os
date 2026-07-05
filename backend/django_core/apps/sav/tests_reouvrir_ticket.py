"""XSAV11/YDOCF1 — action gardée ``reouvrir`` (ticket → NOUVEAU).

Contexte : la machine d'états (``machine_etats.py``) autorise la réouverture
vers NOUVEAU depuis PLANIFIE/RESOLU/CLOTURE, mais AUCUNE action gardée ne
l'exposait (seulement planifier/demarrer/resoudre/cloturer). Côté UI, choisir
« Nouveau » était donc un no-op silencieux laissant un statut périmé affiché.
``reouvrir`` comble ce trou.

Couvre :
  * RESOLU → NOUVEAU (200, statut nouveau, reopen_count incrémenté) ;
  * CLOTURE → NOUVEAU (200, reopen_count incrémenté) ;
  * EN_COURS → NOUVEAU refusé par la machine gardée (400, statut inchangé) ;
  * le tier de permission (sav_gerer) est verrouillé par
    ``tests_ticket_action_permissions.py`` (reouvrir y est découvert
    dynamiquement comme toute @action).

Run :
    python manage.py test apps.sav.tests_reouvrir_ticket -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket

User = get_user_model()


def make_company(slug='sav-reouvrir', nom='Sav Reouvrir'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReouvrirTicketTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='reouvrir_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Reo',
            email='reo-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-REO', client=self.client_obj)
        self._n = 0

    def _ticket(self, statut):
        self._n += 1
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-REO-{self._n}',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, statut=statut, created_by=self.admin)

    def _reouvrir(self, ticket):
        return self.api.post(
            f'/api/django/sav/tickets/{ticket.pk}/reouvrir/', {}, format='json')

    def test_reouvrir_depuis_resolu_incremente_reopen_count(self):
        t = self._ticket(Ticket.Statut.RESOLU)
        r = self._reouvrir(t)
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.NOUVEAU)
        self.assertEqual(t.reopen_count, 1)

    def test_reouvrir_depuis_cloture_incremente_reopen_count(self):
        t = self._ticket(Ticket.Statut.CLOTURE)
        r = self._reouvrir(t)
        self.assertEqual(r.status_code, 200, r.data)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.NOUVEAU)
        self.assertEqual(t.reopen_count, 1)

    def test_reouvrir_depuis_en_cours_refuse_400(self):
        t = self._ticket(Ticket.Statut.EN_COURS)
        r = self._reouvrir(t)
        self.assertEqual(r.status_code, 400, r.data)
        t.refresh_from_db()
        self.assertEqual(t.statut, Ticket.Statut.EN_COURS)
        self.assertEqual(t.reopen_count, 0)

    def test_reouvrir_scope_par_societe(self):
        autre = Company.objects.get_or_create(
            slug='sav-reouvrir-autre', defaults={'nom': 'Autre'})[0]
        other_admin = User.objects.create_user(
            username='reouvrir_autre', password='x', role_legacy='admin',
            company=autre)
        t = self._ticket(Ticket.Statut.RESOLU)
        r = auth(other_admin).post(
            f'/api/django/sav/tickets/{t.pk}/reouvrir/', {}, format='json')
        self.assertEqual(r.status_code, 404)
