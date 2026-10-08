"""APAR10 — frontière transactionnelle du moteur d'automatisation.

Constat C-APAR-010 : ``engine._execute`` exécutait l'action dans la
transaction de l'ÉMETTEUR, sans point de sauvegarde ni ``on_commit`` :
(1) un changement d'étape ensuite ANNULÉ avait déjà envoyé l'e-mail au client ;
(2) une action en erreur SQL (valeur trop longue) avortait la transaction de
l'émetteur, dont la requête suivante levait ``TransactionManagementError``.

``TransactionTestCase`` OBLIGATOIRE : un ``TestCase`` enveloppe tout dans une
transaction jamais validée — ``on_commit`` n'y tire jamais et un rollback
« réel » de l'émetteur n'y est pas observable.

Test-du-test : retirer le ``transaction.atomic()`` de ``engine._run_isole`` ⇒
``test_erreur_sql_n_avorte_pas_l_emetteur`` rouge ; retirer ``on_commit`` de
``engine._execute_au_commit`` ⇒ ``test_rollback_n_envoie_rien`` rouge.
"""
from django.core import mail
from django.db import transaction
from django.test import TransactionTestCase

from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType,
)
from apps.crm.models import Lead
from apps.crm.stages import CONTACTED, NEW
from authentication.models import Company
from core.test_utils import WideTeardownTimeoutMixin


class _Annule(Exception):
    """Annulation volontaire de la transaction de l'émetteur."""


class FrontiereTransactionTests(WideTeardownTimeoutMixin, TransactionTestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='APAR10', slug='apar10-co')
        mail.outbox = []

    def _regle_email(self):
        return AutomationRule.objects.create(
            company=self.co, nom='E-mail étape', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SEND_EMAIL,
            action_config={'subject': 'Suivi', 'body': 'Bonjour'})

    def _lead(self):
        return Lead.objects.create(
            company=self.co, nom='Client APAR10', stage=NEW,
            email='apar10@example.invalid')

    def test_rollback_n_envoie_rien(self):
        regle = self._regle_email()
        lead = self._lead()
        with self.assertRaises(_Annule):
            with transaction.atomic():
                lead.stage = CONTACTED
                lead.save()
                raise _Annule()
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AutomationRun.objects.filter(rule=regle).count(), 0)

    def test_commit_envoie_et_journalise_une_fois(self):
        regle = self._regle_email()
        lead = self._lead()
        with transaction.atomic():
            lead.stage = CONTACTED
            lead.save()
            # Rien n'est parti AVANT le commit.
            self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(len(mail.outbox), 1)
        runs = AutomationRun.objects.filter(rule=regle)
        self.assertEqual(runs.count(), 1)
        self.assertEqual(runs.get().status, AutomationRun.Status.SUCCESS)

    def test_erreur_sql_n_avorte_pas_l_emetteur(self):
        regle = AutomationRule.objects.create(
            company=self.co, nom='Priorité trop longue', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SET_FIELD,
            action_config={'field': 'priorite', 'value': 'x' * 12})
        lead = self._lead()
        with transaction.atomic():
            lead.stage = CONTACTED
            lead.save()
            # La transaction de l'émetteur reste utilisable.
            self.assertEqual(
                Lead.objects.filter(company=self.co).count(), 1)
            lead.save()  # la valeur refusée n'est pas restée en mémoire
        run = AutomationRun.objects.get(rule=regle)
        self.assertEqual(run.status, AutomationRun.Status.FAILED)
        self.assertTrue(run.message)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, CONTACTED)
        self.assertNotEqual(lead.priorite, 'x' * 12)
