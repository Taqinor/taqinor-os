"""XPLT23 — seed idempotent du registre des traitements CNDP (loi 09-08).

Pré-remplit, POUR CHAQUE société (ou une seule via ``--company``), les
traitements types du produit (leads/clients, RH/paie, GED, marketing). Rejouable
sans doublon : ``update_or_create`` sur ``(company, code)`` ne touche PAS le n°
de récépissé CNDP ni la date déjà saisis (jamais écrasés).
"""
from django.core.management.base import BaseCommand

from authentication.models import Company
from core.models import RegistreTraitement

# Traitements types du produit — additifs, éditables ensuite par la société.
TRAITEMENTS = [
    {
        'code': 'leads_clients',
        'finalite': 'Gestion des prospects et clients (CRM, devis, factures).',
        'base_legale': 'Exécution de mesures précontractuelles / contrat.',
        'categories_donnees': 'Identité, coordonnées, données de facturation, '
                              'données de consommation énergétique.',
        'categories_personnes': 'Prospects, clients.',
        'destinataires': 'Service commercial, service ADV, comptabilité, '
                         'sous-traitants (hébergement, messagerie).',
        'duree_conservation': '3 ans après le dernier contact (prospects), '
                              'durée légale comptable pour les clients.',
    },
    {
        'code': 'rh_paie',
        'finalite': 'Gestion du personnel, de la paie et des obligations '
                    'sociales.',
        'base_legale': 'Obligation légale et exécution du contrat de travail.',
        'categories_donnees': 'Identité, coordonnées, données bancaires, '
                              'données de rémunération, CNSS/AMO.',
        'categories_personnes': 'Salariés, candidats.',
        'destinataires': 'Service RH, comptabilité, organismes sociaux '
                         '(CNSS, AMO), administration fiscale.',
        'duree_conservation': 'Durée légale des obligations sociales et '
                              'fiscales.',
    },
    {
        'code': 'ged_documents',
        'finalite': 'Gestion électronique des documents de l\'entreprise.',
        'base_legale': 'Intérêt légitime / obligation légale de conservation.',
        'categories_donnees': 'Documents contractuels, techniques et '
                              'administratifs.',
        'categories_personnes': 'Clients, salariés, fournisseurs.',
        'destinataires': 'Services internes habilités.',
        'duree_conservation': 'Durée légale propre à chaque type de document.',
    },
    {
        'code': 'marketing',
        'finalite': 'Prospection commerciale et communication marketing.',
        'base_legale': 'Consentement.',
        'categories_donnees': 'Identité, coordonnées, préférences de contact.',
        'categories_personnes': 'Prospects, clients, contacts.',
        'destinataires': 'Service marketing, prestataires d\'emailing/SMS.',
        'duree_conservation': 'Jusqu\'au retrait du consentement.',
    },
]


class Command(BaseCommand):
    help = ('Seed idempotent du registre des traitements CNDP (XPLT23) pour '
            'chaque société.')

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
            for spec in TRAITEMENTS:
                # N'écrase PAS le récépissé CNDP / actif déjà saisis : les
                # defaults ne portent que le contenu descriptif du produit.
                defaults = {k: v for k, v in spec.items() if k != 'code'}
                _, created = RegistreTraitement.objects.update_or_create(
                    company=company, code=spec['code'], defaults=defaults)
                if created:
                    crees += 1
                else:
                    maj += 1
        self.stdout.write(self.style.SUCCESS(
            f'Registre CNDP : {crees} créés, {maj} mis à jour.'))
