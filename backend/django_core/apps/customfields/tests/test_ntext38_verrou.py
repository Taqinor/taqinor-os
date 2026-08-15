"""NTEXT38 — verrouillage d'un objet / champ personnalisé (anti-casse).

Un champ ou un objet verrouillé ne peut être ni supprimé ni renommé par l'API
tant qu'il n'a pas été explicitement déverrouillé (action admin dédiée), et
chaque bascule du verrou laisse une trace au Journal d'audit des paramètres.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.audit_plateforme import SECTION_PLATEFORME
from apps.customfields.models import CustomFieldDef, CustomObjectDef
from apps.parametres.models import SettingsAuditLog

User = get_user_model()

CHAMPS = '/api/django/custom-fields/definitions/'
OBJETS = '/api/django/custom-fields/objects/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VerrouChampTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT38 Co')
        self.admin = User.objects.create_user(
            username='ntext38_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.admin)
        self.champ = CustomFieldDef.objects.create(
            company=self.company, module='lead', code='origine',
            libelle='Origine', type='text')

    def test_champ_non_verrouille_par_defaut(self):
        self.assertFalse(self.champ.verrouille)
        res = self.api.get(f'{CHAMPS}{self.champ.pk}/')
        self.assertFalse(res.data['verrouille'])

    def test_supprimer_un_champ_verrouille_renvoie_403_francais(self):
        self.api.post(f'{CHAMPS}{self.champ.pk}/verrouiller/', format='json')
        res = self.api.delete(f'{CHAMPS}{self.champ.pk}/')
        self.assertEqual(res.status_code, 403, res.data)
        self.assertIn('verrouillé', str(res.data['detail']))
        self.assertTrue(
            CustomFieldDef.objects.filter(pk=self.champ.pk).exists())

    def test_renommer_un_champ_verrouille_renvoie_403(self):
        self.api.post(f'{CHAMPS}{self.champ.pk}/verrouiller/', format='json')
        res = self.api.patch(f'{CHAMPS}{self.champ.pk}/',
                             {'libelle': 'Origine (renommée)'}, format='json')
        self.assertEqual(res.status_code, 403, res.data)
        self.champ.refresh_from_db()
        self.assertEqual(self.champ.libelle, 'Origine')

    def test_reglages_daffichage_restent_modifiables_meme_verrouille(self):
        self.api.post(f'{CHAMPS}{self.champ.pk}/verrouiller/', format='json')
        res = self.api.patch(f'{CHAMPS}{self.champ.pk}/',
                             {'ordre': 7, 'visible_liste': True},
                             format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.champ.refresh_from_db()
        self.assertEqual(self.champ.ordre, 7)

    def test_deverrouiller_puis_supprimer_reussit_et_est_audite(self):
        self.api.post(f'{CHAMPS}{self.champ.pk}/verrouiller/', format='json')
        res = self.api.post(f'{CHAMPS}{self.champ.pk}/deverrouiller/',
                            format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['verrouille'])

        res = self.api.delete(f'{CHAMPS}{self.champ.pk}/')
        self.assertEqual(res.status_code, 204)
        self.assertFalse(
            CustomFieldDef.objects.filter(pk=self.champ.pk).exists())

        labels = list(SettingsAuditLog.objects.filter(
            company=self.company, section='champs'
        ).values_list('field_label', flat=True))
        self.assertIn('Champ verrouillé', labels)
        self.assertIn('Champ déverrouillé', labels)
        self.assertIn('Champ personnalisé supprimé', labels)

    def test_le_verrou_ne_se_retire_pas_par_un_patch_ordinaire(self):
        self.api.post(f'{CHAMPS}{self.champ.pk}/verrouiller/', format='json')
        self.api.patch(f'{CHAMPS}{self.champ.pk}/', {'verrouille': False},
                       format='json')
        self.champ.refresh_from_db()
        self.assertTrue(self.champ.verrouille)


class VerrouObjetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT38 Obj')
        self.admin = User.objects.create_user(
            username='ntext38_obj', password='x', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.admin)
        self.objet = CustomObjectDef.objects.create(
            company=self.company, code='cles', libelle='Registre de clés')

    def test_objet_verrouille_ne_se_supprime_ni_ne_se_renomme(self):
        self.api.post(f'{OBJETS}{self.objet.pk}/verrouiller/', format='json')

        res = self.api.delete(f'{OBJETS}{self.objet.pk}/')
        self.assertEqual(res.status_code, 403, res.data)

        res = self.api.patch(f'{OBJETS}{self.objet.pk}/',
                             {'libelle': 'Autre'}, format='json')
        self.assertEqual(res.status_code, 403, res.data)

        self.assertTrue(
            CustomObjectDef.objects.filter(pk=self.objet.pk).exists())

    def test_deverrouiller_puis_supprimer_reussit_et_est_audite(self):
        self.api.post(f'{OBJETS}{self.objet.pk}/verrouiller/', format='json')
        self.api.post(f'{OBJETS}{self.objet.pk}/deverrouiller/', format='json')
        res = self.api.delete(f'{OBJETS}{self.objet.pk}/')
        self.assertEqual(res.status_code, 204)

        labels = list(SettingsAuditLog.objects.filter(
            company=self.company, section=SECTION_PLATEFORME
        ).values_list('field_label', flat=True))
        self.assertIn('Objet personnalisé verrouillé', labels)
        self.assertIn('Objet personnalisé déverrouillé', labels)
        self.assertIn('Objet personnalisé supprimé', labels)
