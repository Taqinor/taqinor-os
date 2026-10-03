"""AGR107 — réglages société du pompage, nullable et SANS valeur par défaut.

Un champ vide est servi ``null`` (jamais un chiffre de repli) ; la société
vient toujours de ``request.user`` (un ``company`` dans le corps est ignoré) ;
la migration est purement additive donc réversible ; les libellés d'audit du
profil nomment les nouveaux champs.
"""
from importlib import import_module

from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import CompanyProfile
from .views_config import PROFILE_CONFIG_FIELDS
from .views_profile import _PROFILE_AUDIT_FIELDS

User = get_user_model()

CHAMPS = (
    'agricole_part_debit_forage_pct',
    'agricole_marge_cable_descente_m',
    'agricole_salissure_supp_pct',
)


def _client(slug):
    company = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})[0]
    user = User.objects.create_user(
        username=f'{slug}_admin', password='x', role_legacy='admin',
        company=company)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return company, api


class ReglagesPompageTests(TestCase):
    def setUp(self):
        self.company, self.api = _client('agr107-a')

    def test_champ_vide_servi_null(self):
        resp = self.api.get('/api/django/parametres/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for champ in CHAMPS:
            self.assertIn(champ, resp.data)
            self.assertIsNone(resp.data[champ], champ)

    def test_patch_puis_vider_renvoie_null(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'agricole_part_debit_forage_pct': '85.5',
             'agricole_marge_cable_descente_m': 3,
             'agricole_salissure_supp_pct': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(str(resp.data['agricole_part_debit_forage_pct']),
                         '85.50')
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'agricole_part_debit_forage_pct': None}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['agricole_part_debit_forage_pct'])
        # Les autres valeurs restent intactes (PATCH partiel).
        self.assertEqual(str(resp.data['agricole_marge_cable_descente_m']),
                         '3.00')

    def test_pourcentage_hors_bornes_refuse(self):
        for champ in ('agricole_part_debit_forage_pct',
                      'agricole_salissure_supp_pct'):
            for valeur in (-1, 150):
                resp = self.api.patch(
                    '/api/django/parametres/update/', {champ: valeur},
                    format='json')
                self.assertEqual(resp.status_code, 400, (champ, valeur))
                self.assertIn(champ, resp.data)

    def test_marge_negative_refusee(self):
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'agricole_marge_cable_descente_m': -2}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('agricole_marge_cable_descente_m', resp.data)

    def test_patch_sur_une_autre_societe_refuse(self):
        autre, _ = _client('agr107-b')
        resp = self.api.patch(
            '/api/django/parametres/update/',
            {'company': autre.pk, 'agricole_salissure_supp_pct': 10},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        profil_autre = CompanyProfile.objects.filter(company=autre).first()
        if profil_autre is not None:
            self.assertIsNone(profil_autre.agricole_salissure_supp_pct)
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertEqual(str(profil.agricole_salissure_supp_pct), '10.00')

    def test_enregistrer_rouvrir_enregistrer_identique(self):
        self.api.patch(
            '/api/django/parametres/update/',
            {'agricole_part_debit_forage_pct': 80}, format='json')
        premier = self.api.get('/api/django/parametres/').data
        corps = {c: premier[c] for c in CHAMPS}
        self.api.patch('/api/django/parametres/update/', corps,
                       format='json')
        second = self.api.get('/api/django/parametres/').data
        self.assertEqual({c: second[c] for c in CHAMPS}, corps)


class ExpositionEtAuditTests(TestCase):
    def test_champs_exportables_et_libelles_audit(self):
        for champ in CHAMPS:
            self.assertIn(champ, PROFILE_CONFIG_FIELDS)
            self.assertIn(champ, _PROFILE_AUDIT_FIELDS)
        self.assertIn('repli', _PROFILE_AUDIT_FIELDS['agricole_pump_hours'])

    def test_migration_additive_donc_reversible(self):
        module = import_module(
            'apps.parametres.migrations.0111_agr107_reglages_pompage')
        ops = module.Migration.operations
        self.assertEqual(len(ops), 3)
        for op in ops:
            self.assertIsInstance(op, migrations.AddField)
            self.assertTrue(op.reversible)
            self.assertTrue(op.field.null)
            self.assertFalse(op.field.has_default())
