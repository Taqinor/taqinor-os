"""ALEC39 (C-ALEC-035) — la photo du toit d'un lead se résout dans la PORTÉE du
rôle, comme la fiche du lead : un Commercial reçoit 404 « Lead introuvable. »
sur le lead d'un collègue (même réponse qu'un lead d'une autre société) ; le
Directeur lit la forme du contrat ``lead_photo_toit.json``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.calepinage.tests.test_lead_photo_toit"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    COMMERCIAL_PERMISSIONS, DIRECTEUR_PERMISSIONS)
from authentication.models import Company

User = get_user_model()
URL = '/api/django/crm/leads/{}/photo-toit/'


class LeadPhotoToitPorteeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ALEC39', slug='alec39-co')

        def compte(nom, permissions):
            role = Role.objects.create(company=self.company, nom=f'{nom} ALEC39',
                                       permissions=list(permissions))
            return User.objects.create_user(
                username=f'alec39-{nom}', password='x', company=self.company,
                role=role)
        self.a = compte('a', COMMERCIAL_PERMISSIONS)
        self.b = compte('b', COMMERCIAL_PERMISSIONS)
        self.directeur = compte('dir', DIRECTEUR_PERMISSIONS)
        self.lead_b = Lead.objects.create(
            company=self.company, nom='Toit de B', owner=self.b,
            telephone='0600000039')

    def _get(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api.get(URL.format(self.lead_b.pk))

    def test_lead_hors_portee_404(self):
        refus = self._get(self.a)
        self.assertEqual(refus.status_code, 404, refus.data)
        self.assertEqual(str(refus.data['detail']), 'Lead introuvable.')
        ok = self._get(self.directeur)
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertEqual(set(ok.data), {'visite_id', 'url', 'texture_calage'})
        self.assertEqual(self._get(self.b).status_code, 200)
