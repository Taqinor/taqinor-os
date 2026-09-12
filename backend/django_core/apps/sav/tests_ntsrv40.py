"""NTSRV40 — Permission de réponse externe par canal.

Critère d'acceptation : un agent SANS ``sav_repondre_client_externe`` ne peut
pas envoyer de réponse externe (le champ est désactivé dans l'inbox NTSRV4 —
côté serveur : 403) mais garde l'accès aux notes INTERNES.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv40 -v 2
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
    COMMERCIAL_RESP_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
    Role,
    TECHNICIEN_PERMISSIONS,
    TECHNICIEN_RESP_PERMISSIONS,
)
from apps.sav.models import Ticket

User = get_user_model()

CODE = 'sav_repondre_client_externe'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV40CatalogueTest(TestCase):
    def test_code_catalogue(self):
        self.assertIn(CODE, ALL_PERMISSIONS)

    def test_aucun_acces_existant_retire(self):
        """Tout rôle système qui portait ``sav_gerer`` porte AUSSI le nouveau
        code : la séparation est opt-OUT (on le retire à l'agent en
        formation), jamais une régression silencieuse."""
        for nom, perms in (
                ('Responsable', RESPONSABLE_PERMISSIONS),
                ('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS),
                ('Technicien responsable', TECHNICIEN_RESP_PERMISSIONS),
                ('Technicien', TECHNICIEN_PERMISSIONS),
                ('Directeur', DIRECTEUR_PERMISSIONS),
                ('Administrateur', ADMIN_PERMISSIONS)):
            if 'sav_gerer' in perms:
                self.assertIn(CODE, perms, nom)

    def test_distinct_de_sav_gerer(self):
        self.assertNotEqual(CODE, 'sav_gerer')
        self.assertIn('sav_gerer', ALL_PERMISSIONS)


class NTSRV40GardeReponseExterneTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv40', defaults={'nom': 'Sav Co NTSRV40'})
        # Agent en FORMATION : le rôle Technicien MOINS le nouveau code.
        self.role_formation = Role.objects.create(
            company=self.company, nom='Technicien en formation NTSRV40',
            permissions=[p for p in TECHNICIEN_PERMISSIONS if p != CODE])
        self.role_confirme = Role.objects.create(
            company=self.company, nom='Technicien confirmé NTSRV40',
            permissions=list(TECHNICIEN_PERMISSIONS))
        self.formation = User.objects.create_user(
            username='ntsrv40_formation', password='x', role_legacy='normal',
            role=self.role_formation, company=self.company)
        self.confirme = User.objects.create_user(
            username='ntsrv40_confirme', password='x', role_legacy='normal',
            role=self.role_confirme, company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV40',
            email='client-ntsrv40@example.test')
        # Portée de visibilité (Feature F) : `TECHNICIEN_PERMISSIONS` porte
        # `records_scope_equipe`, donc `TicketViewSet.get_queryset` ne montre
        # à un technicien que les tickets dont il est le responsable OU le
        # créateur. Un ticket SANS propriétaire serait invisible (404) des
        # deux agents — ce que NTSRV40 ne teste pas. On rattache donc chaque
        # agent par un bout : le fil reste visible des deux, seule la garde
        # `sav_repondre_client_externe` les distingue.
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV40-1',
            client=self.client_obj, statut=Ticket.Statut.EN_COURS,
            technicien_responsable=self.confirme, created_by=self.formation)

    def _repondre(self, user):
        return auth(user).post(
            f'/api/django/sav/tickets/{self.ticket.pk}/repondre-email/',
            {'corps': 'Bonjour, votre onduleur est réparé.',
             'destinataire': 'client-ntsrv40@example.test'}, format='json')

    def _noter(self, user):
        return auth(user).post(
            f'/api/django/sav/tickets/{self.ticket.pk}/noter/',
            {'body': 'Note interne : pièce commandée.'}, format='json')

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_agent_en_formation_403_sur_reponse_externe(self):
        self.assertEqual(self._repondre(self.formation).status_code, 403)

    def test_agent_en_formation_garde_les_notes_internes(self):
        resp = self._noter(self.formation)
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_agent_en_formation_garde_la_lecture_du_fil(self):
        resp = auth(self.formation).get(
            f'/api/django/sav/tickets/{self.ticket.pk}/emails/')
        self.assertEqual(resp.status_code, 200, resp.content)

    # ── L'agent confirmé, lui, répond ────────────────────────────────────
    def test_agent_confirme_repond(self):
        resp = self._repondre(self.confirme)
        self.assertEqual(resp.status_code, 201, resp.content)

    # ── Non-régression comptes hérités SANS rôle fin ─────────────────────
    def test_compte_herite_responsable_repond_toujours(self):
        legacy = User.objects.create_user(
            username='ntsrv40_legacy', password='x', role_legacy='admin',
            company=self.company)
        self.assertEqual(self._repondre(legacy).status_code, 201)
