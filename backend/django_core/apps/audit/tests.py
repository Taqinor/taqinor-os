"""Tests du Journal d'activité (Feature G).

Couvre : capture connexion/échec/déconnexion, capture CRUD + changement de
statut via les signaux pendant une requête, non-capture hors requête (ORM
direct), gating de permission (Directeur uniquement par défaut), et les
endpoints stats/liste.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.roles.models import (
    Role, DIRECTEUR_PERMISSIONS, COMMERCIAL_PERMISSIONS, ADMIN_PERMISSIONS,
)
from apps.crm.models import Client, Lead
from apps.audit.models import AuditLog


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AuditBase(TestCase):
    def setUp(self):
        cache.clear()  # remet à zéro le throttle de connexion entre tests
        self.company = Company.objects.create(nom='Audit Co', slug='audit-co')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        self.admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ADMIN_PERMISSIONS, est_systeme=True)
        self.com_role = Role.objects.create(
            company=self.company, nom='Commercial',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.directeur = CustomUser.objects.create_user(
            username='dir', password='Secret@2026', company=self.company,
            role=self.dir_role, role_legacy='admin')
        self.admin = CustomUser.objects.create_user(
            username='adm', password='Secret@2026', company=self.company,
            role=self.admin_role, role_legacy='admin')
        self.com = CustomUser.objects.create_user(
            username='com', password='Secret@2026', company=self.company,
            role=self.com_role)


class TestCapture(AuditBase):
    def test_orm_create_outside_request_not_logged(self):
        Lead.objects.create(company=self.company, nom='Direct ORM')
        self.assertFalse(
            AuditLog.objects.filter(action='create').exists())

    def test_api_create_logs(self):
        auth(self.com).post('/api/django/crm/leads/', {'nom': 'Via API'})
        entry = AuditLog.objects.filter(action='create').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user_id, self.com.id)
        self.assertEqual(entry.company_id, self.company.id)

    def test_status_change_logged(self):
        lead = Lead.objects.create(company=self.company, nom='Funnel')
        auth(self.directeur).patch(
            f'/api/django/crm/leads/{lead.id}/',
            {'stage': 'CONTACTED'}, format='json')
        entry = AuditLog.objects.filter(
            action='status', object_id=str(lead.id)).first()
        self.assertIsNotNone(entry)
        self.assertIn('→', entry.detail)

    def test_login_success_and_failure_logged(self):
        api = APIClient()
        ok = api.post('/api/django/token/',
                      {'username': 'dir', 'password': 'Secret@2026'},
                      format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(
            action='login', user=self.directeur).exists())
        bad = api.post('/api/django/token/',
                       {'username': 'ghost', 'password': 'nope'},
                       format='json')
        self.assertEqual(bad.status_code, 401)
        failed = AuditLog.objects.filter(action='login_failed').first()
        self.assertIsNotNone(failed)
        self.assertEqual(failed.actor_username, 'ghost')
        self.assertIsNone(failed.user_id)


class TestReadApi(AuditBase):
    def test_permission_directeur_only(self):
        # Commercial : pas la permission journal → 403.
        self.assertEqual(
            auth(self.com).get('/api/django/audit/entries/').status_code, 403)
        # Admin : pas le journal par défaut → 403.
        self.assertEqual(
            auth(self.admin).get('/api/django/audit/entries/').status_code, 403)
        # Directeur : 200.
        self.assertEqual(
            auth(self.directeur).get('/api/django/audit/entries/').status_code,
            200)

    def test_stats_buckets(self):
        auth(self.com).post('/api/django/crm/leads/', {'nom': 'X'})
        resp = auth(self.directeur).get('/api/django/audit/stats/?period=jour')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['granularity'], 'hour')
        self.assertEqual(len(resp.data['buckets']), 24)
        self.assertGreaterEqual(resp.data['total'], 1)

    def test_list_company_scoped(self):
        other = Company.objects.create(nom='Other', slug='other-audit')
        AuditLog.objects.create(company=other, action='create',
                                object_repr='foreign')
        AuditLog.objects.create(company=self.company, action='create',
                                object_repr='mine')
        resp = auth(self.directeur).get('/api/django/audit/entries/')
        reprs = {r['object_repr'] for r in resp.data['results']}
        self.assertIn('mine', reprs)
        self.assertNotIn('foreign', reprs)


class TestPdfEventCapture(AuditBase):
    """M4 — la génération d'un PDF (devis/facture) produit toujours une entrée
    ``AuditLog.Action.PDF``, désormais via l'événement ``document_pdf_generated``
    du bus ``core.events`` (ventes n'importe plus ``apps.audit``)."""

    def _client(self):
        return Client.objects.create(company=self.company, nom='Cli PDF')

    def test_devis_pdf_logs_pdf_audit_row(self):
        from apps.ventes.models import Devis
        devis = Devis.objects.create(
            company=self.company, reference='DEV-AUD-0001',
            client=self._client(), statut='brouillon',
            taux_tva=Decimal('20.00'), created_by=self.directeur)
        with patch('apps.ventes.tasks.task_generate_devis_pdf') as task:
            task.delay.return_value = MagicMock(id='t1')
            resp = auth(self.directeur).post(
                f'/api/django/ventes/devis/{devis.id}/generer-pdf/')
        self.assertEqual(resp.status_code, 202)
        entry = AuditLog.objects.filter(
            action='pdf', object_id=str(devis.id)).first()
        self.assertIsNotNone(entry)
        # Acteur, société et détail identiques à l'ancien appel direct.
        self.assertEqual(entry.user_id, self.directeur.id)
        self.assertEqual(entry.company_id, self.company.id)
        self.assertEqual(entry.detail, 'PDF devis généré')

    def test_facture_pdf_logs_pdf_audit_row(self):
        from apps.ventes.models import Facture
        facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD-0001',
            client=self._client(), statut='emise',
            taux_tva=Decimal('20.00'), created_by=self.directeur)
        with patch('apps.ventes.tasks.task_generate_facture_pdf') as task:
            task.delay.return_value = MagicMock(id='t2')
            resp = auth(self.directeur).post(
                f'/api/django/ventes/factures/{facture.id}/generer-pdf/')
        self.assertEqual(resp.status_code, 202)
        entry = AuditLog.objects.filter(
            action='pdf', object_id=str(facture.id)).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user_id, self.directeur.id)
        self.assertEqual(entry.company_id, self.company.id)
        self.assertEqual(entry.detail, 'PDF facture généré')


