"""NTCON37 — Sweep quotidien : relance les visas en attente de revue (Celery beat).

Notifie le ``revu_par`` désigné ET son manager hiérarchique (lu via
``rh.selectors``, jamais ``rh.models``) pour tout ``VisaDocument``
``statut=soumis`` ou ``en_revue`` dont ``date_limite`` (calculée à partir de
``delai_revue_jours``) est dépassée — UNE SEULE relance par jour par visa
(idempotence via ``VisaDocument.derniere_relance_retard``).

La relance s'arrête d'elle-même à l'approbation ou au refus : le sélecteur
``selectors.visas_en_retard`` ne retient que les deux statuts OUVERTS, donc un
visa décidé n'est jamais examiné — aucun drapeau supplémentaire à gérer.

Même schéma que NTCON4 (``alertes_rfi_retard``). Réellement planifié :
``btp_chantier.alertes_visas_en_attente`` dans ``erp_agentique/celery.py``
(queue ``scheduled``). Le corps du balayage vit dans
``services.alerter_visas_en_attente``, unique implémentation partagée par cette
commande (à la demande) et par la tâche planifiée.

Run :
    python manage.py alertes_visas_en_attente
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Relance (best-effort) le revuseur et son manager pour tout visa '
        'soumis/en revue dont la date limite est dépassée — une seule '
        'relance par jour par visa (idempotent).'
    )

    def handle(self, *args, **options):
        from apps.btp_chantier.services import alerter_visas_en_attente

        resultat = alerter_visas_en_attente()
        self.stdout.write(self.style.SUCCESS(
            f"alertes_visas_en_attente : {resultat['examines']} visa(s) en "
            f"retard, {resultat['alertes_envoyees']} relance(s) envoyée(s) "
            f"(idempotent)."))
