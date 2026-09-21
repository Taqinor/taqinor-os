"""SOLMVP52 — Semis et démo, sans les 47 apps sorties du MVP solaire.

Preuve que le chemin de tenant-creation (`appliquer_gabarit_solaire`) reste
vert avec les 47 apps réduites à des coquilles de migrations : la société
obtient bien sa structure de catalogue + son tableau de bord + son plan de
licence, et ce plan ne liste JAMAIS une app parquée comme installable (le vrai
bug que corrige SOLMVP52 dans `apps.adminops.plan_seeds`).
"""
from django.test import TestCase

from apps.adminops.plan_seeds import modules_du_plan_solaire
from apps.parametres.models import CompanyProfile
from apps.reporting.models import DashboardConfig
from apps.stock.models import Categorie
from authentication.models import Company
from authentication.tenant_templates import (
    CARTES_SOLAIRES, appliquer_gabarit_solaire,
)
from core.parked import APPS_PARQUEES


class GabaritSolaireSansModulesSortisTests(TestCase):
    """Sur une société NEUVE, le gabarit compose l'existant sans exception,
    même avec les 47 apps réduites à des coquilles de migrations."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Installateur SOLMVP52', slug='solmvp52-ma')

    def test_aucune_exception_bout_en_bout(self):
        rapport = appliquer_gabarit_solaire(self.company)
        for etape in ('plan', 'roles', 'catalogue', 'dashboard'):
            self.assertIn(etape, rapport)
            valeur = rapport[etape]
            self.assertFalse(
                isinstance(valeur, str) and valeur.startswith('erreur:'),
                f'étape « {etape} » en échec : {valeur}')

    def test_structure_catalogue_et_dashboard_poses(self):
        appliquer_gabarit_solaire(self.company)
        self.assertTrue(
            Categorie.objects.filter(company=self.company).exists())
        configs = set(
            DashboardConfig.objects
            .filter(company=self.company, user=None)
            .values_list('menu_tier', flat=True))
        self.assertEqual(configs, set(CARTES_SOLAIRES))

    def test_plan_assigne_et_sans_app_parquee(self):
        appliquer_gabarit_solaire(self.company)
        profil = CompanyProfile.objects.get(company=self.company)
        self.assertIsNotNone(profil.plan)
        modules = set(profil.plan.modules_inclus or [])
        # Le vrai point de SOLMVP52 : une coquille garde son manifeste
        # (contrat de coquille, core/parked.py) mais ne doit JAMAIS revenir
        # dans un plan de licence vendu.
        self.assertEqual(modules & set(APPS_PARQUEES), set())

    def test_aucun_manifeste_parque_liste_installable(self):
        """Même vérification, directement sur la source dérivée par le
        plan_seeder (pas seulement sur le plan déjà assigné)."""
        inclus = set(modules_du_plan_solaire())
        self.assertEqual(inclus & set(APPS_PARQUEES), set())

    def test_idempotent(self):
        appliquer_gabarit_solaire(self.company)
        avant = Categorie.objects.filter(company=self.company).count()
        rapport = appliquer_gabarit_solaire(self.company)
        apres = Categorie.objects.filter(company=self.company).count()
        self.assertEqual(avant, apres)
        self.assertEqual(rapport['catalogue']['categories'], [])
