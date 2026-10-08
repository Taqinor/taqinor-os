"""ASEC32 — intervention et chantier : FK inscriptibles bornées à la société,
champs posés par le serveur figés.

Constat C-ASEC-005 site (f) + C-ASEC-009 volet chantier : l'intervention
acceptait un technicien / une équipe d'une AUTRE société et laissait PATCHer
sa signature client ; le chantier acceptait un ``technicien_responsable``
étranger et un PATCH de son ``etape`` (posée par les transitions AUD305/CH2).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Intervention
from apps.installations.models_chantier import StageModele
from apps.installations.models_equipe import Equipe
from authentication.models import Company

User = get_user_model()
BASE = '/api/django/installations'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class InterventionInstallationTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC32 A', slug='asec32-a')
        self.b = Company.objects.create(nom='ASEC32 B', slug='asec32-b')
        self.admin = User.objects.create_user(
            username='asec32_admin', password='x', role_legacy='admin',
            company=self.a)
        self.tech_a = User.objects.create_user(
            username='asec32_tech_a', password='x', role_legacy='normal',
            company=self.a)
        self.tech_b = User.objects.create_user(
            username='asec32_tech_b_secret', password='x',
            role_legacy='normal', company=self.b)
        self.equipe_a = Equipe.objects.create(company=self.a, nom='Équipe A')
        self.equipe_b = Equipe.objects.create(company=self.b, nom='Équipe B')
        client = Client.objects.create(company=self.a, nom='Client A')
        self.inst = Installation.objects.create(
            company=self.a, reference='CHT-ASEC32', client=client)
        self.interv = Intervention.objects.create(
            company=self.a, installation=self.inst)
        self.api = _api(self.admin)

    def _patch_interv(self, corps):
        return self.api.patch(
            f'{BASE}/interventions/{self.interv.pk}/', corps, format='json')

    def test_technicien_etranger_400(self):
        r = self._patch_interv({'technicien': self.tech_b.pk})
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('technicien', r.data)
        self.assertNotIn('secret', str(r.data))
        self.interv.refresh_from_db()
        self.assertIsNone(self.interv.technicien_id)
        r2 = self.api.post(f'{BASE}/interventions/', {
            'installation': self.inst.pk, 'technicien': self.tech_b.pk},
            format='json')
        self.assertEqual(r2.status_code, 400, r2.content)

    def test_equipe_etrangere_400(self):
        r = self._patch_interv({'equipe_ref': self.equipe_b.pk})
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('equipe_ref', r.data)
        r2 = self._patch_interv({'equipe': [self.tech_b.pk]})
        self.assertEqual(r2.status_code, 400, r2.content)
        self.assertIn('equipe', r2.data)
        self.interv.refresh_from_db()
        self.assertIsNone(self.interv.equipe_ref_id)
        self.assertFalse(self.interv.equipe.filter(pk=self.tech_b.pk).exists())

    def test_technicien_responsable_etranger_400(self):
        r = self.api.patch(f'{BASE}/chantiers/{self.inst.pk}/',
                           {'technicien_responsable': self.tech_b.pk},
                           format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('technicien_responsable', r.data)
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.technicien_responsable_id)

    def test_signature_non_posable_par_patch(self):
        r = self._patch_interv({
            'signature_client': 'data:image/png;base64,AAAA',
            'signataire_nom': 'Pirate', 'signe_le': '2026-10-07T10:00:00Z'})
        self.assertEqual(r.status_code, 200, r.content)
        self.interv.refresh_from_db()
        self.assertFalse(self.interv.signature_client)
        self.assertFalse(self.interv.signataire_nom)
        self.assertIsNone(self.interv.signe_le)

    def test_etape_non_posable_par_patch(self):
        etape = StageModele.objects.create(
            company=self.a, cle='remise', libelle='Remise client', ordre=9)
        r = self.api.patch(f'{BASE}/chantiers/{self.inst.pk}/',
                           {'etape': etape.pk}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.etape_id)

    def test_ids_societe_ok(self):
        r = self._patch_interv({
            'technicien': self.tech_a.pk, 'equipe_ref': self.equipe_a.pk,
            'equipe': [self.tech_a.pk]})
        self.assertEqual(r.status_code, 200, r.content)
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.technicien_id, self.tech_a.pk)
        self.assertEqual(self.interv.equipe_ref_id, self.equipe_a.pk)
        r2 = self.api.patch(f'{BASE}/chantiers/{self.inst.pk}/',
                            {'technicien_responsable': self.tech_a.pk},
                            format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
