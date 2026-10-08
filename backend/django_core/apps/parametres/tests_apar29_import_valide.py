"""APAR29 — l'import de configuration et l'assistant de localisation passent
par les MÊMES validations que ``PATCH /parametres/update/``.

Constat C-APAR-040 : ``config_import`` (``_import_profile``,
``_import_statuts``) et ``onboarding_localisation`` écrivaient par ``setattr``
direct : TVA -5, remise 900 %, libellé de statut de 130 caractères, fuseau
« Mars/Olympus », langue « zz » entraient en base (et une devise de 12
caractères levait un 500). L'import n'était pas tout-ou-rien et ne
journalisait pas ses CRÉATIONS.

Test-du-test : rétablir le ``setattr`` direct dans ``_import_profile`` ⇒
``test_import_valeurs_interdites_400_rien_ecrit`` rouge.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.parametres.models import CompanyProfile, SettingsAuditLog
from apps.parametres.models_statuses import StatutConfig
from apps.parametres.statuses_defaults import default_statuses
from apps.roles.models import Role
from apps.roles.permissions_registre import ADMIN_PERMISSIONS
from authentication.models import Company

IMPORT = '/api/django/parametres/config-import/'
ONBOARDING = '/api/django/parametres/onboarding-localisation/'


class ImportValideTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APAR29', slug='apar29-co')
        role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(ADMIN_PERMISSIONS), est_systeme=True)
        self.admin = get_user_model().objects.create_user(
            username='apar29-admin', password='x', company=self.company,
            role_legacy='admin', role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.profile = CompanyProfile.get(self.company)
        self.profile.tva_standard = Decimal('20')
        self.profile.remise_max_pct = Decimal('15')
        self.profile.save()

    def _relu(self):
        return CompanyProfile.objects.get(pk=self.profile.pk)

    def test_import_valeurs_interdites_400_rien_ecrit(self):
        cles = [c for c, _l, _o in default_statuses('chantier')]
        statuts = [{'domaine': 'chantier', 'cle': c, 'libelle': f'S{i}',
                    'ordre': i, 'actif': True}
                   for i, c in enumerate(cles[:4])]
        statuts.append({'domaine': 'chantier', 'cle': cles[4],
                        'libelle': 'x' * 130, 'ordre': 5, 'actif': True})
        r = self.api.post(f'{IMPORT}?mode=overwrite', {
            'profile': {'tva_standard': '-5', 'remise_max_pct': '900'},
            'statuts': statuts,
            'roles': [{'nom': 'Rôle importé', 'permissions': ['crm_voir'],
                       'est_systeme': False}],
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('statuts[4].libelle', r.data)
        # Tout-ou-rien : AUCUNE écriture, même pas les statuts/rôles valides.
        self.assertFalse(StatutConfig.objects.filter(
            company=self.company).exists())
        self.assertFalse(Role.objects.filter(
            company=self.company, nom='Rôle importé').exists())
        relu = self._relu()
        self.assertEqual(relu.tva_standard, Decimal('20'))
        self.assertEqual(relu.remise_max_pct, Decimal('15'))

    def test_profil_invalide_nomme_chaque_champ(self):
        r = self.api.post(f'{IMPORT}?mode=overwrite', {
            'profile': {'tva_standard': '-5', 'remise_max_pct': '900'},
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('profile.tva_standard', r.data)
        self.assertIn('profile.remise_max_pct', r.data)
        self.assertEqual(self._relu().tva_standard, Decimal('20'))

    def test_import_valide_journalise_ses_creations(self):
        cle = default_statuses('chantier')[0][0]
        r = self.api.post(IMPORT, {
            'roles': [{'nom': 'Rôle importé', 'permissions': ['crm_voir'],
                       'est_systeme': False}],
            'message_templates': [{'cle': 'facture', 'corps_fr': 'Hello'}],
            'statuts': [{'domaine': 'chantier', 'cle': cle,
                         'libelle': 'Importé', 'ordre': 1, 'actif': True}],
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        champs = set(SettingsAuditLog.objects.filter(
            company=self.company, section='config_import').values_list(
            'field', flat=True))
        self.assertIn('role.Rôle importé', champs)
        self.assertIn('message_template.facture', champs)
        self.assertIn(f'statut.chantier.{cle}', champs)

    def test_onboarding_valeurs_invalides_400(self):
        for corps, champ in (
                ({'fuseau_horaire': 'Mars/Olympus'}, 'fuseau_horaire'),
                ({'langue_repli': 'zz'}, 'langue_repli'),
                ({'devise': 'X' * 12}, 'devise_defaut')):
            with self.subTest(champ=champ):
                r = self.api.post(ONBOARDING, dict(corps, pays='MA'),
                                  format='json')
                self.assertEqual(r.status_code, 400, r.data)
                self.assertIn(champ, r.data)
        relu = self._relu()
        self.assertEqual(relu.fuseau_horaire, 'Africa/Casablanca')
        self.assertEqual(relu.langue_repli, 'fr')
        self.assertEqual(relu.devise_defaut, 'MAD')

    def test_onboarding_valide_journalise(self):
        r = self.api.post(ONBOARDING, {'pays': 'MA', 'langue_repli': 'ar'},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(SettingsAuditLog.objects.filter(
            company=self.company, section='localisation',
            field='langue_repli').exists())
