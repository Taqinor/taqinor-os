"""NTGRC23 — seed IDEMPOTENT des trames de questionnaire fournisseur.

Installe, pour chaque société (ou une seule via ``--company``), deux trames de
départ : un questionnaire RGPD « sous-traitant » (art. 28 RGPD / loi 09-08) et
un questionnaire sécurité. Rejouable sans doublon : ``update_or_create`` sur
``(company, code)``.

Ce que le seed NE TOUCHE JAMAIS : ``actif``. C'est la seule colonne qu'une
société pilote elle-même ; la réécrire rallumerait une trame volontairement
désactivée. Les questions, elles, sont RÉALIGNÉES à chaque passage — c'est le
catalogue de référence, et une trame instanciée garde de toute façon SA copie
figée (``instancier_questionnaire``).
"""
from django.core.management.base import BaseCommand

from apps.grc.models import ModeleQuestionnaire, QuestionnaireFournisseur
from authentication.models import Company


def _q(intitule, obligatoire=True, type_reponse='texte'):
    return {'intitule': intitule, 'obligatoire': obligatoire,
            'type_reponse': type_reponse}


MODELES = [
    {
        'code': 'RGPD-ST',
        'nom': 'Sous-traitant — protection des données (art. 28 / loi 09-08)',
        'type': QuestionnaireFournisseur.TYPE_RGPD,
        'questions': [
            _q('Quelles catégories de données personnelles traitez-vous pour '
               'notre compte ?'),
            _q('Où ces données sont-elles hébergées (pays, prestataire) ?'),
            _q('Transférez-vous tout ou partie de ces données hors du Maroc ? '
               'Si oui, sous quelles garanties (CCT, adéquation, '
               'dérogation) ?'),
            _q('Une clause de sous-traitance conforme est-elle signée avec '
               'nous ?', type_reponse='oui_non'),
            _q('Faites-vous appel à des sous-traitants ultérieurs ? '
               'Lesquels ?'),
            _q('Quelle est votre durée de conservation, et comment les '
               'données sont-elles détruites en fin de contrat ?'),
            _q('Comment nous notifiez-vous une violation de données, et sous '
               'quel délai ?'),
            _q('Avez-vous désigné un responsable de la protection des '
               'données ? Coordonnées ?', obligatoire=False),
        ],
    },
    {
        'code': 'SEC-BASE',
        'nom': 'Sécurité de l\'information — socle',
        'type': QuestionnaireFournisseur.TYPE_SECURITE,
        'questions': [
            _q('Disposez-vous d\'une politique de sécurité de l\'information '
               'formalisée ?', type_reponse='oui_non'),
            _q('L\'authentification à double facteur est-elle imposée sur les '
               'accès aux données de vos clients ?', type_reponse='oui_non'),
            _q('Comment les sauvegardes sont-elles réalisées, et à quelle '
               'fréquence une restauration est-elle testée ?'),
            _q('Les données sont-elles chiffrées au repos et en transit ?',
               type_reponse='oui_non'),
            _q('Quel est votre processus de gestion des correctifs de '
               'sécurité ?'),
            _q('Disposez-vous d\'une certification (ISO 27001 ou autre) ? '
               'Joignez l\'attestation.', obligatoire=False),
        ],
    },
]


class Command(BaseCommand):
    help = ('Seed idempotent des trames de questionnaire fournisseur '
            '(NTGRC23) : RGPD sous-traitant + sécurité.')

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
            for spec in MODELES:
                # `actif` est volontairement ABSENT des defaults : il
                # appartient à la société, pas au catalogue.
                defaults = {k: v for k, v in spec.items() if k != 'code'}
                _, created = ModeleQuestionnaire.objects.update_or_create(
                    company=company, code=spec['code'], defaults=defaults)
                if created:
                    crees += 1
                else:
                    maj += 1
        self.stdout.write(self.style.SUCCESS(
            f'Modèles de questionnaire : {crees} créés, {maj} mis à jour.'))
