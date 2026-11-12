"""APAR26 — les envois d'automatisation respectent la fenêtre des messages.

Constat C-APAR-034 : à 23:30 (Africa/Casablanca, fenêtre fermée), une règle
``send_email`` sur LEAD_STAGE_CHANGE envoyait immédiatement au client. Hors
fenêtre, l'envoi est désormais REPORTÉ au prochain créneau par une
``AutomationScheduledStep`` (mécanique NTEXT7) que le beat reprend.

Heure injectée : ``frozen`` prend une heure UTC — 22:30 UTC = 23:30 au Maroc.

Test-du-test : retirer l'appel à ``reporter_hors_fenetre`` de
``actions._send_email`` ⇒ ``test_23h30_rien_avant_l_ouverture`` rouge.
"""
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.automation.beat_tasks import process_due_automation_steps
from apps.automation.engine import run_action
from apps.automation.models import (
    ActionType, AutomationRule, AutomationRun, AutomationScheduledStep,
    TriggerType,
)
from apps.crm.models import Client, Lead
from apps.crm.stages import CONTACTED, NEW
from apps.ventes.models import Facture
from authentication.models import Company
from testkit.time import frozen

NUIT = '2026-01-05 22:30:00'      # lundi 23:30 au Maroc
LENDEMAIN = '2026-01-06 09:00:00'  # mardi 10:00 au Maroc


def _facture_echue(company, reference):
    client = Client.objects.create(
        company=company, nom=f'Cli {reference}', email=f'{reference.lower()}@example.invalid')
    return Facture.objects.create(
        company=company, client=client, reference=reference, statut='emise',
        montant_ttc=Decimal('100'), date_echeance=timezone.localdate() - timedelta(days=30))


