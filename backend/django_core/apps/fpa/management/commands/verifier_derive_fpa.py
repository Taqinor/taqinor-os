"""NTFPA14 — commande cron-ready : vérifie la dérive des hypothèses de
recrutement (confirmées vs prévues) par cycle/département et notifie le
responsable FP&A (best-effort) au-delà du seuil de la société.

Cron-ready (réutilise le Celery beat existant — aucun scheduler nouveau). Ne
lève jamais : une notification en échec n'interrompt pas le balayage.
"""
from django.core.management.base import BaseCommand

from apps.fpa.models import CycleBudgetaire, Departement
from apps.fpa.selectors import derive_hypotheses


class Command(BaseCommand):
    help = 'Notifie les dérives de driver FP&A (>seuil) par cycle/département.'

    def handle(self, *args, **options):
        notifiees = 0
        cycles = CycleBudgetaire.objects.exclude(
            statut=CycleBudgetaire.Statut.CLOS)
        for cycle in cycles:
            for row in derive_hypotheses(cycle.company, cycle):
                if not row['depasse']:
                    continue
                dept = Departement.objects.filter(pk=row['departement_id']).first()
                destinataire = getattr(dept, 'responsable', None) if dept else None
                if destinataire is None:
                    continue
                try:
                    from apps.notifications.services import notify
                    notify(
                        destinataire, 'fpa_derive_driver',
                        title=f'Dérive budgétaire — {dept.nom}',
                        body=(f"L'écart entre masse salariale confirmée et prévue "
                              f"dépasse le seuil ({row['ecart_pct']:.0%})."),
                        company=cycle.company,
                    )
                    notifiees += 1
                except Exception:  # noqa: BLE001 — best-effort
                    continue
        self.stdout.write(self.style.SUCCESS(
            f'{notifiees} dérive(s) notifiée(s).'))
