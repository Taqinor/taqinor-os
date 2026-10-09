"""ACAL249 — le GET d'un lead publie son repère toit unique
(``repere_toit`` : pin, source, contour_utilisable) calculé par
``crm.selectors.repere_toit`` (QJR598), en lecture seule.

NB : le chemin ``apps/crm/tests/test_acal_repere_toit_lead.py`` du texte de
la tâche est impossible (``apps/crm/tests.py`` est un MODULE : un paquet
``tests/`` homonyme le masquerait) — même contenu, au patron
``apps/crm/tests_*.py``.

Test-du-test : faire primer ``roof_point`` sur le GPS dans la méthode du
sérialiseur ⇒ source 'roof_point' ⇒ test_get_lead_publie_repere_gps_corrige
échoue ; retirer le champ ⇒ KeyError.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead

User = get_user_model()

#: A = Casablanca (épingle du tunnel), B = Marrakech (GPS corrigé, hors R).
A = {'lat': 33.5731, 'lng': -7.5898}
B = {'lat': 31.6295, 'lng': -7.9811}
_D = 0.001
#: Contour du toit au format du webhook : sommets ``[lat, lng]``.
CARRE_R = [
    [A['lat'] - _D, A['lng'] - _D], [A['lat'] - _D, A['lng'] + _D],
    [A['lat'] + _D, A['lng'] + _D], [A['lat'] + _D, A['lng'] - _D],
]


class RepereToitLeadTests(TestCase):

    def setUp(self):
        from apps.roles.models import Role
        from apps.roles.permissions_registre import ADMIN_PERMISSIONS
        self.company = Company.objects.create(
            nom='ACAL249 Solaire', slug='acal249-repere')
        role, _ = Role.objects.get_or_create(
            company=self.company, nom='Administrateur',
            defaults={'permissions': ADMIN_PERMISSIONS, 'est_systeme': True})
        self.user = User.objects.create_user(
            username='acal249-admin', password='x', company=self.company,
            role=role, role_legacy='admin')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _get(self, lead):
        resp = self.api.get(f'/api/django/crm/leads/{lead.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['repere_toit']

    def test_get_lead_publie_repere_gps_corrige(self):
        from apps.crm.selectors import repere_toit
        lead = Lead.objects.create(
            company=self.company, nom='Toit', owner=self.user,
            roof_point=dict(A), roof_outline=CARRE_R,
            gps_lat=Decimal(str(B['lat'])), gps_lng=Decimal(str(B['lng'])))
        rendu = self._get(lead)
        self.assertEqual(rendu['source'], 'gps')
        self.assertFalse(rendu['contour_utilisable'])
        self.assertAlmostEqual(float(rendu['pin']['lat']), B['lat'], 4)
        self.assertAlmostEqual(float(rendu['pin']['lng']), B['lng'], 4)
        # Jamais recopié : la même valeur que le sélecteur.
        pin, source, utilisable = repere_toit(lead)
        self.assertEqual(rendu, {'pin': pin, 'source': source,
                                 'contour_utilisable': utilisable})

    def test_lead_sans_repere(self):
        lead = Lead.objects.create(
            company=self.company, nom='Rien', owner=self.user)
        self.assertEqual(self._get(lead), {
            'pin': None, 'source': None, 'contour_utilisable': False})

    def test_patch_repere_ignore(self):
        lead = Lead.objects.create(
            company=self.company, nom='Toit', owner=self.user,
            roof_point=dict(A), roof_outline=CARRE_R)
        avant = self._get(lead)
        self.assertEqual(avant['source'], 'roof_point')
        resp = self.api.patch(
            f'/api/django/crm/leads/{lead.pk}/',
            {'repere_toit': {'pin': B, 'source': 'gps',
                             'contour_utilisable': False},
             'ville': 'Casablanca'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self._get(lead), avant)
