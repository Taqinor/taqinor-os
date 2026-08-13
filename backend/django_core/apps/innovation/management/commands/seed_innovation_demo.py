"""NTIDE66 — ``manage.py seed_innovation_demo --company SLUG``.

Sème un jeu de démonstration LOCAL du module Innovation : 5 idées (réparties
sur les statuts, dont un brouillon et une masquée), 2 campagnes (une active,
une brouillon) et 10 retours produit (thèmes/sentiments/pages variés).

Idempotent et ADDITIF : chaque ligne est retrouvée par son titre/nom au sein
de la société (``get_or_create``) — relancer la commande ne duplique rien et
ne modifie aucune ligne existante. Aucune suppression.

Réservé à la démo/au développement : refusé hors ``DEBUG`` sans ``--force``,
même convention que ``seed_demo`` (ERR88).

Exemples :
  python manage.py seed_innovation_demo --company taqinor-demo
  python manage.py seed_innovation_demo --company taqinor-demo --force
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# (titre, contexte, statut, draft, archived)
IDEES = [
    ('Scanner les bons de livraison au dépôt', 'Stock', 'ouvert', False, False),
    ('Relance automatique des devis sans réponse', 'Devis', 'examinee', False, False),
    ('Photo obligatoire à la clôture d\'un ticket SAV', 'SAV', 'retenue', False, False),
    ('Fiche technique PDF envoyée avec le devis', 'Devis', 'realisee', False, False),
    ('Idée encore en brouillon (démo)', 'Interne', 'ouvert', True, False),
]

CAMPAGNES = [
    {
        'nom': 'Vos idées pour le dépôt',
        'description': 'Comment fluidifier les entrées/sorties de stock ?',
        'statut': 'active',
        'segment': ['Technicien'],
        'cible_departement': 'Technicien',
        'message_incitation': 'Nous cherchons vos idées sur la gestion du dépôt.',
        'tag_auto': 'Dépôt',
    },
    {
        'nom': 'Parcours client 2027',
        'description': 'Idées sur le suivi client après installation.',
        'statut': 'brouillon',
        'segment': ['Commercial'],
        'cible_departement': 'Commercial',
        'message_incitation': 'Racontez-nous les frictions du suivi client.',
        'tag_auto': '',
    },
]

FEEDBACKS = [
    ('Le tableau des devis rame à partir de 200 lignes', 'performance', 'negatif', '/ventes/devis'),
    ('J\'adore le nouveau générateur de devis', 'feature', 'positif', '/ventes/devis/nouveau'),
    ('Le filtre par statut se réinitialise', 'bug', 'negatif', '/crm/leads'),
    ('Ajouter un raccourci clavier pour la recherche', 'feature', 'neutre', '/dashboard'),
    ('Les libellés de colonnes sont trop longs sur mobile', 'ux', 'negatif', '/stock/produits'),
    ('Export XLSX parfait, rien à dire', 'feature', 'positif', '/ventes/devis'),
    ('La carte des chantiers met du temps à charger', 'performance', 'neutre', '/installations'),
    ('Un doublon de client n\'est pas détecté', 'bug', 'negatif', '/crm/clients'),
    ('Le mode sombre est très confortable', 'ux', 'positif', '/dashboard'),
    ('Rien de particulier, juste un retour', 'autre', '', '/dashboard'),
]


class Command(BaseCommand):
    help = (
        'Sème un jeu de démonstration du module Innovation (5 idées, '
        '2 campagnes, 10 retours produit) pour UNE société. Idempotent, '
        'additif, réservé à la démo/au développement.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', required=True,
            help='Slug de la société à peupler.')
        parser.add_argument(
            '--force', action='store_true',
            help='Autorise le seed hors DEBUG (données de démo explicites).')

    @transaction.atomic
    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model

        from authentication.models import Company

        from apps.innovation.models import (
            CampagneInnovation, FeedbackProduit, Idee,
        )

        if not settings.DEBUG and not opts.get('force'):
            raise CommandError(
                'seed_innovation_demo est refusé hors DEBUG : il crée des '
                'données de démonstration. Relancez avec --force si vous '
                'ciblez volontairement un environnement de démo.')

        slug = opts['company']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f'Société introuvable : {slug}')

        User = get_user_model()
        auteur = User.objects.filter(company=company).order_by('id').first()
        if auteur is None:
            raise CommandError(
                f'Aucun utilisateur dans la société {slug} : créez-en un '
                '(ou lancez seed_demo) avant de semer les idées.')

        nb_idees = 0
        for titre, contexte, statut, draft, archived in IDEES:
            _, cree = Idee.objects.get_or_create(
                company=company, titre=titre,
                defaults={
                    'description': 'Idée de démonstration (seed_innovation_demo).',
                    'contexte': contexte, 'statut': statut,
                    'draft': draft, 'archived': archived, 'auteur': auteur,
                })
            nb_idees += int(cree)

        nb_campagnes = 0
        for donnees in CAMPAGNES:
            defaults = {k: v for k, v in donnees.items() if k != 'nom'}
            _, cree = CampagneInnovation.objects.get_or_create(
                company=company, nom=donnees['nom'], defaults=defaults)
            nb_campagnes += int(cree)

        nb_feedbacks = 0
        for titre, theme, sentiment, page in FEEDBACKS:
            _, cree = FeedbackProduit.objects.get_or_create(
                company=company, titre=titre,
                defaults={
                    'description': 'Retour de démonstration (seed_innovation_demo).',
                    'theme': theme, 'sentiment': sentiment,
                    'source_page': page, 'auteur': auteur,
                })
            nb_feedbacks += int(cree)

        self.stdout.write(self.style.SUCCESS(
            f'Société {slug} : {nb_idees} idée(s), {nb_campagnes} campagne(s) '
            f'et {nb_feedbacks} retour(s) créés '
            '(les lignes déjà présentes sont laissées intactes).'))
