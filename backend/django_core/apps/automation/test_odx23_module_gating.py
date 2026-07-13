"""ODX23 (reliquat) — gating ``ModuleToggle`` du moteur d'automatisation.

Une règle dont le déclencheur (déduit de l'``app_label`` du modèle
déclencheur) ou l'action (``CREATE_SAV_TICKET`` → ``sav``, voir
``engine.ACTION_MODULE_MAP``) vise un module désactivé pour la société ne
s'exécute plus : un run ``SKIPPED`` est journalisé (« module désactivé »)
à la place, best-effort, isolé par société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from core.models import ModuleToggle
from apps.crm.models import Lead
from apps.stock.models import Produit

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TriggerModuleGatingTests(TestCase):
    """Le module du DÉCLENCHEUR (app_label de l'instance) est désactivé."""

    def setUp(self):
        self.co = make_company('odx23-a', 'ODX23 A')
        AutomationRule.objects.create(
            company=self.co, nom='Stock bas',
            trigger_type=TriggerType.STOCK_BELOW_THRESHOLD, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'x'})

    def test_disabled_trigger_module_skips_and_logs(self):
        ModuleToggle.objects.create(company=self.co, module='stock', actif=False)
        Produit.objects.create(
            company=self.co, nom='Vis', prix_vente=10,
            quantite_stock=2, seuil_alerte=5)

        run = AutomationRun.objects.filter(
            rule__trigger_type=TriggerType.STOCK_BELOW_THRESHOLD).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AutomationRun.Status.SKIPPED)
        self.assertIn('désactivé', run.message)

    def test_default_active_module_runs_normally(self):
        # Aucun ModuleToggle -> policy FG391 : actif par défaut, comportement
        # inchangé (non-régression).
        Produit.objects.create(
            company=self.co, nom='Vis', prix_vente=10,
            quantite_stock=2, seuil_alerte=5)
        run = AutomationRun.objects.filter(
            rule__trigger_type=TriggerType.STOCK_BELOW_THRESHOLD).first()
        self.assertIsNotNone(run)
        self.assertNotEqual(run.status, AutomationRun.Status.SKIPPED)

    def test_multi_tenant_isolation(self):
        """Désactiver le module pour A n'affecte pas la société B."""
        co_b = make_company('odx23-b', 'ODX23 B')
        AutomationRule.objects.create(
            company=co_b, nom='Stock bas B',
            trigger_type=TriggerType.STOCK_BELOW_THRESHOLD, trigger_config={},
            action_type=ActionType.CREATE_ACTIVITY, action_config={'body': 'x'})
        ModuleToggle.objects.create(company=self.co, module='stock', actif=False)

        Produit.objects.create(
            company=co_b, nom='Vis B', prix_vente=10,
            quantite_stock=2, seuil_alerte=5)
        run_b = AutomationRun.objects.filter(
            company=co_b, rule__trigger_type=TriggerType.STOCK_BELOW_THRESHOLD
        ).first()
        self.assertIsNotNone(run_b)
        self.assertNotEqual(run_b.status, AutomationRun.Status.SKIPPED)


class ActionModuleGatingTests(TestCase):
    """L'ACTION (CREATE_SAV_TICKET -> module ``sav``) est désactivée, alors
    même que le module du déclencheur (crm) reste actif."""

    def setUp(self):
        self.co = make_company('odx23-c', 'ODX23 C')
        AutomationRule.objects.create(
            company=self.co, nom='Ticket SAV si perdu',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'COLD'},
            action_type=ActionType.CREATE_SAV_TICKET,
            action_config={'description': 'Suivi perte lead'})

    def test_disabled_action_module_skips_ticket_creation(self):
        ModuleToggle.objects.create(company=self.co, module='sav', actif=False)
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        lead.stage = 'COLD'
        lead.save()

        run = AutomationRun.objects.filter(
            rule__trigger_type=TriggerType.LEAD_STAGE_CHANGE).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AutomationRun.Status.SKIPPED)
        self.assertIn('désactivé', run.message)
        from apps.sav.models import Ticket
        self.assertFalse(Ticket.objects.filter(company=self.co).exists())
