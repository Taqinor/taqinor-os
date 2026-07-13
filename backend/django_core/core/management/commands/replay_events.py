"""NTPLT13 — Rejeu ciblé d'événements outbox vers UN handler (support).

    python manage.py replay_events --company 3 --event devis_accepted \
        --depuis 2026-07-01 --handler crm_advance_stage --dry-run

Rejoue des ``OutboxEvent`` DÉJÀ LIVRÉS vers UN handler durable nommé — la
réparation type après le bug d'un abonné (les autres handlers ne sont pas
retouchés). GARDE-FOU : seuls les handlers déclarés ``rejouable=True`` au
``subscribe_durable`` sont éligibles ; sinon la commande refuse. ``--dry-run``
liste ce qui serait rejoué sans rien exécuter. ``core`` reste fondation :
aucun import d'app métier (le handler s'est enregistré lui-même dans son
``ready()``).
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = ("Rejoue des OutboxEvent déjà livrés vers UN handler durable nommé "
            "(rejouable=True obligatoire).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='ID de la société (optionnel : sinon toutes sociétés).')
        parser.add_argument(
            '--event', required=True,
            help="Nom de l'événement (ex. devis_accepted).")
        parser.add_argument(
            '--handler', required=True,
            help='Nom du handler durable cible (rejouable=True requis).')
        parser.add_argument(
            '--depuis', default=None,
            help='Date de début AAAA-MM-JJ (occurred_at >= ), optionnelle.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Liste sans exécuter.')

    def handle(self, *args, **options):
        from core import dispatch_outbox, events
        from core.models import OutboxEvent

        event_name = options['event']
        handler_name = options['handler']
        dry_run = options['dry_run']

        # Garde-fou d'éligibilité VÉRIFIÉ AVANT tout travail : le handler doit
        # être abonné à cet événement ET déclaré rejouable=True.
        entry = next(
            (e for e in events.durable_handlers(event_name)
             if e[0] == handler_name), None)
        if entry is None:
            raise CommandError(
                f"Handler '{handler_name}' non abonné à '{event_name}'.")
        if not entry[2]:
            raise CommandError(
                f"Handler '{handler_name}' n'est pas rejouable=True — "
                f"rejeu refusé (garde-fou NTPLT13).")

        qs = OutboxEvent.objects.filter(
            event_name=event_name, statut=OutboxEvent.STATUT_DELIVERED)
        if options['company'] is not None:
            qs = qs.filter(company_id=options['company'])
        depuis = options['depuis']
        if depuis:
            try:
                d = datetime.strptime(depuis, '%Y-%m-%d')
            except ValueError:
                raise CommandError('--depuis attend le format AAAA-MM-JJ.')
            d = timezone.make_aware(d) if timezone.is_naive(d) else d
            qs = qs.filter(occurred_at__gte=d)
        qs = qs.order_by('occurred_at')

        total = qs.count()
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] {total} événement(s) '{event_name}' seraient "
                f"rejoués vers '{handler_name}'."))
            return

        replayed = failed = 0
        for event in qs.iterator():
            ok = dispatch_outbox.replay_one_to_handler(event, handler_name)
            if ok:
                replayed += 1
            else:
                failed += 1
        self.stdout.write(self.style.SUCCESS(
            f"Rejeu vers '{handler_name}' : {replayed} réussi(s), "
            f"{failed} en échec sur {total} événement(s)."))
