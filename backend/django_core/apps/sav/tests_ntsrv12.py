"""NTSRV12 — Escalade SLA MULTI-NIVEAUX configurable (étend XSAV6).

Critère d'acceptation : deux paliers configurés déclenchent DEUX
notifications distinctes, à J+0 et J+1 — jamais avant.

Couvre aussi :
  * aucun palier configuré → comportement XSAV6 binaire strictement inchangé ;
  * idempotence par palier (le balayage du lendemain ne rejoue rien) ;
  * destinataires : utilisateur désigné > rôle visé > défaut de l'événement.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv12 -v 2
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.sav.models import EscaladeSlaNiveau, SavSlaSettings, Ticket
from apps.sav.views import scan_sla_pre_alerts_and_escalations

User = get_user_model()


class NTSRV12PaliersEscaladeTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv12', defaults={'nom': 'Sav Co NTSRV12'})
        self.responsable = User.objects.create_user(
            username='ntsrv12_resp', password='x', role_legacy='normal',
            company=self.company)
        self.directeur = User.objects.create_user(
            username='ntsrv12_dir', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV12')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV12-1',
            client=self.client_obj, statut=Ticket.Statut.EN_COURS,
            sla_due_at=date.today())

    def _paliers(self):
        p0 = EscaladeSlaNiveau.objects.create(
            company=self.company, libelle='J+0 responsable', ordre=1,
            seuil_jours_apres_echeance=0,
            notifier_utilisateur=self.responsable)
        p1 = EscaladeSlaNiveau.objects.create(
            company=self.company, libelle='J+1 direction', ordre=2,
            seuil_jours_apres_echeance=1,
            notifier_utilisateur=self.directeur)
        return p0, p1

    def _decaler_echeance(self, jours):
        """Simule le passage du temps en reculant l'échéance du ticket."""
        self.ticket.sla_due_at = date.today() - timedelta(days=jours)
        self.ticket.save(update_fields=['sla_due_at'])

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_deux_paliers_deux_notifications_a_j0_puis_j1(self):
        self._paliers()
        Notification.objects.all().delete()

        # J+0 : l'échéance est AUJOURD'HUI → seul le 1er palier se déclenche.
        r0 = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(r0['escalations'], 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.responsable).count(), 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.directeur).count(), 0)

        # J+1 (lendemain) : le 2ᵉ palier se déclenche, le 1er ne rejoue pas.
        self._decaler_echeance(1)
        r1 = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(r1['escalations'], 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.responsable).count(), 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.directeur).count(), 1)

    def test_jamais_avant_l_echeance(self):
        self._paliers()
        self.ticket.sla_due_at = date.today() + timedelta(days=1)
        self.ticket.save(update_fields=['sla_due_at'])
        Notification.objects.all().delete()
        self.assertEqual(
            scan_sla_pre_alerts_and_escalations()['escalations'], 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.ticket.refresh_from_db()
        self.assertIn(self.ticket.sla_escalade_paliers_notifies, (None, []))

    def test_idempotent_au_repassage(self):
        self._paliers()
        self.assertEqual(
            scan_sla_pre_alerts_and_escalations()['escalations'], 1)
        self.assertEqual(
            scan_sla_pre_alerts_and_escalations()['escalations'], 0)

    def test_paliers_memorises_sur_le_ticket(self):
        p0, _p1 = self._paliers()
        scan_sla_pre_alerts_and_escalations()
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.sla_escalade_paliers_notifies, [p0.pk])

    def test_deux_paliers_echus_le_meme_jour_se_declenchent_tous_les_deux(self):
        self._paliers()
        self._decaler_echeance(5)  # J+5 : les deux seuils sont franchis.
        self.assertEqual(
            scan_sla_pre_alerts_and_escalations()['escalations'], 2)

    def test_palier_inactif_ignore(self):
        p0, p1 = self._paliers()
        EscaladeSlaNiveau.objects.filter(pk=p0.pk).update(actif=False)
        Notification.objects.all().delete()
        self._decaler_echeance(5)
        self.assertEqual(
            scan_sla_pre_alerts_and_escalations()['escalations'], 1)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.sla_escalade_paliers_notifies, [p1.pk])

    # ── Non-régression XSAV6 ─────────────────────────────────────────────
    def test_aucun_palier_garde_le_binaire_xsav6(self):
        sla = SavSlaSettings.get(self.company)
        sla.escalade_activee = True
        sla.save(update_fields=['escalade_activee'])
        self._decaler_echeance(1)
        Notification.objects.all().delete()

        resultat = scan_sla_pre_alerts_and_escalations()
        self.assertEqual(resultat['escalations'], 1)
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.sla_escalade_notifiee)
        self.assertIn(self.ticket.sla_escalade_paliers_notifies, (None, []))

    def test_paliers_remplacent_le_binaire_pour_la_societe(self):
        sla = SavSlaSettings.get(self.company)
        sla.escalade_activee = True
        sla.save(update_fields=['escalade_activee'])
        self._paliers()
        self._decaler_echeance(1)

        scan_sla_pre_alerts_and_escalations()
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.sla_escalade_notifiee,
                         'le binaire XSAV6 ne double jamais les paliers')

    def test_defaut_aucun_palier(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv12-b', defaults={'nom': 'Autre'})
        self.assertEqual(
            EscaladeSlaNiveau.objects.filter(company=autre).count(), 0)

    # ── Destinataires ────────────────────────────────────────────────────
    def test_palier_par_role(self):
        EscaladeSlaNiveau.objects.create(
            company=self.company, libelle='Direction', ordre=1,
            seuil_jours_apres_echeance=0, notifier_role='admin')
        Notification.objects.all().delete()
        self.assertEqual(
            scan_sla_pre_alerts_and_escalations()['escalations'], 1)
        self.assertTrue(
            Notification.objects.filter(recipient=self.directeur).exists())
