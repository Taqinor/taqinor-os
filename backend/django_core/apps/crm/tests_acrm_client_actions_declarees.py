"""ACRM21 (C-ACRM-014) — les @action de ``ClientViewSet`` répondent selon
LEUR déclaration, plus selon le repli brut ``IsAdminRole``.

Sonde V_VA LVIEW1-5 : ``consolidation`` (déclarée ``IsAnyRole``) et
``data-export`` (déclarée ``IsResponsableOrAdmin``) répondaient 403 au
Commercial, au Commercial responsable et au Responsable — le bloc « CA
groupe » de la fiche client restait vide. ``documents`` est inchangé ;
``segments`` est RETIRÉE (ACRM67, D-ACRM-6 (iv)) — son 404 vit dans
``tests_acrm_routes_retirees``.

Rôles réels de ``permissions_registre`` ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
    DIRECTEUR_PERMISSIONS, RESPONSABLE_PERMISSIONS)

User = get_user_model()
CLIENTS = '/api/django/crm/clients/'
ROLES = (
    ('Commercial', COMMERCIAL_PERMISSIONS),
    ('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS),
    ('Responsable', RESPONSABLE_PERMISSIONS),
    ('Directeur', DIRECTEUR_PERMISSIONS),
)


class ClientActionsDeclareesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM21 Solaire', slug='acrm21-declarees')
        self.client_c = Client.objects.create(
            company=self.company, nom='Groupe', prenom='Mere')
        self.users = {}
        for nom, perms in ROLES:
            role = Role.objects.create(
                company=self.company, nom=nom, permissions=list(perms),
                est_systeme=True)
            user = User.objects.create_user(
                username=f'acrm21-{nom.replace(" ", "-").lower()}',
                password='x', company=self.company, role=role)
            self.users[nom] = user
            Lead.objects.create(company=self.company, nom=f'Lead {nom}',
                                owner=user, client=self.client_c)

    def _get(self, nom, suffixe):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.users[nom])}'))
        return api.get(f'{CLIENTS}{self.client_c.pk}/{suffixe}/')

    def test_consolidation_commercial_200(self):
        for nom, _ in ROLES:
            resp = self._get(nom, 'consolidation')
            self.assertEqual(resp.status_code, 200, (nom, resp.content))
            self.assertIn('ca_devis_total', resp.data)

    def test_data_export_palier_responsable_200(self):
        for nom, _ in ROLES:
            resp = self._get(nom, 'data-export')
            self.assertEqual(resp.status_code, 200, (nom, resp.content))
            self.assertEqual(resp.data['identite']['id'], self.client_c.pk)

    def test_documents_inchange(self):
        for nom, _ in ROLES:
            resp = self._get(nom, 'documents')
            self.assertEqual(resp.status_code, 200, (nom, resp.content))
            self.assertEqual(set(resp.data), {'devis', 'factures',
                                              'chantiers'})
