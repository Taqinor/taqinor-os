"""AGEN1 — Seed idempotent de la table de faits (dd-assumption-engine §10.2
point 1 : « génération ANCRÉE sur la table de faits »).

Pose une PREMIÈRE ``FactTable`` PUBLIÉE par société active (créée+publiée si
aucune n'existe), puis SÈME des ``FactEntry`` de départ (tranches ONEE, FDA
30% sans plafond, production mesurée) — **additif seulement** :
``get_or_create`` par ``(table, cle)`` ne touche JAMAIS une entrée déjà
présente (même règle que ``seed_catalogue`` — corriger une valeur est un
geste humain volontaire, jamais un seed). Les valeurs ONEE/production sont
des ESTIMATIONS publiques — le champ ``source`` le dit explicitement ; À
CONFIRMER par le fondateur (édition directe de la ``FactEntry``, jamais un
re-seed) avant toute génération créative qui les cite (AGEN2+, whitelist
numérique AGEN3).
"""
from datetime import date

from django.core.management.base import BaseCommand

# Faits de départ Taqinor. Chaque entrée porte sa propre honnêteté dans
# ``source`` — rien ici n'est présenté comme définitif.
SEED_FACTS = [
    # FDA — Fonds de Développement Agricole, subvention pompage solaire.
    {
        'cle': 'fda_taux_subvention_pompage_pct',
        'valeur': '30',
        'unite': '%',
        'source': 'FDA — subvention pompage solaire agricole, SANS plafond',
    },
    # ONEE — grille tarifaire Basse Tension (usage domestique), estimation.
    {
        'cle': 'onee_bt_tranche1_0_100kwh',
        'valeur': '0.9010',
        'unite': 'MAD/kWh',
        'source': (
            'ONEE grille tarifaire BT, tranche 1 (0-100 kWh) — ESTIMATION,'
            ' à confirmer'),
    },
    {
        'cle': 'onee_bt_tranche2_101_200kwh',
        'valeur': '1.0179',
        'unite': 'MAD/kWh',
        'source': (
            'ONEE grille tarifaire BT, tranche 2 (101-200 kWh) — ESTIMATION,'
            ' à confirmer'),
    },
    {
        'cle': 'onee_bt_tranche3_201_500kwh',
        'valeur': '1.1216',
        'unite': 'MAD/kWh',
        'source': (
            'ONEE grille tarifaire BT, tranche 3 (201-500 kWh) — ESTIMATION,'
            ' à confirmer'),
    },
    {
        'cle': 'onee_bt_tranche4_plus_500kwh',
        'valeur': '1.6624',
        'unite': 'MAD/kWh',
        'source': (
            'ONEE grille tarifaire BT, tranche 4 (>500 kWh) — ESTIMATION,'
            ' à confirmer'),
    },
    # Production mesurée — moyenne installations Taqinor.
    {
        'cle': 'production_mesuree_kwh_par_kwc_jour',
        'valeur': '4.5',
        'unite': 'kWh/kWc/jour',
        'source': (
            'Moyenne mesurée installations Taqinor (irradiance Maroc) —'
            ' ESTIMATION, à confirmer'),
    },
]


class Command(BaseCommand):
    help = ('Seed idempotent de la table de faits (ONEE, FDA, production '
            'mesurée) — additif seulement, jamais un écrasement.')

    def handle(self, *args, **options):
        from authentication.selectors import active_companies
        from apps.adsengine.models import FactEntry, FactTable

        tables_created = 0
        entries_created = 0
        for company in active_companies():
            table = FactTable.published_for(company)
            if table is None:
                table = FactTable.create_draft(company)
                table.publish()
                tables_created += 1
            for fact in SEED_FACTS:
                _, was_created = FactEntry.objects.get_or_create(
                    table=table, cle=fact['cle'],
                    defaults={
                        'company': company,
                        'valeur': fact['valeur'],
                        'unite': fact['unite'],
                        'source': fact['source'],
                        'verifie_le': date.today(),
                    })
                if was_created:
                    entries_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'seed_fact_table : {tables_created} FactTable(s) créée(s), '
            f'{entries_created} FactEntry(s) créée(s).'))
        return None
