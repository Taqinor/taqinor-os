"""APAR16 — verrou optimiste du profil société (C-APAR-019).

A charge le profil, B change le RIB et enregistre, puis A enregistre un
changement de TVA avec l'``updated_at`` lu au chargement : le serveur répond
409 (« modifié par B »), rien n'est écrit ; le RIB reste celui de B et le
journal ne porte aucune ligne ``rib`` au nom de A. Après rechargement, A
renvoie le seul champ modifié avec le nouvel horodatage : 200.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models import SettingsAuditLog
from apps.parametres.models_company import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

User = get_user_model()
URL_GET = '/api/django/parametres/'
URL_PATCH = '/api/django/parametres/update/'


class VerrouProfilTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR16', slug='apar16')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS), est_systeme=True)
        self.a = User.objects.create_user(
            username='apar16_a', password='x', role=role,
            company=self.company)
        self.b = User.objects.create_user(
            username='apar16_b', password='x', role=role,
            company=self.company, first_name='Bea', last_name='B')
        profil = CompanyProfile.get(company=self.company)
        profil.rib = 'RIB-INITIAL'
        profil.save()

    def _api(self, user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(user))
        return api

    def test_get_expose_updated_at(self):
        r = self._api(self.a).get(URL_GET)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.get('updated_at'))

    def test_ecriture_concurrente_409(self):
        lu_par_a = self._api(self.a).get(URL_GET).data['updated_at']
        r_b = self._api(self.b).patch(URL_PATCH, {
            'rib': 'B-RIB', 'updated_at': lu_par_a}, format='json')
        self.assertEqual(r_b.status_code, 200, r_b.data)

        r_a = self._api(self.a).patch(URL_PATCH, {
            'tva_standard': 14, 'updated_at': lu_par_a}, format='json')
        self.assertEqual(r_a.status_code, 409, r_a.data)
        self.assertIn('Bea B', r_a.data['detail'])
        self.assertIn('recharger', r_a.data['detail'])

        profil = CompanyProfile.objects.get(company=self.company)
        self.assertEqual(profil.rib, 'B-RIB')
        self.assertNotEqual(float(profil.tva_standard), 14.0)
        self.assertFalse(SettingsAuditLog.objects.filter(
            company=self.company, user=self.a).exists())

        # Rechargement puis nouvel enregistrement du SEUL champ modifié.
        relu = self._api(self.a).get(URL_GET).data
        r_a2 = self._api(self.a).patch(URL_PATCH, {
            'tva_standard': 14, 'updated_at': relu['updated_at']},
            format='json')
        self.assertEqual(r_a2.status_code, 200, r_a2.data)
        profil.refresh_from_db()
        self.assertEqual(profil.rib, 'B-RIB')
        self.assertEqual(float(profil.tva_standard), 14.0)
        self.assertFalse(SettingsAuditLog.objects.filter(
            company=self.company, user=self.a, field='rib').exists())
        # L'horodatage renvoyé suit l'écriture (prochain PATCH comparable).
        self.assertNotEqual(r_a2.data['updated_at'], relu['updated_at'])

    def test_sans_updated_at_comportement_historique(self):
        r = self._api(self.a).patch(
            URL_PATCH, {'rib': 'SEUL'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_updated_at_illisible_400(self):
        r = self._api(self.a).patch(
            URL_PATCH, {'rib': 'X', 'updated_at': 'pas une date'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_updated_at_jamais_ecrit_par_le_corps(self):
        r = self._api(self.a).get(URL_GET)
        r2 = self._api(self.a).patch(URL_PATCH, {
            'updated_at': r.data['updated_at']}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertNotIn('updated_at', [
            ligne.field for ligne in SettingsAuditLog.objects.filter(
                company=self.company)])
