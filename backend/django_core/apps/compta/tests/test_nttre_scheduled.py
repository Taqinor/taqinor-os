"""Tests NTTRE29/31 — tâches planifiées trésorerie (Celery Beat)."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import LignePrevisionnelTresorerie
from apps.compta.scheduled import (
    recalculer_alerte_rupture, relances_tresorerie_du_jour)

User = get_user_model()


class AlerteRuptureTaskTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='nttre29', defaults={'nom': 'NTTRE29 Co'})
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        User.objects.create_user(
            username='nttre29-admin', password='x', company=self.co,
            role_legacy='admin')
        # Gros décaissement la semaine prochaine → rupture imminente.
        lundi = timezone.localdate() - timedelta(
            days=timezone.localdate().weekday())
        LignePrevisionnelTresorerie.objects.create(
            company=self.co, libelle='Gros décaissement',
            date_prevue=lundi + timedelta(days=1), montant=Decimal('-50000'))

    def test_notifie_une_seule_fois_par_jour(self):
        from apps.notifications.models import Notification
        first = recalculer_alerte_rupture()
        self.assertEqual(first, 1)
        avant = Notification.objects.filter(company=self.co).count()
        self.assertGreaterEqual(avant, 1)
        # Deuxième exécution le même jour : aucune nouvelle notification (dedup).
        second = recalculer_alerte_rupture()
        self.assertEqual(second, 0)
        apres = Notification.objects.filter(company=self.co).count()
        self.assertEqual(avant, apres)


class RelancesTaskTests(TestCase):
    def test_relances_du_jour_sans_erreur(self):
        co, _ = Company.objects.get_or_create(
            slug='nttre31', defaults={'nom': 'NTTRE31 Co'})
        # Sans plan ni facture en retard : la tâche tourne et renvoie 0.
        self.assertEqual(relances_tresorerie_du_jour(), 0)
