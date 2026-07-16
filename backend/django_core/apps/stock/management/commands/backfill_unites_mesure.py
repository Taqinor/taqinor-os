"""ARC27 — Backfill des unités de mesure produit en référentiel.

Pour chaque société, crée une entrée ``parametres.UniteMesure`` par CODE distinct
de ``Produit.unite_stock`` (idempotent — jamais de doublon) et relie chaque
produit à son unité via la FK miroir ``unite``.

Additif et rejouable : ``unite_stock`` reste MAÎTRE ; la commande ne fait que
peupler le référentiel + poser la FK miroir. Un produit déjà relié n'est PAS
retouché (idempotence).

Run:
    docker compose exec django_core python manage.py backfill_unites_mesure
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

# parametres est une app de FONDATION (import descendant autorisé, cf. CLAUDE.md).
from apps.parametres.models import UNITES_MESURE_DEFAUT, UniteMesure
from apps.stock.models import Produit

# Libellés FR connus des unités par défaut (repli sur le code sinon).
_LIBELLES = {e['code']: e['libelle'] for e in UNITES_MESURE_DEFAUT}


class Command(BaseCommand):
    help = ("ARC27 — crée les unités de mesure du référentiel à partir des "
            "codes distincts de Produit.unite_stock et relie chaque produit à "
            "son unité (idempotent).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', dest='company_slug', default=None,
            help='Limiter le backfill à une société (slug). Défaut : toutes.')

    def handle(self, *args, **options):
        qs = Produit.objects.filter(company__isnull=False)
        slug = options.get('company_slug')
        if slug:
            qs = qs.filter(company__slug=slug)

        unites_creees = 0
        produits_relies = 0

        with transaction.atomic():
            for p in qs.select_related('company').iterator():
                # Idempotence : un produit déjà relié n'est jamais retouché.
                if p.unite_id is not None:
                    continue
                code = (p.unite_stock or 'unité').strip() or 'unité'
                unite, created = UniteMesure.objects.get_or_create(
                    company=p.company, code=code,
                    defaults={'libelle': _LIBELLES.get(code, code),
                              'actif': True})
                if created:
                    unites_creees += 1
                p.unite = unite
                p.save(update_fields=['unite'])
                produits_relies += 1

        self.stdout.write(self.style.SUCCESS(
            f'ARC27 backfill : {unites_creees} unité(s) créée(s), '
            f'{produits_relies} produit(s) relié(s).'))