class TestAuditAnalytics(TestCase):
    """FG97 — audit/analytics/ rollups (top users, action mix, churn, failed logins)."""

    def setUp(self):
        # Pas de cache.clear() ici (pas de Redis en CI/test local).
        self.company = Company.objects.create(nom='Analytics Co', slug='analytics-co')
        self.dir_role = Role.objects.create(
            company=self.company, nom='Directeur-A97',
            permissions=DIRECTEUR_PERMISSIONS, est_systeme=True)
        self.admin_role = Role.objects.create(
            company=self.company, nom='Admin-A97',
            permissions=ADMIN_PERMISSIONS, est_systeme=True)
        self.com_role = Role.objects.create(
            company=self.company, nom='Commercial-A97',
            permissions=COMMERCIAL_PERMISSIONS, est_systeme=True)
        self.directeur = CustomUser.objects.create_user(
            username='dir_a97', password='Secret@2026', company=self.company,
            role=self.dir_role, role_legacy='admin')
        self.admin = CustomUser.objects.create_user(
            username='adm_a97', password='Secret@2026', company=self.company,
            role=self.admin_role, role_legacy='admin')
        self.com = CustomUser.objects.create_user(
            username='com_a97', password='Secret@2026', company=self.company,
            role=self.com_role)

    def _seed(self):
        """Crée quelques entrées de log pour la société de test."""
        AuditLog.objects.create(
            company=self.company, user=self.directeur,
            actor_username='dir_a97', action='create', object_repr='Lead 1')
        AuditLog.objects.create(
            company=self.company, user=self.com,
            actor_username='com_a97', action='update', object_repr='Lead 1')
        AuditLog.objects.create(
            company=self.company, actor_username='ghost',
            action='login_failed', object_repr='')
        AuditLog.objects.create(
            company=self.company, actor_username='ghost',
            action='login_failed', object_repr='')

    def test_analytics_requires_directeur_permission(self):
        """Les commerciaux/admins ne peuvent pas voir les analytics."""
        self.assertEqual(
            auth(self.com).get('/api/django/audit/analytics/').status_code, 403)
        self.assertEqual(
            auth(self.admin).get('/api/django/audit/analytics/').status_code, 403)

    def test_analytics_directeur_200(self):
        """Le Directeur obtient un 200 avec les blocs attendus."""
        self._seed()
        resp = auth(self.directeur).get('/api/django/audit/analytics/?days=30')
        self.assertEqual(resp.status_code, 200)
        for key in ('top_users', 'action_mix', 'daily_counts',
                    'failed_logins', 'object_churn', 'total_entries'):
            self.assertIn(key, resp.data, f'Clé manquante : {key}')

    def test_analytics_top_users_ranked(self):
        """top_users est trié par count décroissant."""
        self._seed()
        resp = auth(self.directeur).get('/api/django/audit/analytics/?days=30')
        users = resp.data['top_users']
        self.assertTrue(len(users) >= 1)
        counts = [u['count'] for u in users]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_analytics_action_mix_has_pct(self):
        """action_mix contient des entrées avec les clés count/pct/label."""
        self._seed()
        resp = auth(self.directeur).get('/api/django/audit/analytics/')
        self.assertEqual(resp.status_code, 200)
        mix = resp.data['action_mix']
        self.assertTrue(len(mix) > 0)
        for item in mix:
            self.assertIn('action', item)
            self.assertIn('count', item)
            self.assertIn('pct', item)
            self.assertIn('label', item)

    def test_analytics_failed_logins_counted(self):
        """Les échecs de connexion sont isolés dans failed_logins."""
        self._seed()
        resp = auth(self.directeur).get('/api/django/audit/analytics/?days=30')
        total_failed = sum(d['count'] for d in resp.data['failed_logins'])
        self.assertEqual(total_failed, 2)

    def test_analytics_company_scoped(self):
        """Les logs d'autres sociétés ne contaminent pas les analytics."""
        other = Company.objects.create(nom='Other97', slug='other-a97')
        for _ in range(10):
            AuditLog.objects.create(company=other, actor_username='hacker_a97',
                                    action='create')
        self._seed()
        resp = auth(self.directeur).get('/api/django/audit/analytics/?days=30')
        usernames = {u['actor_username'] for u in resp.data['top_users']}
        self.assertNotIn('hacker_a97', usernames)

    def test_analytics_daily_counts_length_matches_days(self):
        """daily_counts a exactement ?days entrées."""
        resp = auth(self.directeur).get('/api/django/audit/analytics/?days=7')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['daily_counts']), 7)
        self.assertEqual(len(resp.data['failed_logins']), 7)


