"""NTRET23 — Click & Collect (XPOS15) : libère automatiquement les
réservations expirées (annule + ré-incrémente le stock si déjà sorti à la
préparation). IDEMPOTENTE — sûre à ré-exécuter (Celery beat ou cron manuel) :
un re-run immédiat ne retrouve aucune réservation à libérer (déjà ANNULE).

    python manage.py liberer_reservations_expirees
"""
from django.core.management.base import BaseCommand

from apps.pos import services


class Command(BaseCommand):
    help = ('NTRET23 — libère les réservations Click & Collect dont le '
            "délai d'expiration configuré (Paramètres POS) est dépassé : "
            'annule la commande et ré-incrémente le stock si déjà sorti. '
            'Idempotente — sûre pour Celery beat.')

    def handle(self, *args, **options):
        count = services.liberer_reservations_expirees()
        self.stdout.write(self.style.SUCCESS(
            f'{count} réservation(s) expirée(s) libérée(s).'))
