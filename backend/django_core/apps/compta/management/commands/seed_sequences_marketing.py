"""XMKT20 — Recettes de séquences marketing prêtes à l'emploi (seed).

Crée 5 flux type adaptés au solaire marocain, DÉSACTIVÉS par défaut
(``actif=False`` — le founder les active en un clic) : idempotente et
additive, ne touche JAMAIS une séquence déjà présente (matchée par nom +
société). Ré-exécutable sans effet si déjà semée (aucun doublon).

Run:
  docker compose exec django_core python manage.py seed_sequences_marketing
  (option --company-slug, default: taqinor-demo)
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Clé canonique STAGES.py, jamais codée en dur — chargée via le loader
# partagé ``apps.crm.stages`` (résout /opt/STAGES.py en conteneur, repo root
# sur host/CI ; règle #2 CLAUDE.md).
from apps.crm.stages import COLD

from apps.compta.models import EtapeSequence, SequenceRelance


# (nom, stage_declencheur, [(ordre, delai_jours, canal, modele_message)])
RECETTES = [
    (
        'Bienvenue nouveau lead',
        '',
        [
            (1, 0, EtapeSequence.Canal.WHATSAPP,
             'Bonjour {prenom}, merci pour votre intérêt pour le solaire ! '
             'Nous revenons vers vous rapidement.'),
            (2, 2, EtapeSequence.Canal.EMAIL,
             'Bonjour {prenom}, voici quelques informations utiles sur nos '
             'solutions solaires.'),
        ],
    ),
    (
        'Relance devis envoyé',
        '',
        [
            (1, 2, EtapeSequence.Canal.WHATSAPP,
             'Bonjour {prenom}, avez-vous eu le temps de consulter notre '
             'devis ?'),
            (2, 5, EtapeSequence.Canal.EMAIL,
             'Bonjour {prenom}, nous restons à votre disposition pour toute '
             'question sur votre devis.'),
            (3, 10, EtapeSequence.Canal.APPEL,
             'Appel de relance devis non répondu.'),
        ],
    ),
    (
        'Réveil base froide',
        COLD,
        [
            (1, 0, EtapeSequence.Canal.EMAIL,
             'Bonjour {prenom}, le solaire vous intéresse toujours ? Nos '
             'offres ont évolué.'),
        ],
    ),
    (
        'Post-installation',
        '',
        [
            (1, 1, EtapeSequence.Canal.WHATSAPP,
             'Merci {prenom} pour votre confiance ! Votre installation '
             'solaire est terminée.'),
            (2, 7, EtapeSequence.Canal.EMAIL,
             'Bonjour {prenom}, seriez-vous disposé(e) à laisser un avis sur '
             'votre expérience ?'),
        ],
    ),
    (
        'No-show rendez-vous',
        '',
        [
            (1, 0, EtapeSequence.Canal.WHATSAPP,
             "Bonjour {prenom}, nous n'avons pas pu vous joindre au rendez-"
             'vous prévu. Souhaitez-vous le reprogrammer ?'),
            (2, 3, EtapeSequence.Canal.APPEL,
             'Appel de reprise de contact après rendez-vous manqué.'),
        ],
    ),
]


class Command(BaseCommand):
    help = ("Seed les recettes de séquences marketing prêtes à l'emploi "
            '(idempotent, additif, désactivées par défaut).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', default='taqinor-demo',
            help="Slug of the company to seed (default: taqinor-demo).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options['company_slug']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f"Company with slug '{slug}' not found.")

        created, skipped = [], []
        for nom, stage_declencheur, etapes in RECETTES:
            if SequenceRelance.objects.filter(company=company, nom=nom).exists():
                skipped.append(nom)
                continue
            sequence = SequenceRelance.objects.create(
                company=company, nom=nom,
                stage_declencheur=stage_declencheur, actif=False)
            for ordre, delai_jours, canal, modele in etapes:
                EtapeSequence.objects.create(
                    company=company, sequence=sequence, ordre=ordre,
                    delai_jours=delai_jours, canal=canal,
                    modele_message=modele)
            created.append(nom)

        self.stdout.write(self.style.SUCCESS(
            f'Séquences créées : {len(created)} ({", ".join(created) or "aucune"})'))
        self.stdout.write(
            f'Séquences déjà présentes (ignorées) : {len(skipped)} '
            f'({", ".join(skipped) or "aucune"})')
