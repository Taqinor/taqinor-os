"""QJ28 — « Contacter mon supérieur » sur un devis (action MANUELLE).

Couvre :
  * un clic notifie le supérieur du créateur du devis — une fois, jamais le
    vendeur lui-même ;
  * repli quand le supérieur manque → managers « Commercial responsable » /
    « Directeur » de la société ;
  * aucun destinataire résolvable → 400 avec message FR (pas de notification) ;
  * isolation multi-société : devis d'une autre société → 404 ; un manager
    d'une autre société n'est jamais notifié ;
  * aucun statut de devis n'est touché (règle #4).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import EventType, Notification
from apps.roles.models import Role
from apps.ventes.models import Devis, DevisActivity

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, supervisor=None, role=None):
    return User.objects.create_user(
        username=username, password='x', company=company,
        supervisor=supervisor, role=role, role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ContacterSuperieurTests(TestCase):
    def setUp(self):
        self.company = _company('qj28-co')
        self.boss = _user(self.company, 'qj28-boss')
        self.seller = _user(self.company, 'qj28-seller', supervisor=self.boss)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Tazi')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJ28-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.seller)
        self.api = _api(self.seller)

    def _post(self, devis=None, body=None, api=None):
        devis = devis or self.devis
        return (api or self.api).post(
            f'/api/django/ventes/devis/{devis.id}/contacter-superieur/',
            body or {}, format='json')

    def test_one_click_notifies_superior_once(self):
        resp = self._post(body={'message': 'Remise exceptionnelle ?'})
        self.assertEqual(resp.status_code, 200)
        notifs = Notification.objects.filter(
            event_type=EventType.DEVIS_SUPERIOR_CONTACT_REQUESTED)
        self.assertEqual(notifs.count(), 1)
        n = notifs.first()
        self.assertEqual(n.recipient, self.boss)
        self.assertEqual(n.company, self.company)
        self.assertIn('DEV-QJ28-0001', n.title)
        self.assertIn('Remise exceptionnelle ?', n.body)
        self.assertIn(f'devis={self.devis.pk}', n.link)
        # Jamais le vendeur lui-même.
        self.assertFalse(notifs.filter(recipient=self.seller).exists())

    def test_writes_devis_chatter_note(self):
        self._post()
        self.assertTrue(DevisActivity.objects.filter(
            devis=self.devis, kind=DevisActivity.Kind.NOTE,
            body__contains='Supérieur notifié').exists())

    def test_status_never_touched(self):
        self._post()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.BROUILLON)

    def test_fallback_to_company_managers(self):
        self.seller.supervisor = None
        self.seller.save(update_fields=['supervisor'])
        role = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=['ventes_voir'])
        manager = _user(self.company, 'qj28-manager', role=role)
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        recipients = set(Notification.objects.filter(
            event_type=EventType.DEVIS_SUPERIOR_CONTACT_REQUESTED,
        ).values_list('recipient_id', flat=True))
        self.assertEqual(recipients, {manager.pk})

    def test_no_recipient_400(self):
        self.seller.supervisor = None
        self.seller.save(update_fields=['supervisor'])
        resp = self._post()
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Notification.objects.count(), 0)

    def test_cross_company_devis_404(self):
        other = _company('qj28-autre')
        etranger = _user(other, 'qj28-etranger')
        resp = self._post(api=_api(etranger))
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Notification.objects.count(), 0)

    def test_other_company_manager_never_notified(self):
        other = _company('qj28-autre2')
        role = Role.objects.create(
            company=other, nom='Directeur', permissions=['ventes_voir'])
        etranger = _user(other, 'qj28-dir-etranger', role=role)
        self.seller.supervisor = None
        self.seller.save(update_fields=['supervisor'])
        Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=['ventes_voir'])
        local_dir = _user(
            self.company, 'qj28-dir-local',
            role=Role.objects.get(company=self.company, nom='Directeur'))
        self._post()
        self.assertFalse(
            Notification.objects.filter(recipient=etranger).exists())
        self.assertTrue(
            Notification.objects.filter(recipient=local_dir).exists())
