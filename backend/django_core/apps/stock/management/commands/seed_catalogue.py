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


# ── Réforme TVA marocaine 2024–2026 (confirmée par le fondateur) ─────────────
# 10 % : panneaux photovoltaïques UNIQUEMENT. 20 % : tout le reste (onduleurs,
# batteries, structures, câbles, pompes, variateurs et toutes prestations).
# Le TTC reste l'ancre : le HT stocké d'un panneau est dérivé à 10 %
# (1 400 TTC → 1 272,73 HT) pour que le prix TTC affiché ne bouge JAMAIS.
def is_panneau(nom):
    return 'panneau' in (nom or '').lower()


def taux_tva_for(nom):
    return Decimal('10.00') if is_panneau(nom) else Decimal('20.00')


def ht_at(ttc, taux):
    """Prix HT (2 décimales) depuis un TTC au taux donné."""
    return (Decimal(str(ttc)) * Decimal(100) / (Decimal(100) + Decimal(taux))
            ).quantize(Decimal('0.01'))


# ── Taxonomie catalogue : CATÉGORIE → MARQUE → ARTICLES (2026-06) ────────────
# Ordre DÉLIBÉRÉ (cœur solaire d'abord, pompage ensuite, services en fin) —
# pas un accident alphabétique. Onduleurs hybrides et réseau SÉPARÉS.
# La re-catégorisation des produits existants est explicitement autorisée
# par le fondateur ; la classification est par MOTS-CLÉS DU NOM, exactement
# comme l'auto-fill (solar.js / builder.py) — elle ne peut pas diverger.
TAXONOMIE = [
    ('Panneaux photovoltaïques', 10),
    ('Onduleurs réseau', 20),
    ('Onduleurs hybrides', 30),
    ('Batteries', 40),
    ('Structures & fixation', 50),
    ('Protection & accessoires', 60),
    ('Câbles', 70),
    ('Pompes', 80),
    ('Variateurs', 90),
    ('Services & prestations', 100),
]


def classify_categorie(nom):
    """Catégorie cible d'un produit, par mots-clés du nom (insensible accents
    usuels). Tout produit a EXACTEMENT une catégorie ; l'inconnu tombe dans
    « Protection & accessoires »."""
    n = (nom or '').lower().replace('â', 'a').replace('é', 'e').replace('è', 'e')
    if 'panneau' in n:
        return 'Panneaux photovoltaïques'
    if 'onduleur' in n and 'hybride' in n:
        return 'Onduleurs hybrides'
    if 'onduleur' in n:
        return 'Onduleurs réseau'
    if 'afficheur' in n or 'variateur' in n or 'coffret complet' in n:
        return 'Variateurs'
    if 'pompe' in n:
        return 'Pompes'
    if 'batterie' in n:
        return 'Batteries'
    if 'structure' in n or 'socle' in n:
        return 'Structures & fixation'
    if 'cable' in n:
        return 'Câbles'
    if ('installation' in n or 'transport' in n or 'suivi' in n
            or 'maintenance' in n or 'main d' in n):
        return 'Services & prestations'
    return 'Protection & accessoires'


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
    ('Câble solaire 6mm² (au mètre)', 'CAB-6MM-M', 13, 5000, 200, None, None, None),
]

