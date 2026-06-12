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


# ── Catalogue POMPAGE solaire (mode Agricole) ────────────────────────────────
# Prix TTC reconstitués du marché marocain (cptechmaroc.ma, mrelec.ma,
# energymarket.ma, ecovolt.ma, magitec.ma — juin 2026) — À CONFIRMER PAR REDA.
# prix_achat laissé à 0 (vide) volontairement : à remplir par le fondateur.
# (nom, sku, ttc, qte, seuil, pompe_cv, hmt_m, debit_m3j)
POMPAGE = [
    ('Pompe immergée solaire 1.5 CV Monophasé', 'PMP-IMM-1.5M', 4500, 20, 2, '1.5', '80', '15'),
    ('Pompe immergée solaire 3 CV Monophasé',   'PMP-IMM-3M',   6500, 20, 2, '3', '120', '25'),
    ('Pompe immergée solaire 4 CV Triphasé',    'PMP-IMM-4T',   8500, 20, 2, '4', '150', '35'),
    ('Pompe immergée solaire 5.5 CV Triphasé',  'PMP-IMM-5.5T', 11000, 20, 2, '5.5', '180', '45'),
    ('Pompe immergée solaire 7.5 CV Triphasé',  'PMP-IMM-7.5T', 14500, 20, 2, '7.5', '220', '60'),
    ('Pompe immergée solaire 10 CV Triphasé',   'PMP-IMM-10T',  19000, 20, 2, '10', '250', '80'),
    ('Pompe de surface solaire 1.5 CV Monophasé', 'PMP-SUR-1.5M', 3000, 20, 2, '1.5', '40', '20'),
    ('Pompe de surface solaire 3 CV Triphasé',    'PMP-SUR-3T',   5500, 20, 2, '3', '60', '40'),
    ('Variateur pompage solaire 1.5 CV Monophasé (coffret complet)', 'VFD-PMP-1.5M', 4000, 20, 2, '1.5', None, None),
    ('Variateur pompage solaire 3 CV Triphasé (coffret complet)',   'VFD-PMP-3T',   4800, 20, 2, '3', None, None),
    ('Variateur pompage solaire 4 CV Triphasé (coffret complet)',   'VFD-PMP-4T',   5500, 20, 2, '4', None, None),
    ('Variateur pompage solaire 5.5 CV Triphasé (coffret complet)', 'VFD-PMP-5.5T', 6500, 20, 2, '5.5', None, None),
    ('Variateur pompage solaire 7.5 CV Triphasé (coffret complet)', 'VFD-PMP-7.5T', 8000, 20, 2, '7.5', None, None),
    ('Variateur pompage solaire 10 CV Triphasé (coffret complet)',  'VFD-PMP-10T',  10500, 20, 2, '10', None, None),
    ('Câble solaire 6mm² (au mètre)', 'CAB-6MM-M', 13, 5000, 200, None, None, None),
]

_DESC_POMPE_IMM = ('Pompe immergée pour forage, corps inox\n'
                   'Pilotée par variateur solaire (AC, compatible champ PV)\n'
                   'Adaptée à l\'irrigation et l\'alimentation en eau agricole')
_DESC_POMPE_SUR = ('Pompe de surface pour puits/bassin, amorçage facilité\n'
                   'Pilotée par variateur solaire (AC, compatible champ PV)')
_DESC_VFD = ('Coffret pompage complet pré-câblé : variateur MPPT dédié pompe\n'
             'Sectionneur + disjoncteurs DC/AC + parafoudre DC\n'
             'Relais de niveau (protection marche à sec / cuve pleine)')

