"""AOF116 — seed IDEMPOTENT et ADDITIF du gabarit de pack de dépôt.

Le pack RÉEL d'un dossier de réponse solaire marocain, tel que déposé :

    00 checklist partenaire · 01 lettre de soumission · 02 mémoire technique ·
    03 note de calcul · 04 bordereau des prix · 05 simulation 25 ans ·
    06 planches A3 · 07 annexe fiches techniques · 08 dossier administratif

ADDITIF : la commande ne touche JAMAIS une pièce existante (un gabarit
retouché à la main survit à un rejeu). Rejouable sans doublon — l'unicité
``(modele, code)`` est en base, la commande ne s'y fie pas seule.

Aucun gabarit ne contient de littéral chiffré : chaque montant, chaque
quantité, chaque durée est un ``{{ placeholder }}`` résolu depuis le contexte
calculé du dossier (``apps.ao.fabrique.gabarits.valider_gabarit`` le vérifie).

    python manage.py seed_pack_ao [--company <slug>]
"""
from django.core.management.base import BaseCommand

from authentication.models import Company

from ...models import ModelePack, PieceDossierAO, PieceModele

#: Code du gabarit de pack de référence.
CODE_PACK = 'AO-DEPOT-SOLAIRE'

_CLIENT = PieceDossierAO.Visibilite.CLIENT
_INTERNE = PieceDossierAO.Visibilite.INTERNE

PIECES_PACK = (
    {
        'code': '00',
        'libelle': 'Checklist partenaire',
        'generateur': 'checklist',
        'format': PieceModele.Format.DOCX,
        'visibilite': _INTERNE,
        'gabarit': (
            'Checklist de remise — {{ appel_offre.reference_acheteur }}\n'
            'Soumissionnaire : {{ soumissionnaire.raison_sociale }}\n'
            'Remise des plis : {{ appel_offre.date_limite }}\n'
            'Exemplaires à remettre : {{ appel_offre.nombre_exemplaires }}'
        ),
    },
    {
        'code': '01',
        'libelle': 'Lettre de soumission',
        'generateur': 'lettre_soumission',
        'format': PieceModele.Format.PDF,
        'gabarit': (
            'Objet : {{ appel_offre.objet }}\n'
            "Le soumissionnaire {{ soumissionnaire.raison_sociale }} s'engage "
            'à exécuter les travaux pour un montant de '
            '{{ bordereau.total_ttc }} MAD TTC '
            '({{ bordereau.total_ttc_lettres }}).\n'
            "Validité de l'offre : {{ appel_offre.validite_offre_jours }} "
            'jours.\n{{ bordereau.clause_reserve }}'
        ),
    },
    {
        'code': '02',
        'libelle': 'Mémoire technique',
        'generateur': 'memoire',
        'format': PieceModele.Format.PDF,
        'gabarit': (
            'Mémoire technique — {{ appel_offre.objet }}\n'
            'Puissance installée : {{ etude.puissance_kwc }} kWc sur '
            '{{ etude.nombre_batiments }} bâtiment(s).\n'
            '{{ memoire.sections_rendues }}'
        ),
    },
    {
        'code': '03',
        'libelle': 'Note de calcul',
        'generateur': 'note_calcul',
        'format': PieceModele.Format.PDF,
        'gabarit': (
            'Note de calcul — {{ appel_offre.reference }}\n'
            'Modules : {{ etude.nombre_modules }} × '
            '{{ etude.puissance_module_w }} W.\n'
            'Productible retenu : {{ etude.productible_kwh_an }} kWh/an '
            '(source : {{ etude.productible_source }}).'
        ),
    },
    {
        'code': '04',
        'libelle': 'Bordereau des prix',
        'generateur': 'bordereau',
        'format': PieceModele.Format.PDF,
        'gabarit': (
            'Bordereau des prix — indice {{ bordereau.indice_revision }}\n'
            'Sous-total HT : {{ bordereau.sous_total_ht }} MAD\n'
            'Total HT : {{ bordereau.total_ht }} MAD\n'
            'Total TTC : {{ bordereau.total_ttc }} MAD\n'
            '{{ bordereau.clause_reserve }}'
        ),
    },
    {
        'code': '05',
        'libelle': 'Simulation de rentabilité',
        'generateur': 'simulation',
        'format': PieceModele.Format.XLSX,
        'gabarit': (
            'Simulation sur {{ simulation.duree_annees }} ans\n'
            'CAPEX hors stockage : {{ simulation.capex_hors_stockage }} MAD\n'
            'Retour simple : {{ simulation.payback_simple_ans }} ans\n'
            'Retour actualisé : {{ simulation.payback_actualise_ans }} ans'
        ),
    },
    {
        'code': '06',
        'libelle': 'Planches A3',
        'generateur': 'planches',
        'format': PieceModele.Format.PDF_A3,
        'gabarit': (
            'Planches d\'implantation — {{ planches.codes }}\n'
            'Engagement porté : {{ planches.modules_engages }} modules.'
        ),
    },
    {
        'code': '07',
        'libelle': 'Annexe — fiches techniques',
        'generateur': 'annexes',
        'format': PieceModele.Format.PDF,
        'gabarit': (
            'Fiches techniques des équipements actifs :\n'
            '{{ annexes.index }}'
        ),
    },
    {
        'code': '08',
        'libelle': 'Dossier administratif',
        'generateur': 'administratif',
        'format': PieceModele.Format.PDF,
        'gabarit': (
            'Pièces administratives de {{ soumissionnaire.raison_sociale }} '
            '(ICE {{ soumissionnaire.ice }}) :\n'
            '{{ administratif.index }}'
        ),
    },
)


def seeder_pack(company):
    """Crée le gabarit de pack manquant. Renvoie ``(crees, existants)``."""
    modele, _ = ModelePack.objects.get_or_create(
        company=company, code=CODE_PACK,
        defaults={
            'libelle': 'Pack de dépôt — réponse solaire (marché public)',
            'description': (
                'Neuf pièces, dans l\'ordre du sommaire remis. '
                'Ajouter une pièce ici l\'ajoute au sommaire (AOF139) et au '
                'manifeste, sans intervention.'),
        })
    crees = existants = 0
    for ordre, gabarit in enumerate(PIECES_PACK):
        donnees = dict(gabarit)
        code = donnees.pop('code')
        if PieceModele.objects.filter(modele=modele, code=code).exists():
            existants += 1
            continue
        PieceModele.objects.create(
            company=company, modele=modele, code=code, ordre=ordre,
            visibilite=donnees.pop('visibilite', _CLIENT), **donnees)
        crees += 1
    return crees, existants


class Command(BaseCommand):
    help = "Seed idempotent et additif du gabarit de pack de dépôt (AOF116)."

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
            crees, existants = seeder_pack(company)
            total_crees += crees
            total_existants += existants
            self.stdout.write(
                f'{company.slug} : {crees} pièce(s) créée(s), '
                f'{existants} déjà présente(s).')
        self.stdout.write(self.style.SUCCESS(
            f'seed_pack_ao : {total_crees} pièce(s) créée(s), '
            f'{total_existants} inchangée(s).'))