@override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=True)
class FenetreMessagesTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='apar26-co', defaults={'nom': 'APAR26'})
        self.regle = AutomationRule.objects.create(
            company=self.co, nom='E-mail étape', enabled=True,
            trigger_type=TriggerType.LEAD_STAGE_CHANGE, trigger_config={},
            action_type=ActionType.SEND_EMAIL,
            action_config={'subject': 'Suivi', 'body': 'Bonjour'})
        self.lead = Lead.objects.create(
            company=self.co, nom='Client APAR26', stage=NEW,
            email='apar26@example.invalid')
        mail.outbox = []

    def test_23h30_rien_avant_l_ouverture(self):
        with frozen(NUIT):
            with self.captureOnCommitCallbacks(execute=True):
                self.lead.stage = CONTACTED
                self.lead.save()
            maintenant = timezone.now()
        self.assertEqual(len(mail.outbox), 0)
        echeance = AutomationScheduledStep.objects.get(
            company=self.co, rule=self.regle)
        self.assertGreater(echeance.run_at, maintenant)
        ouverture = timezone.localtime(echeance.run_at)
        self.assertGreaterEqual((ouverture.hour, ouverture.minute), (8, 30))

        # Le beat avant l'ouverture ne fait rien.
        with frozen(NUIT):
            with self.captureOnCommitCallbacks(execute=True):
                process_due_automation_steps()
        self.assertEqual(len(mail.outbox), 0)

        # À l'ouverture, le beat envoie UNE fois.
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                process_due_automation_steps()
                process_due_automation_steps()
        self.assertEqual(len(mail.outbox), 1)
        echeance.refresh_from_db()
        self.assertEqual(echeance.statut, AutomationScheduledStep.Statut.REPRISE)
        self.assertTrue(AutomationRun.objects.filter(
            rule=self.regle, status=AutomationRun.Status.SUCCESS).exists())

    def test_en_journee_l_envoi_part_tout_de_suite(self):
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                self.lead.stage = CONTACTED
                self.lead.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(AutomationScheduledStep.objects.filter(
            rule=self.regle).exists())

    def test_email_reply_to_societe_et_porte_de_sortie_lead(self):
        """AMSG65 — réponse vers la société ; un lead reçoit la porte de sortie
        des cadences (darija selon sa langue) ; une facture n'en a aucune."""
        from apps.parametres.models import CompanyProfile
        from apps.parametres.models_messages import PORTE_DE_SORTIE_DARIJA
        profil = CompanyProfile.get(company=self.co)
        profil.email = 'contact@apar26.example'
        profil.save()
        self.lead.langue_preferee = 'darija'
        self.lead.save(update_fields=['langue_preferee'])
        facture = _facture_echue(self.co, 'FAC-AMSG65')
        regle_facture = AutomationRule.objects.create(
            company=self.co, nom='Relance', enabled=True, trigger_type=TriggerType.FACTURE_OVERDUE,
            trigger_config={}, action_type=ActionType.SEND_EMAIL,
            action_config={'subject': 'Relance', 'body': 'Votre facture'})
        mail.outbox = []
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                run_action(self.regle, self.lead, self.co)
                run_action(regle_facture, facture, self.co)
        au_lead, a_la_facture = mail.outbox
        self.assertEqual(au_lead.reply_to, ['contact@apar26.example'])
        self.assertTrue(au_lead.body.endswith(PORTE_DE_SORTIE_DARIJA), au_lead.body)
        self.assertEqual(a_la_facture.reply_to, ['contact@apar26.example'])
        self.assertNotIn('STOP', a_la_facture.body)
        self.assertEqual(AutomationRun.objects.filter(
            rule=self.regle, status=AutomationRun.Status.SUCCESS).count(), 1)

        profil.email = ''
        profil.save()
        mail.outbox = []
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                run_action(self.regle, self.lead, self.co)
        self.assertEqual(mail.outbox[0].reply_to, [])

    def test_send_email_sans_corps_refuse_et_ignore(self):
        """AMSG68 — sans ``body``/``message``/``template`` : 400 à la création ;
        une règle ancienne sans corps finit SKIPPED, aucun e-mail."""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        admin = get_user_model().objects.create_user(
            username='amsg68-admin', password='x', company=self.co, role_legacy='admin')
        api = APIClient()
        api.force_authenticate(admin)
        avant = AutomationRule.objects.count()
        r = api.post('/api/django/automation/rules/', {
            'nom': 'Sans corps', 'trigger_type': 'lead_stage_change', 'trigger_config': {},
            'action_type': 'send_email', 'action_config': {'subject': 'Bonjour'}}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('corps obligatoire', str(r.data['action_config']))
        self.assertEqual(AutomationRule.objects.count(), avant)

        ancienne = AutomationRule.objects.create(
            company=self.co, nom='Ancienne', enabled=False, trigger_type=TriggerType.LEAD_STAGE_CHANGE,
            trigger_config={}, action_type=ActionType.SEND_EMAIL, action_config={'subject': 'Bonjour'})
        mail.outbox = []
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                run_action(ancienne, self.lead, self.co)
        self.assertEqual(mail.outbox, [])
        run = AutomationRun.objects.get(rule=ancienne)
        self.assertEqual(run.status, AutomationRun.Status.SKIPPED)
        self.assertEqual(run.message, 'Corps vide : e-mail non envoyé.')

    def test_reprise_relit_l_etat_metier(self):
        """AMSG75 — reportés de nuit, l'e-mail et la tâche WhatsApp d'une facture
        payée entre-temps ne partent pas à la reprise ; module coupé : rien."""
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity
        from core.models import ModuleToggle
        facture = _facture_echue(self.co, 'FAC-AMSG75')
        facture.client.telephone = '+212612345678'
        facture.client.save(update_fields=['telephone'])
        regles = [AutomationRule.objects.create(
            company=self.co, nom=f'Relance {action}', enabled=True, trigger_type=TriggerType.FACTURE_OVERDUE,
            trigger_config={}, action_type=action, action_config={'subject': 'Relance', cle: 'Facture en attente'})
            for action, cle in ((ActionType.SEND_EMAIL, 'body'), (ActionType.SEND_WHATSAPP, 'message'))]
        with frozen(NUIT):
            with self.captureOnCommitCallbacks(execute=True):
                for regle in regles:
                    run_action(regle, facture, self.co)
                run_action(self.regle, self.lead, self.co)
        self.assertEqual(AutomationScheduledStep.objects.filter(company=self.co).count(), 3)
        Facture.objects.filter(pk=facture.pk).update(statut=Facture.Statut.PAYEE)
        ModuleToggle.objects.create(company=self.co, module='crm', actif=False)
        mail.outbox = []
        with frozen(LENDEMAIN):
            with self.captureOnCommitCallbacks(execute=True):
                process_due_automation_steps()
        self.assertEqual(mail.outbox, [])
        self.assertEqual(Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Facture), object_id=facture.pk).count(), 0)
        for regle in regles:
            dernier = AutomationRun.objects.filter(rule=regle).order_by('-id').first()
            self.assertEqual(dernier.status, AutomationRun.Status.SKIPPED)
            self.assertEqual(dernier.message, 'Facture soldée : relance sans objet.')
        dernier = AutomationRun.objects.filter(rule=self.regle).order_by('-id').first()
        self.assertEqual(dernier.status, AutomationRun.Status.SKIPPED)
        self.assertIn('Module désactivé (crm)', dernier.message)
        self.assertFalse(AutomationScheduledStep.objects.filter(
            company=self.co, statut=AutomationScheduledStep.Statut.EN_ATTENTE).exists())
