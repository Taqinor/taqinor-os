"""AGR540 — le comptage CADM7, découpé par segment, en LECTURE SEULE.

Imprime en JSON le bloc ``par_segment`` de la mesure de cadence
(``apps/crm/mesure_cadence.par_segment``, contrat ``mesure_cadence.json``)
pour UNE société. N'écrit RIEN : aucune ligne, aucun réglage, aucun seuil —
la commande sert à lire la production (accès en lecture déjà accordé) avant
toute révision du rythme (CAD52/CAD124).

    python manage.py mesurer_par_segment <slug> [--jours 90]
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('AGR540 — imprime la mesure de cadence par segment (JSON) pour '
            'une société, en lecture seule.')

    def add_arguments(self, parser):
        parser.add_argument('slug', help='Slug de la société.')
        parser.add_argument('--jours', type=int, default=None,
                            help='Profondeur en jours (défaut : celle de la '
                                 'mesure de cadence), bornée à [1, 365].')

    def handle(self, *args, **options):
        from authentication.models import Company

        from apps.crm.mesure_cadence import JOURS_MESURE_DEFAUT, par_segment

        company = Company.objects.filter(slug=options['slug']).first()
        if company is None:
            raise CommandError(
                f"Société inconnue : « {options['slug']} ».")
        jours = options.get('jours') or JOURS_MESURE_DEFAUT
        jours = max(1, min(365, int(jours)))
        resultat = {
            'societe': company.slug,
            'jours': jours,
            'par_segment': par_segment(company, jours=jours),
        }
        self.stdout.write(json.dumps(resultat, ensure_ascii=False, indent=2))
