"""ASEC43 — le brouillon d'automatisation proposé par l'agent exige le même
droit que le viewset canonique des automatisations (``IsAdminRole``), et
aucun compte portail n'atteint les vues agent.

Constat C-ASEC-017 : ``AutomationDraftView`` n'exigeait que
``IsAuthenticated`` — un Viewer et un compte portail créaient une règle.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.automation.models import AutomationRule
from apps.roles.models import Role
from apps.roles.permissions_registre import VIEWER_PERMISSIONS
from authentication.models import Company

User = get_user_model()
URL = '/api/django/agent/actions/automation-draft/'
CORPS = {
    'nom': 'Relance J+2 après devis accepté',
    'trigger_type': 'devis_accepted',
    'trigger_config': {},
    'action_type': 'create_activity',
    'action_config': {'delai_jours': 2},
}


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AutomationDraftDroitsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASEC43', slug='asec43')
        viewer = Role.objects.create(
            company=self.company, nom='Viewer',
            permissions=list(VIEWER_PERMISSIONS), est_systeme=True)
        self.viewer = User.objects.create_user(
            username='asec43_viewer', password='x', role=viewer,
            company=self.company)
        self.portail = User.objects.create_user(
            username='asec43_portail', password='x', role_legacy='admin',
            company=self.company, portee=User.PORTEE_PORTAIL_CLIENT,
            portail_client_id=1)
        self.admin = User.objects.create_user(
            username='asec43_admin', password='x', role_legacy='admin',
            company=self.company)

    def _refus(self, user):
        avant = AutomationRule.objects.count()
        r = _api(user).post(URL, CORPS, format='json')
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(AutomationRule.objects.count(), avant)

    def test_viewer_403(self):
        self._refus(self.viewer)

    def test_portail_403(self):
        self._refus(self.portail)
        # Aucune vue agent n'est atteinte par un compte portail.
        api = _api(self.portail)
        self.assertEqual(api.get('/api/django/agent/actions/').status_code,
                         403)
        self.assertEqual(api.get('/api/django/agent/logs/').status_code, 403)
        self.assertEqual(api.post('/api/django/agent/logs/confirmer/', {},
                                  format='json').status_code, 403)

    def test_admin_201(self):
        r = _api(self.admin).post(URL, CORPS, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        regle = AutomationRule.objects.get(pk=r.data['id'])
        self.assertEqual(regle.company_id, self.company.id)
        self.assertFalse(regle.enabled)
