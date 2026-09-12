"""NTSRV39 — Permissions fines pour Problème / NPS / sentiment IA.

Critère d'acceptation : un technicien SANS ``sav_probleme_gerer`` reçoit 403
sur ``problemes/`` en écriture, et 200 en lecture s'il a ``sav_voir``.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv39 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.roles.models import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
    PERMISSION_MODULE,
    Role,
    TECHNICIEN_PERMISSIONS,
    TECHNICIEN_RESP_PERMISSIONS,
)
from apps.sav.models import Probleme, Ticket

User = get_user_model()

CODES = ('sav_probleme_gerer', 'sav_nps_voir', 'sav_sentiment_ia_voir')
LISTE = '/api/django/sav/problemes/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV39CatalogueTest(TestCase):
    """Les trois codes existent au catalogue (sinon 403 pour TOUS les rôles
    fins — c'est la classe de bug WIR169)."""

    def test_codes_catalogues(self):
        for code in CODES:
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_rattaches_au_module_sav(self):
        for code in CODES:
            self.assertEqual(PERMISSION_MODULE.get(code), 'sav', code)

    def test_directeur_et_admin_les_portent(self):
        for code in CODES:
            self.assertIn(code, DIRECTEUR_PERMISSIONS, code)
            self.assertIn(code, ADMIN_PERMISSIONS, code)

    def test_technicien_responsable_les_porte(self):
        for code in CODES:
            self.assertIn(code, TECHNICIEN_RESP_PERMISSIONS, code)

    def test_technicien_de_base_ne_les_porte_pas(self):
        for code in CODES:
            self.assertNotIn(code, TECHNICIEN_PERMISSIONS, code)

    def test_technicien_de_base_garde_le_ticket_standard(self):
        # Non-régression : le retrait est CIBLÉ, l'accès ticket reste entier.
        self.assertIn('sav_voir', TECHNICIEN_PERMISSIONS)
        self.assertIn('sav_gerer', TECHNICIEN_PERMISSIONS)


class NTSRV39GardeProblemeTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv39', defaults={'nom': 'Sav Co NTSRV39'})
        self.role_technicien = Role.objects.create(
            company=self.company, nom='Technicien NTSRV39',
            permissions=list(TECHNICIEN_PERMISSIONS))
        self.role_responsable = Role.objects.create(
            company=self.company, nom='Technicien responsable NTSRV39',
            permissions=list(TECHNICIEN_RESP_PERMISSIONS))
        self.technicien = User.objects.create_user(
            username='ntsrv39_tech', password='x', role_legacy='normal',
            role=self.role_technicien, company=self.company)
        self.responsable = User.objects.create_user(
            username='ntsrv39_resp', password='x', role_legacy='normal',
            role=self.role_responsable, company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV39')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV39-1',
            client=self.client_obj, statut=Ticket.Statut.EN_COURS)
        self.probleme = Probleme.objects.create(
            company=self.company, reference='PRB-NTSRV39-1',
            titre='Onduleur X en panne')

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_technicien_403_en_ecriture(self):
        resp = auth(self.technicien).post(
            LISTE, {'titre': 'Tentative'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_technicien_200_en_lecture(self):
        resp = auth(self.technicien).get(LISTE)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_technicien_403_sur_lier_ticket(self):
        resp = auth(self.technicien).post(
            f'{LISTE}{self.probleme.pk}/lier-ticket/',
            {'ticket': self.ticket.pk}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_technicien_403_sur_delier_ticket(self):
        resp = auth(self.technicien).post(
            f'{LISTE}{self.probleme.pk}/delier-ticket/',
            {'ticket': self.ticket.pk}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_technicien_403_sur_le_wizard_de_creation(self):
        resp = auth(self.technicien).post(
            f'{LISTE}creer-depuis-regroupement/',
            {'titre': 'Tentative', 'ticket_ids': [self.ticket.pk]},
            format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_technicien_200_sur_les_lectures_annexes(self):
        api = auth(self.technicien)
        self.assertEqual(
            api.get(f'{LISTE}{self.probleme.pk}/tickets/').status_code, 200)
        self.assertEqual(
            api.get(f'{LISTE}regroupements-suggeres/').status_code, 200)

    # ── Le responsable, lui, passe ───────────────────────────────────────
    def test_responsable_cree_un_probleme(self):
        resp = auth(self.responsable).post(
            LISTE, {'titre': 'Cause racine identifiée'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_responsable_lie_un_ticket(self):
        resp = auth(self.responsable).post(
            f'{LISTE}{self.probleme.pk}/lier-ticket/',
            {'ticket': self.ticket.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['cree'])

    # ── Non-régression comptes hérités SANS rôle fin ─────────────────────
    def test_compte_herite_admin_sans_role_fin_passe(self):
        legacy = User.objects.create_user(
            username='ntsrv39_legacy', password='x', role_legacy='admin',
            company=self.company)
        resp = auth(legacy).post(LISTE, {'titre': 'Hérité'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
