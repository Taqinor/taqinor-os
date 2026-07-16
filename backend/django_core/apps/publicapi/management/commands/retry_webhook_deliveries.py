"""NTAPI8 — rejoue les livraisons webhook en échec selon la cascade PROGRAMMÉE
(1 min, 5 min, 30 min, 2 h, 6 h ; max 6 tentatives au total).

Idempotente : ne traite QUE les `WebhookDeliveryAttempt` dont
`prochain_essai_at` est échu ET `statut='en_attente'` — un run répété sans
nouvelle échéance due ne fait rien. Réutilise l'infra Celery-beat (FG368)
quand elle est provisionnée ; sinon appelable manuellement (cron externe ou
à la main) :

    python manage.py retry_webhook_deliveries
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.publicapi.models import WebhookDeliveryAttempt
from apps.publicapi.retry import run_due_retries


class Command(BaseCommand):
    help = ('NTAPI8 — rejoue les tentatives de livraison webhook '
            'programmées (cascade 1 min/5 min/30 min/2 h/6 h) échues.')

    def handle(self, *args, **options):
        now = timezone.now()
        results = run_due_retries(now=now)
        nb_succes = sum(
            1 for a in results if a.statut == WebhookDeliveryAttempt.Statut.SUCCES)
        nb_echec = len(results) - nb_succes
        self.stdout.write(self.style.SUCCESS(
            f'{len(results)} tentative(s) traitée(s) '
            f'({nb_succes} réussie(s), {nb_echec} en échec/reprogrammée(s)).'))