# ── Variateurs VEICHI (prix réels fondateur, 2026-06) ────────────────────────
# "Prix public" = prix de vente TTC ; "prix revendeur" = prix d'ACHAT TTC
# (alimente l'indicateur de marge INTERNE — jamais dans un PDF client).
# Remplacent les anciens coffrets "Variateur pompage solaire ... (coffret
# complet)" aux prix estimés : ces placeholders sont ARCHIVÉS par le seeder
# (autorisation explicite du fondateur, 2026-06-12) — la protection qu'ils
# regroupaient est couverte par les articles protection/accessoires existants.
# (nom, sku, sell_ttc, buy_ttc, kw, tension_v)
VEICHI = [
    ('AFFICHEUR VARIATEUR SI22',           'VEI-SI22-AFF',     420,     360,    None,  None),
    ('VARIATEUR VEICHI SI22 2.2KW 220V',   'VEI-SI22-2.2-220', 1580,    1400,   '2.2', 220),
    ('VARIATEUR VEICHI SI23 2.2KW 220V',   'VEI-SI23-2.2-220', 2530,    2300,   '2.2', 220),
    ('VARIATEUR VEICHI SI23 2.2KW 380V',   'VEI-SI23-2.2-380', 2812.5,  2250,   '2.2', 380),
    ('VARIATEUR VEICHI SI23 4KW 380V',     'VEI-SI23-4-380',   2750,    2400,   '4',   380),
    ('VARIATEUR VEICHI SI23 5.5KW 380V',   'VEI-SI23-5.5-380', 3250,    2850,   '5.5', 380),
    ('VARIATEUR VEICHI SI23 7.5KW 380V',   'VEI-SI23-7.5-380', 4000,    3450,   '7.5', 380),
    ('VARIATEUR VEICHI SI23 11KW 380V',    'VEI-SI23-11-380',  4950,    4300,   '11',  380),
    ('VARIATEUR VEICHI SI23 15KW 380V',    'VEI-SI23-15-380',  6200,    5500,   '15',  380),
    ('VARIATEUR VEICHI SI23 18KW 380V',    'VEI-SI23-18-380',  7000,    6750,   '18',  380),
    ('VARIATEUR VEICHI SI23 22KW 380V',    'VEI-SI23-22-380',  8800,    8000,   '22',  380),
    ('VARIATEUR VEICHI SI23 30KW 380V',    'VEI-SI23-30-380',  10800,   9900,   '30',  380),
    ('VARIATEUR VEICHI SI23 37KW 380V',    'VEI-SI23-37-380',  15500,   14150,  '37',  380),
    ('VARIATEUR VEICHI SI23 45KW 380V',    'VEI-SI23-45-380',  21250,   19260,  '45',  380),
    ('VARIATEUR VEICHI SI23 55KW 380V',    'VEI-SI23-55-380',  22550,   20550,  '55',  380),
    ('VARIATEUR VEICHI SI23 75KW 380V',    'VEI-SI23-75-380',  24750,   22500,  '75',  380),
]

# Placeholders à archiver (jamais supprimés — autorisation fondateur 2026-06-12)
PLACEHOLDER_VFD_SKUS = [
    'VFD-PMP-1.5M', 'VFD-PMP-3T', 'VFD-PMP-4T',
    'VFD-PMP-5.5T', 'VFD-PMP-7.5T', 'VFD-PMP-10T',
]

# ── Pompes OSP série 30 (3", immergées, triphasées 380 V) ────────────────────
# Courbes de performance constructeur : HMT (m) délivrée à chaque débit (m³/h).
# PRIX VOLONTAIREMENT VIDES (0) : à renseigner par le fondateur — tant que le
# prix est vide, le produit est exclu du chiffrage automatique ("prix à
# renseigner" dans le générateur).
OSP_DEBITS_M3H = [0, 12, 24, 30, 36, 39]
# (nom, sku, cv, kw, [hmt aux débits ci-dessus])
OSP = [
    ('Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)',    'PMP-OSP-30-8',  '10',   '7.5',  [91, 85, 70, 60, 43, 34]),
    ('Pompe immergée OSP 30/11 — 12.5 CV / 9.3 kW (3", 380V)', 'PMP-OSP-30-11', '12.5', '9.3',  [125, 117, 97, 83, 59, 46]),
    ('Pompe immergée OSP 30/13 — 15 CV / 11 kW (3", 380V)',    'PMP-OSP-30-13', '15',   '11',   [148, 138, 114, 98, 70, 55]),
    ('Pompe immergée OSP 30/15 — 17.5 CV / 13 kW (3", 380V)',  'PMP-OSP-30-15', '17.5', '13',   [171, 159, 132, 113, 81, 63]),
    ('Pompe immergée OSP 30/16 — 20 CV / 15 kW (3", 380V)',    'PMP-OSP-30-16', '20',   '15',   [182, 170, 141, 120, 86, 67]),
    ('Pompe immergée OSP 30/17 — 20 CV / 15 kW (3", 380V)',    'PMP-OSP-30-17', '20',   '15',   [194, 180, 150, 128, 92, 71]),
    ('Pompe immergée OSP 30/20 — 25 CV / 18.5 kW (3", 380V)',  'PMP-OSP-30-20', '25',   '18.5', [228, 212, 176, 150, 108, 84]),
    ('Pompe immergée OSP 30/21 — 25 CV / 18.5 kW (3", 380V)',  'PMP-OSP-30-21', '25',   '18.5', [239, 223, 185, 158, 113, 88]),
    ('Pompe immergée OSP 30/25 — 30 CV / 22 kW (3", 380V)',    'PMP-OSP-30-25', '30',   '22',   [285, 265, 220, 188, 135, 105]),
    ('Pompe immergée OSP 30/26 — 30 CV / 22 kW (3", 380V)',    'PMP-OSP-30-26', '30',   '22',   [296, 276, 229, 195, 140, 109]),
    ('Pompe immergée OSP 30/35 — 40 CV / 30 kW (3", 380V)',    'PMP-OSP-30-35', '40',   '30',   [399, 371, 308, 263, 189, 147]),
]

