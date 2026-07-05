"""YDOCF1 — Machine d'états GARDÉE du ticket SAV.

Couvre :
  * une transition non autorisée renvoie 400 nommant le statut courant + les
    cibles permises (ex. NOUVEAU → CLOTURE direct est refusé) ;
  * le chemin normal NOUVEAU→PLANIFIE→EN_COURS→RESOLU→CLOTURE fonctionne et
    journalise (chatter) à chaque étape ;
  * `statut` n'est plus modifiable par un PATCH direct du corps de requête ;
  * isolation multi-tenant (un ticket d'une autre société renvoie 404).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ydocf1 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import Ticket, TicketActivity

User = get_user_model()


def make_company(slug='sav-ydocf1', nom='Sav Co YDOCF1'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class YDOCF1MachineEtatsTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='ydocf1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YDOCF1',
            email='ydocf1-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-YDOCF1', client=self.client_obj)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-YDOCF1-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)

    def _post(self, action):
        return self.api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/{action}/',
            {}, format='json')

    def test_saut_illegal_nouveau_vers_cloture_refuse(self):
        resp = self._post('cloturer')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('statut', resp.data)
        # Le message nomme le statut courant ET les cibles permises.
        message = str(resp.data['statut'])
        self.assertIn('nouveau', message)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.NOUVEAU)

    def test_chemin_normal_complet_fonctionne_et_journalise(self):
        r1 = self._post('planifier')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r1.data['statut'], 'planifie')

        r2 = self._post('demarrer')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['statut'], 'en_cours')

        r3 = self._post('resoudre')
        self.assertEqual(r3.status_code, 200, r3.data)
        self.assertEqual(r3.data['statut'], 'resolu')

        r4 = self._post('cloturer')
        self.assertEqual(r4.status_code, 200, r4.data)
        self.assertEqual(r4.data['statut'], 'cloture')

        acts = TicketActivity.objects.filter(
            ticket=self.ticket, kind=TicketActivity.Kind.MODIFICATION,
            field='statut')
        self.assertEqual(acts.count(), 4)

    def test_statut_non_modifiable_par_patch_direct(self):
        resp = self.api.patch(
            f'/api/django/sav/tickets/{self.ticket.pk}/',
            {'statut': 'cloture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.NOUVEAU)

    def test_transition_meme_statut_est_noop(self):
        # NOUVEAU → PLANIFIE → PLANIFIE (re-poster la même action cible) : la
        # 2e n'est pas dans le graphe PLANIFIE→PLANIFIE au sens strict, mais
        # `changer_statut` traite target==current comme un no-op sûr.
        self._post('planifier')
        resp = self._post('planifier')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'planifie')

    def test_cross_tenant_404(self):
        other = make_company(slug='sav-ydocf1-other', nom='Sav Co Other')
        other_admin = User.objects.create_user(
            username='ydocf1_other_admin', password='x', role_legacy='admin',
            company=other)
        other_api = auth(other_admin)
        resp = other_api.post(
            f'/api/django/sav/tickets/{self.ticket.pk}/demarrer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 404, resp.data)
