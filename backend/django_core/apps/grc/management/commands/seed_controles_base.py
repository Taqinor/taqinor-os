"""NTGRC16 — seed IDEMPOTENT du catalogue de contrôles internes (SOX-lite).

Installe, pour chaque société (ou une seule via ``--company``), 12 contrôles
génériques couvrant les sept domaines de la bibliothèque. Rejouable sans
doublon : ``update_or_create`` sur ``(company, code)``.

Ce que le seed NE TOUCHE JAMAIS : ``proprietaire`` et ``actif``. Ce sont les
deux seules colonnes qu'une société renseigne elle-même ; les réécrire à
chaque passage effacerait l'affectation et rallumerait un contrôle
volontairement désactivé.
"""
from django.core.management.base import BaseCommand

from apps.grc.models import ControleInterne
from authentication.models import Company

C = ControleInterne

#: Les 12 contrôles génériques — un socle raisonnable, éditable ensuite.
CONTROLES = [
    {'code': 'ACC-01', 'domaine': 'acces',
     'intitule': 'Revue trimestrielle des comptes utilisateurs',
     'objectif': 'Aucun compte actif ne subsiste pour une personne partie ou '
                 'ayant changé de fonction.',
     'type': C.TYPE_DETECTIF, 'frequence': C.FREQ_TRIMESTRIEL,
     'reference_cadre': 'ISO27001'},
    {'code': 'ACC-02', 'domaine': 'acces',
     'intitule': 'Retrait des accès au départ d\'un collaborateur',
     'objectif': 'Les accès sont retirés le jour du départ, pas après.',
     'type': C.TYPE_PREVENTIF, 'frequence': C.FREQ_PERMANENT,
     'reference_cadre': 'ISO27001'},
    {'code': 'SOD-01', 'domaine': 'segregation_taches',
     'intitule': 'Séparation saisie / validation des paiements',
     'objectif': "La personne qui saisit un paiement n'est jamais celle qui "
                 'le valide.',
     'type': C.TYPE_PREVENTIF, 'frequence': C.FREQ_PERMANENT,
     'reference_cadre': 'SOX'},
    {'code': 'SOD-02', 'domaine': 'segregation_taches',
     'intitule': 'Séparation commande / réception fournisseur',
     'objectif': 'La réception est constatée par une autre personne que celle '
                 'qui a commandé.',
     'type': C.TYPE_PREVENTIF, 'frequence': C.FREQ_PERMANENT,
     'reference_cadre': 'SOX'},
    {'code': 'CPT-01', 'domaine': 'cloture_compta',
     'intitule': 'Rapprochement bancaire mensuel',
     'objectif': 'Chaque compte bancaire est rapproché et les écarts sont '
                 'justifiés.',
     'type': C.TYPE_DETECTIF, 'frequence': C.FREQ_MENSUEL,
     'reference_cadre': 'CGNC'},
    {'code': 'CPT-02', 'domaine': 'cloture_compta',
     'intitule': 'Revue des écritures manuelles de clôture',
     'objectif': 'Toute écriture manuelle de clôture est justifiée et '
                 'approuvée.',
     'type': C.TYPE_DETECTIF, 'frequence': C.FREQ_MENSUEL,
     'reference_cadre': 'SOX'},
    {'code': 'ACH-01', 'domaine': 'achats',
     'intitule': 'Approbation des bons de commande au-delà du seuil',
     'objectif': 'Aucun engagement au-delà du seuil sans approbation tracée.',
     'type': C.TYPE_PREVENTIF, 'frequence': C.FREQ_PERMANENT,
     'reference_cadre': 'SOX'},
    {'code': 'ACH-02', 'domaine': 'achats',
     'intitule': 'Rapprochement facture / commande / réception',
     'objectif': "Aucune facture fournisseur n'est payée sans son trio "
                 'complet.',
     'type': C.TYPE_DETECTIF, 'frequence': C.FREQ_MENSUEL,
     'reference_cadre': 'CGNC'},
    {'code': 'PAI-01', 'domaine': 'paie',
     'intitule': 'Contrôle des variables de paie avant validation',
     'objectif': 'Les variables du mois sont contrôlées et approuvées avant '
                 'le calcul définitif.',
     'type': C.TYPE_PREVENTIF, 'frequence': C.FREQ_MENSUEL,
     'reference_cadre': 'interne'},
    {'code': 'SI-01', 'domaine': 'si',
     'intitule': 'Revue des journaux de sécurité',
     'objectif': 'Les alertes de sécurité sont revues et traitées.',
     'type': C.TYPE_DETECTIF, 'frequence': C.FREQ_HEBDO,
     'reference_cadre': 'ISO27001'},
    {'code': 'SAV-01', 'domaine': 'sauvegarde',
     'intitule': 'Vérification quotidienne des sauvegardes',
     'objectif': 'La sauvegarde du jour a réussi et son échec déclenche une '
                 'alerte.',
     'type': C.TYPE_DETECTIF, 'frequence': C.FREQ_QUOTIDIEN,
     'reference_cadre': 'ISO27001'},
    {'code': 'SAV-02', 'domaine': 'sauvegarde',
     'intitule': 'Test annuel de restauration',
     'objectif': 'Une restauration réelle est testée au moins une fois par an '
                 '— une sauvegarde jamais restaurée ne prouve rien.',
     'type': C.TYPE_DETECTIF, 'frequence': C.FREQ_ANNUEL,
     'reference_cadre': 'ISO27001'},
]


class Command(BaseCommand):
    help = ('Seed idempotent de la bibliothèque de contrôles internes '
            '(NTGRC16) pour chaque société.')

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

        crees = maj = 0
        for company in companies:
            for spec in CONTROLES:
                # `proprietaire` et `actif` sont volontairement ABSENTS des
                # defaults : ils appartiennent à la société, pas au catalogue.
                defaults = {k: v for k, v in spec.items() if k != 'code'}
                _, created = ControleInterne.objects.update_or_create(
                    company=company, code=spec['code'], defaults=defaults)
                if created:
                    crees += 1
                else:
                    maj += 1
        self.stdout.write(self.style.SUCCESS(
            f'Contrôles internes : {crees} créés, {maj} mis à jour.'))
