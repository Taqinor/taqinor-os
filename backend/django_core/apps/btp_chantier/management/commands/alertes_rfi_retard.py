"""NTCON4 — Sweep quotidien : alerte les RFI en retard (Celery beat).

Notifie le ``destinataire_user`` ET le créateur (``pose_par``) de tout
``RFI`` ``statut=ouvert`` dont ``date_limite_reponse`` est dépassée — UNE
SEULE notification par jour par RFI (idempotence via
``RFI.derniere_alerte_retard``, comparée à la date du jour). Les RFI
répondus/clos sont exclus (le sélecteur ``selectors.rfi_en_retard`` ne
retient que ``statut=ouvert``).

AUD231 — ce balayage est désormais RÉELLEMENT planifié
(``btp_chantier.alertes_rfi_retard`` dans ``erp_agentique/celery.py``,
queue ``scheduled``) : la docstring ci-dessus l'annonçait depuis toujours alors
qu'aucune entrée de beat n'existait. Le corps du balayage vit dans
``services.alerter_rfi_en_retard`` — unique implémentation, partagée par cette
commande (à la demande) et par la tâche planifiée.

Run :
    python manage.py alertes_rfi_retard
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Notifie (best-effort) le destinataire et le créateur de tout RFI '
        'ouvert en retard — une seule alerte par jour par RFI (idempotent).'
    )

    def handle(self, *args, **options):
        from apps.btp_chantier.services import alerter_rfi_en_retard

        resultat = alerter_rfi_en_retard()
        self.stdout.write(self.style.SUCCESS(
            f"alertes_rfi_retard : {resultat['examines']} RFI en retard, "
            f"{resultat['alertes_envoyees']} alerte(s) envoyée(s) "
            f"(idempotent)."))
