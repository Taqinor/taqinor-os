"""Tests apps.adminops (NTADM5/10-17/33/34/36/38)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from authentication.models import Company

from ..models import (
    AdminOpsSettings, EvenementUsage, HealthScoreSnapshot,
    SandboxEnvironment,
)

User = get_user_model()


def _company(nom='AdminOpsCo'):
    return Company.objects.create(nom=nom)


def _admin(company, username='admin'):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy='admin', is_staff=True)


class HealthScoreTests(TestCase):
    def setUp(self):
        self.company = _company()

    def test_score_varie_avec_completude(self):
        from ..health_score import calculer_health_score
        base = calculer_health_score(self.company)
        self.assertIn('score', base)
        self.assertIn('completude', base['sous_scores'])
        # Ajouter un rôle custom augmente la complétude.
        from apps.roles.models import Role
        Role.objects.create(company=self.company, nom='Custom', est_systeme=False)
        apres = calculer_health_score(self.company)
        self.assertGreaterEqual(apres['sous_scores']['completude'],
                                base['sous_scores']['completude'])

    def test_scope_company(self):
        from ..health_score import calculer_health_score
        r = calculer_health_score(self.company)
        self.assertTrue(0 <= r['score'] <= 100)


class SandboxTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def test_creer_puis_clone_sync(self):
        from ..sandbox_service import cloner_sandbox_sync, creer_sandbox
        env = creer_sandbox(self.company, self.admin)
        self.assertEqual(env.statut, SandboxEnvironment.Statut.EN_CREATION)
        cloner_sandbox_sync(env.id)
        env.refresh_from_db()
        self.assertEqual(env.statut, SandboxEnvironment.Statut.PRET)
        self.assertIsNotNone(env.sandbox_company)
        # jamais d'écriture dans le tenant source
        self.assertNotEqual(env.sandbox_company_id, self.company.id)

    def test_rate_limit_un_sandbox_actif(self):
        from ..sandbox_service import SandboxDejaActif, creer_sandbox
        creer_sandbox(self.company, self.admin)
        with self.assertRaises(SandboxDejaActif):
            creer_sandbox(self.company, self.admin)

    def test_sandbox_non_autorise(self):
        from ..sandbox_service import SandboxNonAutorise, creer_sandbox
        AdminOpsSettings.objects.create(
            company=self.company, sandbox_autorise=False)
        with self.assertRaises(SandboxNonAutorise):
            creer_sandbox(self.company, self.admin)

    def test_prolonger_max_deux_fois(self):
        from ..sandbox_service import cloner_sandbox_sync, creer_sandbox, prolonger_sandbox
        env = creer_sandbox(self.company, self.admin)
        cloner_sandbox_sync(env.id)
        env.refresh_from_db()
        prolonger_sandbox(env)
        prolonger_sandbox(env)
        with self.assertRaises(ValueError):
            prolonger_sandbox(env)

    def test_purge_sandbox_expire(self):
        from ..sandbox_service import cloner_sandbox_sync, creer_sandbox
        from ..tasks import purger_sandbox_expires
        env = creer_sandbox(self.company, self.admin)
        cloner_sandbox_sync(env.id)
        env.refresh_from_db()
        env.date_expiration = timezone.now() - timezone.timedelta(days=1)
        env.save(update_fields=['date_expiration'])
        purger_sandbox_expires()
        env.refresh_from_db()
        self.assertEqual(env.statut, SandboxEnvironment.Statut.EXPIRE)
        env.sandbox_company.refresh_from_db()
        self.assertFalse(env.sandbox_company.actif)


class ConfigPackageTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def test_export_puis_diff_idempotent(self):
        from ..config_package_service import (
            appliquer_import, exporter_config, previsualiser_import)
        from apps.roles.models import Role
        Role.objects.create(company=self.company, nom='Vendeur', est_systeme=False,
                            permissions=['crm_voir'])
        package = exporter_config(self.company, nom='Test', user=self.admin)
        self.assertNotIn('leads', package.contenu)  # jamais de donnée métier
        # Nouvelle société cible sans ce rôle : diff détecte 1 ajout.
        cible = _company('Cible')
        diff = previsualiser_import(cible, package.contenu)
        self.assertEqual(len(diff['roles_custom']['ajouts']), 1)
        # Appliquer, puis re-diff => vide (idempotent).
        appliquer_import(cible, package.contenu, user=self.admin)
        diff2 = previsualiser_import(cible, package.contenu)
        self.assertEqual(len(diff2['roles_custom']['ajouts']), 0)
        self.assertEqual(len(diff2['roles_custom']['modifications']), 0)

    def test_versionning(self):
        from ..config_package_service import exporter_config
        p1 = exporter_config(self.company, nom='Cfg', user=self.admin)
        p2 = exporter_config(self.company, nom='Cfg', user=self.admin)
        self.assertEqual(p1.version, 1)
        self.assertEqual(p2.version, 2)


class AdoptionTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)

    def test_evenements_agreges_par_module(self):
        from ..selectors import adoption_par_module
        for ecran in ('crm.leads', 'crm.leads', 'ventes.devis'):
            EvenementUsage.objects.create(
                company=self.company, module=ecran.split('.')[0],
                ecran=ecran, utilisateur=self.admin)
        agg = adoption_par_module(self.company)
        self.assertEqual(agg['crm']['nb_evenements'], 2)
        self.assertEqual(agg['ventes']['nb_evenements'], 1)

    def test_purge_evenements(self):
        from ..tasks import purger_evenements_usage
        vieux = EvenementUsage.objects.create(
            company=self.company, module='crm', utilisateur=self.admin)
        EvenementUsage.objects.filter(pk=vieux.pk).update(
            horodatage=timezone.now() - timezone.timedelta(days=200))
        purger_evenements_usage()
        self.assertFalse(EvenementUsage.objects.filter(pk=vieux.pk).exists())


class AdminOpsApiTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _admin(self.company)
        self.client_api = APIClient()
        self.client_api.force_authenticate(self.admin)

    def test_health_score_endpoint(self):
        resp = self.client_api.get('/api/django/adminops/health-score/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('score', resp.data)

    def test_tracker_usage(self):
        resp = self.client_api.post(
            '/api/django/adminops/tracker-usage/',
            {'module': 'crm', 'ecran': 'crm.leads'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(EvenementUsage.objects.filter(company=self.company).count(), 1)

    def test_settings_borne_validation(self):
        resp = self.client_api.patch(
            '/api/django/adminops/settings/',
            {'sandbox_duree_defaut_jours': 999}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_settings_ok(self):
        resp = self.client_api.patch(
            '/api/django/adminops/settings/',
            {'seuil_alerte_sieges_pct': 80}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['seuil_alerte_sieges_pct'], 80)

    def test_diagnostic_scope(self):
        resp = self.client_api.get('/api/django/adminops/diagnostic/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('nb_utilisateurs', resp.data)

    def test_non_admin_health_score_refuse(self):
        normal = User.objects.create_user(
            username='u', password='pw', company=self.company, role_legacy='normal')
        c = APIClient()
        c.force_authenticate(normal)
        resp = c.get('/api/django/adminops/health-score/')
        self.assertIn(resp.status_code, (401, 403))


class HealthScoreSnapshotTaskTests(TestCase):
    def test_recalcul_persiste_snapshot(self):
        company = _company()
        from ..tasks import recalculer_health_score_tenants
        recalculer_health_score_tenants()
        self.assertTrue(HealthScoreSnapshot.objects.filter(company=company).exists())
