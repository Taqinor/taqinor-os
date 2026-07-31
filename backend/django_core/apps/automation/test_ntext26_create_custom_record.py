"""NTEXT26 — automatisation : action CRÉER un enregistrement d'objet custom.

``ActionType.CREATE_CUSTOM_RECORD`` (``action_config={'object_code': 'x',
'data': {...}}``) matérialise un ``customfields.CustomRecord`` scopé société
via le chemin de validation EXISTANT (``validate_custom_data`` — même règles
obligatoire/type que la création manuelle par API, jamais de contournement).
Les valeurs texte de ``data`` supportent la substitution ``{var}`` depuis le
``context`` du déclencheur (XPRJ23, réutilisé — pas de second mécanisme).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead
from apps.customfields.models import CustomFieldDef, CustomObjectDef, CustomRecord

from apps.automation import engine
from apps.automation.models import ActionType, AutomationRule, AutomationRun, TriggerType

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CreateCustomRecordActionTests(TestCase):
    def setUp(self):
        self.co = make_company('ntext26-a', 'NTEXT26 A')
        self.objet = CustomObjectDef.objects.create(
            company=self.co, code='suivi-qualite', libelle='Suivi qualité')
        CustomFieldDef.objects.create(
            company=self.co, module='custom:suivi-qualite', code='titre',
            libelle='Titre', type='text', obligatoire=True)
        CustomFieldDef.objects.create(
            company=self.co, module='custom:suivi-qualite', code='niveau',
            libelle='Niveau', type='text')
        self.lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')

    def _rule(self, **cfg):
        return AutomationRule.objects.create(
            company=self.co, nom='Créer suivi qualité',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_CUSTOM_RECORD,
            action_config=cfg)

    def test_creates_record_with_context_substitution(self):
        rule = self._rule(
            object_code='suivi-qualite',
            data={'titre': 'Ticket {reference}', 'niveau': 'normal'})
        status, message = engine.run_action(
            rule, self.lead, self.co,
            context={'reference': 'SAV-042'})
        self.assertEqual(status, AutomationRun.Status.SUCCESS)
        record = CustomRecord.objects.get(company=self.co, objet=self.objet)
        self.assertEqual(record.data['titre'], 'Ticket SAV-042')
        self.assertEqual(record.data['niveau'], 'normal')

    def test_missing_object_code_is_noop(self):
        rule = self._rule(data={'titre': 'x'})
        status, message = engine.run_action(rule, self.lead, self.co)
        self.assertEqual(status, AutomationRun.Status.NOOP)
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_unknown_object_code_is_noop(self):
        rule = self._rule(object_code='introuvable', data={'titre': 'x'})
        status, message = engine.run_action(rule, self.lead, self.co)
        self.assertEqual(status, AutomationRun.Status.NOOP)
        self.assertIn('introuvable', message)
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_missing_required_field_after_substitution_fails_cleanly(self):
        rule = self._rule(object_code='suivi-qualite', data={'niveau': 'x'})
        status, message = engine.run_action(rule, self.lead, self.co)
        self.assertEqual(status, AutomationRun.Status.FAILED)
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_other_company_object_never_resolved(self):
        other = make_company('ntext26-b', 'NTEXT26 B')
        rule = AutomationRule.objects.create(
            company=other, nom='Autre société',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.CREATE_CUSTOM_RECORD,
            action_config={'object_code': 'suivi-qualite', 'data': {'titre': 'x'}})
        other_lead = Lead.objects.create(company=other, nom='T', stage='NEW')
        status, message = engine.run_action(rule, other_lead, other)
        self.assertEqual(status, AutomationRun.Status.NOOP)
        self.assertEqual(CustomRecord.objects.count(), 0)

    def test_end_to_end_via_trigger_creates_run_and_record(self):
        self._rule(
            object_code='suivi-qualite',
            data={'titre': 'Lead {stage}'})
        self.lead.stage = 'SIGNED'
        self.lead.save()
        run = AutomationRun.objects.filter(company=self.co).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AutomationRun.Status.SUCCESS)
        record = CustomRecord.objects.get(company=self.co, objet=self.objet)
        # Aucune variable ``stage`` dans le contexte de ce déclencheur : la
        # substitution est tolérante et laisse l'accolade littérale (XPRJ23).
        self.assertEqual(record.data['titre'], 'Lead {stage}')
