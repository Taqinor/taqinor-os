"""
Seed the Stock module with the founder's devis-simulator catalogue
(vendored from RedaSolar/devis-simulator brand_catalog.json, 2026-06).

The simulator works in TTC; the Stock model stores HT prices, so each price
here is the simulator's TTC divided by 1.2 (TVA 20%). The generator screen
multiplies back (x1.2, rounded) so the displayed TTC matches the simulator
to the dirham.

Idempotent and strictly additive:
  - a product is matched by SKU or by name (case-insensitive, per company);
  - existing products are NEVER modified or duplicated — only missing ones
    are created (a skipped collision is listed in the output).

Run:
  docker compose exec django_core python manage.py seed_catalogue
  (option --company-slug, default: taqinor-demo)
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# (nom, sku, categorie, sell_ttc, buy_ttc, quantite, seuil)
CATALOGUE = [
    # ── Onduleurs réseau (Huawei — "Onduleur Injection" du simulateur) ──
    ('Onduleur réseau Huawei 5kW Monophasé',   'OND-R-HUA-5M',   'Onduleurs', 14000, 9500, 500, 5),
    ('Onduleur réseau Huawei 10kW Monophasé',  'OND-R-HUA-10M',  'Onduleurs', 18000, 11000, 500, 5),
    ('Onduleur réseau Huawei 10kW Triphasé',   'OND-R-HUA-10T',  'Onduleurs', 20000, 12500, 500, 5),
    ('Onduleur réseau Huawei 12kW Monophasé',  'OND-R-HUA-12M',  'Onduleurs', 20000, 12500, 500, 5),
    ('Onduleur réseau Huawei 15kW Triphasé',   'OND-R-HUA-15T',  'Onduleurs', 23000, 13200, 500, 5),
    ('Onduleur réseau Huawei 20kW Triphasé',   'OND-R-HUA-20T',  'Onduleurs', 28000, 16000, 500, 5),
    ('Onduleur réseau Huawei 25kW Triphasé',   'OND-R-HUA-25T',  'Onduleurs', 35000, 22000, 500, 5),
    ('Onduleur réseau Huawei 50kW Triphasé',   'OND-R-HUA-50T',  'Onduleurs', 55000, 30300, 500, 5),
    ('Onduleur réseau Huawei 100kW Triphasé',  'OND-R-HUA-100T', 'Onduleurs', 78000, 56600, 500, 5),
    ('Onduleur réseau Huawei 150kW Triphasé',  'OND-R-HUA-150T', 'Onduleurs', 123000, 87000, 500, 5),
    # ── Onduleurs hybrides (Deye) ──
    ('Onduleur hybride Deye 5kW Monophasé',    'OND-H-DEY-5M',   'Onduleurs', 17000, 12000, 500, 5),
    ('Onduleur hybride Deye 10kW Monophasé',   'OND-H-DEY-10M',  'Onduleurs', 28000, 24000, 500, 5),
    ('Onduleur hybride Deye 10kW Triphasé',    'OND-H-DEY-10T',  'Onduleurs', 28000, 24000, 500, 5),
    ('Onduleur hybride Deye 15kW Triphasé',    'OND-H-DEY-15T',  'Onduleurs', 36000, 30000, 500, 5),
    ('Onduleur hybride Deye 20kW Triphasé',    'OND-H-DEY-20T',  'Onduleurs', 48000, 42000, 500, 5),
    # ── Panneaux ──
    ('Panneau Canadien Solar 710W', 'PAN-CS-710', 'Panneaux solaires', 1400, 1200, 1000, 20),
    ('Panneau Jinko 710W',          'PAN-JK-710', 'Panneaux solaires', 1400, 1200, 1000, 20),
    # ── Batteries ──
    ('Batterie Deyness 5 kWh',  'BAT-DEY-5',  'Batteries', 17000, 13000, 500, 5),
    ('Batterie Deyness 10 kWh', 'BAT-DEY-10', 'Batteries', 30000, 22000, 500, 5),
    ('Batterie Lithium 5 kWh',  'BAT-LIT-5',  'Batteries', 15500, 13200, 500, 5),
    ('Batterie Gel 2.2 kWh',    'BAT-GEL-22', 'Batteries', 5000, 3100, 500, 5),
    # ── Structure & divers ──
    ('Structures acier',           'STR-ACIER', 'Accessoires', 500, 350, 2000, 50),
    ('Structures aluminium',       'STR-ALU',   'Accessoires', 850, 600, 2000, 50),
    ('Socles',                     'SOC-BET',   'Accessoires', 80, 50, 5000, 100),
    ('Smart Meter',                'SMART-MET', 'Accessoires', 1800, 1200, 500, 5),
    ('Wifi Dongle',                'WIFI-DON',  'Accessoires', 1200, 700, 500, 5),
    ('Accessoires',                'ACC-CAT',   'Accessoires', 2000, 2000, 999, 0),
    ('Tableau De Protection AC/DC', 'TAB-PROT', 'Accessoires', 2000, 1500, 999, 0),
    ('Installation',               'INST-CAT',  'Accessoires', 4800, 4000, 999, 0),
    ('Transport',                  'TRANS-CAT', 'Accessoires', 1000, 800, 999, 0),
    ('Suivi journalier, maintenance chaque 12 mois pendent 2 ans',
     'SUIVI-2A', 'Accessoires', 5000, 4000, 999, 0),
]


def ht(ttc):
    """Prix HT (2 décimales) depuis le TTC du simulateur (TVA 20 %)."""
    return (Decimal(ttc) / Decimal('1.2')).quantize(Decimal('0.01'))


class Command(BaseCommand):
    help = "Seed the stock with the devis-simulator catalogue (idempotent, additive only)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', default='taqinor-demo',
            help="Slug of the company to seed (default: taqinor-demo).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.stock.models import Categorie, Produit, MouvementStock

        slug = options['company_slug']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f"Company with slug '{slug}' not found.")

        created, skipped = [], []
        categories = {}

        def get_categorie(nom):
            if nom not in categories:
                categories[nom], _ = Categorie.objects.get_or_create(
                    company=company, nom=nom,
                    defaults={'description': 'Catalogue simulateur'},
                )
            return categories[nom]

        for nom, sku, cat, sell_ttc, buy_ttc, qte, seuil in CATALOGUE:
            # match by SKU or by exact name — never touch what already exists
            if (Produit.objects.filter(company=company, sku=sku).exists()
                    or Produit.objects.filter(company=company, nom__iexact=nom).exists()):
                skipped.append(nom)
                continue

            produit = Produit.objects.create(
                company=company,
                nom=nom,
                sku=sku,
                categorie=get_categorie(cat),
                prix_achat=ht(buy_ttc),
                prix_vente=ht(sell_ttc),
                quantite_stock=qte,
                seuil_alerte=seuil,
                tva=Decimal('20.00'),
            )
            MouvementStock.objects.create(
                company=company,
                produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=qte, quantite_avant=0, quantite_apres=qte,
                reference='SEED-CATALOGUE',
                note='Stock initial (catalogue simulateur)',
            )
            created.append(nom)

        self.stdout.write(self.style.SUCCESS(
            f"\nCatalogue seed for '{company.nom}': "
            f"{len(created)} created, {len(skipped)} already present (untouched)."
        ))
        for nom in created:
            self.stdout.write(f"  + {nom}")
        if skipped:
            self.stdout.write(self.style.WARNING(
                "\nAlready existed (kept as-is — check their prices against the catalogue):"
            ))
            for nom in skipped:
                self.stdout.write(f"  = {nom}")
