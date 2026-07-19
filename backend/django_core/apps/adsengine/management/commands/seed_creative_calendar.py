"""PUB78 — Seed idempotent du calendrier créatif marocain.

Sème par société active les fenêtres saisonnières (Ramadan mobile, Aïds,
rentrée, canicule, saison agricole post-récolte) via
``calendar.seed_calendar`` — additif seulement (``get_or_create`` sur
``(company, tag, date_debut)``, jamais un écrasement). Les dates sont des
fenêtres de PLANIFICATION éditables (jamais un chiffre client-facing).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Seed idempotent du calendrier créatif marocain (Ramadan, Aïds, '
            'rentrée, canicule, saison agricole) — additif seulement.')

    def handle(self, *args, **options):
        from authentication.selectors import active_companies

        from apps.adsengine import calendar as calendar_mod

        total = 0
        for company in active_companies():
            total += calendar_mod.seed_calendar(company)

        self.stdout.write(self.style.SUCCESS(
            f'seed_creative_calendar : {total} événement(s) créé(s).'))
        return None
