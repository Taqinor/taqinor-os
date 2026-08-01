"""AOF26 — seed IDEMPOTENT et ADDITIF du catalogue de kits de calepinage.

Trois kits de référence, un par société :

* ``AO-TABLE-PORTRAIT`` — table dos-à-dos, 2 modules PORTRAIT, pas 1,134 m,
  emprise 4,70 m DÉRIVÉE de ``2 × 2,382 × cos 15° + faîtage`` ;
* ``AO-TABLE-PAYSAGE`` — table dos-à-dos, 2 modules PAYSAGE, pas 2,382 m,
  emprise 2,25 m DÉRIVÉE de ``2 × 1,134 × cos 15° + faîtage`` ;
* ``VILLA-PANNEAU`` — panneau simple villa, 1 module 2,384 × 1,303, 720 Wc, 13°.

Ce sont les kits des bâtiments DÉJÀ approvisionnés : l'argument commercial
« nous posons ce que nous avons en stock » devient exploitable, à condition que
le catalogue le dise.

ADDITIF : la commande ne touche JAMAIS un kit existant (ni son produit lié, ni
une emprise figée). Rejouable sans effet de bord.

    python manage.py seed_ao_kits [--company <slug>]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from authentication.models import Company

from ...models import KitCalepinage

KITS_REFERENCE = (
    {
        'code': 'AO-TABLE-PORTRAIT',
        'libelle': 'Table dos-à-dos — 2 modules portrait (2 × 625 Wc)',
        'mode': KitCalepinage.Mode.TABLE_DOS_A_DOS,
        'modules_par_kit': 2,
        'pas_rangee_m': Decimal('1.134'),
        'longueur_pente_m': Decimal('2.382'),
        'faitage_m': Decimal('0.098'),
        'puissance_module_w': 625,
        'inclinaison_deg': Decimal('15.00'),
        'orientation_modules': KitCalepinage.Orientation.PORTRAIT,
        'emprise_mesuree_m': Decimal('4.700'),
    },
    {
        'code': 'AO-TABLE-PAYSAGE',
        'libelle': 'Table dos-à-dos — 2 modules paysage (2 × 625 Wc)',
        'mode': KitCalepinage.Mode.TABLE_DOS_A_DOS,
        'modules_par_kit': 2,
        'pas_rangee_m': Decimal('2.382'),
        'longueur_pente_m': Decimal('1.134'),
        'faitage_m': Decimal('0.059'),
        'puissance_module_w': 625,
        'inclinaison_deg': Decimal('15.00'),
        'orientation_modules': KitCalepinage.Orientation.PAYSAGE,
        'emprise_mesuree_m': Decimal('2.250'),
    },
    {
        'code': 'VILLA-PANNEAU',
        'libelle': 'Panneau simple villa — 1 module 720 Wc (2,384 × 1,303)',
        'mode': KitCalepinage.Mode.PANNEAU_SIMPLE,
        'modules_par_kit': 1,
        'pas_rangee_m': Decimal('1.303'),
        'longueur_pente_m': Decimal('2.384'),
        'faitage_m': Decimal('0.000'),
        'puissance_module_w': 720,
        'inclinaison_deg': Decimal('13.00'),
        'orientation_modules': KitCalepinage.Orientation.PORTRAIT,
    },
)


def seeder_kits(company):
    """Crée les kits manquants d'une société. Renvoie ``(crees, existants)``."""
    crees = existants = 0
    for gabarit in KITS_REFERENCE:
        donnees = dict(gabarit)
        code = donnees.pop('code')
        if KitCalepinage.objects.filter(
                company=company, code=code).exists():
            existants += 1
            continue
        kit = KitCalepinage(company=company, code=code, **donnees)
        kit.appliquer_emprise()
        kit.save()
        crees += 1
    return crees, existants


class Command(BaseCommand):
    help = "Seed idempotent et additif des kits de calepinage (AOF26)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Slug de la société (toutes les sociétés par défaut).')

    def handle(self, *args, **options):
        societes = Company.objects.all()
        if options['company']:
            societes = societes.filter(slug=options['company'])
        from ...services import seeder_presets

        total_crees = total_existants = total_presets = 0
        for company in societes:
            crees, existants = seeder_kits(company)
            presets = seeder_presets(company)
            total_crees += crees
            total_existants += existants
            total_presets += presets
            self.stdout.write(
                f'{company.slug} : {crees} kit(s) créé(s), '
                f'{existants} déjà présent(s), {presets} preset(s) créé(s).')
        self.stdout.write(self.style.SUCCESS(
            f'seed_ao_kits : {total_crees} kit(s) créé(s), '
            f'{total_existants} inchangé(s), '
            f'{total_presets} preset(s) créé(s).'))
