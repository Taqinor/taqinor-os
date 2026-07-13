"""NTSEC25 — Désactivation automatique des comptes dormants.

Pour chaque société ayant armé ``CompanyProfile.dormant_days`` (> 0), désactive
les comptes inactifs au-delà du seuil et révoque leurs sessions, après une
notification préalable au Directeur. Idempotent ; ``--dry-run`` ne modifie rien.
Seuil 0 = jamais. La réactivation reste manuelle (aucune suppression).
"""
from django.core.management.base import BaseCommand

from authentication.selectors import comptes_dormants, revoke_user_sessions


class Command(BaseCommand):
    help = "Désactive les comptes dormants selon le seuil société."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--company', type=int, default=None)

    def handle(self, *args, **options):
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
            seuil = getattr(profile, 'dormant_days', 0) or 0
            if seuil <= 0:
                continue
            dormants = list(comptes_dormants(profile.company, seuil))
            if not dormants:
                continue
            if dry:
                self.stdout.write(
                    'société %s : %d comptes dormants (seuil %d j).'
                    % (profile.company_id, len(dormants), seuil))
                continue
            self._notify_directeur(profile.company, dormants)
            for user in dormants:
                user.is_active = False
                user.save(update_fields=['is_active'])
                revoke_user_sessions(user)
                total += 1
            self.stdout.write(
                'société %s : %d comptes désactivés (seuil %d j).'
                % (profile.company_id, len(dormants), seuil))
        self.stdout.write(self.style.SUCCESS(
            'Terminé : %d comptes désactivés.' % total))

    def _notify_directeur(self, company, dormants):
        try:
            from apps.notifications.models import EventType
            from apps.notifications.services import notify, resolve_recipients
            noms = ', '.join(u.username for u in dormants[:20])
            for recipient in resolve_recipients(
                    company, EventType.SECURITY_ALERT):
                notify(recipient, EventType.SECURITY_ALERT,
                       'Comptes dormants désactivés',
                       body=f'{len(dormants)} compte(s) : {noms}',
                       company=company, respect_quiet_hours=False)
        except Exception:
            pass
