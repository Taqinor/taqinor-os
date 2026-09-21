"""NTESG16 — Bibliothèque de facteurs d'émission éditable et versionnée.

Critère d'acceptation : sélectionner un facteur de référence pré-remplit la
ligne sans bloquer une valeur manuelle différente (côté qhse, hors périmètre
de ce lane) ; l'historique de version se consulte.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory

from apps.esg import services
from apps.esg.models import FacteurEmissionReference


class CreerVersionFacteurTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def test_first_version_is_1_and_active(self):
        facteur = services.creer_version_facteur(
            self.company, categorie='Électricité (réseau MA)', unite='kgCO2e/kWh',
            valeur=Decimal('0.718'), source='ADEME Base Carbone générique',
            date_maj=date(2026, 1, 1))
        self.assertEqual(facteur.version, 1)
        self.assertTrue(facteur.actif)

    def test_second_version_increments_and_deactivates_previous(self):
        v1 = services.creer_version_facteur(
            self.company, categorie='Gasoil', unite='kgCO2e/L',
            valeur=Decimal('2.51'), source='ADEME',
            date_maj=date(2025, 1, 1))
        v2 = services.creer_version_facteur(
            self.company, categorie='Gasoil', unite='kgCO2e/L',
            valeur=Decimal('2.55'), source='ADEME (mise à jour 2026)',
            date_maj=date(2026, 1, 1))
        v1.refresh_from_db()
        self.assertEqual(v2.version, 2)
        self.assertTrue(v2.actif)
        self.assertFalse(v1.actif)
        # L'ancienne version reste en base (jamais supprimée).
        self.assertEqual(
            FacteurEmissionReference.objects.filter(
                company=self.company, categorie='Gasoil', unite='kgCO2e/L'
            ).count(), 2)

    def test_version_numbering_never_regresses_after_deactivation(self):
        """ARC6 — max(version)+1, jamais count()+1 : une éventuelle
        suppression manuelle d'une version intermédiaire ne doit jamais
        faire réutiliser un numéro de version déjà attribué."""
        services.creer_version_facteur(
            self.company, categorie='Essence', unite='kgCO2e/L',
            valeur=Decimal('2.28'), source='ADEME', date_maj=date(2024, 1, 1))
        v2 = services.creer_version_facteur(
            self.company, categorie='Essence', unite='kgCO2e/L',
            valeur=Decimal('2.30'), source='ADEME', date_maj=date(2025, 1, 1))
        v2.delete()
        v3 = services.creer_version_facteur(
            self.company, categorie='Essence', unite='kgCO2e/L',
            valeur=Decimal('2.32'), source='ADEME', date_maj=date(2026, 1, 1))
        self.assertEqual(v3.version, 3)

    def test_different_categorie_or_unite_gets_own_version_1(self):
        services.creer_version_facteur(
            self.company, categorie='Gasoil', unite='kgCO2e/L',
            valeur=Decimal('2.51'), source='ADEME', date_maj=date(2025, 1, 1))
        autre = services.creer_version_facteur(
            self.company, categorie='Gasoil', unite='litres/km',
            valeur=Decimal('0.08'), source='ADEME', date_maj=date(2025, 1, 1))
        self.assertEqual(autre.version, 1)


class FacteurEmissionReferenceApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/facteurs-emission/'

    def test_create_forces_company_and_starts_at_version_1(self):
        r = self.client_as().post(
            self.BASE,
            {'categorie': 'Électricité', 'unite': 'kgCO2e/kWh',
             'valeur': '0.718', 'source': 'ADEME',
             'date_maj': '2026-01-01'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        facteur = FacteurEmissionReference.objects.get(id=r.data['id'])
        self.assertEqual(facteur.company_id, self.company.id)
        self.assertEqual(facteur.version, 1)
        self.assertTrue(facteur.actif)

    def test_repost_same_categorie_unite_creates_new_active_version(self):
        self.client_as().post(
            self.BASE,
            {'categorie': 'Gasoil', 'unite': 'kgCO2e/L', 'valeur': '2.51',
             'source': 'ADEME', 'date_maj': '2025-01-01'}, format='json')
        r2 = self.client_as().post(
            self.BASE,
            {'categorie': 'Gasoil', 'unite': 'kgCO2e/L', 'valeur': '2.55',
             'source': 'ADEME 2026', 'date_maj': '2026-01-01'}, format='json')
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertEqual(r2.data['version'], 2)
        actifs = FacteurEmissionReference.objects.filter(
            company=self.company, categorie='Gasoil', unite='kgCO2e/L',
            actif=True)
        self.assertEqual(actifs.count(), 1)
        self.assertEqual(actifs.first().version, 2)

    def test_patch_not_allowed(self):
        facteur = FacteurEmissionReference.objects.create(
            company=self.company, categorie='Gasoil', unite='kgCO2e/L',
            valeur=Decimal('2.51'), source='ADEME', date_maj=date(2025, 1, 1))
        r = self.client_as().patch(
            f'{self.BASE}{facteur.id}/', {'valeur': '9.99'}, format='json')
        self.assertEqual(r.status_code, 405)

    def test_historique_requires_both_params(self):
        r = self.client_as().get(f'{self.BASE}historique/')
        self.assertEqual(r.status_code, 400)

    def test_historique_returns_all_versions_ordered_desc(self):
        self.client_as().post(
            self.BASE,
            {'categorie': 'Gasoil', 'unite': 'kgCO2e/L', 'valeur': '2.51',
             'source': 'ADEME', 'date_maj': '2025-01-01'}, format='json')
        self.client_as().post(
            self.BASE,
            {'categorie': 'Gasoil', 'unite': 'kgCO2e/L', 'valeur': '2.55',
             'source': 'ADEME 2026', 'date_maj': '2026-01-01'}, format='json')
        r = self.client_as().get(
            f'{self.BASE}historique/',
            {'categorie': 'Gasoil', 'unite': 'kgCO2e/L'})
        self.assertEqual(r.status_code, 200, r.content)
        versions = [row['version'] for row in r.data]
        self.assertEqual(versions, [2, 1])

    def test_cross_tenant_isolation(self):
        foreign = FacteurEmissionReference.objects.create(
            company=self.other_company, categorie='Gasoil', unite='kgCO2e/L',
            valeur=Decimal('2.51'), source='ADEME', date_maj=date(2025, 1, 1))
        r = self.client_as().get(f'{self.BASE}{foreign.id}/')
        self.assertIn(r.status_code, (403, 404))
