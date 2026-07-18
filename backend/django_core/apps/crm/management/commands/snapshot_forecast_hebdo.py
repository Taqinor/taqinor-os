"""NTCRM6 — Snapshot hebdomadaire du forecast (idempotent, Celery Beat).

Pour CHAQUE société, agrège les ``ForecastEntry`` courantes par catégorie et
crée/upsert un ``ForecastSnapshot`` pour la semaine ISO courante — un snapshot
SOCIÉTÉ (owner=None) et un snapshot PAR commercial ayant au moins une entrée.
Exécuter deux fois la même semaine ne crée JAMAIS de doublon (upsert sur la
contrainte unique company+semaine_iso+categorie+owner) :

    python manage.py snapshot_forecast_hebdo
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'NTCRM6 — Crée/upsert le snapshot forecast hebdomadaire (idempotent).'

    def handle(self, *args, **options):
        nb = snapshot_forecast_hebdo()
        self.stdout.write(self.style.SUCCESS(
            f'{nb} snapshot(s) de forecast créés/mis à jour.'))


def _semaine_iso(now=None):
    now = now or timezone.now()
    iso = now.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def snapshot_forecast_hebdo(now=None):
    """Cœur de la commande — appelable directement (tests, tâche Celery).
    Renvoie le nombre de lignes ``ForecastSnapshot`` créées/mises à jour."""
    from authentication.models import Company

    from apps.crm.models import ForecastEntry, ForecastSnapshot

    semaine = _semaine_iso(now)
    nb = 0
    for company in Company.objects.all():
        entries = (
            ForecastEntry.objects.filter(company=company)
            .select_related('lead', 'lead__owner')
        )
        # Agrégats société + par owner : {(categorie, owner_id): {'montant': D, 'nb': int}}
        buckets = {}
        for entry in entries:
            montant = entry.montant_effectif or 0
            owner_id = entry.lead.owner_id if entry.lead else None
            keys = {(entry.categorie, None)}  # snapshot société (owner=None)
            if owner_id is not None:
                keys.add((entry.categorie, owner_id))  # snapshot individuel
            for key in keys:
                bucket = buckets.setdefault(key, {'montant': 0, 'nb': 0})
                bucket['montant'] += montant
                bucket['nb'] += 1

        for (categorie, owner_id), agg in buckets.items():
            ForecastSnapshot.objects.update_or_create(
                company=company, semaine_iso=semaine, categorie=categorie,
                owner_id=owner_id,
                defaults={'montant_total': agg['montant'], 'nb_leads': agg['nb']},
            )
            nb += 1
    return nb
