"""CIQ114 — charge de toiture : capacité DÉCLARÉE (avec source), plus aucune
capacité « indicative » par type de toit ni coefficient non sourcé.

Remplace ``test_roof_load.py`` (FG253), dont les capacités par type, la masse
forfaitaire et le coefficient 1,1 ont été retirés par CIQ114.
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.ventes.roof_load import (
    MESSAGE_AMIANTE, MESSAGE_NON_DECLAREE, VERDICT_DEPASSEMENT, VERDICT_MARGE,
    VERDICT_NON_DECLAREE, ChargeNonSourcee, verifier_charge_toiture,
)
from authentication.models import Company

User = get_user_model()
URL = '/api/django/ventes/toiture/charge/'
DOSSIER = Path(__file__).resolve().parent.parent


class ChargeToitureModuleTests(SimpleTestCase):
    def test_sans_saisie_non_declaree_sans_nombre(self):
        r = verifier_charge_toiture()
        self.assertEqual(r['verdict'], VERDICT_NON_DECLAREE)
        self.assertEqual(r['message'], MESSAGE_NON_DECLAREE)
        self.assertIsNone(r['capacite_kg_m2'])
        self.assertIsNone(r['marge_kg_m2'])
        self.assertTrue(r['interne'])

    def test_marge_calculee_sans_coefficient(self):
        r = verifier_charge_toiture(
            charge_admissible_kg_m2=25, charge_admissible_source=(
                'Note bureau de contrôle 2026-09'),
            struct_masse_kg_m2=12, poids_module_kg=28, aire_module_m2=3.1)
        self.assertEqual(r['verdict'], VERDICT_MARGE)
        self.assertAlmostEqual(r['masse_ajoutee_kg_m2'], 12 + 28 / 3.1,
                               places=3)
        self.assertAlmostEqual(r['marge_kg_m2'], 25 - (12 + 28 / 3.1),
                               places=3)
        self.assertIsNone(r['coefficient'])
        self.assertNotIn('suffisant', r['message'])

    def test_masse_du_calepinage_prioritaire_et_depassement(self):
        r = verifier_charge_toiture(
            charge_admissible_kg_m2=15, charge_admissible_source='Doc',
            struct_masse_kg_m2=5, poids_module_kg=28, aire_module_m2=3.1,
            masse_layout_kg_m2=40)
        self.assertEqual(r['masse_provenance'], 'lestage du calepinage')
        self.assertEqual(r['verdict'], VERDICT_DEPASSEMENT)

    def test_saisie_sans_source_refusee(self):
        with self.assertRaises(ChargeNonSourcee) as ctx:
            verifier_charge_toiture(charge_admissible_kg_m2=25)
        self.assertEqual(ctx.exception.champ, 'charge_admissible_source')
        with self.assertRaises(ChargeNonSourcee):
            verifier_charge_toiture(charge_admissible_kg_m2=25,
                                    charge_admissible_source='x',
                                    coefficient_securite=1.1)

    def test_fibrociment_alerte_bloquante(self):
        r = verifier_charge_toiture(couverture='fibrociment')
        bloquants = [a for a in r['alertes'] if a['niveau'] == 'bloquant']
        self.assertEqual(bloquants[0]['message'], MESSAGE_AMIANTE)

    def test_aucune_ancienne_constante(self):
        for fichier in ('roof_load.py', 'roof_load_view.py'):
            texte = (DOSSIER / fichier).read_text(encoding='utf-8')
            for interdit in ('DEFAULT_MODULE_KG_M2', 'SAFETY_FACTOR',
                             'ROOF_TYPES', 'capacite_kg_m2": 1'):
                self.assertNotIn(interdit, texte, (fichier, interdit))


class ChargeToitureEndpointTests(TestCase):
    def setUp(self):
        company = Company.objects.create(nom='Acme', slug='ciq114-acme')
        user = User.objects.create_user(
            username='ciq114_u', password='x', role_legacy='responsable',
            company=company)
        self.api = APIClient()
        self.api.force_authenticate(user)

    def test_saisie_sans_source_400_fr(self):
        r = self.api.post(URL, {'charge_admissible_kg_m2': 25}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('charge_admissible_source', r.data)

    def test_sans_saisie_non_declaree(self):
        r = self.api.post(URL, {}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['verdict'], VERDICT_NON_DECLAREE)
        self.assertNotIn('prix', str(r.data))