class TestTrackedModelsCoverage(TestCase):
    """FG15 — les écritures argent/sécurité sont désormais suivies par l'audit.

    On vérifie (a) que les nouvelles paires sont déclarées et (b) qu'elles
    résolvent toutes en un vrai modèle (anti-typo app_label/ModelName).
    """
    def test_money_and_security_models_are_tracked(self):
        from apps.audit.signals import TRACKED_MODELS
        attendus = {
            ('ventes', 'BonCommande'),
            # ODX17 — Paiement déplacé vers ``facturation`` (state-only).
            ('facturation', 'Paiement'),
            ('sav', 'ContratMaintenance'),
            # ODX19 — chaîne achats fournisseur déplacée de ``stock`` vers
            # ``achats``.
            ('achats', 'BonCommandeFournisseur'),
            ('achats', 'ReceptionFournisseur'),
            ('achats', 'FactureFournisseur'),
            ('achats', 'PaiementFournisseur'),
            ('publicapi', 'ApiKey'),
            ('publicapi', 'Webhook'),
        }
        self.assertTrue(attendus.issubset(set(TRACKED_MODELS)))

    def test_all_tracked_models_resolve(self):
        from django.apps import apps as django_apps
        from apps.audit.signals import TRACKED_MODELS
        for app_label, model_name in TRACKED_MODELS:
            # Lève LookupError si la paire est erronée.
            django_apps.get_model(app_label, model_name)


