"""NTOBS10 — seed idempotent du trust center (faits VÉRIFIÉS uniquement).

RÈGLE ABSOLUE (checked-facts-only) : n'affiche AUCUNE certification ni
conformité non réellement obtenue — chaque entrée ci-dessous est un fait
d'architecture vérifiable dans ce dépôt (CLAUDE.md, docker-compose.yml),
jamais une allégation commerciale. Aucune localisation géographique n'est
affirmée tant qu'elle n'a pas été confirmée par le fondateur (ex. le pays
exact du datacenter Hetzner) — le champ reste alors sobre plutôt qu'inventé.

Idempotent : ``get_or_create`` sur ``(categorie, titre)`` — jamais de doublon
en relançant la commande."""
from django.core.management.base import BaseCommand

from core.trust_center import TrustCenterEntry

ENTRIES = [
    {
        'categorie': TrustCenterEntry.Categorie.LOCALISATION_DONNEES,
        'titre': 'Hébergement infrastructure',
        'description': (
            'Base de données, stockage documentaire et applications hébergés '
            'chez Hetzner. Le pays exact du datacenter reste à confirmer '
            'avant publication précise.'
        ),
        'ordre_affichage': 10,
    },
    {
        'categorie': TrustCenterEntry.Categorie.SOUS_TRAITANT,
        'titre': 'Stockage des données',
        'description': (
            'PostgreSQL, Redis et MinIO (stockage objet) sont self-hébergés '
            'sur notre propre infrastructure — aucun sous-traitant tiers '
            "n'héberge les données pour le compte de Taqinor."
        ),
        'ordre_affichage': 20,
    },
    {
        'categorie': TrustCenterEntry.Categorie.SOUS_TRAITANT,
        'titre': 'Reconnaissance de documents (OCR)',
        'description': (
            "Zhipu AI traite les documents envoyés à l'OCR, uniquement "
            'quand cette fonctionnalité est activée par le client.'
        ),
        'ordre_affichage': 30,
    },
    {
        'categorie': TrustCenterEntry.Categorie.SOUS_TRAITANT,
        'titre': 'Assistant conversationnel',
        'description': (
            "Groq (ou un fournisseur équivalent) traite les requêtes de "
            "l'assistant/agent de requêtes en langage naturel, uniquement "
            'quand cette fonctionnalité est activée par le client.'
        ),
        'ordre_affichage': 40,
    },
]


class Command(BaseCommand):
    help = 'Seed idempotent du trust center (faits vérifiés uniquement).'

    def handle(self, *args, **options):
        crees = 0
        for entry in ENTRIES:
            _obj, created = TrustCenterEntry.objects.get_or_create(
                categorie=entry['categorie'], titre=entry['titre'],
                defaults={
                    'description': entry['description'],
                    'ordre_affichage': entry['ordre_affichage'],
                },
            )
            if created:
                crees += 1
        self.stdout.write(self.style.SUCCESS(
            f'{crees} entrée(s) créée(s) ({len(ENTRIES) - crees} déjà présente(s)).'))
