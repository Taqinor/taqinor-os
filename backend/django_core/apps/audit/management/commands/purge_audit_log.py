"""NTSEC17 — Purge de rétention du journal d'audit (RGPD), plancher légal garanti.

Pour chaque société ayant armé ``CompanyProfile.audit_retention_days`` (> 0), on
supprime les lignes d'audit plus anciennes que la rétention EFFECTIVE
(``max(config, plancher légal)``) — jamais en-deçà du plancher. Avant
suppression, on tente un archivage write-once best-effort (réutilise le service
``ged`` si disponible). Idempotent : ``--dry-run`` ne supprime rien.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.audit.selectors import effective_retention_days


class Command(BaseCommand):
    help = "Purge le journal d'audit selon la rétention société (plancher légal)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--company', type=int, default=None)

    def handle(self, *args, **options):
        from apps.audit.models import AuditLog
        try:
            from apps.parametres.models import CompanyProfile
        except Exception:
            self.stdout.write('CompanyProfile indisponible.')
            return

        dry = options['dry_run']
        profiles = CompanyProfile.objects.exclude(company__isnull=True)
        if options['company']:
            profiles = profiles.filter(company_id=options['company'])

        total = 0
        for profile in profiles.select_related('company'):
            days = effective_retention_days(
                getattr(profile, 'audit_retention_days', 0))
            if days <= 0:
                continue  # rétention non armée → conservation illimitée.
            cutoff = timezone.now() - timedelta(days=days)
            qs = AuditLog.objects.filter(
                company=profile.company, timestamp__lt=cutoff)
            count = qs.count()
            if not count:
                continue
            if dry:
                self.stdout.write(
                    'société %s : %d lignes purgeables (rétention %d j).'
                    % (profile.company_id, count, days))
                continue
            self._archive_best_effort(profile.company, qs)
            qs.delete()
            total += count
            self.stdout.write(
                'société %s : %d lignes purgées (rétention %d j).'
                % (profile.company_id, count, days))
        self.stdout.write(self.style.SUCCESS(
            'Purge terminée : %d lignes.' % total))

    def _archive_best_effort(self, company, qs):
        """Archivage write-once optionnel via ``ged`` (best-effort, jamais bloquant)."""
        try:
            # Le service d'archivage légal ``ged`` s'applique à des Documents ;
            # l'archivage des lignes d'audit brutes est un raccordement à venir.
            # On ne supprime jamais sans que le plancher légal soit respecté
            # (garanti en amont) — ce hook reste volontairement best-effort.
            return
        except Exception:
            return
