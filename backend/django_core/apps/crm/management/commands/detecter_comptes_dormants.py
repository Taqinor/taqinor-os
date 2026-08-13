"""NTCRM14 — Détection des comptes dormants (Celery Beat / cron quotidien).

Pour CHAQUE société, calcule les clients dormants (`crm.selectors.
comptes_dormants`) et notifie (`notifications.notify`) le commercial
propriétaire — au plus UNE fois par franchissement de seuil (anti-spam via
`Client.derniere_alerte_dormance`, NTCRM14). Best-effort par client : un
échec (notification, propriétaire introuvable) n'interrompt jamais le
traitement des autres clients.

    python manage.py detecter_comptes_dormants [--seuil 90] [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = ('NTCRM14 — Détecte les comptes dormants (aucune activité depuis '
            'le seuil) et notifie le commercial propriétaire, une seule '
            'fois par franchissement.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--seuil', type=int, default=90,
            help='Seuil de jours sans activité (défaut : 90).')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Liste ce qui serait fait sans écrire en base.')

    def handle(self, *args, **options):
        seuil = options['seuil']
        dry_run = options.get('dry_run', False)
        nb_alertes = detecter_comptes_dormants(seuil_jours=seuil, dry_run=dry_run)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[dry-run] {nb_alertes} compte(s) dormant(s) seraient alertés '
                f'(seuil {seuil}j).'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'{nb_alertes} compte(s) dormant(s) alerté(s) (seuil {seuil}j).'))


def detecter_comptes_dormants(seuil_jours=90, now=None, dry_run=False):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie le nombre de nouvelles alertes envoyées. Company-scopé : itère
    TOUTES les sociétés, chacune isolée. Idempotent : un client déjà alerté
    pour la dormance en cours (`derniere_alerte_dormance` postérieure à sa
    `derniere_activite`) n'est jamais réalerté."""
    from authentication.models import Company

    from apps.crm import selectors

    now = now or timezone.now()
    nb_alertes = 0

    for company in Company.objects.all():
        dormants = selectors.comptes_dormants(
            company, seuil_jours=seuil_jours, now=now)
        for entry in dormants:
            client = entry['client']
            derniere = entry['derniere_activite']
            # Anti-spam : déjà alerté APRÈS la dernière activité connue —
            # rien de nouveau à signaler tant que le client reste dormant.
            if (client.derniere_alerte_dormance is not None
                    and (derniere is None
                         or client.derniere_alerte_dormance.date() >= derniere)):
                continue
            nb_alertes += 1
            if not dry_run:
                _alerter(client, entry, now)

    return nb_alertes


def _alerter(client, entry, now):
    from .. import services as crm_services
    from ..models import Client, Lead

    Client.objects.filter(pk=client.pk).update(
        derniere_alerte_dormance=now)

    # Propriétaire = owner du lead le plus récent lié à ce client, sinon
    # repli sur le responsable assigné par défaut de la société.
    owner = (Lead.objects
             .filter(company=client.company, client=client, owner__isnull=False)
             .order_by('-date_creation')
             .values_list('owner', flat=True).first())
    if owner is not None:
        from authentication.models import CustomUser
        owner = CustomUser.objects.filter(pk=owner).first()
    if owner is None:
        try:
            owner = crm_services.default_responsable_for(client.company)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            owner = None

    if owner is None:
        return

    nom = f'{client.nom} {client.prenom or ""}'.strip()
    jours = entry['jours_inactivite']
    body = (f"{nom} n'a montré aucune activité depuis "
            f"{jours if jours is not None else 'toujours'} jour(s).")
    try:
        from apps.notifications.services import notify

        notify(
            owner, 'lead_assigned',
            f'Compte à réactiver : {nom}',
            body=body,
            link=f'/crm?client={client.pk}',
            company=client.company,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        pass
