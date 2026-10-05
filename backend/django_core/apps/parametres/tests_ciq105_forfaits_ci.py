"""CIQ105 — réglages société C&I SANS défaut : forfaits des prestations C&I
et bande interne de contrôle du prix au kWc.

Champ vide servi ``{}`` / ``null`` ; un montant sans ``source`` est refusé
(400 FR nommant le champ) ; la société vient toujours de ``request.user`` ;
migration additive donc réversible ; libellés d'audit à jour.
"""
from importlib import import_module

from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import CompanyProfile
from .serializers_company import FORFAITS_CI_PRESTATIONS
from .views_profile import _PROFILE_AUDIT_FIELDS

User = get_user_model()

URL_GET = '/api/django/parametres/'
URL_PATCH = '/api/django/parametres/update/'


def _client(slug):
    company = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})[0]
    user = User.objects.create_user(
        username=f'{slug}_admin', password='x', role_legacy='admin',
        company=company)
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return company, api


FORFAIT_POSE = {
    'fixe_ht': '5000', 'par_kwc_ht': '120.5', 'par_panneau_ht': None,
    'source': 'Devis sous-traitant pose 2026-09', 'date': '2026-09-15',
}


class ForfaitsCiTests(TestCase):
    def setUp(self):
        self.company, self.api = _client('ciq105-a')

    def test_champs_vides_servis_objet_vide_et_null(self):
        resp = self.api.get(URL_GET)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['forfaits_ci'], {})
        self.assertIsNone(resp.data['bande_prix_kwc_ci'])

    def test_saisie_sourcee_acceptee_et_normalisee(self):
        resp = self.api.patch(
            URL_PATCH, {'forfaits_ci': {'pose_modules': FORFAIT_POSE}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        entree = resp.data['forfaits_ci']['pose_modules']
        self.assertEqual(entree['fixe_ht'], '5000')
        self.assertEqual(entree['par_kwc_ht'], '120.5')
        self.assertIsNone(entree['par_panneau_ht'])
        self.assertEqual(entree['source'], FORFAIT_POSE['source'])
        # aucune autre prestation inventée : « prix à renseigner »
        self.assertEqual(set(resp.data['forfaits_ci']), {'pose_modules'})

    def test_saisie_sans_source_400_fr_nommant_le_champ(self):
        resp = self.api.patch(
            URL_PATCH,
            {'forfaits_ci': {'pose_modules': {'fixe_ht': '5000'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('forfaits_ci', resp.data)
        self.assertIn('source', str(resp.data['forfaits_ci']))
        resp = self.api.patch(
            URL_PATCH, {'bande_prix_kwc_ci': {'min_ht': 4000, 'max_ht': 6000}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('bande_prix_kwc_ci', resp.data)

    def test_prestation_inconnue_et_montant_negatif_refuses(self):
        resp = self.api.patch(
            URL_PATCH, {'forfaits_ci': {'installation': FORFAIT_POSE}},
            format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.api.patch(
            URL_PATCH,
            {'forfaits_ci': {'pose_modules': {**FORFAIT_POSE,
                                              'fixe_ht': '-1'}}},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_bande_min_superieur_max_refusee(self):
        resp = self.api.patch(URL_PATCH, {'bande_prix_kwc_ci': {
            'min_ht': 7000, 'max_ht': 6000, 'source': 'Trois offres',
            'date': None}}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_ligne_videe_retiree(self):
        self.api.patch(URL_PATCH, {'forfaits_ci': {'pose_modules':
                                                   FORFAIT_POSE}},
                       format='json')
        resp = self.api.patch(URL_PATCH, {'forfaits_ci': {'pose_modules': {
            'fixe_ht': '', 'par_kwc_ht': None, 'par_panneau_ht': None,
            'source': '', 'date': None}}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['forfaits_ci'], {})

    def test_patch_sur_une_autre_societe_refuse(self):
        autre, _ = _client('ciq105-b')
        resp = self.api.patch(
            URL_PATCH, {'company': autre.pk,
                        'forfaits_ci': {'transport_ci': FORFAIT_POSE}},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        profil_autre = CompanyProfile.objects.filter(company=autre).first()
        if profil_autre is not None:
            self.assertEqual(profil_autre.forfaits_ci, {})
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertIn('transport_ci', profil.forfaits_ci)

    def test_enregistrer_rouvrir_enregistrer_identique(self):
        self.api.patch(URL_PATCH, {
            'forfaits_ci': {'pose_modules': FORFAIT_POSE},
            'bande_prix_kwc_ci': {'min_ht': '4000', 'max_ht': '6000',
                                  'source': 'Trois offres réelles',
                                  'date': '2026-10-01'}}, format='json')
        premier = self.api.get(URL_GET).data
        corps = {c: premier[c] for c in ('forfaits_ci', 'bande_prix_kwc_ci')}
        self.api.patch(URL_PATCH, corps, format='json')
        second = self.api.get(URL_GET).data
        self.assertEqual(
            {c: second[c] for c in ('forfaits_ci', 'bande_prix_kwc_ci')},
            corps)


class ExpositionEtAuditTests(TestCase):
    def test_prestations_sont_des_roles_ci(self):
        from core.product_roles import ROLES_CI
        for prestation in FORFAITS_CI_PRESTATIONS:
            self.assertIn(prestation, ROLES_CI)

    def test_libelles_audit(self):
        self.assertIn('C&I', _PROFILE_AUDIT_FIELDS['forfaits_ci'])
        self.assertIn('jamais imprimé',
                      _PROFILE_AUDIT_FIELDS['bande_prix_kwc_ci'])

    def test_migration_additive_donc_reversible(self):
        module = import_module(
            'apps.parametres.migrations.0117_ciq105_forfaits_ci')
        ops = module.Migration.operations
        self.assertEqual(len(ops), 2)
        for op in ops:
            self.assertIsInstance(op, migrations.AddField)
            self.assertTrue(op.reversible)
