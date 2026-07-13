"""VX215 — boucle de retour « pris en charge » : après « Contacter mon
supérieur » (QJ28), le vendeur voit si sa demande a été VUE par le
supérieur notifié, sans jamais lire le contenu des notifications d'autrui —
seulement l'état `read`/qui a lu, pour CETTE demande précise.

Couvre :
  * aucune demande envoyée encore -> `requested: False` ;
  * demande envoyée, pas encore lue -> `requested: True, seen: False` ;
  * le supérieur marque sa notification lue -> `seen: True` + son username ;
  * isolation multi-société (devis d'une autre société -> 404, jamais de
    fuite d'un autre client).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import EventType, Notification
from apps.ventes.models import Devis

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, supervisor=None):
    return User.objects.create_user(
        username=username, password='x', company=company,
        supervisor=supervisor, role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SuperieurContactStatusTests(TestCase):
    def setUp(self):
        self.company = _company('vx215-co')
        self.boss = _user(self.company, 'vx215-boss')
        self.seller = _user(self.company, 'vx215-seller', supervisor=self.boss)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Benjelloun')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-VX215-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.seller)
        self.api = _api(self.seller)

    def _status(self, devis=None, api=None):
        devis = devis or self.devis
        return (api or self.api).get(
            f'/api/django/ventes/devis/{devis.id}/superior-contact-status/')

    def test_no_request_yet(self):
        resp = self._status()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, {'requested': False})

    def test_requested_but_not_seen(self):
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/contacter-superieur/',
            {}, format='json')
        resp = self._status()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['requested'])
        self.assertFalse(resp.data['seen'])
        self.assertEqual(resp.data['seen_by'], [])

    def test_seen_after_boss_reads_it(self):
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/contacter-superieur/',
            {}, format='json')
        notif = Notification.objects.get(
            event_type=EventType.DEVIS_SUPERIOR_CONTACT_REQUESTED,
            recipient=self.boss)
        # Le directeur ouvre sa notification (même chemin que le clic réel
        # côté cloche : POST .../notifications/<id>/read/).
        boss_api = _api(self.boss)
        boss_api.post(
            f'/api/django/notifications/notifications/{notif.id}/read/')

        resp = self._status()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['requested'])
        self.assertTrue(resp.data['seen'])
        self.assertIn('vx215-boss', resp.data['seen_by'])

    def test_cross_company_devis_404(self):
        other = _company('vx215-autre')
        etranger = _user(other, 'vx215-etranger')
        resp = self._status(api=_api(etranger))
        self.assertEqual(resp.status_code, 404)

    def test_never_leaks_another_devis_notification(self):
        # Un deuxième devis de la même société, jamais contacté — sa demande
        # à lui ne doit rien montrer, même si le premier a une notif.
        other_devis = Devis.objects.create(
            company=self.company, reference='DEV-VX215-0002',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.seller)
        self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/contacter-superieur/',
            {}, format='json')
        resp = self._status(devis=other_devis)
        self.assertEqual(resp.data, {'requested': False})
