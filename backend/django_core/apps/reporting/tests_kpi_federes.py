"""ARC40 — endpoint KPI fédéré piloté par le registre plateforme.

Couvre : (1) les 3 providers pilotes (rh, compta, gestion_projet) renvoient
des tuiles normalisées agrégées par ``reports/kpi-federes/`` ; (2) le scope
société (les données d'une autre société ne comptent jamais) ; (3) le gatage
``ModuleToggle`` (module OFF ⇒ ses tuiles disparaissent) ; (4) un provider
déclaré par manifeste apparaît SANS toucher apps/reporting ; (5) une clé
héritée non-dotted (``crm_sales_report``) est ignorée sans erreur.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ModuleToggle

User = get_user_model()

URL = '/api/django/reporting/reports/kpi-federes/'


def fake_kpi_provider(company):
    """Provider fictif pour le test « déclaré ⇒ apparaît sans toucher
    reporting » (référencé en dotted par un manifeste simulé)."""
    return [{'id': 'fake_arc40', 'label': 'Tuile fictive ARC40', 'valeur': 42}]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class KpiFederesTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='arc40-kpi', defaults={'nom': 'ARC40 KPI Co'})[0]
        self.other = Company.objects.create(slug='arc40-other', nom='Autre')
        self.user = User.objects.create_user(
            username='arc40_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    # ── Fixtures métier minimales ─────────────────────────────────────────

    def _seed_rh(self):
        from apps.rh.models import DemandeConge, DossierEmploye, TypeAbsence
        emp = DossierEmploye.objects.create(
            company=self.company, matricule='ARC40-1', nom='Alaoui',
            prenom='Sara')  # statut par défaut : actif
        DossierEmploye.objects.create(
            company=self.company, matricule='ARC40-2', nom='Sorti',
            prenom='Omar', statut=DossierEmploye.Statut.SORTI)
        # Employé d'une AUTRE société — ne doit jamais compter.
        DossierEmploye.objects.create(
            company=self.other, matricule='ARC40-X', nom='Externe',
            prenom='N')
        type_conge = TypeAbsence.objects.create(
            company=self.company, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True, deduit_solde=True, remunere=True)
        DemandeConge.objects.create(
            company=self.company, employe=emp, type_absence=type_conge,
            date_debut=date.today() - timedelta(days=1),
            date_fin=date.today() + timedelta(days=2),
            statut=DemandeConge.Statut.VALIDEE)

    def _seed_compta(self):
        from apps.compta.models import Effet
        today = date.today()
        # À échoir dans 15 jours (ouvert) → compte dans « 30 j ».
        Effet.objects.create(
            company=self.company, sens=Effet.Sens.RECEVOIR,
            montant=Decimal('1000'), date_emission=today,
            date_echeance=today + timedelta(days=15))
        # Échu depuis 5 jours (ouvert) → compte dans « dépassées ».
        Effet.objects.create(
            company=self.company, sens=Effet.Sens.PAYER,
            montant=Decimal('500'), date_emission=today - timedelta(days=40),
            date_echeance=today - timedelta(days=5))
        # Encaissé (soldé) → ne compte nulle part.
        Effet.objects.create(
            company=self.company, sens=Effet.Sens.RECEVOIR,
            montant=Decimal('700'), date_emission=today - timedelta(days=40),
            date_echeance=today - timedelta(days=10),
            statut=Effet.Statut.ENCAISSE)

    def _seed_projets(self):
        from apps.gestion_projet.models import Projet
        Projet.objects.create(
            company=self.company, code='PRJ-A', nom='Centrale A',
            statut=Projet.Statut.EN_COURS)
        Projet.objects.create(
            company=self.company, code='PRJ-B', nom='Centrale B',
            statut=Projet.Statut.EN_COURS)
        Projet.objects.create(
            company=self.company, code='PRJ-C', nom='Centrale C',
            statut=Projet.Statut.TERMINE)

    def _tiles_by_id(self, resp):
        return {t['id']: t for t in resp.data['tuiles']}


class TestThreeProviders(KpiFederesTestCase):
    def test_three_pilot_providers_return_normalized_tiles(self):
        self._seed_rh()
        self._seed_compta()
        self._seed_projets()
        resp = self.api.get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        tuiles = self._tiles_by_id(resp)

        # rh — effectif actif (1 actif, le sorti et l'externe exclus).
        self.assertEqual(tuiles['rh_effectif_actif']['valeur'], 1)
        # rh — absence validée couvrant aujourd'hui.
        self.assertEqual(tuiles['rh_absences_en_cours']['valeur'], 1)
        # compta — échéances.
        self.assertEqual(tuiles['compta_echeances_30j']['valeur'], 1)
        self.assertEqual(tuiles['compta_echeances_depassees']['valeur'], 1)
        # gestion_projet — répartition par statut.
        self.assertEqual(tuiles['projets_en_cours']['valeur'], 2)
        self.assertEqual(tuiles['projets_termine']['valeur'], 1)

        # Forme normalisée : id/label/valeur (+ provider posé par l'endpoint).
        for t in resp.data['tuiles']:
            for cle in ('id', 'label', 'valeur', 'provider'):
                self.assertIn(cle, t)
            # Un provider est toujours un dotted résoluble — la clé héritée
            # non-dotted 'crm_sales_report' (manifeste crm) est ignorée.
            self.assertIn('.', t['provider'])

    def test_company_scoping_is_absolute(self):
        """Les données d'une autre société n'alimentent JAMAIS les tuiles."""
        from apps.gestion_projet.models import Projet
        Projet.objects.create(
            company=self.other, code='PRJ-EXT', nom='Externe',
            statut=Projet.Statut.EN_COURS)
        resp = self.api.get(URL)
        tuiles = self._tiles_by_id(resp)
        # Aucun projet dans NOTRE société → aucune tuile projets.
        self.assertNotIn('projets_en_cours', tuiles)


class TestToggleGating(KpiFederesTestCase):
    def test_module_off_drops_its_tiles(self):
        self._seed_rh()
        self._seed_compta()
        ModuleToggle.objects.create(
            company=self.company, module='rh', actif=False)
        resp = self.api.get(URL)
        tuiles = self._tiles_by_id(resp)
        self.assertNotIn('rh_effectif_actif', tuiles)
        self.assertNotIn('rh_absences_en_cours', tuiles)
        # compta reste visible.
        self.assertIn('compta_echeances_30j', tuiles)


class TestRegistryDriven(KpiFederesTestCase):
    def test_declared_provider_appears_without_touching_reporting(self):
        """Un provider déclaré par un manifeste fictif (dotted vers une
        fonction de CE module de test) apparaît dans l'endpoint fédéré sans
        aucune modification d'apps/reporting."""
        from core import platform as core_platform

        vrais = core_platform.collect_platform_manifests()
        faux = dict(vrais)
        faux['module_fictif_arc40'] = {
            'module': 'module_fictif_arc40',
            'kpi_providers': [
                'apps.reporting.tests_kpi_federes.fake_kpi_provider'],
            'record_targets': [], 'searchable_models': [],
            'customfield_models': [], 'import_specs': [],
            'agent_actions_module': '', 'automation_state_fields': [],
        }

        with mock.patch(
                'core.platform.collect_platform_manifests',
                side_effect=lambda: faux):
            resp = self.api.get(URL)
        tuiles = self._tiles_by_id(resp)
        self.assertIn('fake_arc40', tuiles)
        self.assertEqual(tuiles['fake_arc40']['valeur'], 42)

    def test_superuser_without_company_gets_empty_list(self):
        su = User.objects.create_superuser(
            username='arc40_su', password='x', email='arc40su@example.com')
        resp = auth(su).get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(resp.data['tuiles'], [])
