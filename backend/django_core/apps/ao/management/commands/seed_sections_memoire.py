"""AOF116 — seed IDEMPOTENT et ADDITIF de la bibliothèque de sections.

Les huit sections récurrentes d'un mémoire technique solaire en appel d'offres :
organisation, méthodologie, matériel, sécurité, planning, garanties,
maintenance, références.

ADDITIF : une section retouchée à la main survit à un rejeu. Aucun corps ne
porte de littéral chiffré — chaque grandeur est un ``{{ placeholder }}``
résolu depuis le contexte du dossier (AOF114/AOF133).

    python manage.py seed_sections_memoire [--company <slug>]
"""
from django.core.management.base import BaseCommand

from authentication.models import Company

from ...models import SectionMemoire

SECTIONS_MEMOIRE = (
    {
        'code': 'ORGANISATION',
        'titre': "Organisation de l'entreprise et moyens affectés",
        'corps': (
            "{{ soumissionnaire.raison_sociale }} affecte au marché "
            "{{ organisation.effectif_chantier }} intervenants encadrés par "
            "{{ organisation.conducteur_travaux }}. "
            "Les moyens matériels mobilisés sont détaillés en annexe."
        ),
    },
    {
        'code': 'METHODOLOGIE',
        'titre': "Méthodologie d'exécution",
        'corps': (
            "Les travaux se déroulent en {{ methodologie.nombre_phases }} "
            "phases sur {{ appel_offre.delai_execution_jours }} jours : "
            "{{ methodologie.phases }}. "
            "Chaque phase fait l'objet d'un point d'arrêt contradictoire."
        ),
    },
    {
        'code': 'MATERIEL',
        'titre': 'Matériel proposé',
        'corps': (
            "Modules : {{ equipements.module.designation }} "
            "({{ equipements.module.quantite }} unités). "
            "Onduleurs : {{ equipements.onduleur.designation }}. "
            "Stockage : {{ equipements.batterie.designation }}. "
            "Les fiches techniques constructeur sont annexées."
        ),
    },
    {
        'code': 'SECURITE',
        'titre': 'Sécurité et prévention',
        'corps': (
            "Le plan de prévention couvre le travail en hauteur, le risque "
            "électrique en courant continu et la co-activité. "
            "L'installation respecte la NF C 15-100 et les prescriptions du "
            "CPS. Responsable sécurité : {{ securite.responsable }}."
        ),
    },
    {
        'code': 'PLANNING',
        'titre': 'Planning prévisionnel',
        'corps': (
            "Démarrage à réception de l'ordre de service, achèvement à "
            "{{ appel_offre.delai_execution_jours }} jours. "
            "Jalons : {{ planning.jalons }}."
        ),
    },
    {
        'code': 'GARANTIES',
        'titre': 'Garanties',
        'corps': (
            "Garantie de bon fonctionnement de l'installation : "
            "{{ garanties.installation }}. "
            "Garanties constructeur : {{ garanties.constructeurs }}. "
            "Assurance responsabilité civile et décennale étanchéité en cours "
            "de validité."
        ),
    },
    {
        'code': 'MAINTENANCE',
        'titre': 'Maintenance et exploitation',
        'corps': (
            "Le contrat de maintenance prévoit {{ maintenance.visites_an }} "
            "visites annuelles, le nettoyage des modules et la supervision à "
            "distance via {{ maintenance.supervision }}. "
            "Délai d'intervention : {{ maintenance.delai_intervention }}."
        ),
    },
    {
        'code': 'REFERENCES',
        'titre': 'Références et attestations de bonne exécution',
        'corps': (
            "Références comparables : {{ references.tableau }}. "
            "Les attestations de bonne exécution correspondantes sont jointes "
            "au dossier administratif."
        ),
    },
)


def seeder_sections(company):
    """Crée les sections manquantes. Renvoie ``(crees, existants)``."""
    crees = existants = 0
    for ordre, gabarit in enumerate(SECTIONS_MEMOIRE):
        donnees = dict(gabarit)
        code = donnees.pop('code')
        if SectionMemoire.objects.filter(
                company=company, code=code).exists():
            existants += 1
            continue
        SectionMemoire.objects.create(
            company=company, code=code, ordre=ordre, **donnees)
        crees += 1
    return crees, existants


class Command(BaseCommand):
    help = "Seed idempotent des sections de mémoire technique (AOF116)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help='Slug de la société (toutes les sociétés par défaut).')

    def handle(self, *args, **options):
        societes = Company.objects.all()
        if options['company']:
            societes = societes.filter(slug=options['company'])
        total_crees = total_existants = 0
        for company in societes:
            crees, existants = seeder_sections(company)
            total_crees += crees
            total_existants += existants
            self.stdout.write(
                f'{company.slug} : {crees} section(s) créée(s), '
                f'{existants} déjà présente(s).')
        self.stdout.write(self.style.SUCCESS(
            f'seed_sections_memoire : {total_crees} section(s) créée(s), '
            f'{total_existants} inchangée(s).'))
