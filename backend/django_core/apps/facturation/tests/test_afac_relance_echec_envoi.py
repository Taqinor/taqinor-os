"""AFAC45 (C-AFAC-033) — une relance planifiée n'est consignée (RelanceLog,
avance du niveau) et un rappel pré-échéance / relevé mensuel n'est marqué
fait QUE si l'e-mail est réellement parti : un ``EmailLog`` en ``echec`` ne
consomme ni le niveau ni le marqueur, l'envoi est retenté au passage suivant.

Rejoue la sonde FREC-1 (3 passages sans e-mail ⇒ niveaux 1, 2, 3 consignés
et `prochaine_relance → None` ; SMTP en échec ⇒ niveau 1 consommé ;
pré-échéance et relevé jamais retentés). Beats réels ; seul
``email_service._send`` est simulé (comme la sonde).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_relance_echec_envoi"
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

_CTR = [0]
ECHEC = patch('apps.ventes.email_service._send',
              return_value=(False, 'SMTP down'))


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RelanceEchecEnvoiTests(TestCase):
    def setUp(self):
        from apps.ventes.recouvrement import ensure_default_followup_levels
        from apps.ventes.scheduled import casablanca_today
        from authentication.models import Company
        self.today = casablanca_today()
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC45 {n}', slug=f'afac45-{n}')
        ensure_default_followup_levels(self.company)

    def _client(self, email=''):
        from apps.crm.models import Client
        return Client.objects.create(
            company=self.company, nom=f'Client {_nxt()}', prenom='AFAC45',
            email=email, releve_mensuel_auto=True)

    def _facture(self, client, statut='en_retard', echeance=None, **kw):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC45-{_nxt():04d}',
            client=client, statut=statut, taux_tva=Decimal('20'),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'),
            date_echeance=echeance or self.today - timedelta(days=40), **kw)

    def _remettre_a_aujourdhui(self, facture):
        type(facture).objects.filter(pk=facture.pk).update(
            prochaine_relance=self.today)

    def test_sans_email_niveau_non_consomme(self):
        from apps.ventes.models import EmailLog, RelanceLog
        from apps.ventes.scheduled import relance_reminders
        f = self._facture(self._client(email=''),
                          prochaine_relance=self.today)
        for _ in range(3):
            relance_reminders()
            self._remettre_a_aujourdhui(f)
        self.assertFalse(RelanceLog.objects.filter(facture=f).exists())
        self.assertEqual(EmailLog.objects.filter(
            facture=f, statut=EmailLog.Statut.ECHEC).count(), 3)

    def test_trois_echecs_arretent_et_notifient(self):
        """AARG42 (C-AARG-045) — 3 échecs consécutifs : `prochaine_relance`
        à None et UNE notification au créateur ; 4e jour : rien ; un envoi
        réussi remet le compteur à zéro."""
        from django.contrib.auth import get_user_model
        from apps.notifications.models import Notification
        from apps.ventes.models import EmailLog
        from apps.ventes.scheduled import relance_reminders
        createur = get_user_model().objects.create_user(
            username=f'aarg42-{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        f = self._facture(self._client(email=''), created_by=createur,
                          prochaine_relance=self.today)
        for jour in range(4):
            relance_reminders()
            if jour < 2:
                self._remettre_a_aujourdhui(f)
        f.refresh_from_db()
        self.assertIsNone(f.prochaine_relance)
        self.assertEqual(EmailLog.objects.filter(
            facture=f, statut=EmailLog.Statut.ECHEC).count(), 3)
        notes = Notification.objects.filter(
            recipient=createur,
            title='Relance impossible : adresse e-mail du client à corriger')
        self.assertEqual(notes.count(), 1)
        # Un envoi réussi remet le compteur à zéro : un nouvel échec reporte.
        EmailLog.objects.create(
            company=self.company, facture=f, statut=EmailLog.Statut.ENVOYE,
            to_email='ok@example.invalid')
        self._remettre_a_aujourdhui(f)
        relance_reminders()
        f.refresh_from_db()
        self.assertGreater(f.prochaine_relance, self.today)
        self.assertEqual(notes.count(), 1)

    def test_report_au_jour_suivant(self):
        from apps.ventes.scheduled import relance_reminders
        f = self._facture(self._client(email=''),
                          prochaine_relance=self.today)
        relance_reminders()
        f.refresh_from_db()
        self.assertIsNotNone(f.prochaine_relance)
        self.assertGreater(f.prochaine_relance, self.today)

    def test_smtp_echec_niveau_non_consomme_puis_envoye(self):
        from apps.ventes.models import EmailLog, RelanceLog
        from apps.ventes.scheduled import relance_reminders
        f = self._facture(self._client(email=f'afac45-{_nxt()}@example.invalid'),
                          prochaine_relance=self.today)
        with ECHEC:
            relance_reminders()
        self.assertFalse(RelanceLog.objects.filter(facture=f).exists())
        self.assertTrue(EmailLog.objects.filter(
            facture=f, statut=EmailLog.Statut.ECHEC).exists())
        self._remettre_a_aujourdhui(f)
        relance_reminders()
        logs = list(RelanceLog.objects.filter(facture=f))
        self.assertEqual(len(logs), 1)
        # Le niveau 1 (le premier, le plus doux) part — pas le niveau 2.
        from apps.ventes.models import FollowupLevel
        premier = FollowupLevel.objects.filter(
            company=self.company).order_by('delai_jours', 'ordre').first()
        self.assertEqual(logs[0].niveau, premier.ordre)

    def test_backend_console_ne_consomme_ni_niveau_ni_marqueur(self):
        """AMSG29 (C-AMSG-008) — sous le backend console (la prod), rien ne
        part : 0 RelanceLog, 0 EmailLog, `prochaine_relance` intacte, aucun
        marqueur ni alerte AARG42, retour 0 pour les trois beats. Mutant :
        retirer le prédicat ⇒ EmailLog « envoye » + niveau 1 consommé."""
        from django.contrib.auth import get_user_model
        from apps.notifications.models import Notification
        from apps.ventes.models import EmailLog, RelanceLog
        from apps.ventes.scheduled import (
            pre_echeance_reminders, relance_reminders,
            releve_mensuel_reminders)
        createur = get_user_model().objects.create_user(
            username=f'amsg29-{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        client = self._client(email=f'amsg29-{_nxt()}@example.invalid')
        retard = self._facture(client, created_by=createur,
                               prochaine_relance=self.today)
        emise = self._facture(client, statut='emise',
                              echeance=self.today + timedelta(days=2))
        with self.settings(
                EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'):
            for _ in range(3):
                self.assertEqual(relance_reminders(), 0)
            self.assertEqual(pre_echeance_reminders(), 0)
            self.assertEqual(releve_mensuel_reminders(), 0)
        retard.refresh_from_db()
        emise.refresh_from_db()
        self.assertEqual(retard.prochaine_relance, self.today)
        self.assertFalse(RelanceLog.objects.filter(
            facture__in=[retard, emise]).exists())
        self.assertFalse(EmailLog.objects.filter(
            company=self.company).exists())
        self.assertFalse(Notification.objects.filter(
            recipient=createur).exists())

    def test_pre_echeance_retente_apres_echec(self):
        from apps.ventes.models import EmailLog
        from apps.ventes.scheduled import pre_echeance_reminders
        f = self._facture(
            self._client(email=f'afac45-{_nxt()}@example.invalid'),
            statut='emise', echeance=self.today + timedelta(days=5))
        with ECHEC:
            self.assertEqual(pre_echeance_reminders(), 0)
        self.assertEqual(pre_echeance_reminders(), 1)
        self.assertEqual(EmailLog.objects.filter(
            facture=f, statut=EmailLog.Statut.ENVOYE).count(), 1)
        # Une fois parti : jamais renvoyé.
        self.assertEqual(pre_echeance_reminders(), 0)

    def test_releve_mensuel_retente_apres_echec(self):
        from apps.ventes.models import EmailLog
        from apps.ventes.scheduled import releve_mensuel_reminders
        client = self._client(email=f'afac45-{_nxt()}@example.invalid')
        self._facture(client, statut='emise')
        with ECHEC:
            self.assertEqual(releve_mensuel_reminders(), 0)
        self.assertEqual(releve_mensuel_reminders(), 1)
        self.assertEqual(EmailLog.objects.filter(
            client=client, statut=EmailLog.Statut.ENVOYE).count(), 1)
        self.assertEqual(releve_mensuel_reminders(), 0)
