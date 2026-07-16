"""NTCON4 — Sweep quotidien : alerte les RFI en retard (Celery beat).

Notifie le ``destinataire_user`` ET le créateur (``pose_par``) de tout
``RFI`` ``statut=ouvert`` dont ``date_limite_reponse`` est dépassée — UNE
SEULE notification par jour par RFI (idempotence via
``RFI.derniere_alerte_retard``, comparée à la date du jour). Les RFI
répondus/clos sont exclus (le sélecteur ``selectors.rfi_en_retard`` ne
retient que ``statut=ouvert``).

Run :
    python manage.py alertes_rfi_retard
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Notifie (best-effort) le destinataire et le créateur de tout RFI '
        'ouvert en retard — une seule alerte par jour par RFI (idempotent).'
    )

    def handle(self, *args, **options):
        from apps.btp_chantier.selectors import rfi_en_retard

        today = timezone.localdate()
        total = 0
        notifiees = 0
        for rfi in rfi_en_retard().select_related(
                'chantier', 'pose_par', 'destinataire_user'):
            total += 1
            if rfi.derniere_alerte_retard == today:
                continue  # déjà alerté aujourd'hui — idempotent
            self._alerter(rfi)
            with transaction.atomic():
                rfi.derniere_alerte_retard = today
                rfi.save(update_fields=['derniere_alerte_retard'])
            notifiees += 1

        self.stdout.write(self.style.SUCCESS(
            f'alertes_rfi_retard : {total} RFI en retard, '
            f'{notifiees} alerte(s) envoyée(s) (idempotent).'))

    def _alerter(self, rfi):
        from apps.btp_chantier.services import _notifier_btp

        titre = f'RFI #{rfi.numero} en retard de réponse'
        corps = (
            f'RFI #{rfi.numero} ({rfi.chantier}) — échéance '
            f'{rfi.date_limite_reponse} dépassée sans réponse.')
        link = f'/btp/rfi/{rfi.id}'
        destinataires = {rfi.destinataire_user, rfi.pose_par} - {None}
        for user in destinataires:
            _notifier_btp(
                user, 'APPROVAL_REMINDER', titre, corps,
                company=rfi.company, link=link)