_DESC_POMPE_IMM = ('Pompe immergée pour forage, corps inox\n'
                   'Pilotée par variateur solaire (AC, compatible champ PV)\n'
                   'Adaptée à l\'irrigation et l\'alimentation en eau agricole')
_DESC_POMPE_SUR = ('Pompe de surface pour puits/bassin, amorçage facilité\n'
                   'Pilotée par variateur solaire (AC, compatible champ PV)')
_DESC_VEICHI = ('Variateur solaire dédié pompage : MPPT intégré, entrée PV directe\n'
                'Pilotage automatique lever/coucher du soleil, protection marche à sec\n'
                'Compatible pompes AC triphasées/monophasées standards')
_DESC_OSP = ('Pompe immergée 3 pouces pour forage, triphasée 380 V\n'
             'Pilotée par variateur solaire (AC, compatible champ PV)\n'
             'Courbe de performance constructeur intégrée (débit ↔ HMT)')

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
    'CAB-6MM-M': {
        'description': 'Câble solaire 6 mm² double isolation, résistant UV (prix au mètre)',
    },
    # Variateurs VEICHI
    'VEI-SI22-AFF': {
        'marque': 'VEICHI',
        'garantie': 'Garantie constructeur 2 ans',
        'description': ('Afficheur déporté pour variateur VEICHI SI22\n'
                        'Lecture des paramètres et défauts au pied du coffret'),
    },
    **{sku: {'marque': 'VEICHI', 'garantie': 'Garantie constructeur 2 ans',
             'description': _DESC_VEICHI,
             } for sku in ('VEI-SI22-2.2-220', 'VEI-SI23-2.2-220',
                           'VEI-SI23-2.2-380', 'VEI-SI23-4-380',
                           'VEI-SI23-5.5-380', 'VEI-SI23-7.5-380',
                           'VEI-SI23-11-380', 'VEI-SI23-15-380',
                           'VEI-SI23-18-380', 'VEI-SI23-22-380',
                           'VEI-SI23-30-380', 'VEI-SI23-37-380',
                           'VEI-SI23-45-380', 'VEI-SI23-55-380',
                           'VEI-SI23-75-380')},
    # Pompes OSP série 30
    **{sku: {'marque': 'OSP', 'garantie': 'Garantie constructeur 2 ans',
             'description': _DESC_OSP,
             } for sku in ('PMP-OSP-30-8', 'PMP-OSP-30-11', 'PMP-OSP-30-13',
                           'PMP-OSP-30-15', 'PMP-OSP-30-16', 'PMP-OSP-30-17',
                           'PMP-OSP-30-20', 'PMP-OSP-30-21', 'PMP-OSP-30-25',
                           'PMP-OSP-30-26', 'PMP-OSP-30-35')},
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

        _ordres = dict(TAXONOMIE)

        def get_categorie(nom):
            if nom not in categories:
                categories[nom], _ = Categorie.objects.get_or_create(
                    company=company, nom=nom,
                    defaults={'description': 'Catalogue simulateur',
                              'ordre': _ordres.get(nom, 100)},
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

            taux = taux_tva_for(nom)
            produit = Produit.objects.create(
                company=company,
                nom=nom,
                sku=sku,
                categorie=get_categorie(classify_categorie(nom)),
                prix_achat=ht_at(buy_ttc, taux),
                prix_vente=ht_at(sell_ttc, taux),
                quantite_stock=qte,
                seuil_alerte=seuil,
                tva=taux,
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
                categorie=get_categorie(classify_categorie(nom)),
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

        # ── Variateurs VEICHI (prix réels : vente publique + achat revendeur) ──
        for nom, sku, sell_ttc, buy_ttc, kw, tension in VEICHI:
            if (Produit.objects.filter(company=company, sku=sku).exists()
                    or Produit.objects.filter(
                        company=company, nom__iexact=nom,
                        is_archived=False).exists()):
                skipped.append(nom)
                continue
            produit = Produit.objects.create(
                company=company, nom=nom, sku=sku,
                categorie=get_categorie(classify_categorie(nom)),
                prix_achat=ht(buy_ttc),
                prix_vente=ht(sell_ttc),
                quantite_stock=20, seuil_alerte=2,
                tva=Decimal('20.00'),
                pompe_kw=Decimal(kw) if kw else None,
                tension_v=tension,
            )
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=20, quantite_avant=0, quantite_apres=20,
                reference='SEED-CATALOGUE',
                note='Stock initial (variateurs VEICHI)',
            )
            created.append(nom)

        # ── Pompes OSP série 30 : courbes constructeur, PRIX VIDES (0) ──
        # Tant que prix_vente vaut 0, le produit est exclu du chiffrage
        # automatique ("prix à renseigner" dans le générateur).
        for nom, sku, cv, kw, hmt_curve in OSP:
            if (Produit.objects.filter(company=company, sku=sku).exists()
                    or Produit.objects.filter(
                        company=company, nom__iexact=nom,
                        is_archived=False).exists()):
                skipped.append(nom)
                continue
            produit = Produit.objects.create(
                company=company, nom=nom, sku=sku,
                categorie=get_categorie(classify_categorie(nom)),
                prix_achat=Decimal('0'),
                prix_vente=Decimal('0'),  # à renseigner par le fondateur
                quantite_stock=20, seuil_alerte=2,
                tva=Decimal('20.00'),
                pompe_cv=Decimal(cv),
                pompe_kw=Decimal(kw),
                tension_v=380,
                hmt_m=Decimal(str(hmt_curve[0])),
                courbe_pompe={'debits_m3h': OSP_DEBITS_M3H, 'hmt_m': hmt_curve},
            )
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=20, quantite_avant=0, quantite_apres=20,
                reference='SEED-CATALOGUE',
                note='Stock initial (pompes OSP — prix à renseigner)',
            )
            created.append(nom)

        # ── Archivage des coffrets variateurs PLACEHOLDER (prix estimés) ──
        # Exception ponctuelle à la règle "additif uniquement", explicitement
        # autorisée par le fondateur (2026-06-12) : ces articles n'ont jamais
        # porté de vrais prix. Archivés (jamais supprimés), prix intacts.
        archived_count = Produit.objects.filter(
            company=company, sku__in=PLACEHOLDER_VFD_SKUS,
            is_archived=False).update(is_archived=True)

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

        # ── Réforme TVA 2024–2026 (autorisation explicite du fondateur) ──
        # Panneaux PV → 10 % avec HT re-dérivé pour PRÉSERVER le TTC à
        # l'identique ; tout produit sans taux → 20 %. Idempotent : un panneau
        # déjà à 10 % n'est jamais retouché. Seuls tva / prix HT dérivés
        # bougent — le TTC affiché et chiffré ne change JAMAIS.
        # ── Taxonomie CATÉGORIE → MARQUE (re-catégorisation autorisée) ──
        # Crée les 10 catégories ordonnées et range CHAQUE produit dans
        # exactement une. Rien n'est supprimé ; prix/specs/marques intacts.
        taxo = {}
        for nom_cat, ordre in TAXONOMIE:
            cat, created_cat = Categorie.objects.get_or_create(
                company=company, nom=nom_cat,
                defaults={'description': 'Taxonomie catalogue', 'ordre': ordre})
            if cat.ordre != ordre:
                cat.ordre = ordre
                cat.save(update_fields=['ordre'])
            taxo[nom_cat] = cat
        recategorises = 0
        for produit in Produit.objects.filter(company=company):
            cible = taxo[classify_categorie(produit.nom)]
            if produit.categorie_id != cible.id:
                produit.categorie = cible
                produit.save(update_fields=['categorie'])
                recategorises += 1

        tva_updated = 0
        for produit in Produit.objects.filter(company=company):
            if is_panneau(produit.nom):
                if produit.tva == Decimal('10.00'):
                    continue
                old_taux = produit.tva if produit.tva is not None else Decimal('20.00')
                facteur = (Decimal(100) + old_taux) / Decimal(110)
                produit.prix_vente = (produit.prix_vente * facteur).quantize(Decimal('0.01'))
                produit.prix_achat = (produit.prix_achat * facteur).quantize(Decimal('0.01'))
                produit.tva = Decimal('10.00')
                produit.save(update_fields=['prix_vente', 'prix_achat', 'tva'])
                tva_updated += 1
            elif produit.tva is None:
                produit.tva = Decimal('20.00')
                produit.save(update_fields=['tva'])
                tva_updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nCatalogue seed for '{company.nom}': "
            f"{len(created)} created, {len(skipped)} already present (untouched), "
            f"{fiches_updated} fiches commerciales mises à jour, "
            f"{archived_count} placeholders archivés, "
            f"{tva_updated} taux TVA alignés (réforme 10 % panneaux), "
            f"{recategorises} produits rangés dans la taxonomie."
        ))
        for nom in created:
            self.stdout.write(f"  + {nom}")
        if skipped:
            self.stdout.write(self.style.WARNING(
                "\nAlready existed (kept as-is — check their prices against the catalogue):"
            ))
            for nom in skipped:
                self.stdout.write(f"  = {nom}")