class TestPaieAuditTrail(AuditBase):
    """XPAI23 — piste d'audit paie : les écritures « argent » (taux/barèmes/
    rubriques/profils/avances/arrêts/périodes) sont désormais suivies, même
    mécanique post_save/post_delete que les autres modèles (aucun changement
    de comportement)."""

    def test_paie_models_are_tracked(self):
        from apps.audit.signals import TRACKED_MODELS
        attendus = {
            ('paie', 'ParametrePaie'),
            ('paie', 'BaremeIR'),
            ('paie', 'Rubrique'),
            ('paie', 'ProfilPaie'),
            ('paie', 'RubriqueEmploye'),
            ('paie', 'AvanceSalarie'),
            ('paie', 'SaisieArret'),
            ('paie', 'PeriodePaie'),
        }
        self.assertTrue(attendus.issubset(set(TRACKED_MODELS)))

    def test_parametre_paie_update_logs_audit_entry(self):
        """Modifier un taux ParametrePaie via l'API produit une entrée
        d'audit, scopée à la société de l'acteur."""
        from apps.paie.models import ParametrePaie

        param = ParametrePaie.objects.create(
            company=self.company, date_effet='2026-01-01',
            taux_cnss_salarial=Decimal('4.48'))
        resp = auth(self.directeur).patch(
            f'/api/django/paie/parametres/{param.id}/',
            {'taux_cnss_salarial': '5.00'}, format='json')
        self.assertEqual(resp.status_code, 200)
        entry = AuditLog.objects.filter(
            action='update', object_id=str(param.id)).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user_id, self.directeur.id)
        self.assertEqual(entry.company_id, self.company.id)

    def test_parametre_paie_orm_create_outside_request_not_logged(self):
        """Même règle que les autres modèles suivis : une écriture ORM
        directe hors requête (migration/seed/test) ne journalise rien."""
        from apps.paie.models import ParametrePaie

        ParametrePaie.objects.create(
            company=self.company, date_effet='2026-02-01')
        self.assertFalse(
            AuditLog.objects.filter(action='create',
                                    object_repr__icontains='2026-02-01')
            .exists())


class TestFournisseurAuditTrail(AuditBase):
    """WIR1 — le RIB/coordonnées/conditions de paiement d'un ``Fournisseur``
    alimentent la chaîne achats déjà tracée mais leur propre modification ne
    produisait aucune ligne AuditLog jusqu'ici (perte d'audit silencieuse,
    surface fraude)."""

    def test_fournisseur_is_tracked(self):
        from apps.audit.signals import TRACKED_MODELS
        self.assertIn(('stock', 'Fournisseur'), TRACKED_MODELS)

    def test_fournisseur_rib_update_logs_filterable_audit_entry(self):
        from apps.stock.models import Fournisseur

        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='ACME Solaire', rib='RIB-OLD')
        resp = auth(self.directeur).patch(
            f'/api/django/stock/fournisseurs/{fournisseur.id}/',
            {'rib': 'RIB-NEW'}, format='json')
        self.assertEqual(resp.status_code, 200)

        entry = AuditLog.objects.filter(
            action='update', object_id=str(fournisseur.id),
            content_type__app_label='stock',
            content_type__model='fournisseur').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.user_id, self.directeur.id)
        self.assertEqual(entry.company_id, self.company.id)

        # Filtrable depuis le Journal (module=stock&model=fournisseur).
        listing = auth(self.directeur).get(
            '/api/django/audit/entries/',
            {'module': 'stock', 'model': 'fournisseur'})
        self.assertEqual(listing.status_code, 200)
        ids = [row['id'] for row in listing.data['results']]
        self.assertIn(entry.id, ids)

    def test_fournisseur_orm_create_outside_request_not_logged(self):
        from apps.stock.models import Fournisseur

        Fournisseur.objects.create(company=self.company, nom='Direct ORM')
        self.assertFalse(
            AuditLog.objects.filter(action='create',
                                    object_repr__icontains='Direct ORM')
            .exists())
