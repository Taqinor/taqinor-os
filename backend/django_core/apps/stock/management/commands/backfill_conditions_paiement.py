"""ARC24 — Backfill des conditions de paiement fournisseur en référentiel.

Pour chaque société, regroupe les fournisseurs par TRIPLET distinct
(delai_paiement_jours, fin_de_mois, escompte_pct), crée l'entrée
``parametres.ConditionPaiement`` correspondante (idempotent — une entrée par
condition distincte, jamais de doublon) et relie chaque fournisseur à sa
condition via ``condition_paiement_ref``.

Additif et rejouable : les trois champs numériques du fournisseur restent
MAÎTRES ; la commande ne fait que peupler le référentiel + poser la FK miroir.
Un fournisseur déjà relié n'est PAS retouché (idempotence).

Run:
    docker compose exec django_core python manage.py backfill_conditions_paiement
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

# parametres est une app de FONDATION (import descendant autorisé, cf. CLAUDE.md).
from apps.parametres.models import ConditionPaiement
from apps.stock.models import Fournisseur


class Command(BaseCommand):
    help = ("ARC24 — crée les conditions de paiement du référentiel à partir "
            "des triplets distincts des fournisseurs et relie chaque "
            "fournisseur à sa condition (idempotent).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', dest='company_slug', default=None,
            help='Limiter le backfill à une société (slug). Défaut : toutes.')

    def handle(self, *args, **options):
        qs = Fournisseur.objects.filter(company__isnull=False)
        slug = options.get('company_slug')
        if slug:
            qs = qs.filter(company__slug=slug)

        conditions_creees = 0
        fournisseurs_relies = 0

        with transaction.atomic():
            for f in qs.select_related('company').iterator():
                # Idempotence : un fournisseur déjà relié n'est jamais retouché.
                if f.condition_paiement_ref_id is not None:
                    continue
                avant = ConditionPaiement.objects.filter(
                    company=f.company).count()
                cond = ConditionPaiement.from_triplet(
                    f.company, f.delai_paiement_jours, f.fin_de_mois,
                    f.escompte_pct)
                apres = ConditionPaiement.objects.filter(
                    company=f.company).count()
                if apres > avant:
                    conditions_creees += 1
                f.condition_paiement_ref = cond
                f.save(update_fields=['condition_paiement_ref'])
                fournisseurs_relies += 1

        self.stdout.write(self.style.SUCCESS(
            f'ARC24 backfill : {conditions_creees} condition(s) créée(s), '
            f'{fournisseurs_relies} fournisseur(s) relié(s).'))
