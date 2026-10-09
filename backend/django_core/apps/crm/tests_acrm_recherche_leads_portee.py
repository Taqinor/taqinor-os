"""ACRM30 (C-ACRM-025) — la recherche minimale de leads
(``crm.selectors.rechercher_leads_minimal``) est bornée aux leads VISIBLES
de l'appelant.

Sonde V_VA LSEL-5 : depuis Visites, un Commercial responsable (portée
sous-arbre) trouvait le lead PROBE d'un collègue hors de son sous-arbre —
id, nom et téléphone. Désormais : absent ; un lead de son sous-arbre est
trouvé ; un admin trouve tout.

Rôles réels ; aucun mock.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_RESP_PERMISSIONS, DIRECTEUR_PERMISSIONS)

User = get_user_model()
URL = '/api/django/visites/leads-recherche/'


class RechercheLeadsPorteeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM30 Solaire', slug='acrm30-recherche')
        resp = Role.objects.create(
            company=self.company, nom='Commercial responsable',
            permissions=list(COMMERCIAL_RESP_PERMISSIONS), est_systeme=True)
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.moi = User.objects.create_user(
            username='acrm30-moi', password='x', company=self.company,
            role=resp)
        self.collegue = User.objects.create_user(
            username='acrm30-collegue', password='x', company=self.company,
            role=resp)
        self.admin = User.objects.create_user(
            username='acrm30-admin', password='x', company=self.company,
            role=directeur)
        self.sonde = Lead.objects.create(
            company=self.company, nom='PROBE Collegue', owner=self.collegue,
            telephone='+212661303030')
        self.mien = Lead.objects.create(
            company=self.company, nom='PROBE Moi', owner=self.moi)

    def _ids(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user)}'))
        resp = api.get(URL, {'q': 'PROBE'})
        self.assertEqual(resp.status_code, 200, resp.content)
        return {ligne['id'] for ligne in resp.data['results']}

    def test_hors_portee_absent(self):
        self.assertNotIn(self.sonde.pk, self._ids(self.moi))

    def test_en_portee_trouve(self):
        self.assertIn(self.mien.pk, self._ids(self.moi))

    def test_admin_tout(self):
        self.assertEqual(self._ids(self.admin), {self.sonde.pk, self.mien.pk})
