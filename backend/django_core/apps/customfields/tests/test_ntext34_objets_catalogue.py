"""NTEXT34 — catalogue de MODÈLES d'objets personnalisés prêts à l'emploi.

``GET customfields/objets-catalogue/`` liste les objets types avec leurs champs
pré-définis ; ``POST customfields/objets-catalogue/installer/<code>/`` pose
l'objet + ses champs pour la société, sans écrire une ligne de code, et de
façon idempotente.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.customfields.catalogue import CATALOGUE, modele_par_code
from apps.customfields.models import (
    CustomFieldDef, CustomObjectDef, CustomRecord,
)

User = get_user_model()

URL = '/api/django/customfields/objets-catalogue/'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CatalogueObjetsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='NTEXT34 Co')
        self.autre = Company.objects.create(nom='NTEXT34 Autre')
        self.admin = User.objects.create_user(
            username='ntext34_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = _auth(self.admin)

    def test_catalogue_lists_models_with_their_fields(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        modeles = {m['code']: m for m in res.data['modeles']}
        self.assertEqual(len(modeles), len(CATALOGUE))
        pret = modeles['pret-materiel']
        self.assertEqual(len(pret['champs']), 5)
        self.assertFalse(pret['deja_installe'])

    def test_install_creates_object_and_its_fields(self):
        res = self.api.post(f'{URL}installer/pret-materiel/', format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['cree'])
        self.assertEqual(res.data['champs_crees'], 5)
        objet = CustomObjectDef.objects.get(
            company=self.company, code='pret-materiel')
        self.assertEqual(objet.libelle, 'Prêt de matériel')
        codes = set(CustomFieldDef.objects.filter(
            company=self.company, module=objet.field_module
        ).values_list('code', flat=True))
        self.assertEqual(
            codes,
            {c['code'] for c in modele_par_code('pret-materiel')['champs']})

    def test_install_is_idempotent_and_preserves_customisation(self):
        self.api.post(f'{URL}installer/pret-materiel/', format='json')
        objet = CustomObjectDef.objects.get(
            company=self.company, code='pret-materiel')
        champ = CustomFieldDef.objects.get(
            company=self.company, module=objet.field_module, code='materiel')
        champ.libelle = 'Matériel (renommé)'
        champ.save(update_fields=['libelle'])
        CustomRecord.objects.create(
            company=self.company, objet=objet, data={'materiel': 'Échelle'})

        res = self.api.post(f'{URL}installer/pret-materiel/', format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['cree'])
        self.assertEqual(res.data['champs_crees'], 0)
        self.assertEqual(CustomObjectDef.objects.filter(
            company=self.company, code='pret-materiel').count(), 1)
        self.assertEqual(CustomFieldDef.objects.filter(
            company=self.company, module=objet.field_module).count(), 5)
        champ.refresh_from_db()
        self.assertEqual(champ.libelle, 'Matériel (renommé)')
        self.assertEqual(
            CustomRecord.objects.filter(company=self.company).count(), 1)

    def test_install_is_scoped_to_the_requesting_company(self):
        self.api.post(f'{URL}installer/pret-materiel/', format='json')
        self.assertEqual(
            CustomObjectDef.objects.filter(company=self.autre).count(), 0)

    def test_catalogue_flags_already_installed_models(self):
        self.api.post(f'{URL}installer/pret-materiel/', format='json')
        res = self.api.get(URL)
        modeles = {m['code']: m for m in res.data['modeles']}
        self.assertTrue(modeles['pret-materiel']['deja_installe'])
        self.assertFalse(modeles['registre-visiteurs']['deja_installe'])

    def test_unknown_model_is_404(self):
        res = self.api.post(f'{URL}installer/inexistant/', format='json')
        self.assertEqual(res.status_code, 404)

    def test_limited_role_can_read_but_not_install(self):
        limite = User.objects.create_user(
            username='ntext34_normal', password='x', role_legacy='normal',
            company=self.company)
        api = _auth(limite)
        self.assertEqual(api.get(URL).status_code, 200)
        self.assertEqual(
            api.post(f'{URL}installer/pret-materiel/',
                     format='json').status_code, 403)
