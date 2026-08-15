"""NTMIG23 — dépose les playbooks d'implémentation prêts-à-l'emploi.

Six playbooks (CRM/Ventes, Stock/Achats, Chantiers, SAV, Compta, RH/Paie),
chacun en six phases : prérequis, réglages, rôles, données de référence,
tests d'acceptation, go-live.

IDEMPOTENT et STRICTEMENT ADDITIF — deux passages donnent les mêmes
playbooks, et un playbook déjà édité par le fondateur n'est JAMAIS réécrit
(l'écriture passe par ``kb.services.seeder_playbook``, qui renvoie l'existant
tel quel ; ce module n'importe jamais ``kb.models``).

Lancer (dans le conteneur django_core, ou avec les variables DB posées) :
    python manage.py seed_playbooks                       # toutes les sociétés
    python manage.py seed_playbooks --company taqinor-demo # une seule
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.migration.playbooks import (
    CATEGORIE, PLAYBOOKS, cle_graine, corps_pour, structure_pour)


class Command(BaseCommand):
    help = (
        "Dépose les playbooks d'implémentation par module (CRM/Ventes, "
        "Stock/Achats, Chantiers, SAV, Compta, RH/Paie) pour toutes les "
        "sociétés ou une seule (--company). Idempotent, additif : un "
        "playbook déjà présent ou personnalisé n'est jamais réécrit."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug de la société à seeder (défaut : toutes).')

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company

        from apps.kb import services as kb_services

        slug = options.get('company')
        if slug:
            try:
                societes = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Société de slug « {slug} » introuvable.")
        else:
            societes = list(Company.objects.all())

        if not societes:
            self.stdout.write(self.style.WARNING(
                'Aucune société à seeder — rien fait.'))
            return

        crees = 0
        conserves = 0
        for company in societes:
            for definition in PLAYBOOKS:
                _, cree = kb_services.seeder_playbook(
                    company,
                    cle_graine=cle_graine(definition['cle']),
                    titre=definition['titre'],
                    categorie=CATEGORIE,
                    corps=corps_pour(definition),
                    contenu_structure=structure_pour(definition),
                    tags='playbook,implementation',
                )
                if cree:
                    crees += 1
                else:
                    conserves += 1

        self.stdout.write(self.style.SUCCESS(
            f'Playbooks seedés pour {len(societes)} société(s) : '
            f'{crees} créé(s), {conserves} conservé(s) tel(s) quel(s).'))
