"""NTASS8 — Alertes de renouvellement des polices d'assurance d'entreprise.

Notifie J-60/J-30/J-7 (et échu) les rôles admin/compta de chaque société via
``apps.notifications.services.notify_many`` (in-app, respecte les
préférences de chaque destinataire)."""
import datetime

from django.core.management.base import BaseCommand

from authentication.models import Company, CustomUser

from apps.assurances.selectors import polices_expirantes

#: Horizons d'alerte (jours) — J-60/J-30/J-7 (NTASS8).
HORIZONS_ALERTE = [60, 30, 7]


def destinataires_admin_compta(company):
    """Utilisateurs admin/responsable de la société à notifier (NTASS8)."""
    return CustomUser.objects.filter(
        company=company, is_active=True,
    ).filter(is_superuser=True) | CustomUser.objects.filter(
        company=company, is_active=True, role_legacy='responsable')


class Command(BaseCommand):
    help = (
        "NTASS8 — notifie les polices d'assurance d'entreprise expirant "
        "sous J-60/J-30/J-7 (rôles admin/compta, via notifications.notify)."
    )

    def handle(self, *args, **options):
        from apps.notifications.services import notify_many

        total_notifiees = 0
        horizon_max = max(HORIZONS_ALERTE)
        for company in Company.objects.all():
            destinataires = list(destinataires_admin_compta(company).distinct())
            if not destinataires:
                continue
            # Une seule notification par police par exécution : chaque police
            # est classée sous le PLUS PETIT horizon qu'elle franchit (le plus
            # urgent), jamais une par horizon franchi (évite le triple envoi
            # d'une police à 5 jours de son échéance, qui matche 60/30/7).
            for police in polices_expirantes(company, within=horizon_max):
                horizon = next(
                    (h for h in sorted(HORIZONS_ALERTE)
                     if _sous_horizon(police, h)), horizon_max)
                notify_many(
                    destinataires, 'assurance_police_expirante',
                    title=(
                        f'Police {police.numero_police} expire le '
                        f'{police.date_echeance}'),
                    body=(
                        f'{police.get_type_police_display()} — '
                        f'échéance dans ≤ {horizon} jours.'),
                    company=company,
                    reason='alertes_expiration_assurances',
                )
                total_notifiees += 1
        self.stdout.write(self.style.SUCCESS(
            f'{total_notifiees} alerte(s) de renouvellement notifiée(s).'))


def _sous_horizon(police, horizon):
    """Vrai si ``police`` tombe sous l'horizon ``horizon`` (jours) à partir
    d'aujourd'hui (NTASS8 — classement au plus urgent des J-60/J-30/J-7)."""
    return police.date_echeance <= datetime.date.today() + datetime.timedelta(
        days=horizon)