# ── Fiches commerciales (marque / description / garantie) ───────────────────
# Garanties issues des termes constructeurs publiés (recherche 2026-06) ;
# descriptions FR factuelles. Mise à jour ADDITIVE de ces 3 champs uniquement.
FICHES = {
    # Onduleurs réseau Huawei (résidentiel ≤ 25 kW : 10 ans ; C&I : 5 ans ext.)
    **{sku: {
        'marque': 'Huawei',
        'garantie': ('Garantie constructeur 10 ans'
                     if sku in ('OND-R-HUA-5M', 'OND-R-HUA-10M', 'OND-R-HUA-10T',
                                'OND-R-HUA-12M', 'OND-R-HUA-15T', 'OND-R-HUA-20T',
                                'OND-R-HUA-25T')
                     else 'Garantie constructeur 5 ans (extensible jusqu\'à 20 ans)'),
        'description': ('Onduleur string on-grid Huawei SUN2000, rendement max ≈ 98,6 %\n'
                        'Protection d\'arc intelligente AFCI, parafoudres DC/AC intégrés\n'
                        'Supervision temps réel via l\'application FusionSolar\n'
                        'Conforme IEC 62109, indice IP65 (pose intérieure/extérieure)'),
    } for sku in ('OND-R-HUA-5M', 'OND-R-HUA-10M', 'OND-R-HUA-10T', 'OND-R-HUA-12M',
                  'OND-R-HUA-15T', 'OND-R-HUA-20T', 'OND-R-HUA-25T', 'OND-R-HUA-50T',
                  'OND-R-HUA-100T', 'OND-R-HUA-150T')},
    # Onduleurs hybrides Deye
    **{sku: {
        'marque': 'Deye',
        'garantie': 'Garantie constructeur 10 ans',
        'description': ('Onduleur hybride Deye SUN-…SG, rendement max ≈ 97,6 %\n'
                        'Compatible batteries lithium 48 V (BMS CAN/RS485)\n'
                        'Bascule secours (EPS/UPS) < 4 ms en cas de coupure réseau\n'
                        'Monitoring Wi-Fi via Solarman Smart / Deye Cloud'),
    } for sku in ('OND-H-DEY-5M', 'OND-H-DEY-10M', 'OND-H-DEY-10T',
                  'OND-H-DEY-15T', 'OND-H-DEY-20T')},
    'PAN-CS-710': {
        'marque': 'Canadien Solar',
        'garantie': '12 ans produit · 30 ans performance linéaire (87,4 %)',
        'description': ('Module Canadian Solar TOPHiKu7 710 Wc, cellules N-type TOPCon\n'
                        'Rendement module jusqu\'à ≈ 22,9 %, dégradation ≤ 0,4 %/an\n'
                        'Excellent comportement à haute température (≈ −0,29 %/°C)\n'
                        'Certifié IEC 61215 / IEC 61730, fabricant Tier 1'),
    },
    'PAN-JK-710': {
        'marque': 'Jinko',
        'garantie': '12 ans produit · 30 ans performance linéaire (87,4 %)',
        'description': ('Module JinkoSolar Tiger Neo 710 Wc, N-type TOPCon\n'
                        'Rendement jusqu\'à ≈ 22,9 %, dégradation ≤ 0,4 %/an\n'
                        'Version bifaciale double verre disponible\n'
                        'Certifié IEC 61215 / IEC 61730'),
    },
    **{sku: {
        'marque': 'Deyness',
        'garantie': 'Garantie 5 ans · ≥ 6 000 cycles (80 % DoD)',
        'description': ('Batterie lithium LiFePO4 basse tension 51,2 V\n'
                        'Chimie fer-phosphate sûre et durable\n'
                        'BMS intégré CAN/RS485, compatible onduleurs hybrides Deye\n'
                        'Extensible en parallèle'),
    } for sku in ('BAT-DEY-5', 'BAT-DEY-10')},
    'BAT-LIT-5': {
        'marque': 'Lithium',
        'garantie': 'Garantie 5 ans · ≥ 6 000 cycles (80 % DoD)',
        'description': ('Batterie lithium LiFePO4 basse tension 51,2 V, 5 kWh\n'
                        'BMS intégré, communication CAN/RS485'),
    },
    'BAT-GEL-22': {
        'marque': 'Gel',
        'garantie': 'Garantie 2 ans',
        'description': 'Batterie gel plomb étanche sans entretien, usage solaire',
    },
    'STR-ACIER': {
        'garantie': 'Garantie 20 ans (structure)',
        'description': ('Structure en acier galvanisé à chaud\n'
                        'Visserie inox, mise à la terre incluse'),
    },
    'STR-ALU': {
        'garantie': 'Garantie 20 ans (structure)',
        'description': ('Structure aluminium anodisé anticorrosion\n'
                        'Visserie inox, mise à la terre incluse'),
    },
    'SOC-BET': {
        'description': 'Plot béton préfabriqué — lestage sans percement de l\'étanchéité',
    },
    'SMART-MET': {
        'marque': 'Huawei',
        'description': ('Compteur intelligent triphasé/monophasé\n'
                        'Mesure production/consommation pour zéro injection et suivi'),
    },
    'WIFI-DON': {
        'marque': 'Huawei',
        'description': 'Passerelle Wi-Fi pour supervision en ligne de l\'onduleur',
    },
    'ACC-CAT': {
        'description': ('Connecteurs MC4, presse-étoupes, visserie inox\n'
                        'Goulottes et chemins de câbles, petites fournitures'),
    },
    'TAB-PROT': {
        'description': ('Coffret IP65 : disjoncteurs DC et AC calibrés\n'
                        'Parafoudres type 2 DC/AC, sectionneur DC\n'
                        'Câblage repéré, schéma fourni'),
    },
    'INST-CAT': {
        'description': ('Pose structures et modules, câblage DC/AC\n'
                        'Raccordement au tableau, mise en service et tests\n'
                        'Formation à l\'application de suivi'),
    },
    'TRANS-CAT': {
        'description': 'Livraison du matériel sur site (Maroc)',
    },
    'SUIVI-2A': {
        'description': ('Suivi de production à distance\n'
                        'Visite de maintenance préventive tous les 12 mois pendant 2 ans'),
    },
    # Pompage
    **{sku: {'garantie': 'Garantie constructeur 2 ans', 'description': _DESC_POMPE_IMM,
             } for sku in ('PMP-IMM-1.5M', 'PMP-IMM-3M', 'PMP-IMM-4T',
                           'PMP-IMM-5.5T', 'PMP-IMM-7.5T', 'PMP-IMM-10T')},
    **{sku: {'garantie': 'Garantie constructeur 2 ans', 'description': _DESC_POMPE_SUR,
             } for sku in ('PMP-SUR-1.5M', 'PMP-SUR-3T')},
    **{sku: {'garantie': 'Garantie constructeur 2 ans', 'description': _DESC_VFD,
             } for sku in ('VFD-PMP-1.5M', 'VFD-PMP-3T', 'VFD-PMP-4T',
                           'VFD-PMP-5.5T', 'VFD-PMP-7.5T', 'VFD-PMP-10T')},
    'CAB-6MM-M': {
        'description': 'Câble solaire 6 mm² double isolation, résistant UV (prix au mètre)',
    },
}


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
            # match by SKU (all rows — the DB unique constraint includes
            # archived ones) or by exact name among ACTIVE products only:
            # an archived demo product frees its name for the catalogue item.
            if (Produit.objects.filter(company=company, sku=sku).exists()
                    or Produit.objects.filter(
                        company=company, nom__iexact=nom,
                        is_archived=False).exists()):
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

        # ── Catalogue POMPAGE (additif, prix d'achat laissés vides) ──
        for nom, sku, ttc, qte, seuil, cv, hmt, debit in POMPAGE:
            if (Produit.objects.filter(company=company, sku=sku).exists()
                    or Produit.objects.filter(
                        company=company, nom__iexact=nom,
                        is_archived=False).exists()):
                skipped.append(nom)
                continue
            produit = Produit.objects.create(
                company=company, nom=nom, sku=sku,
                categorie=get_categorie('Pompage'),
                prix_achat=Decimal('0'),  # à remplir par le fondateur
                prix_vente=ht(ttc),
                quantite_stock=qte, seuil_alerte=seuil,
                tva=Decimal('20.00'),
                pompe_cv=Decimal(cv) if cv else None,
                hmt_m=Decimal(hmt) if hmt else None,
                debit_m3j=Decimal(debit) if debit else None,
            )
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=qte, quantite_avant=0, quantite_apres=qte,
                reference='SEED-CATALOGUE',
                note='Stock initial (catalogue pompage)',
            )
            created.append(nom)

        # ── Fiches commerciales : mise à jour ADDITIVE des seuls champs
        #    descriptifs (marque/description/garantie) — jamais prix/quantités ──
        fiches_updated = 0
        for sku, fiche in FICHES.items():
            produit = Produit.objects.filter(company=company, sku=sku).first()
            if not produit:
                continue
            for field in ('marque', 'description', 'garantie'):
                if field in fiche:
                    setattr(produit, field, fiche[field])
            produit.save(update_fields=[f for f in ('marque', 'description', 'garantie')
                                        if f in fiche])
            fiches_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nCatalogue seed for '{company.nom}': "
            f"{len(created)} created, {len(skipped)} already present (untouched), "
            f"{fiches_updated} fiches commerciales mises à jour."
        ))
        for nom in created:
            self.stdout.write(f"  + {nom}")
        if skipped:
            self.stdout.write(self.style.WARNING(
                "\nAlready existed (kept as-is — check their prices against the catalogue):"
            ))
            for nom in skipped:
                self.stdout.write(f"  = {nom}")
