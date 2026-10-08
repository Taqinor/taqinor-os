"""ACRM17 (C-ACRM-010, volet LSVC5-1) — une règle d'automatisation n'écrit
JAMAIS à une personne qui a demandé à ne plus être contactée.

Sonde V_VB LSVC5-1 : règle ``lead_stage_change`` / ``send_email``, lead
« ne plus contacter » passé CONTACTED → un e-mail partait (outbox 1,
exécution SUCCESS). Désormais ``crm.selectors.peut_contacter`` est lu par
``_send_email`` et ``_send_whatsapp`` : exécution SKIPPED « Contact
refusé : la personne a demandé à ne plus être contactée », aucun envoi,
aucun lien préparé ; un lead non opposé reçoit l'e-mail comme avant.

Backend e-mail locmem de Django (pas un mock de la source) ; horloge gelée
en semaine à 10 h (fenêtre d'envoi APAR26 ouverte).

NB : le fichier vit à la racine de ``apps/automation`` (convention de
l'app : ``tests.py`` + ``test_*.py``) — un paquet ``tests/`` masquerait
``tests.py``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from authentication.models import Company
from testkit.time import frozen

from apps.automation import actions
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, TriggerType)
from apps.crm import horaires
from apps.crm.models import Lead
from apps.crm.selectors import MOTIF_CONTACT_REFUSE
from apps.records.models import Activity

User = get_user_model()
MARDI_10H = datetime.datetime(2026, 10, 13, 10, 0, tzinfo=horaires.CASABLANCA)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AutomationOppositionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM17 Solaire', slug='acrm17-opposition')
        self.user = User.objects.create_user(
            username='acrm17-admin', password='x', company=self.company,
            role_legacy='admin')
        self.oppose = Lead.objects.create(
            company=self.company, nom='Oppose', email='oppose@example.com',
            telephone='+212661171701', ne_plus_contacter=True)
        self.normal = Lead.objects.create(
            company=self.company, nom='Normal', email='normal@example.com',
            telephone='+212661171702')

    def _regle(self, action_type):
        return AutomationRule.objects.create(
            company=self.company, nom=f'Règle {action_type}',
            trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={'stage': 'CONTACTED'},
            action_type=action_type, action_config={'body': 'Bonjour'})

    def test_email_refuse_si_oppose(self):
        regle = self._regle(ActionType.SEND_EMAIL)
        mail.outbox = []
        with frozen(MARDI_10H):
            statut, motif = actions.run(
                regle, self.oppose, self.company, {}, self.user)
        self.assertEqual(statut, AutomationRun.Status.SKIPPED)
        self.assertEqual(motif, MOTIF_CONTACT_REFUSE)
        self.assertEqual(mail.outbox, [])

    def test_whatsapp_refuse_si_oppose(self):
        regle = self._regle(ActionType.SEND_WHATSAPP)
        avant = Activity.objects.count()
        with frozen(MARDI_10H):
            statut, motif = actions.run(
                regle, self.oppose, self.company, {}, self.user)
        self.assertEqual(statut, AutomationRun.Status.SKIPPED)
        self.assertEqual(motif, MOTIF_CONTACT_REFUSE)
        self.assertEqual(Activity.objects.count(), avant)

    def test_non_oppose_inchange(self):
        regle = self._regle(ActionType.SEND_EMAIL)
        mail.outbox = []
        with frozen(MARDI_10H):
            statut, _motif = actions.run(
                regle, self.normal, self.company, {}, self.user)
        self.assertEqual(statut, AutomationRun.Status.SUCCESS)
        self.assertEqual([m.to for m in mail.outbox],
                         [['normal@example.com']])
