"""NTSCM47 — Audit log des actions sensibles SCM.

`avancer-statut` (NTSCM12), `reouvrir` (réouverture admin d'un cycle clos) et
la modification manuelle de `stock_securite_manuel` (NTSCM6) s'enregistrent
dans `apps.audit.AuditLog` via l'entonnoir `apps.audit.recorder.
record_field_change` (ARC16 — MÊME mécanisme que les autres actions
sensibles de l'ERP, ex. `apps/douane` NTLOG50).

Critère d'acceptation : réouvrir un cycle S&OP clos crée une entrée
`AuditLog` consultable par un Administrateur."""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.roles.models import ALL_PERMISSIONS, Role
from apps.scm.models import CyclePlanificationSOP, PolitiqueStock
from apps.scm.services import avancer_statut_cycle, reouvrir_cycle
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


def _make_admin_avec_journal_activite(company, username):
    """Le repli légacy (`role_legacy='admin'`) N'ACCORDE PAS
    `journal_activite_voir` (`CustomUser.can_view_activity_log` renvoie
    ``False`` sans rôle fin, voir `authentication/models.py`) — un rôle fin
    est nécessaire pour CONSULTER le journal d'audit."""
    role = Role.objects.create(
        company=company, nom='Administrateur (fin)', permissions=ALL_PERMISSIONS,
        est_systeme=True)
    user = make_user(company, username, 'admin')
    user.role = role
    user.save(update_fields=['role'])
    return user


class AuditReouvrirCycleTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-audit-reouvrir', 'Supply Audit Réouvrir')
        self.admin = _make_admin_avec_journal_activite(
            self.company, 'scm-audit-reouvrir-admin')
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-04',
            statut=CyclePlanificationSOP.Statut.CLOS)

    def test_reouvrir_cree_une_entree_auditlog(self):
        ct = ContentType.objects.get_for_model(CyclePlanificationSOP)
        avant = AuditLog.objects.filter(
            company=self.company, content_type=ct, object_id=str(self.cycle.id)).count()

        reouvrir_cycle(self.cycle, self.admin, motif='erreur de saisie')

        qs = AuditLog.objects.filter(
            company=self.company, content_type=ct, object_id=str(self.cycle.id)
        ).order_by('-id')
        self.assertEqual(qs.count(), avant + 1)
        entree = qs.first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.user_id, self.admin.id)
        self.assertIsNotNone(entree.timestamp)

    def test_entree_auditlog_consultable_par_un_administrateur(self):
        reouvrir_cycle(self.cycle, self.admin, motif='test NTSCM47')

        resp = auth(self.admin).get('/api/django/audit/entries/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        self.assertTrue(any(
            str(self.cycle.id) == str(r.get('object_id'))
            and r.get('module') == 'scm'
            and r.get('model') == 'cycleplanificationsop'
            for r in rows
        ))

    def test_reouvrir_refuse_sans_journal_activite_voir(self):
        normal = make_user(self.company, 'scm-audit-reouvrir-normal', 'normal')
        resp = auth(normal).get('/api/django/audit/entries/')
        self.assertEqual(resp.status_code, 403)


class AuditAvancerStatutTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-audit-avancer', 'Supply Audit Avancer')
        self.admin = _make_admin_avec_journal_activite(
            self.company, 'scm-audit-avancer-admin')
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-05')

    def test_avancer_statut_cree_une_entree_auditlog(self):
        ct = ContentType.objects.get_for_model(CyclePlanificationSOP)
        avancer_statut_cycle(self.cycle, self.admin)

        entree = AuditLog.objects.filter(
            company=self.company, content_type=ct, object_id=str(self.cycle.id)
        ).order_by('-id').first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.action, AuditLog.Action.STATUS)


class AuditStockSecuriteManuelTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-audit-stock-securite', 'Supply Audit Stock Sécu')
        self.admin = _make_admin_avec_journal_activite(
            self.company, 'scm-audit-stock-securite-admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 10kW', prix_vente=12000)
        self.politique = PolitiqueStock.objects.create(
            company=self.company, produit=self.produit, classe_abc='A',
            service_level_pct=Decimal('95'), point_commande=Decimal('20'),
            stock_securite_calcule=Decimal('8'))

    def test_modifier_stock_securite_manuel_cree_une_entree_auditlog(self):
        ct = ContentType.objects.get_for_model(PolitiqueStock)

        resp = auth(self.admin).patch(
            f'/api/django/scm/politiques-stock/{self.politique.id}/',
            {'stock_securite_manuel': '15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        entree = AuditLog.objects.filter(
            company=self.company, content_type=ct, object_id=str(self.politique.id)
        ).order_by('-id').first()
        self.assertIsNotNone(entree)
        self.assertEqual(entree.action, AuditLog.Action.UPDATE)
