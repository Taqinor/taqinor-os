"""NTSRV38 — Rescan planifié des paliers d'escalade multi-niveaux.

Critère d'acceptation : deux exécutions SIMULTANÉES ne produisent jamais deux
notifications pour le même palier du même ticket.

Couvre aussi : la cadence au quart d'heure réellement câblée au beat, le
routage sur la file ``scheduled``, et le fait qu'un appel SÉQUENTIEL suivant
n'est PAS bloqué par le verrou (c'est un verrou, pas une clé d'idempotence à
durée fixe).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv38 -v 2
"""
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.notifications.models import Notification
from apps.sav.models import EscaladeSlaNiveau, SavSlaSettings, Ticket
from apps.sav.tasks import (
    scan_sla_breaches_quart_heure,
    scan_sla_pre_alerts_and_escalations_quotidien,
)

User = get_user_model()

TACHE_PRE_ALERTS = 'sav.scan_sla_pre_alerts_and_escalations_quotidien'
TACHE_BREACHES = 'sav.scan_sla_breaches_quart_heure'


class NTSRV38BeatCablageTest(TestCase):
    """Le beat EXISTE vraiment (la classe de panne : « (Celery beat) » en
    commentaire, aucune entrée réelle)."""

    def _entrees(self):
        from erp_agentique.celery import app
        return app.conf.beat_schedule

    def test_les_deux_balayages_sont_au_beat(self):
        taches = {e['task'] for e in self._entrees().values()}
        self.assertIn(TACHE_PRE_ALERTS, taches)
        self.assertIn(TACHE_BREACHES, taches)

    def test_cadence_au_quart_dheure(self):
        for entree in self._entrees().values():
            if entree['task'] in (TACHE_PRE_ALERTS, TACHE_BREACHES):
                minutes = entree['schedule'].minute
                self.assertEqual(
                    len(minutes), 4,
                    f"{entree['task']} : attendu 4 déclenchements par heure, "
                    f'obtenu {sorted(minutes)}')

    def test_routage_file_scheduled(self):
        for nom in (TACHE_PRE_ALERTS, TACHE_BREACHES):
            self.assertEqual(
                settings.CELERY_TASK_ROUTES[nom]['queue'], 'scheduled', nom)


class NTSRV38VerrouTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv38', defaults={'nom': 'Sav Co NTSRV38'})
        self.responsable = User.objects.create_user(
            username='ntsrv38_resp', password='x', role_legacy='normal',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV38')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV38-1',
            client=self.client_obj,
            statut=Ticket.Statut.EN_COURS, sla_due_at=date.today())
        self.palier = EscaladeSlaNiveau.objects.create(
            company=self.company, libelle='J+0 responsable', ordre=1,
            seuil_jours_apres_echeance=0,
            notifier_utilisateur=self.responsable)
        Notification.objects.all().delete()

    def tearDown(self):
        cache.clear()

    def _notifs(self):
        return Notification.objects.filter(recipient=self.responsable).count()

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_execution_concurrente_ne_double_notifie_pas(self):
        """Une 2ᵉ exécution PENDANT la 1ʳᵉ (verrou tenu) ne notifie rien."""
        # La 1ʳᵉ exécution est simulée en tenant le verrou qu'elle poserait.
        self.assertTrue(cache.add('sav-sla-scan:pre-alerts', 1, 600))
        resultat = scan_sla_pre_alerts_and_escalations_quotidien()
        self.assertEqual(resultat, {'skipped': True})
        self.assertEqual(self._notifs(), 0)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.sla_escalade_paliers_notifies or [], [])

        # Verrou relâché : le balayage suivant notifie UNE fois.
        cache.delete('sav-sla-scan:pre-alerts')
        resultat = scan_sla_pre_alerts_and_escalations_quotidien()
        self.assertEqual(resultat['escalations'], 1)
        self.assertEqual(self._notifs(), 1)

    def test_appel_sequentiel_suivant_non_bloque(self):
        """Le verrou est RELÂCHÉ en fin de tâche : le quart d'heure suivant
        tourne normalement (et reste idempotent par palier)."""
        premier = scan_sla_pre_alerts_and_escalations_quotidien()
        self.assertEqual(premier['escalations'], 1)
        second = scan_sla_pre_alerts_and_escalations_quotidien()
        self.assertNotIn('skipped', second)
        self.assertEqual(second['escalations'], 0)
        self.assertEqual(self._notifs(), 1)

    def test_verrou_relache_en_sortie_de_contexte(self):
        from apps.sav import tasks as sav_tasks

        with sav_tasks._verrou_scan('essai') as obtenu:
            self.assertTrue(obtenu)
            with sav_tasks._verrou_scan('essai') as concurrent:
                self.assertFalse(concurrent)
        # Relâché en sortie : le suivant l'obtient.
        with sav_tasks._verrou_scan('essai') as apres:
            self.assertTrue(apres)


class NTSRV38BreachesTest(TestCase):
    def setUp(self):
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv38b', defaults={'nom': 'Sav Co NTSRV38b'})
        self.technicien = User.objects.create_user(
            username='ntsrv38_tech', password='x', role_legacy='normal',
            company=self.company)
        reglages = SavSlaSettings.get(self.company)
        reglages.sla_breach_enabled = True
        reglages.save(update_fields=['sla_breach_enabled'])
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV38b')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV38-B1',
            client=self.client_obj,
            statut=Ticket.Statut.EN_COURS,
            technicien_responsable=self.technicien,
            sla_due_at=date(2020, 1, 1))
        Notification.objects.all().delete()

    def tearDown(self):
        cache.clear()

    def test_balayage_marque_le_depassement(self):
        resultat = scan_sla_breaches_quart_heure()
        self.assertEqual(resultat, {'skipped': False, 'tickets': 1})
        self.ticket.refresh_from_db()
        self.assertTrue(self.ticket.sla_breach)

    def test_execution_concurrente_ignoree(self):
        self.assertTrue(cache.add('sav-sla-scan:breaches', 1, 600))
        self.assertEqual(scan_sla_breaches_quart_heure(), {'skipped': True})
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.sla_breach)

    def test_verrous_distincts_par_balayage(self):
        """Le verrou des violations n'empêche pas celui des pré-alertes."""
        self.assertTrue(cache.add('sav-sla-scan:breaches', 1, 600))
        resultat = scan_sla_pre_alerts_and_escalations_quotidien()
        self.assertNotIn('skipped', resultat)
