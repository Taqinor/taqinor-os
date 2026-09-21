"""NTGRC33 — seed IDEMPOTENT des cadres de conformité et de leurs exigences.

Installe, pour chaque société (ou une seule via ``--company``), deux cadres de
départ : la **loi 09-08** (obligatoire au Maroc — c'est elle qui doit exister
même quand personne n'a rien configuré) et un squelette **ISO 27001**.
Rejouable sans doublon : ``update_or_create`` sur ``(company, code)`` et sur
``(cadre, code_exigence)``.

Ce que le seed NE TOUCHE JAMAIS : ``actif`` d'un cadre, ni ``controle_ref`` /
``statut_couverture`` d'une exigence. Ce sont les colonnes que la société
renseigne elle-même — les réécrire à chaque passage effacerait le mapping vers
les contrôles internes, c'est-à-dire tout le travail.
"""
from django.core.management.base import BaseCommand

from apps.grc.models import CadreConformite, ExigenceCadre
from authentication.models import Company

CADRES = [
    {
        'code': CadreConformite.CODE_LOI_09_08,
        'intitule': 'Loi 09-08 relative à la protection des personnes '
                    'physiques à l\'égard du traitement des données à '
                    'caractère personnel',
        'exigences': [
            ('09-08-A1', 'Déclaration préalable des traitements à la CNDP'),
            ('09-08-A2', 'Information des personnes concernées'),
            ('09-08-A3', "Recueil du consentement lorsqu'il est requis"),
            ('09-08-A4', "Exercice des droits (accès, rectification, "
                         'opposition)'),
            ('09-08-A5', 'Sécurité et confidentialité des traitements'),
            ('09-08-A6', 'Encadrement des transferts hors du Maroc'),
            ('09-08-A7', 'Encadrement contractuel des sous-traitants'),
            ('09-08-A8', 'Durées de conservation et destruction'),
        ],
    },
    {
        'code': CadreConformite.CODE_ISO27001,
        'intitule': 'ISO/IEC 27001 — système de management de la sécurité de '
                    "l'information (squelette)",
        'exigences': [
            ('A.5', 'Politiques de sécurité de l\'information'),
            ('A.6', "Organisation de la sécurité de l'information"),
            ('A.7', 'Sécurité des ressources humaines'),
            ('A.8', 'Gestion des actifs'),
            ('A.9', "Contrôle d'accès"),
            ('A.12', "Sécurité liée à l'exploitation"),
            ('A.16', "Gestion des incidents de sécurité de l'information"),
            ('A.18', 'Conformité'),
        ],
    },
]


class Command(BaseCommand):
    help = ('Seed idempotent des cadres de conformité (NTGRC33) : loi 09-08 '
            '+ squelette ISO 27001.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='ID de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        company_id = options.get('company')
        if company_id:
            companies = Company.objects.filter(pk=company_id)
        else:
            companies = Company.objects.all()

        cadres = exigences = 0
        for company in companies:
            for spec in CADRES:
                # `actif` est volontairement ABSENT des defaults.
                cadre, cree = CadreConformite.objects.update_or_create(
                    company=company, code=spec['code'],
                    defaults={'intitule': spec['intitule']})
                if cree:
                    cadres += 1
                for code_exigence, intitule in spec['exigences']:
                    # `controle_ref` et `statut_couverture` appartiennent à la
                    # société : le seed ne les réécrit jamais.
                    _, cree_exigence = ExigenceCadre.objects.update_or_create(
                        company=company, cadre=cadre,
                        code_exigence=code_exigence,
                        defaults={'intitule': intitule})
                    if cree_exigence:
                        exigences += 1
        self.stdout.write(self.style.SUCCESS(
            f'Cadres de conformité : {cadres} créé(s), '
            f'{exigences} exigence(s) créée(s).'))
