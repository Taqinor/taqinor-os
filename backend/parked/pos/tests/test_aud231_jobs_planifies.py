"""AUD231 — huit balayages « écrits pour Celery beat » et planifiés NULLE PART.

Défaut d'origine (grep sur ``erp_agentique/`` : ZÉRO occurrence) : huit
commandes de gestion annonçaient dans leur docstring « Plannifiable par Celery
beat » / « cron / Celery beat » / « Sweep quotidien … (Celery beat) » alors
qu'aucune entrée de ``beat_schedule`` ni aucune tâche Celery n'existait. Elles
ne tournaient que si quelqu'un les lançait à la main. Conséquence la plus
visible et la plus coûteuse : une réservation Click & Collect expirée n'était
JAMAIS libérée — son stock restait réservé indéfiniment — alors que
``apps/pos/models.py`` AFFIRMAIT le contraire en commentaire.

S'y ajoutait une entrée de beat DUPLIQUÉE : ``reporting.email_saved_reports``
était planifié deux fois (quotidien 6 h 00 ET hebdomadaire lundi 6 h 00) pour
une tâche SANS argument qui décide elle-même des rapports dus — donc rejouée
une 2ᵉ fois chaque lundi à la même minute.

Test ROUGE avant le correctif : ``test_une_reservation_expiree_est_liberee_
par_le_job_planifie`` (le job n'existait pas) et
``test_les_huit_balayages_sont_planifies``.

La récidive est fermée par la garde ``scripts/check_commandes_planifiees.py``
(généralisation de WIR25 à TOUTES les apps ; QX11 ne voit que les
``@shared_task``, jamais une commande sans tâche).

Run :
    python manage.py test core.tests.test_aud231_jobs_planifies -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

User = get_user_model()

#: Les huit balayages nommés par AUD231 (3 stock/POS + 5 signalés par R3).
HUIT_BALAYAGES = (
    'stock.generer_comptages_tournants',
    'stock.liberer_vagues_planifiees',
    'pos.liberer_reservations_expirees',
    'installations.generer_interventions_recurrentes',
    'gestion_projet.generer_taches_recurrentes',
    'gestion_projet.alertes_retards_projets',
    'gestion_projet.rappels_timesheets',
    'btp_chantier.alertes_rfi_retard',
)


def _entrees_beat():
    from erp_agentique.celery import app
    return list(app.conf.beat_schedule.values())


class BeatScheduleTests(TestCase):
    def test_les_huit_balayages_sont_planifies(self):
        planifiees = {e['task'] for e in _entrees_beat()}
        for nom in HUIT_BALAYAGES:
            self.assertIn(nom, planifiees,
                          f'{nom} absent du beat_schedule — il ne tournera '
                          f'jamais.')

    def test_les_huit_sont_routes_vers_la_file_scheduled(self):
        for nom in HUIT_BALAYAGES:
            self.assertIn(nom, settings.CELERY_TASK_ROUTES, nom)
            self.assertEqual(
                settings.CELERY_TASK_ROUTES[nom]['queue'], 'scheduled', nom)

    def test_email_saved_reports_napparait_quune_seule_fois(self):
        doublons = [e for e in _entrees_beat()
                    if e['task'] == 'reporting.email_saved_reports']
        self.assertEqual(len(doublons), 1)

    def test_aucune_tache_nest_planifiee_deux_fois(self):
        """Le doublon `reporting.email_saved_reports` était le seul ; ce test
        empêche qu'un autre s'installe."""
        noms = [e['task'] for e in _entrees_beat()]
        doublons = sorted({n for n in noms if noms.count(n) > 1})
        self.assertEqual(doublons, [])


class EnveloppesJoignablesTests(TestCase):
    """Chaque enveloppe est appelable et NO-OP sans donnée (idempotence : un
    beat qui explose au premier tick ne vaut pas mieux qu'un beat absent)."""

    def test_les_huit_enveloppes_tournent_a_vide_sans_erreur(self):
        from apps.btp_chantier.tasks import alertes_rfi_retard_task
        from apps.gestion_projet.tasks import (
            alertes_retards_projets_task, generer_taches_recurrentes_task,
            rappels_timesheets_task,
        )
        from apps.installations.tasks import (
            generer_interventions_recurrentes_task,
        )
        from apps.pos.tasks import liberer_reservations_expirees_task
        from apps.stock.tasks import (
            generer_comptages_tournants_task, liberer_vagues_planifiees_task,
        )

        Company.objects.get_or_create(
            slug='aud231-co', defaults={'nom': 'AUD231 Co'})
        for enveloppe in (
            generer_comptages_tournants_task, liberer_vagues_planifiees_task,
            liberer_reservations_expirees_task,
            generer_interventions_recurrentes_task,
            generer_taches_recurrentes_task, alertes_retards_projets_task,
            rappels_timesheets_task, alertes_rfi_retard_task,
        ):
            self.assertEqual(enveloppe(), 0, enveloppe.name)

    def test_les_enveloppes_portent_le_nom_planifie(self):
        from apps.btp_chantier.tasks import alertes_rfi_retard_task
        from apps.pos.tasks import liberer_reservations_expirees_task
        from apps.stock.tasks import liberer_vagues_planifiees_task

        self.assertEqual(liberer_vagues_planifiees_task.name,
                         'stock.liberer_vagues_planifiees')
        self.assertEqual(liberer_reservations_expirees_task.name,
                         'pos.liberer_reservations_expirees')
        self.assertEqual(alertes_rfi_retard_task.name,
                         'btp_chantier.alertes_rfi_retard')


class ReservationClickAndCollectTests(TestCase):
    """Le scénario métier d'AUD231 : une réservation expirée doit être libérée
    PAR LE JOB PLANIFIÉ, pas seulement par une commande lancée à la main."""

    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Categorie, Produit

        self.co, _ = Company.objects.get_or_create(
            slug='aud231-pos', defaults={'nom': 'AUD231 POS'})
        self.user = User.objects.create_user(
            username='aud231-magasinier', password='x', company=self.co,
            role_legacy='responsable')
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(
            company=self.co, nom='Accessoires AUD231')
        self.produit = Produit.objects.create(
            company=self.co, nom='Régulateur AUD231',
            prix_vente=Decimal('300'), prix_achat=Decimal('150'),
            quantite_stock=15, categorie=categorie)

    def _reservation_expiree(self):
        from apps.pos.models import CommandeRetrait, LigneCommandeRetrait

        commande = CommandeRetrait.objects.create(
            company=self.co, reference='RET-AUD231-1',
            client=self.client_obj, created_by=self.user)
        LigneCommandeRetrait.objects.create(
            commande=commande, produit=self.produit, quantite=3)
        commande.date_expiration_reservation = (
            timezone.now() - timedelta(hours=1))
        commande.save(update_fields=['date_expiration_reservation'])
        return commande

    def test_une_reservation_expiree_est_liberee_par_le_job_planifie(self):
        from apps.pos.models import CommandeRetrait
        from apps.pos.tasks import liberer_reservations_expirees_task

        commande = self._reservation_expiree()

        liberees = liberer_reservations_expirees_task()

        commande.refresh_from_db()
        self.assertEqual(liberees, 1)
        self.assertEqual(commande.statut, CommandeRetrait.Statut.ANNULE)

    def test_le_job_est_idempotent(self):
        from apps.pos.tasks import liberer_reservations_expirees_task

        self._reservation_expiree()

        self.assertEqual(liberer_reservations_expirees_task(), 1)
        # Un second tick immédiat ne retrouve plus rien à libérer.
        self.assertEqual(liberer_reservations_expirees_task(), 0)

    def test_une_reservation_non_expiree_nest_pas_touchee(self):
        from apps.pos.models import CommandeRetrait
        from apps.pos.tasks import liberer_reservations_expirees_task

        commande = self._reservation_expiree()
        commande.date_expiration_reservation = (
            timezone.now() + timedelta(days=1))
        commande.save(update_fields=['date_expiration_reservation'])

        self.assertEqual(liberer_reservations_expirees_task(), 0)
        commande.refresh_from_db()
        self.assertEqual(commande.statut, CommandeRetrait.Statut.A_PREPARER)
