"""SOL9 — `manage.py seed_plan_solaire` : crée/rafraîchit le plan « Solaire ».

Idempotent. N'assigne le plan à AUCUNE société : `CompanyProfile.plan` reste
posé par le founder (admin Django) ou par le gabarit de tenant Solaire (SOL10).
Sortie en français.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("Crée ou rafraîchit le plan de licence « Solaire » "
            "(tous les modules installables sauf les verticaux parqués). "
            "N'assigne le plan à aucune société.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--ne-pas-mettre-a-jour', action='store_true',
            help="Laisse un plan « Solaire » existant strictement intact "
                 "(ne réécrit pas modules_inclus).")

    def handle(self, *args, **options):
        from apps.adminops.plan_seeds import seed_plan_solaire

        plan, cree = seed_plan_solaire(
            mettre_a_jour=not options['ne_pas_mettre_a_jour'])
        modules = list(plan.modules_inclus or [])
        verbe = 'créé' if cree else 'à jour'
        self.stdout.write(
            f'Plan de licence « {plan.nom} » ({plan.code}) {verbe} : '
            f'{len(modules)} module(s) inclus.')
        self.stdout.write('  ' + ', '.join(modules))
        self.stdout.write(self.style.SUCCESS(
            "Aucune société modifiée — l'assignation du plan reste manuelle "
            "(admin Django) ou passe par le gabarit de tenant Solaire."))
