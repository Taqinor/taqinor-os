"""NTDATA35 — `seed_dashboards_modeles` : 3 dashboards partagés par société.

Direction (CA / marge / pipeline), Commerce (conversion / pipeline / panier),
Finance (DSO / CA TTC / marge) — chaque widget référence une MÉTRIQUE NOMMÉE
par sa clé (voir ``apps/semantic/dashboards_modeles.py``). Idempotente et
additive : un modèle déjà posé, édité ou non, n'est jamais réécrit. À lancer
après ``seed_metriques`` (qui sème les clés que ces widgets référencent).
"""
from django.core.management.base import BaseCommand

from apps.semantic.dashboards_modeles import semer_dashboards_modeles
from authentication.models import Company


class Command(BaseCommand):
    help = ("Sème les 3 dashboards modèles (Direction, Commerce, Finance) sur "
            "les métriques nommées (idempotent, additif : ne modifie JAMAIS "
            "un dashboard existant).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help="Identifiant d'une société précise (défaut : toutes).")

    def handle(self, *args, **options):
        societes = Company.objects.all()
        if options.get('company'):
            societes = societes.filter(pk=options['company'])
        total_crees = 0
        for company in societes:
            crees, intacts = semer_dashboards_modeles(company)
            total_crees += crees
            self.stdout.write(
                '%s : %d dashboard(s) modèle(s) créé(s), %d laissé(s) intact(s).'
                % (company.nom, crees, intacts))
        self.stdout.write(self.style.SUCCESS(
            'seed_dashboards_modeles : %d créé(s) sur %d société(s).'
            % (total_crees, societes.count())))
