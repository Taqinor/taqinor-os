"""NTESG7 — Objectifs de trajectoire ESG : interpolation linéaire vs réalisé.

Critère d'acceptation : un objectif avec 3 années de données réelles calcule
l'écart correct par rapport à la trajectoire linéaire ; jamais d'extrapolation
au-delà des données réelles disponibles (elles n'existent simplement pas dans
la structure — champ `reel=None`).
"""
from django.test import TestCase

from testkit.base import TenantAPITestCase
from testkit.factories import CompanyFactory

from apps.esg.models import ObjectifESGTrajectoire
from apps.esg.selectors import trajectoire_vs_realise


class TrajectoireVsRealiseTests(TestCase):
    def setUp(self):
        self.company = CompanyFactory()

    def _seed_indicateur(self, code, annee, valeur):
        from apps.qhse.models import IndicateurESG

        IndicateurESG.objects.create(
            company=self.company, code=code, libelle='Émissions',
            pilier=IndicateurESG.Pilier.ENVIRONNEMENT, valeur=valeur,
            annee=annee)

    def test_linear_interpolation_matches_expected_values(self):
        objectif = ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E5',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        resultat = trajectoire_vs_realise(objectif)
        theoriques = {r['annee']: r['theorique'] for r in resultat}
        # 100 → 50 sur 4 ans : -12.5/an.
        self.assertEqual(theoriques[2024], 100.0)
        self.assertEqual(theoriques[2026], 75.0)
        self.assertEqual(theoriques[2028], 50.0)

    def test_ecart_correct_with_three_years_of_real_data(self):
        objectif = ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E5',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        self._seed_indicateur('E5', 2024, 100)
        self._seed_indicateur('E5', 2025, 90)
        self._seed_indicateur('E5', 2026, 60)  # mieux que la trajectoire.
        resultat = trajectoire_vs_realise(objectif)
        by_year = {r['annee']: r for r in resultat}

        self.assertEqual(by_year[2024]['reel'], 100.0)
        self.assertEqual(by_year[2024]['ecart_pct'], 0.0)

        # théorique 2025 = 87.5, réel 90 → +2.86 % (moins bon).
        self.assertAlmostEqual(by_year[2025]['ecart_pct'], 2.86, places=1)

        # théorique 2026 = 75, réel 60 → -20 % (meilleur, en baisse favorable).
        self.assertEqual(by_year[2026]['ecart_pct'], -20.0)

        # 2027/2028 : aucune donnée réelle saisie → jamais extrapolé.
        self.assertIsNone(by_year[2027]['reel'])
        self.assertIsNone(by_year[2027]['ecart_pct'])
        self.assertIsNone(by_year[2028]['reel'])
        self.assertIsNone(by_year[2028]['ecart_pct'])

    def test_no_real_data_returns_none_for_every_year(self):
        objectif = ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E5',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2026)
        resultat = trajectoire_vs_realise(objectif)
        self.assertTrue(all(r['reel'] is None for r in resultat))
        self.assertTrue(all(r['ecart_pct'] is None for r in resultat))


class ObjectifESGTrajectoireApiTests(TenantAPITestCase):
    BASE = '/api/django/esg/objectifs-esg/'

    def test_create_forces_company_server_side(self):
        r = self.client_as().post(
            self.BASE,
            {'indicateur_code': 'E5', 'valeur_reference': 100,
             'annee_reference': 2024, 'valeur_cible': 50,
             'annee_cible': 2028}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        objectif = ObjectifESGTrajectoire.objects.get(id=r.data['id'])
        self.assertEqual(objectif.company_id, self.company.id)

    def test_duplicate_actif_objectif_refused(self):
        ObjectifESGTrajectoire.objects.create(
            company=self.company, indicateur_code='E5',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        r = self.client_as().post(
            self.BASE,
            {'indicateur_code': 'E5', 'valeur_reference': 90,
             'annee_reference': 2025, 'valeur_cible': 40,
             'annee_cible': 2028}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_annee_cible_must_be_after_reference(self):
        r = self.client_as().post(
            self.BASE,
            {'indicateur_code': 'E5', 'valeur_reference': 100,
             'annee_reference': 2028, 'valeur_cible': 50,
             'annee_cible': 2024}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_cross_tenant_isolation(self):
        foreign = ObjectifESGTrajectoire.objects.create(
            company=self.other_company, indicateur_code='E5',
            valeur_reference=100, annee_reference=2024,
            valeur_cible=50, annee_cible=2028)
        r = self.client_as().get(f'{self.BASE}{foreign.id}/')
        self.assertIn(r.status_code, (403, 404))
