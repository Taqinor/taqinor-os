"""ACRM8 (C-ACRM-005) — les ÉCRITURES des viewsets enfants d'un lead sont
bornées à la PORTÉE du rôle (``selectors.leads_en_portee``).

Sonde V_VA LVIEW2-1 : un Commercial créait un RDV sur le lead L1 d'un
collègue hors équipe (GET L1 → 404) — POST 201, chatter de L1 0 → 3, un
BookingLink créé. Désormais chaque geste visant un lead hors portée rend
``{lead: ["Lead introuvable."]}`` (400, ou 404 sur une route de détail),
IDENTIQUE à un id inexistant, sans aucun effet ; un lead de sa portée est
servi comme avant.

Rôles réels ; aucun mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import (
    Appointment, BookingLink, ConcurrentPerte, Lead, LeadActivity,
    MessageTemplate, PointContact)
from apps.roles.models import Role
from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS

User = get_user_model()
BASE = '/api/django/crm/'
INTROUVABLE = {'lead': ['Lead introuvable.']}
INEXISTANT = 99999999


def _sans_request_id(data):
    """Corps d'erreur sans ``error.request_id`` (YAPIC3 : unique par
    requête) — le reste de l'enveloppe doit être IDENTIQUE."""
    corps = dict(data)
    if isinstance(corps.get('error'), dict):
        corps['error'] = {k: v for k, v in corps['error'].items()
                          if k != 'request_id'}
    return corps


class PorteeEnfantsEcrituresTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM8 Solaire', slug='acrm8-enfants')
        role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=list(COMMERCIAL_PERMISSIONS), est_systeme=True)
        self.moi = User.objects.create_user(
            username='acrm8-moi', password='x', company=self.company,
            role=role)
        self.collegue = User.objects.create_user(
            username='acrm8-collegue', password='x', company=self.company,
            role=role)
        self.mien = Lead.objects.create(
            company=self.company, nom='Mien', owner=self.moi)
        self.l1 = Lead.objects.create(
            company=self.company, nom='HorsPortee', owner=self.collegue)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.moi)}'))
        self.quand = (timezone.now() + datetime.timedelta(days=3)).isoformat()

    def _empreinte_l1(self):
        return (
            Appointment.objects.filter(lead=self.l1).count(),
            ConcurrentPerte.objects.filter(lead=self.l1).count(),
            PointContact.objects.filter(lead=self.l1).count(),
            LeadActivity.objects.filter(lead=self.l1).count(),
            BookingLink.objects.filter(lead=self.l1).count(),
        )

    def _refuse_comme_inexistant(self, methode, url, corps_pour):
        """POST/PATCH ``corps_pour(L1)`` et ``corps_pour(inexistant)`` : même
        400 ``{lead: ["Lead introuvable."]}``, aucun effet sur L1."""
        avant = self._empreinte_l1()
        envoyer = getattr(self.api, methode)
        hors = envoyer(url, corps_pour(self.l1.pk), format='json')
        absent = envoyer(url, corps_pour(INEXISTANT), format='json')
        self.assertEqual(hors.status_code, 400, hors.content)
        self.assertEqual(_sans_request_id(hors.data),
                         _sans_request_id(absent.data))
        self.assertEqual(hors.data['lead'], INTROUVABLE['lead'])
        self.assertEqual(self._empreinte_l1(), avant)

    def test_rdv_post(self):
        self._refuse_comme_inexistant(
            'post', f'{BASE}appointments/',
            lambda lead: {'lead': lead, 'scheduled_at': self.quand})
        resp = self.api.post(f'{BASE}appointments/',
                             {'lead': self.mien.pk,
                              'scheduled_at': self.quand}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_rdv_patch(self):
        rdv = Appointment.objects.create(
            company=self.company, lead=self.mien,
            scheduled_at=timezone.now() + datetime.timedelta(days=2))
        self._refuse_comme_inexistant(
            'patch', f'{BASE}appointments/{rdv.pk}/',
            lambda lead: {'lead': lead})
        rdv.refresh_from_db()
        self.assertEqual(rdv.lead_id, self.mien.pk)

    def test_concurrent_perte(self):
        self._refuse_comme_inexistant(
            'post', f'{BASE}concurrents-perte/',
            lambda lead: {'lead': lead, 'concurrent_nom': 'Rival'})
        resp = self.api.post(f'{BASE}concurrents-perte/',
                             {'lead': self.mien.pk, 'concurrent_nom': 'Rival'},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_point_contact(self):
        self._refuse_comme_inexistant(
            'post', f'{BASE}points-contact/',
            lambda lead: {'lead': lead, 'canal': 'telephone',
                          'date_contact': self.quand})
        resp = self.api.post(f'{BASE}points-contact/',
                             {'lead': self.mien.pk, 'canal': 'telephone',
                              'date_contact': self.quand}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_playbook_hors_portee_404(self):
        avant = self._empreinte_l1()
        resp = self.api.post(f'{BASE}leads/{self.l1.pk}/playbook/',
                             {'tache': 1, 'fait': True}, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self._empreinte_l1(), avant)

    def test_rendu_gabarit_sans_lien_rdv_hors_portee(self):
        tpl = MessageTemplate.objects.create(
            company=self.company, nom='RDV', corps='Réservez : {lien_rdv}')
        url = f'{BASE}message-templates/{tpl.pk}/render/'
        avant = self._empreinte_l1()
        hors = self.api.post(url, {'lead_id': self.l1.pk}, format='json')
        absent = self.api.post(url, {'lead_id': INEXISTANT}, format='json')
        self.assertEqual(hors.status_code, 400, hors.content)
        self.assertEqual(_sans_request_id(hors.data),
                         _sans_request_id(absent.data))
        self.assertEqual(self._empreinte_l1(), avant)
        ok = self.api.post(url, {'lead_id': self.mien.pk}, format='json')
        self.assertEqual(ok.status_code, 200, ok.content)
