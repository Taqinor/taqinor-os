"""NTWMS12 — libère les vagues de prélèvement dont la règle est atteinte.

IDEMPOTENTE : relancer la commande ne relance jamais une vague déjà lancée.
Plannifiable par Celery beat comme les autres jobs du module.

    python manage.py liberer_vagues_planifiees            # toutes les sociétés
    python manage.py liberer_vagues_planifiees --company 3
    python manage.py liberer_vagues_planifiees --dry-run
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Lance les vagues de prélèvement en mode AUTO_HEURE / AUTO_SEUIL "
            "dont la condition de libération est atteinte (idempotent).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (id). Défaut : toutes.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'écrit rien : affiche seulement ce qui serait libéré.")

    def handle(self, *args, **options):
        from apps.stock.services import liberer_vagues_planifiees
        from apps.stock.models import VaguePicking
        from authentication.models import Company

        company = None
        if options.get('company'):
            company = Company.objects.filter(id=options['company']).first()
            if company is None:
                self.stderr.write('Société introuvable.')
                return

        if options.get('dry_run'):
            qs = (VaguePicking.objects
                  .filter(statut=VaguePicking.Statut.BROUILLON)
                  .exclude(
                      mode_liberation=VaguePicking.ModeLiberation.MANUEL))
            if company is not None:
                qs = qs.filter(company=company)
            self.stdout.write(
                f'{qs.count()} vague(s) candidate(s) — aucune écriture '
                f'(--dry-run).')
            return

        resultat = liberer_vagues_planifiees(company=company)
        self.stdout.write(
            f"{len(resultat['liberees'])} vague(s) libérée(s) sur "
            f"{resultat['examinees']} examinée(s).")
        for reference in resultat['liberees']:
            self.stdout.write(f'  - {reference}')
