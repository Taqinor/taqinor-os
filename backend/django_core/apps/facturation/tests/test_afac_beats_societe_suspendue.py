"""AFAC43 (C-AFAC-036) — les beats de recouvrement ignorent les sociétés
SUSPENDUES (``actif=False``) : bascule en retard, promesses expirées, relances,
rappels pré-échéance, relevés mensuels et les deux beats devis
(``send_devis_followup_nudges``, ``expire_stale_devis``) ne lisent que
``authentication.selectors.active_company_ids()`` (SCA19).

Rejoue les sondes FEVT-1 / FREC-4 (société suspendue : `emise -> en_retard`,
promesse rompue, relance + rappel + relevé envoyés). Beats réels, e-mail
locmem, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_beats_societe_suspendue"
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BeatsSocieteSuspendueTests(TestCase):
    def setUp(self):
        from apps.ventes.scheduled import casablanca_today
        self.today = casablanca_today()
        self.a = self._societe(actif=True)
        self.b = self._societe(actif=False)

    def _societe(self, actif):
        from apps.crm.models import Client
        from authentication.models import Company
        n = _nxt()
        company = Company.objects.create(
            nom=f'AFAC43 {n}', slug=f'afac43-{n}')
        client = Client.objects.create(
            company=company, nom=f'Client {n}', prenom='AFAC43',
            email=f'afac43-{n}@example.invalid', releve_mensuel_auto=True)
        ctx = {'company': company, 'client': client}
        ctx['echue'] = self._facture(
            company, client, 'emise', self.today - timedelta(days=40))
        ctx['en_retard'] = self._facture(
            company, client, 'en_retard', self.today - timedelta(days=40),
            prochaine_relance=self.today)
        ctx['pre_echeance'] = self._facture(
            company, client, 'emise', self.today + timedelta(days=5))
        from apps.ventes.models import PromessePaiement
        ctx['promesse'] = PromessePaiement.objects.create(
            company=company, facture=ctx['en_retard'],
            montant_promis=Decimal('500'),
            date_promise=self.today - timedelta(days=2),
            statut=PromessePaiement.Statut.EN_COURS)
        if not actif:
            # Suspension APRÈS la mise en place (le pont bool↔statut SCA18).
            Company.objects.filter(pk=company.pk).update(
                actif=False, statut='suspendu')
        return ctx

    def _facture(self, company, client, statut, echeance, **kw):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=company, reference=f'FAC-AFAC43-{_nxt():04d}',
            client=client, statut=statut, taux_tva=Decimal('20'),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'), date_echeance=echeance, **kw)

    def _statut(self, facture):
        return type(facture).objects.get(pk=facture.pk).statut

    def test_bascule_retard_societe_suspendue(self):
        from apps.ventes.scheduled import check_overdue_factures
        check_overdue_factures()
        self.assertEqual(self._statut(self.b['echue']), 'emise')
        self.assertEqual(self._statut(self.a['echue']), 'en_retard')

    def test_promesse_societe_suspendue(self):
        from apps.ventes.models import PromessePaiement
        from apps.ventes.scheduled import _check_promesses_expirees
        _check_promesses_expirees(self.today)
        self.assertEqual(
            PromessePaiement.objects.get(pk=self.b['promesse'].pk).statut,
            PromessePaiement.Statut.EN_COURS)
        self.assertEqual(
            PromessePaiement.objects.get(pk=self.a['promesse'].pk).statut,
            PromessePaiement.Statut.ROMPUE)

    def test_relance_societe_suspendue(self):
        from apps.ventes.models import EmailLog, RelanceLog
        from apps.ventes.scheduled import relance_reminders
        relance_reminders()
        self.assertFalse(RelanceLog.objects.filter(
            facture__company=self.b['company']).exists())
        self.assertFalse(EmailLog.objects.filter(
            client=self.b['client']).exists())
        self.assertTrue(RelanceLog.objects.filter(
            facture=self.a['en_retard']).exists())

    def test_pre_echeance_societe_suspendue(self):
        from apps.ventes.models import EmailLog
        from apps.ventes.scheduled import pre_echeance_reminders
        pre_echeance_reminders()
        self.assertFalse(EmailLog.objects.filter(
            facture=self.b['pre_echeance']).exists())
        self.assertTrue(EmailLog.objects.filter(
            facture=self.a['pre_echeance']).exists())

    def test_releve_mensuel_societe_suspendue(self):
        from django.core import mail
        from apps.ventes.models import EmailLog
        from apps.ventes.scheduled import releve_mensuel_reminders
        releve_mensuel_reminders()
        self.assertFalse(EmailLog.objects.filter(
            client=self.b['client']).exists())
        self.assertNotIn(self.b['client'].email,
                         [d for m in mail.outbox for d in m.to])
        self.assertTrue(EmailLog.objects.filter(
            client=self.a['client']).exists())

    def test_beats_devis_societe_suspendue(self):
        from apps.ventes.domain.recouvrement import (
            expire_stale_devis, send_devis_followup_nudges,
        )
        from apps.ventes.models import Devis
        from django.utils import timezone
        devis = Devis.objects.create(
            company=self.b['company'], reference=f'DEV-AFAC43-{_nxt()}',
            client=self.b['client'], statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'),
            date_envoi=timezone.now() - timedelta(days=400))
        Devis.objects.filter(pk=devis.pk).update(
            date_validite=self.today - timedelta(days=200))
        send_devis_followup_nudges()
        expire_stale_devis()
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertFalse(devis.nudge_logs.exists())

    def test_societe_active_temoin(self):
        """Réactiver B ⇒ le passage suivant la traite."""
        from authentication.models import Company
        from apps.ventes.scheduled import check_overdue_factures
        Company.objects.filter(pk=self.b['company'].pk).update(
            actif=True, statut='actif')
        check_overdue_factures()
        self.assertEqual(self._statut(self.b['echue']), 'en_retard')
