"""NTCON28 — Sweep quotidien : recalcule le cache des pénalités par lot (Celery beat).

Recalcule ``selectors.penalites_retard_par_lot`` (NTCON15) pour tous les
chantiers portant AU MOINS un lot en retard actif et fige le résultat sur
``Lot.penalite_calculee_cache`` + ``penalite_calculee_le``, pour que le cockpit
(NTCON21) LISE au lieu de RECALCULER à chaque GET.

Aucune seconde formule : le calcul reste celui de NTCON15, on ne fait qu'en
figer une photo datée. Un cache absent ou périmé (> 36 h) fait retomber l'API
sur le calcul synchrone — jamais un chiffre périmé servi en silence.

Réellement planifié : ``btp_chantier.recalculer_penalites_lots`` dans
``erp_agentique/celery.py`` (queue ``scheduled``).

Run :
    python manage.py recalculer_penalites_lots              # lots en retard
    python manage.py recalculer_penalites_lots --tous       # tous les lots
    python manage.py recalculer_penalites_lots --chantier 7 # un chantier
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Recalcule et met en cache l'exposition aux pénalités de retard par "
        'lot (NTCON15) pour les chantiers ayant un lot en retard actif.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--tous', action='store_true',
            help='Recalculer TOUS les chantiers, pas seulement ceux en retard.')
        parser.add_argument(
            '--chantier', type=int, default=None,
            help="Recalculer UN seul chantier (recalcul manuel forcé).")

    def handle(self, *args, **options):
        from apps.btp_chantier.models import Lot
        from apps.btp_chantier.services import recalculer_penalites_lots

        chantier = None
        if options.get('chantier'):
            Chantier = Lot._meta.get_field('chantier').related_model
            chantier = Chantier.objects.filter(
                pk=options['chantier']).first()
            if chantier is None:
                raise CommandError(
                    f"Chantier #{options['chantier']} introuvable.")

        resultat = recalculer_penalites_lots(
            chantier=chantier, tous=bool(options.get('tous')))
        self.stdout.write(self.style.SUCCESS(
            f"recalculer_penalites_lots : {resultat['chantiers']} chantier(s), "
            f"{resultat['lots']} lot(s) mis en cache."))
