"""NTEXT8 — action serveur SCRIPTÉE sûre (CEL-style, jamais du Python).

``action_config = {'expressions': [{'field': 'x', 'value': '<formule>'}]}`` —
chaque expression est évaluée par ``core.formula`` (AST sûr, jamais ``eval``)
sur le contexte de LECTURE de l'enregistrement et écrite dans un champ du
MÊME registre fermé que SET_FIELD (``actions.SET_FIELD_TARGETS``) : jamais
company/prix_achat ni un champ de machine à états (``statut``/``stage``…).
"""
import itertools

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Lead

from apps.automation import engine
from apps.automation.models import ActionType, AutomationRule, TriggerType

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(
        slug=f'ntext8-co-{n}', nom=f'NTEXT8 Co {n}')


class ServerActionTests(TestCase):
    def setUp(self):
        self.co = make_company()

    def _rule(self, expressions):
        return AutomationRule.objects.create(
            company=self.co, nom='Action scriptée',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'SIGNED'},
            action_type=ActionType.SERVER_ACTION,
            action_config={'expressions': expressions})

    def test_expression_calcule_et_ecrit_un_champ_autorise(self):
        rule = self._rule([
            {'field': 'priorite',
             'value': "'haute' if montant_estime > 1000 else 'normale'"},
        ])
        lead = Lead.objects.create(
            company=self.co, nom='T', stage='NEW', montant_estime=5000,
            priorite='normale')
        status, message = engine.run_action(rule, lead, self.co)
        self.assertEqual(status, 'success', message)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'haute')
        self.assertIn('priorite', message)

    def test_expression_avec_valeur_basse_ecrit_normale(self):
        rule = self._rule([
            {'field': 'priorite',
             'value': "'haute' if montant_estime > 1000 else 'normale'"},
        ])
        lead = Lead.objects.create(
            company=self.co, nom='T', stage='NEW', montant_estime=10,
            priorite='haute')
        engine.run_action(rule, lead, self.co)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'normale')

    def test_champ_hors_registre_est_ignore_sans_ecrire(self):
        """'stage' est un champ de machine à états : jamais écrit par une
        action serveur scriptée, même si l'expression est sûre."""
        rule = self._rule([
            {'field': 'stage', 'value': "'SIGNED'"},
        ])
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        status, message = engine.run_action(rule, lead, self.co)
        self.assertEqual(status, 'noop', message)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'NEW')

    def test_champ_prix_achat_toujours_refuse(self):
        rule = self._rule([{'field': 'prix_achat', 'value': '1'}])
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        status, _message = engine.run_action(rule, lead, self.co)
        self.assertEqual(status, 'noop')

    def test_expression_illegale_est_ignoree_sans_lever(self):
        """Aucune boucle, aucun import : une expression qui tente d'y
        échapper est simplement rejetée par core.formula (AST fermé)."""
        rule = self._rule([
            {'field': 'priorite', 'value': "__import__('os').system('ls')"},
        ])
        lead = Lead.objects.create(
            company=self.co, nom='T', stage='NEW', priorite='normale')
        status, _message = engine.run_action(rule, lead, self.co)
        self.assertEqual(status, 'noop')
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, 'normale')

    def test_ne_lit_jamais_prix_achat_meme_present_dans_le_contexte(self):
        """Le contexte de lecture retire prix_achat AVANT évaluation : une
        expression ne peut donc jamais le recopier, même indirectement."""
        rule = self._rule([
            {'field': 'note', 'value': "'x' if prix_achat else 'y'"},
        ])
        lead = Lead.objects.create(company=self.co, nom='T', stage='NEW')
        status, _message = engine.run_action(
            rule, lead, self.co, context={'prix_achat': 999999})
        # `prix_achat` est absent du contexte évalué → variable inconnue →
        # FormulaError → expression ignorée → NOOP (rien n'est écrit).
        self.assertEqual(status, 'noop')
