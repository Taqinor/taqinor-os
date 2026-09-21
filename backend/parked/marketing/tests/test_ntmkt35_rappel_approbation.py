"""NTMKT35 — Tâche Celery beat « rappel d'approbation d'envoi en attente ».

Notifie (``notifications.Notification`` existant) l'approbateur désigné
(rôles admin/responsable) si une ``ApprobationEnvoiCampagne`` est en attente
depuis plus de 24h — une seule relance par demande (pas de doublon au run
suivant).
"""
import datetime

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from authentication.models import Company

from apps.marketing import services as mkt_services
from apps.marketing.models import ApprobationEnvoiCampagne, Campagne
from apps.notifications.models import Notification

User = get_user_model()


class RappelerApprobationsEnvoiTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt35', nom='NTMKT35')
        self.approbateur = User.objects.create_user(
            username='ntmkt35_approbateur', password='x',
            role_legacy='responsable', company=self.co)
        self.campagne = Campagne.objects.create(company=self.co, nom='Promo')
        # Mardi 10h — jour ouvré, hors fenêtre de silence, déterministe
        # (jamais un weekend/nuit selon le jour d'exécution du run, ARC29).
        self.maintenant = timezone.make_aware(
            datetime.datetime(2026, 8, 11, 10, 0),
            timezone.get_current_timezone())

    def _demande(self, il_y_a_heures):
        # ``date_creation`` est ``auto_now_add=True`` : on la recule ensuite
        # par un ``update()`` (bypass), la seule façon de simuler une demande
        # ancienne sans dépendre de l'horloge réelle du run.
        demande = ApprobationEnvoiCampagne.objects.create(
            company=self.co, campagne=self.campagne,
            nb_destinataires_demandes=500,
            statut=ApprobationEnvoiCampagne.Statut.EN_ATTENTE)
        ApprobationEnvoiCampagne.objects.filter(pk=demande.pk).update(
            date_creation=self.maintenant - datetime.timedelta(
                hours=il_y_a_heures))
        demande.refresh_from_db()
        return demande

    def test_demande_en_attente_depuis_25h_genere_une_notification(self):
        demande = self._demande(25)
        notifiees = mkt_services.rappeler_approbations_envoi_en_attente(
            self.co, maintenant=self.maintenant)
        self.assertEqual(notifiees, [demande.id])
        demande.refresh_from_db()
        self.assertIsNotNone(demande.rappel_envoye_le)
        self.assertEqual(
            Notification.objects.filter(recipient=self.approbateur).count(), 1)

    def test_demande_recente_ne_declenche_rien(self):
        self._demande(2)
        notifiees = mkt_services.rappeler_approbations_envoi_en_attente(
            self.co, maintenant=self.maintenant)
        self.assertEqual(notifiees, [])
        self.assertEqual(Notification.objects.count(), 0)

    def test_pas_de_doublon_au_run_suivant(self):
        self._demande(25)
        mkt_services.rappeler_approbations_envoi_en_attente(
            self.co, maintenant=self.maintenant)
        notifiees_2 = mkt_services.rappeler_approbations_envoi_en_attente(
            self.co, maintenant=self.maintenant + datetime.timedelta(hours=1))
        self.assertEqual(notifiees_2, [])
        self.assertEqual(
            Notification.objects.filter(recipient=self.approbateur).count(), 1)

    def test_demande_deja_approuvee_est_ignoree(self):
        demande = self._demande(48)
        demande.statut = ApprobationEnvoiCampagne.Statut.APPROUVE
        demande.save(update_fields=['statut'])
        notifiees = mkt_services.rappeler_approbations_envoi_en_attente(
            self.co, maintenant=self.maintenant)
        self.assertEqual(notifiees, [])

    def test_la_tache_beat_est_joignable(self):
        from apps.marketing.tasks import rappeler_approbations_envoi_task
        resultat = rappeler_approbations_envoi_task()
        self.assertIn('rappels', resultat)
