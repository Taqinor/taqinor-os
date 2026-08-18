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

Les fiches (commerciales et techniques) sont RÉ-APPLIQUÉES à chaque run, ce qui
rattrape une base de production restée en arrière du catalogue — c'est pourquoi
``scripts/deploy-prod.ps1`` appelle cette commande à chaque déploiement. Sur une
fiche technique DÉJÀ existante, le défaut est de COMBLER les champs vides sans
jamais écraser une valeur saisie par le fondateur (``--reappliquer-fiches``
rouvre explicitement cette porte pour une correction de datasheet).

Run:
  docker compose exec django_core python manage.py seed_catalogue
  (options --company-slug, default: taqinor-demo ; --reappliquer-fiches)
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
    # Marque RÉELLE : Dyness (dyness.com). Le catalogue historique écrivait
    # « Deyness » — faute corrigée (décision fondateur 2026-08-18). Les SKU
    # BAT-DEY-* NE CHANGENT PAS : l'appariement du seeder se fait par SKU
    # d'abord, donc une base déjà seedée est retrouvée et SAUTÉE (aucun
    # doublon), que la migration de renommage soit passée ou non.
    ('Batterie Dyness 5 kWh',  'BAT-DEY-5',  'Batteries', 17000, 13000, 500, 5),
    ('Batterie Dyness 10 kWh', 'BAT-DEY-10', 'Batteries', 30000, 22000, 500, 5),
    ('Batterie Lithium 5 kWh',  'BAT-LIT-5',  'Batteries', 15500, 13200, 500, 5),
    ('Batterie Gel 2.2 kWh',    'BAT-GEL-22', 'Batteries', 5000, 3100, 500, 5),
    # ── Structure & divers ──
    ('Structures acier',           'STR-ACIER', 'Accessoires', 500, 350, 2000, 50),
    ('Structures aluminium',       'STR-ALU',   'Accessoires', 850, 600, 2000, 50),
    ('Socles',                     'SOC-BET',   'Accessoires', 80, 50, 5000, 100),
    # ── Câbles Nexans 6 mm² AU MÈTRE (règle fondateur 18/08) ──
    # 12,00 MAD HT le mètre → 14,40 TTC (TVA 20 %). Les métrés sont posés par
    # l'auto-composition : 60 m de DC par palier de 5 kWc, 25 m + 15 m/palier
    # de terre. prix_achat laissé vide (à renseigner par le fondateur).
    ('Câble solaire Nexans 6 mm² (au mètre)',  'CAB-NEX-DC-6',  'Accessoires', 14.4, 0, 10000, 500),
    ('Câble de terre Nexans 6 mm² (au mètre)', 'CAB-NEX-TER-6', 'Accessoires', 14.4, 0, 10000, 500),
    ('Smart Meter',                'SMART-MET', 'Accessoires', 1800, 1200, 500, 5),
    ('Wifi Dongle',                'WIFI-DON',  'Accessoires', 1200, 700, 500, 5),
    ('Accessoires',                'ACC-CAT',   'Accessoires', 2000, 2000, 999, 0),
    ('Tableau De Protection AC/DC', 'TAB-PROT', 'Accessoires', 2000, 1500, 999, 0),
    ('Installation',               'INST-CAT',  'Accessoires', 4800, 4000, 999, 0),
    ('Transport',                  'TRANS-CAT', 'Accessoires', 1000, 800, 999, 0),
    ('Suivi journalier, maintenance chaque 12 mois pendant 2 ans',
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

# PVOND (2026-08-18) — ARTEFACTS catalogue à archiver, MÊME patron que les
# coffrets estimés ci-dessus (autorisation fondateur : jamais de suppression).
# artefact PVG4 : palier inexistant chez Huawei ; le besoin mono 10-12 kW se
# couvre par Deye SG02LP1 (à référencer sur décision fondateur).
ARTEFACTS_ONDULEUR_SKUS = ['OND-R-HUA-10M', 'OND-R-HUA-12M']

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

# ── PVG3 — Câbles & protections DC/AC (prix vides, approuvé fondateur
# 2026-08-14) ─────────────────────────────────────────────────────────────
# Référentiel SKU pur : sections/calibres normalisés d'une installation PV
# résidentielle/C&I (câble solaire, protections DC/AC, coffrets). PRIX
# VOLONTAIREMENT VIDES (0) : à renseigner par le fondateur — tant que
# prix_vente vaut 0, le produit est exclu du chiffrage automatique, même
# garde que les pompes OSP (cf. apps/ventes/services._has_price).
# Câbles vendus AU MÈTRE : suit exactement le précédent CAB-6MM-M
# (nom seul « (au mètre) », unite_stock laissé au défaut « unité »).
# (nom, sku, qte, seuil)
CABLES_PROTECTIONS_VIDES = [
    # Câbles solaires H1Z2Z2-K (DC, double isolation, résistant UV)
    ('Câble solaire H1Z2Z2-K 4 mm² (au mètre)',  'CAB-H1Z2Z2-4-M',  5000, 200),
    ('Câble solaire H1Z2Z2-K 6 mm² (au mètre)',  'CAB-H1Z2Z2-6-M',  5000, 200),
    ('Câble solaire H1Z2Z2-K 10 mm² (au mètre)', 'CAB-H1Z2Z2-10-M', 5000, 200),
    ('Câble solaire H1Z2Z2-K 16 mm² (au mètre)', 'CAB-H1Z2Z2-16-M', 5000, 200),
    # Fusibles & porte-fusible DC
    ('Fusible gPV 1000 VDC 15 A', 'FUS-GPV-1000-15A', 200, 10),
    ('Fusible gPV 1000 VDC 20 A', 'FUS-GPV-1000-20A', 200, 10),
    ('Porte-fusible 1000 VDC',    'PF-1000',           200, 10),
    # Parafoudres
    ('Parafoudre DC type 2 1000 V', 'PARA-DC-T2-1000', 100, 5),
    ('Parafoudre AC type 2',        'PARA-AC-T2',       100, 5),
    # Sectionneur DC
    ('Sectionneur DC 1000 V 25 A', 'SECT-DC-1000-25A', 100, 5),
    # Disjoncteurs AC courbe C — mono ET tétrapolaire
    ('Disjoncteur AC courbe C 16 A monophasé',    'DISJ-AC-C-16-1P', 100, 5),
    ('Disjoncteur AC courbe C 20 A monophasé',    'DISJ-AC-C-20-1P', 100, 5),
    ('Disjoncteur AC courbe C 25 A monophasé',    'DISJ-AC-C-25-1P', 100, 5),
    ('Disjoncteur AC courbe C 32 A monophasé',    'DISJ-AC-C-32-1P', 100, 5),
    ('Disjoncteur AC courbe C 16 A tétrapolaire', 'DISJ-AC-C-16-4P', 100, 5),
    ('Disjoncteur AC courbe C 20 A tétrapolaire', 'DISJ-AC-C-20-4P', 100, 5),
    ('Disjoncteur AC courbe C 25 A tétrapolaire', 'DISJ-AC-C-25-4P', 100, 5),
    ('Disjoncteur AC courbe C 32 A tétrapolaire', 'DISJ-AC-C-32-4P', 100, 5),
    # Différentiels (DDR) type A
    ('Différentiel (DDR) type A 300 mA 40 A', 'DDR-A-300-40', 50, 5),
    ('Différentiel (DDR) type A 300 mA 63 A', 'DDR-A-300-63', 50, 5),
    # Coffrets
    ('Coffret DC 2 strings', 'COF-DC-2STR', 100, 5),
    ('Coffret AC',           'COF-AC',      100, 5),
]

# ── PVG4 — Onduleur Deye 15 kW BASSE TENSION (décision fondateur 2026-08-18)
# Série officielle Deye SUN-14/15/16/18/20K-SG05LP3-EU-SM2 (triphasé BASSE
# TENSION 48 V, lancée 2024). Le catalogue n'avait que le palier 10 kW
# (OND-H-DEY-10T, PV85) ; ce palier 15 kW COMPLÈTE la gamme LV SG05LP3 — À NE
# PAS CONFONDRE avec OND-H-DEY-15T (gamme HAUTE TENSION SG01HP3, cf. la note
# PVG4 « INCOMPATIBILITÉ MÉTIER » plus haut : deux appareils réels différents
# au même palier de puissance, d'où un SKU et un nom distincts ici). PRIX
# VOLONTAIREMENT VIDE (0) : à renseigner par le fondateur — même garde que
# les pompes OSP / câbles PVG3 ci-dessus (``_has_price`` exclut le produit de
# l'auto-composition, le générateur l'affiche grisé « prix à renseigner »).
#
# PVOND (18/08/2026) — le palier 20 kW rejoint la gamme LV pour la MÊME raison
# que le 15 kW : OND-H-DEY-20T est un SG01HP3 HAUTE TENSION (160-700 V), donc
# INCOMPATIBLE avec les batteries Dyness 51,2 V de la maison. Sans son jumeau
# basse tension, un devis 20 kW « avec batterie » n'avait aucun onduleur
# apparaissable au catalogue. Même patron exact que le 15 kW : SKU et nom
# distincts, prix VIDES (jamais inventés), modèle « supposé — à confirmer ».
# (nom, sku, qte, seuil)
ONDULEUR_DEYE_15K_LV_VIDE = [
    ('Onduleur hybride Deye 15kW Triphasé Basse Tension', 'OND-DEY-15K-LV', 500, 5),
    ('Onduleur hybride Deye 20kW Triphasé Basse Tension', 'OND-DEY-20K-LV', 500, 5),
]

# ── Batterie Dyness HAUTE TENSION — 16 kWh (décision fondateur 2026-08-18) ──
# Vendue PAR TRANCHE de 16 kWh, 3 000 DH/kWh (prix fondateur) → 48 000 DH TTC
# la tranche ; rack et control box inclus dans le prix. Prix ACHAT
# volontairement VIDE (0, non communiqué) : ne retire PAS le produit de
# l'auto-composition (seul prix_vente=0 le ferait, cf. ``_has_price``) — ce
# produit est un vrai article vendable, à la différence des pompes OSP/câbles.
# Vérifié sur dyness.com/dyness.us (recherche 2026-08-18) : AUCUNE
# configuration officielle Dyness ne fait exactement 16 kWh — Tower
# T7/T10/T14/T17/T21 = 7,10/10,66/14,21/17,76/21,31 kWh, Orion = 9,9/14,9/19,9
# kWh. Produit catalogue GÉNÉRIQUE (marque Dyness, capacité, prix,
# description) SANS référence de modèle ni tension nominale inventées (règle
# des faits vérifiés) — aucune ``FicheTechnique`` n'est donc créée pour ce SKU.
# ⚠ HAUTE TENSION : ne doit JAMAIS être choisie par l'auto-composition
# résidentielle BASSE TENSION (48 V, BAT-DEY-5/10) — garde posée côté
# apps/ventes/services.py (mot-clé « haute tension » exclu du vivier
# batterie, cf. ``_is_battery_basse_tension`` et le filtre dans
# ``composition_residentielle``).
# (nom, sku, sell_ttc, qte, seuil)
BATTERIE_DYNESS_HV = [
    ('Batterie Dyness haute tension — 16 kWh', 'BAT-DYN-HV-16', 48000, 500, 5),
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
    # PVG4 — Onduleur Deye 15 kW BASSE TENSION (décision fondateur 2026-08-18,
    # SUN-15K-SG05LP3-EU-SM2). Le modèle est donné directement par le
    # fondateur (source WebFetch, pas une supposition) : l'addendum
    # « Modèle confirmé fondateur : … » est posé automatiquement ci-dessous
    # via MODELE_SUPPOSE_PVG4/MODELES_CONFIRMES_FONDATEUR, comme OND-H-DEY-10T.
    'OND-DEY-15K-LV': {
        'marque': 'Deye',
        'garantie': 'Garantie constructeur 5 à 10 ans (selon site d\'installation)',
        'description': ('Onduleur hybride Deye SUN-…K-SG05LP3, série basse tension 48 V (2024)\n'
                        'Compatible batteries lithium/plomb 48 V (plage 40-60 V, BMS auto-adaptatif)\n'
                        'Bascule secours (EPS/UPS), monitoring GPRS/WiFi/Bluetooth/4G/LAN\n'
                        'Rendement max 97,6 % · rendement euro 97,0 %'),
    },
    # PVOND (18/08/2026) — jumeau BASSE TENSION du palier 20 kW. Même
    # datasheet de famille que le 15 kW (SUN-14-20K-SG05LP3-EU-SM2) ; le
    # modèle exact n'est PAS confirmé par le fondateur, il porte donc
    # « Modèle supposé : … — à confirmer fondateur » (il n'est volontairement
    # pas listé dans MODELES_CONFIRMES_FONDATEUR).
    'OND-DEY-20K-LV': {
        'marque': 'Deye',
        'garantie': 'Garantie constructeur 5 à 10 ans (selon site d\'installation)',
        'description': ('Onduleur hybride Deye SUN-…K-SG05LP3, série basse tension 48 V (2024)\n'
                        'Compatible batteries lithium/plomb 48 V (plage 40-60 V, BMS auto-adaptatif)\n'
                        'Bascule secours (EPS/UPS), monitoring GPRS/WiFi/Bluetooth/4G/LAN\n'
                        'Rendement max 97,6 % · rendement euro 97,0 %'),
    },
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
        'marque': 'Dyness',
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
    # PVG4 — Batterie Dyness HAUTE TENSION, 16 kWh (décision fondateur
    # 2026-08-18) : produit catalogue GÉNÉRIQUE (vérifié dyness.com/dyness.us,
    # aucune configuration officielle ne fait 16 kWh — cf. le commentaire sur
    # BATTERIE_DYNESS_HV plus haut). Pas de garantie sourcée : champ omis
    # plutôt qu'inventé.
    'BAT-DYN-HV-16': {
        'marque': 'Dyness',
        'description': ('Batterie Dyness haute tension, vendue par tranche de 16 kWh\n'
                        'Rack et control box inclus dans le prix de la tranche\n'
                        'Produit catalogue générique : aucune référence Dyness officielle '
                        'ne correspond à 16 kWh (Tower/Orion) — modèle et tension nominale '
                        'non renseignés, faute de source vérifiée'),
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
    # ── PVG3 — Câbles & protections (descriptions FR courtes) ──
    'CAB-H1Z2Z2-4-M': {
        'description': 'Câble solaire H1Z2Z2-K 4 mm², double isolation, résistant UV (au mètre)',
    },
    'CAB-H1Z2Z2-6-M': {
        'description': 'Câble solaire H1Z2Z2-K 6 mm², double isolation, résistant UV (au mètre)',
    },
    'CAB-H1Z2Z2-10-M': {
        'description': 'Câble solaire H1Z2Z2-K 10 mm², double isolation, résistant UV (au mètre)',
    },
    'CAB-H1Z2Z2-16-M': {
        'description': 'Câble solaire H1Z2Z2-K 16 mm², double isolation, résistant UV (au mètre)',
    },
    'FUS-GPV-1000-15A': {
        'description': 'Fusible cartouche gPV 1000 VDC, calibre 15 A, protection string PV',
    },
    'FUS-GPV-1000-20A': {
        'description': 'Fusible cartouche gPV 1000 VDC, calibre 20 A, protection string PV',
    },
    'PF-1000': {
        'description': 'Porte-fusible 1000 VDC pour cartouche gPV (coffret DC)',
    },
    'PARA-DC-T2-1000': {
        'description': 'Parafoudre DC type 2, tension max 1000 V, protection champ PV',
    },
    'PARA-AC-T2': {
        'description': 'Parafoudre AC type 2, protection surtension réseau',
    },
    'SECT-DC-1000-25A': {
        'description': 'Sectionneur DC 1000 V, calibre 25 A, coupure de charge champ PV',
    },
    'DISJ-AC-C-16-1P': {
        'description': 'Disjoncteur AC courbe C 16 A monophasé, protection ligne onduleur',
    },
    'DISJ-AC-C-20-1P': {
        'description': 'Disjoncteur AC courbe C 20 A monophasé, protection ligne onduleur',
    },
    'DISJ-AC-C-25-1P': {
        'description': 'Disjoncteur AC courbe C 25 A monophasé, protection ligne onduleur',
    },
    'DISJ-AC-C-32-1P': {
        'description': 'Disjoncteur AC courbe C 32 A monophasé, protection ligne onduleur',
    },
    'DISJ-AC-C-16-4P': {
        'description': 'Disjoncteur AC courbe C 16 A tétrapolaire, protection ligne onduleur triphasé',
    },
    'DISJ-AC-C-20-4P': {
        'description': 'Disjoncteur AC courbe C 20 A tétrapolaire, protection ligne onduleur triphasé',
    },
    'DISJ-AC-C-25-4P': {
        'description': 'Disjoncteur AC courbe C 25 A tétrapolaire, protection ligne onduleur triphasé',
    },
    'DISJ-AC-C-32-4P': {
        'description': 'Disjoncteur AC courbe C 32 A tétrapolaire, protection ligne onduleur triphasé',
    },
    'DDR-A-300-40': {
        'description': 'Différentiel (DDR) type A 300 mA, calibre 40 A, protection des personnes',
    },
    'DDR-A-300-63': {
        'description': 'Différentiel (DDR) type A 300 mA, calibre 63 A, protection des personnes',
    },
    'COF-DC-2STR': {
        'description': 'Coffret DC 2 strings : sectionneur, fusibles et parafoudre DC pré-câblés',
    },
    'COF-AC': {
        'description': 'Coffret AC : disjoncteur et parafoudre AC pré-câblés en sortie onduleur',
    },
}


# ── PVG4 — Modèle constructeur SUPPOSÉ par palier catalogue (recherche
# 2026-08-14, sourcée — approuvé fondateur) ─────────────────────────────────
# Le catalogue ne référence aucun modèle réel : chaque entrée ci-dessous
# reconstitue le modèle constructeur le PLUS PROBABLE pour ce palier de
# puissance/gamme. Utilisé UNIQUEMENT pour agrémenter la description
# commerciale (« Modèle supposé : … — à confirmer fondateur ») — jamais pour
# fabriquer une caractéristique électrique non sourcée (cf. dictionnaires
# ONDULEUR_/BATTERIE_FICHES_TECHNIQUES plus bas, où chaque champ porte sa
# propre source ou reste NULL).
#
# ⚠ INCOMPATIBILITÉ MÉTIER remontée au fondateur : les Deye triphasés 15/20
# kW réels appartiennent à la gamme HAUTE TENSION (batterie HV 160-700 V,
# SG01HP3) ; la gamme basse tension 51,2 V (SG04LP3/SG05LP3, compatible
# BAT-DEY-5/10) s'arrête à 12 kW — l'appairage OND-H-DEY-15T/20T + BAT-DEY-5/10
# est ÉLECTRIQUEMENT IMPOSSIBLE dans la gamme réelle. Les paliers Huawei mono
# réseau 10/12 kW sont eux des ARTEFACTS catalogue : aucun SUN2000 mono
# réseau réel ne dépasse 6 kW (au-delà la gamme Huawei mono passe en
# hybride, autre catégorie) — d'où OND-R-HUA-10M / OND-R-HUA-12M SANS fiche
# technique (absents des dictionnaires ci-dessous, aucune valeur inventée).
MODELE_SUPPOSE_PVG4 = {
    'OND-R-HUA-5M': 'Huawei SUN2000-5KTL-L1',            # solar.huawei.com sun2000-3-4-5-6ktl-l1/specs
    'OND-R-HUA-10T': 'Huawei SUN2000-10KTL-M1',          # solar.huawei.com m1/specs
    'OND-R-HUA-15T': 'Huawei SUN2000-15KTL-M5',          # enfsolar 16424 + huawei EDOC1100253093
    'OND-R-HUA-20T': 'Huawei SUN2000-20KTL-M5',          # globalsunhub
    'OND-R-HUA-25T': 'Huawei SUN2000-25KTL-M5',          # enfsolar
    # PVOND (2026-08-18) — édition PRÉSUMÉE M3 (gamme EMEA courante) ; le M0
    # (édition AU) reste documenté dans FICHES_TECHNIQUES, à confirmer à l'achat.
    'OND-R-HUA-50T': 'Huawei SUN2000-50KTL-M3',          # huawei EDOC1100016052 (M0) / fiche M3 EMEA
    'OND-R-HUA-100T': 'Huawei SUN2000-100KTL-M2',        # globalsunhub
    'OND-R-HUA-150T': 'Huawei SUN2000-150K-MG0',         # solar.huawei.com mg0/specs
    'OND-H-DEY-5M': 'Deye SUN-5K-SG04LP1-EU(-SM2)',      # liriksolar datasheet
    'OND-H-DEY-10M': 'Deye SUN-10K-SG02LP1-EU-AM3',      # nastechsolar datasheet — divergence plage MPPT
    # PV85 — TRANCHÉ PAR LE FONDATEUR (2026-08-15) : le 10 kW triphasé du
    # catalogue est un SG05LP3 (révision SM2), PAS le SG04LP3 supposé en PVG4.
    # Seul SKU dont le modèle est CONFIRMÉ (cf. MODELES_CONFIRMES_FONDATEUR).
    'OND-H-DEY-10T': 'Deye SUN-10K-SG05LP3-EU-SM2',      # deyeinverter.com datasheet 2024-09 + manuel 2025-11
    'OND-H-DEY-15T': 'Deye SUN-15K-SG01HP3-EU-AM2',      # deyeinverter datasheet sun-(5-25)k-sg01hp3
    'OND-H-DEY-20T': 'Deye SUN-20K-SG01HP3-EU-AM2',      # solarhouse.bg + pretapower
    'BAT-DEY-5': 'Dyness DL5.0C',                        # dyness.com DL5.0C datasheet
    'BAT-DEY-10': 'Dyness Powerbox Pro/G2 10.24',        # inverter-warehouse.co.za
    # PVG4 — décision fondateur 2026-08-18 : nouveau palier 15 kW basse
    # tension, modèle donné DIRECTEMENT par le fondateur (pas une supposition
    # à deviner) — CONFIRMÉ dès la première seed, comme le 10T ci-dessus.
    'OND-DEY-15K-LV': 'Deye SUN-15K-SG05LP3-EU-SM2',     # deyeinverter.com datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf (2024-06-01)
    'OND-DEY-20K-LV': 'Deye SUN-20K-SG05LP3-EU-SM2',     # deyeinverter.com datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf (2024-06-01) — colonne 20K, modèle SUPPOSÉ (non confirmé fondateur)
}
# PV85 — SKU dont le modèle constructeur n'est PLUS une supposition : le
# fondateur a tranché. Leur addendum de description dit « Modèle confirmé
# fondateur : … » (pas « supposé … — à confirmer »), et c'est cette mention
# qui autorise le moteur électrique à NOMMER l'appareil sur le schéma.
MODELES_CONFIRMES_FONDATEUR = ('OND-H-DEY-10T', 'OND-DEY-15K-LV')

# Ajoute la mention du modèle (supposé ou confirmé) à la description
# commerciale existante (SKU déjà présent dans FICHES ci-dessus) — additif,
# déterministe donc idempotent (le même texte complet est reposé à chaque run).
for _sku_pvg4, _modele_pvg4 in MODELE_SUPPOSE_PVG4.items():
    if _sku_pvg4 in FICHES and 'description' in FICHES[_sku_pvg4]:
        if _sku_pvg4 in MODELES_CONFIRMES_FONDATEUR:
            _addendum = f'\nModèle confirmé fondateur : {_modele_pvg4}'
        else:
            _addendum = (f'\nModèle supposé : {_modele_pvg4}'
                         ' — à confirmer fondateur')
        if not FICHES[_sku_pvg4]['description'].endswith(_addendum):
            FICHES[_sku_pvg4]['description'] += _addendum


# ── PVOND — PLAGE DE TENSION BATTERIE par référence onduleur ────────────────
#
# La neuvième variable du CONTRAT ONDULEUR (``apps/stock/selectors.py``) —
# celle qui décide quelle batterie s'accroche à quel onduleur — n'a AUCUN champ
# sur ``FicheTechnique`` (constat déjà écrit noir sur blanc dans les
# commentaires PV85 ci-dessous : « NON seedés faute de champ … plage batterie
# 40-60 V »). Elle est donc posée EN DONNÉE, sur une ligne marquée de la
# description — même patron que « Modèle confirmé fondateur : … » juste
# au-dessus, et lue par ``stock.selectors.plage_batterie_onduleur``.
#
# ``None`` = déclaration EXPLICITE « pas de batterie » (onduleur réseau) : le
# contrat est SATISFAIT. Ne rien déclarer du tout voudrait dire « on ne sait
# pas » — et l'onduleur serait grisé au générateur.
#
# ⚠ Les dix références Huawei du catalogue sont vendues par TAQINOR en
# configuration RÉSEAU (string on-grid, sans stockage) : c'est ce que dit leur
# nom, et c'est ce que déclare cette table. Deux appareils de la gamme
# SUPPORTENT pourtant une batterie sur leur fiche constructeur (SUN2000-5KTL-L1
# : 350-450 V avec une LG Chem RESU, 350-560 V avec une Huawei Smart ESS ;
# SUN2000-10KTL-M1 : 600-980 V avec une Huawei Smart String ESS) — donc PAS une
# fenêtre unique, mais une fenêtre PAR MARQUE de batterie, que le contrat (un
# seul couple min/max) ne sait pas représenter. Le jour où le fondateur vend
# l'un d'eux AVEC stockage, la ligne se change ici, en donnée.
PLAGE_BATTERIE_ONDULEUR = {
    # Huawei SUN2000 — vendus en réseau (cf. l'avertissement ci-dessus).
    'OND-R-HUA-5M': None,
    'OND-R-HUA-10M': None,
    'OND-R-HUA-10T': None,
    'OND-R-HUA-12M': None,
    'OND-R-HUA-15T': None,
    'OND-R-HUA-20T': None,
    'OND-R-HUA-25T': None,
    'OND-R-HUA-50T': None,
    'OND-R-HUA-100T': None,
    'OND-R-HUA-150T': None,
    # Deye BASSE TENSION 48 V — familles SG04LP1 / SG02LP1 / SG05LP3.
    # Sources : datasheet SG04LP1 (liriksolar) ; datasheet SG02LP1-EU-AM3
    # (liriksolar) ; datasheet officielle deyeinverter.com
    # datasheet_sun-3-12k-sg05lp3-eu-sm2_240927_en.pdf (2024-09-27) et
    # datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf (2024-06-01) — la
    # fenêtre 40-60 V y est donnée PARTAGÉE par toute la famille SG05LP3.
    'OND-H-DEY-5M': (40, 60),
    'OND-H-DEY-10M': (40, 60),
    'OND-H-DEY-10T': (40, 60),
    'OND-DEY-15K-LV': (40, 60),
    'OND-DEY-20K-LV': (40, 60),
    # Deye HAUTE TENSION — famille SG01HP3, batterie lithium-ion 160-700 V.
    # Source : datasheet officielle deyeinverter.com
    # datasheet_sun-(5-25)k-sg01hp3-eu_230724_en.pdf (2023-07-24). C'est
    # exactement l'incompatibilité métier déjà signalée au fondateur plus haut
    # (une Dyness 51,2 V ne s'accroche PAS à ces deux appareils) — le garde
    # data-driven de ``ventes.services`` la fait maintenant respecter par les
    # CHIFFRES, plus par un mot-clé.
    'OND-H-DEY-15T': (160, 700),
    'OND-H-DEY-20T': (160, 700),
}

for _sku_bat, _plage_bat in PLAGE_BATTERIE_ONDULEUR.items():
    if _sku_bat not in FICHES or 'description' not in FICHES[_sku_bat]:
        continue
    if _plage_bat is None:
        _ligne_bat = '\nPlage batterie : aucune (onduleur réseau)'
    else:
        _ligne_bat = '\nPlage batterie : %s-%s V' % _plage_bat
    if _ligne_bat not in FICHES[_sku_bat]['description']:
        FICHES[_sku_bat]['description'] += _ligne_bat


# ── PVOND — onduleurs dont le CONTRAT reste INCOMPLET, et pourquoi ──────────
#
# Le verrou de complétude grise au générateur tout onduleur auquel il manque
# une variable du contrat. Cette table déclare les manques CONNUS et ASSUMÉS,
# avec leur motif : elle n'est pas décorative, un test (``apps/stock/tests.py``)
# refuse le seed d'un onduleur incomplet qui n'y figurerait pas — autrement dit,
# ajouter demain une référence sans ses variables ne passe pas en silence.
#
# ORDRE FONDATEUR (2026-08-18, « ne laisse rien griser ») : la table est
# désormais VIDE. Les neuf références jadis grisées ont été TRANCHÉES (chaque
# valeur porte sa source et sa date dans ``FICHES_TECHNIQUES`` ci-dessous :
# courants asymétriques ramenés au tracker LE PLUS FAIBLE par règle prudente,
# édition M3 présumée pour le 50 kW, révision fondateur 2026-08-16 pour le Deye
# 10 kW mono) et les deux ARTEFACTS Huawei mono 10/12 kW sont ARCHIVÉS
# (``ARTEFACTS_ONDULEUR_SKUS``) plutôt que grisés — jamais supprimés.
#
# Le MÉCANISME, lui, reste ARMÉ pour les références FUTURES : une fixture
# SYNTHÉTIQUE incomplète le prouve dans ``apps/stock/tests.py``. La règle qui
# produit un manque est celle de PVG4/PV85, inchangée : on ne SAISIT que ce
# qu'une source donne, et une valeur qu'il faut TRANCHER est une décision
# fondateur — écrite ici avec son motif tant qu'elle n'est pas prise.
ONDULEURS_CONTRAT_INCOMPLET = {}


# ── PV9 — Fiches techniques (FicheTechnique, PV5) : SEULES les valeurs
# SOURCÉES ci-dessous sont saisies ; tout le reste reste NULL sur la fiche
# (« à vérifier fondateur — PVG4 »).
#
# PV85 — RÉ-APPLICATION (même philosophie que les fiches commerciales
# marque/description/garantie) : les champs DÉCLARÉS ici sont reposés à chaque
# run, y compris sur une base DÉJÀ seedée — sans quoi une correction de
# datasheet (ex. le 10 kW triphasé passé de SG04LP3 à SG05LP3 : 26 A/MPPT au
# lieu de 16 A) n'atteindrait jamais une base existante. Ce qui reste
# INTOUCHABLE : tout champ NON déclaré ici (le PDF constructeur téléversé, une
# valeur saisie à la main sur un champ que le catalogue ne source pas) et la
# fiche d'un produit absent de ce dictionnaire.
FICHES_TECHNIQUES = {
    # PV85 — Canadian Solar CS7N-710TB-AG (TOPBiHiKu7), datasheet
    # static.csisolar.com v1.61/v1.9 — valeurs STC. NON seedés faute de champ
    # sur FicheTechnique (jamais inventé) : NMOT 41±3 °C (537 W / Vmp 38,2 /
    # Voc 45,7), tension système max 1500 V, fusible série max 35 A,
    # bifacialité 80 % ±5.
    'PAN-CS-710': {
        'type_fiche': 'module',
        'pmax_wc': Decimal('710.00'),
        'voc_v': Decimal('48.30'),
        'isc_a': Decimal('18.59'),
        'vmp_v': Decimal('40.40'),
        'imp_a': Decimal('17.59'),
        'rendement_pct': Decimal('22.90'),
        'longueur_mm': 2384,
        'largeur_mm': 1303,
        'epaisseur_mm': 35,
        'poids_kg': Decimal('37.90'),
        'techno_cellule': 'N-type TOPCon (TOPBiHiKu7)',
        'bifacial': True,
        'temp_coeff_voc_pct_c': Decimal('-0.250'),
        'temp_coeff_pmax_pct_c': Decimal('-0.290'),
    },
    'PAN-JK-710': {
        'type_fiche': 'module',
        # Source : datasheet JKM710-735N-66HL5-BDV. Pas de dimensions —
        # non vérifiées, à confirmer fondateur (PVG4).
        'temp_coeff_pmax_pct_c': Decimal('-0.290'),
        'temp_coeff_voc_pct_c': Decimal('-0.250'),
    },
    # ── PVG4 — Onduleurs réseau Huawei (valeurs SOURCÉES uniquement ; tout
    # champ interpolé/« non confirmé »/divergent selon la source reste NULL
    # — voir docs/PLAN2.md PVG4 pour le détail par palier). ──
    'OND-R-HUA-5M': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('90.0'), 'ond_mppt_v_max': Decimal('560.0'),
        'ond_v_max_abs': Decimal('600.0'), 'ond_i_max_mppt_a': Decimal('12.5'),
        'ond_ac_kw': Decimal('5'), 'ond_phases': 1,
        'ond_rendement_euro_pct': Decimal('97.8'),
    },
    'OND-R-HUA-10T': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('140.0'), 'ond_mppt_v_max': Decimal('980.0'),
        'ond_v_max_abs': Decimal('1100.0'), 'ond_i_max_mppt_a': Decimal('13.5'),
        'ond_ac_kw': Decimal('10'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('98.1'),
    },
    'OND-R-HUA-15T': {
        # PVOND (2026-08-18, ordre fondateur « ne laisse rien griser ») —
        # asymétrique 30/20 A (fiche FAMILLE SUN2000-12-25KTL-M5,
        # solar.huawei.com, Version 01-20190716) — valeur retenue : 20 A,
        # RÈGLE PRUDENTE (le moteur de chaînes ne peut alors jamais produire
        # une config qui surcharge le tracker faible). Rendement euro 98,0 % =
        # valeur OFFICIELLE de la famille 12-25KTL-M5, publiée par cette même
        # fiche pour le palier 15 kW (remplace le « interpolé » de PVG4).
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('1000.0'),
        'ond_v_max_abs': Decimal('1100.0'), 'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('15'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('98.0'),
    },
    'OND-R-HUA-20T': {
        # PVOND — nombre de MPPT SOURCÉ : la fiche FAMILLE
        # SUN2000-12-25KTL-M5 (Version 01-20190716) donne 2 trackers pour TOUS
        # les paliers 12-25 kW. Ce n'est donc pas l'extrapolation 15T/25T que
        # PVG4 refusait : c'est la fiche du produit lui-même.
        # PVOND (2026-08-18) — asymétrique 30/20 A (même fiche) — valeur
        # retenue : 20 A, règle prudente.
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('1000.0'),
        'ond_v_max_abs': Decimal('1100.0'), 'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('20'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('98.1'),
    },
    'OND-R-HUA-25T': {
        # PVOND — 2 trackers, même fiche famille 12-25KTL-M5 que ci-dessus.
        # PVOND (2026-08-18) — asymétrique 30/20 A (même fiche) — valeur
        # retenue : 20 A, règle prudente.
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('1000.0'),
        'ond_v_max_abs': Decimal('1100.0'), 'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('25'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('98.2'),
    },
    'OND-R-HUA-50T': {
        # PVOND (2026-08-18, ordre fondateur) — édition présumée M3 (gamme
        # EMEA courante) : 4 MPPT / 30 A / 98,0 % (fiche SUN2000-50KTL-M3,
        # solar.huawei.com). M0 (22 A / 98,5 %, 6 trackers, édition AU,
        # huawei EDOC1100016052) documenté — à confirmer à l'achat.
        'type_fiche': 'onduleur', 'ond_n_mppt': 4,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('1000.0'),
        'ond_v_max_abs': Decimal('1100.0'), 'ond_i_max_mppt_a': Decimal('30.0'),
        'ond_ac_kw': Decimal('50'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('98.0'),
    },
    'OND-R-HUA-100T': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 10,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('1000.0'),
        'ond_v_max_abs': Decimal('1100.0'), 'ond_i_max_mppt_a': Decimal('30.0'),
        'ond_ac_kw': Decimal('100'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('98.4'),
    },
    'OND-R-HUA-150T': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 7,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('1000.0'),
        'ond_v_max_abs': Decimal('1100.0'), 'ond_i_max_mppt_a': Decimal('48.0'),
        'ond_ac_kw': Decimal('150'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('98.4'),
    },
    # OND-R-HUA-10M / OND-R-HUA-12M : PAS de fiche — aucun Huawei mono
    # réseau réel à cette puissance (artefact catalogue, cf. commentaire
    # MODELE_SUPPOSE_PVG4 ci-dessus). PVOND (2026-08-18) : ces deux SKU ne
    # sont plus GRISÉS mais ARCHIVÉS (``ARTEFACTS_ONDULEUR_SKUS``).
    # ── PVG4 — Onduleurs hybrides Deye ──
    'OND-H-DEY-5M': {
        # PVOND — courant d'entrée désormais SOURCÉ : la fiche SG04LP1 donne
        # « 13+13 A », soit la MÊME valeur sur les deux trackers — c'est donc
        # bien un courant PAR MPPT propre (13 A), pas une valeur composée
        # asymétrique comme le « 36+20 A » du SG05LP3 15 kW.
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('150.0'), 'ond_mppt_v_max': Decimal('425.0'),
        'ond_v_max_abs': Decimal('600.0'), 'ond_i_max_mppt_a': Decimal('13.0'),
        'ond_ac_kw': Decimal('5'), 'ond_phases': 1,
        # 97.6 % max / 96.5 % euro — champ = rendement EURO uniquement.
        'ond_rendement_euro_pct': Decimal('96.5'),
    },
    'OND-H-DEY-10M': {
        # PVOND (2026-08-18, ordre fondateur « ne laisse rien griser ») — la
        # DIVERGENCE est conservée EN COMMENTAIRE, la valeur est tranchée sur
        # la datasheet du modèle nommé plus haut (Deye SUN-10K-SG02LP1-EU-AM3,
        # liriksolar — déjà la source de la plage batterie 40-60 V) :
        # 2 trackers (autres sources : 3 vs 2×2), plage MPPT 150-425 V (autres
        # sources : 125-520 / 125-550 V), 600 V DC max.
        # Courant 26 A/MPPT = valeur DÉJÀ VALIDÉE en production par le
        # fondateur le 2026-08-16 pour les paliers 10K/12K (révision actuelle)
        # — divergence documentée : la fiche de sept-2024 donnait 20 A.
        # Rendement euro 97,0 % (même famille basse tension 48 V que les
        # SG04LP1/SG05LP3 seedés ici, dont le rendement euro publié est 97,0 %).
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('150.0'), 'ond_mppt_v_max': Decimal('425.0'),
        'ond_v_max_abs': Decimal('600.0'), 'ond_i_max_mppt_a': Decimal('26.0'),
        'ond_ac_kw': Decimal('10'), 'ond_phases': 1,
        'ond_rendement_euro_pct': Decimal('97.0'),
    },
    # PV85 — Deye SUN-10K-SG05LP3-EU-SM2, modèle CONFIRMÉ FONDATEUR.
    # Sources : datasheet deyeinverter.com 2024-09 + manuel 2025-11.
    # AC 10 000 W nominal / 11 000 VA max, 3 phases 230/400 V ; PV 800 V DC
    # max, démarrage 160 V, MPPT 200-650 V, 2 MPPT × 2 chaînes.
    # ⚠ DIVERGENCE DOCUMENTAIRE ASSUMÉE sur le courant d'entrée : la fiche
    # sept-2024 donnait 20 A / Isc 30 A / 1 chaîne pour TOUTE la gamme, la
    # révision actuelle (manuel nov-2025 + page produit) donne 26 A / Isc 39 A
    # / 2 chaînes pour les 10K et 12K précisément. On seede la révision
    # ACTUELLE (26 A) — à confirmer au numéro de série de l'appareil livré.
    # NON seedés faute de champ sur FicheTechnique (jamais inventé) : tension
    # de démarrage 160 V, Isc max 39 A/MPPT, 210 A charge/décharge, rendement
    # MAX 97,6 % (le champ est le rendement EURO), poids 35,2 kg.
    # La PLAGE BATTERIE 40-60 V, elle, n'est plus perdue : PVOND la loge en
    # DONNÉE sur la description (``PLAGE_BATTERIE_ONDULEUR`` plus haut).
    'OND-H-DEY-10T': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('650.0'),
        'ond_v_max_abs': Decimal('800.0'), 'ond_i_max_mppt_a': Decimal('26.0'),
        'ond_ac_kw': Decimal('10'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('97.0'),
    },
    # PV85 — Deye SUN-15K-SG05LP3-EU-SM2 (gamme BASSE TENSION SG05LP3,
    # décision fondateur 2026-08-18 — complète le palier 10 kW déjà seedé
    # OND-H-DEY-10T ci-dessus, même famille de datasheet).
    # Source : datasheet officielle deyeinverter.com/deyeinverter/2024/06/01/
    # datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf (2024-06-01), colonne
    # SUN-15K-SG05LP3-EU-SM2. La plage MPPT/V max/nb de trackers et le
    # rendement EURO sont donnés PARTAGÉS pour toute la famille SG05LP3
    # (14-20K) par la datasheet elle-même — pas une extrapolation.
    # NON seedés faute de champ sur FicheTechnique (jamais inventé, même
    # garde que OND-H-DEY-10T) : tension de démarrage 160 V, 280 A charge/
    # décharge, poids 50,6 kg. La PLAGE BATTERIE 40-60 V est désormais logée
    # en DONNÉE sur la description (PVOND, ``PLAGE_BATTERIE_ONDULEUR``).
    'OND-DEY-15K-LV': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('160.0'), 'ond_mppt_v_max': Decimal('650.0'),
        'ond_v_max_abs': Decimal('800.0'),
        # PVOND (2026-08-18, ordre fondateur) — asymétrique 36/20 A (fiche
        # SG05LP3 14-20K, deyeinverter.com 2024-06-01, 2/2+1 chaînes) —
        # valeur retenue : 20 A, règle prudente (jamais une config qui
        # surcharge le tracker faible), même règle que OND-R-HUA-15T.
        'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('15'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('97.0'),
    },
    # PVOND (18/08/2026) — Deye SUN-20K-SG05LP3-EU-SM2, jumeau BASSE TENSION
    # du palier 20 kW (OND-H-DEY-20T est un SG01HP3 HAUTE TENSION 160-700 V,
    # incompatible avec les batteries 51,2 V de la maison).
    # Source : MÊME datasheet officielle que le 15 kW ci-dessus —
    # deyeinverter.com/deyeinverter/2024/06/01/
    # datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf (2024-06-01), colonne
    # SUN-20K-SG05LP3-EU-SM2. Plage MPPT (160-650 V), tension DC max (800 V),
    # nombre de trackers (2) et rendement EURO (97,0 %) sont donnés PARTAGÉS
    # par la datasheet pour toute la famille SG05LP3 14-20K : ce ne sont pas
    # des extrapolations. Seule la puissance AC (20 kW) est propre à la
    # colonne 20K.
    # NON seedés faute de champ sur FicheTechnique (jamais inventé, même garde
    # que le 15 kW) : tension de démarrage 160 V, courants de charge/décharge,
    # poids. La PLAGE BATTERIE 40-60 V est logée en DONNÉE sur la description
    # (PVOND, ``PLAGE_BATTERIE_ONDULEUR``).
    'OND-DEY-20K-LV': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('160.0'), 'ond_mppt_v_max': Decimal('650.0'),
        'ond_v_max_abs': Decimal('800.0'),
        # Asymétrique 36/20 A sur la fiche (2/2+1 chaînes) — valeur retenue :
        # 20 A, MÊME règle prudente que le 15 kW LV et OND-R-HUA-15T (jamais
        # une configuration qui surcharge le tracker le plus faible).
        'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('20'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('97.0'),
    },
    'OND-H-DEY-15T': {
        # Confiance moyenne : plage FAMILLE SG01HP3 (5-25K) documentée, pas
        # spécifique au 15T — seedée quand même (règle PVG4), l'incertitude
        # est portée par la mention « modèle supposé » sur la description.
        # PVOND — nb de MPPT SOURCÉ (2 trackers) par la fiche officielle
        # deyeinverter.com datasheet_sun-(5-25)k-sg01hp3-eu_230724_en.pdf.
        # PVOND (2026-08-18, ordre fondateur) — asymétrique 26/20 A (cette
        # même fiche) — valeur retenue : 20 A, règle prudente.
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('150.0'), 'ond_mppt_v_max': Decimal('850.0'),
        'ond_v_max_abs': Decimal('1000.0'), 'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('15'), 'ond_phases': 3,
        # 97.6/97.0 — même ordre max/euro que le 5M → euro = 97.0.
        'ond_rendement_euro_pct': Decimal('97.0'),
    },
    'OND-H-DEY-20T': {
        # L'ancienne source donnait « charge max 50A » : c'est le courant de
        # charge BATTERIE, pas un courant d'entrée MPPT PV — il n'a jamais eu
        # sa place ici. PVOND — la fiche OFFICIELLE de la famille
        # (deyeinverter.com datasheet_sun-(5-25)k-sg01hp3-eu_230724_en.pdf,
        # 2023-07-24) donne pour le 20K « 26+26 A » : même valeur sur les deux
        # trackers, donc un courant PAR MPPT propre (26 A) — plus 2 trackers et
        # un rendement euro de 97,0 %.
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('150.0'), 'ond_mppt_v_max': Decimal('850.0'),
        'ond_v_max_abs': Decimal('1000.0'), 'ond_i_max_mppt_a': Decimal('26.0'),
        'ond_ac_kw': Decimal('20'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('97.0'),
    },
    # ── PVG4 — Batteries Dyness ──
    'BAT-DEY-5': {
        'type_fiche': 'batterie',
        'bat_kwh_nominal': Decimal('5.12'), 'bat_kwh_usable': Decimal('4.60'),
        'bat_dod_pct': Decimal('90.0'), 'bat_v_nominal': Decimal('51.2'),
        # 75 A continu × 51,2 V ≈ 3,84 kW (valeur constructeur, dyness.com).
        'bat_max_charge_kw': Decimal('3.84'),
    },
    'BAT-DEY-10': {
        'type_fiche': 'batterie',
        'bat_kwh_nominal': Decimal('10.24'),
        # Source : 9.216 kWh usable, arrondi aux 2 décimales du champ.
        'bat_kwh_usable': Decimal('9.22'),
        'bat_dod_pct': Decimal('90.0'), 'bat_v_nominal': Decimal('51.2'),
        # 100 A × 51,2 V = 5,12 kW (valeur constructeur).
        'bat_max_charge_kw': Decimal('5.12'),
    },
}


def _fiche_champ_vide(valeur):
    """Un champ de ``FicheTechnique`` est-il VIDE, c.-à-d. jamais renseigné ?

    ``None`` (tous les champs de la fiche sont ``null=True``) et la chaîne vide
    (``type_fiche``) sont les DEUX seuls états « rien de saisi ». ``0`` — ou
    ``Decimal('0')`` — est une VALEUR : c'est une donnée que quelqu'un a tapée,
    fût-elle fausse, et le seeder ne la remplace pas sans qu'on le lui demande
    (``--reappliquer-fiches``).
    """
    if valeur is None:
        return True
    return isinstance(valeur, str) and not valeur.strip()


class Command(BaseCommand):
    help = "Seed the stock with the devis-simulator catalogue (idempotent, additive only)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-slug', default='taqinor-demo',
            help="Slug of the company to seed (default: taqinor-demo).",
        )
        parser.add_argument(
            '--reappliquer-fiches', action='store_true',
            help=("Repose les champs de FicheTechnique DÉCLARÉS par le "
                  "catalogue PAR-DESSUS les valeurs existantes (porte des "
                  "CORRECTIONS de datasheet, PV85). Sans ce drapeau — et donc "
                  "à chaque déploiement — le seeder se contente de COMBLER "
                  "les champs vides : une saisie du fondateur n'est JAMAIS "
                  "écrasée."),
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

        # ── PVG3 — Câbles & protections DC/AC : PRIX VIDES (0) ──
        # Tant que prix_vente vaut 0, le produit est exclu du chiffrage
        # automatique — même garde que les pompes OSP ci-dessus.
        for nom, sku, qte, seuil in CABLES_PROTECTIONS_VIDES:
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
                quantite_stock=qte, seuil_alerte=seuil,
                tva=Decimal('20.00'),
            )
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=qte, quantite_avant=0, quantite_apres=qte,
                reference='SEED-CATALOGUE',
                note='Stock initial (câbles/protections — prix à renseigner)',
            )
            created.append(nom)

        # ── Onduleurs Deye BASSE TENSION (SG05LP3) : PRIX VIDES (0) ──
        # Même garde que les pompes OSP / câbles PVG3 ci-dessus : tant que
        # prix_vente vaut 0, le produit est exclu du chiffrage automatique.
        for nom, sku, qte, seuil in ONDULEUR_DEYE_15K_LV_VIDE:
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
                quantite_stock=qte, seuil_alerte=seuil,
                tva=Decimal('20.00'),
            )
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=qte, quantite_avant=0, quantite_apres=qte,
                reference='SEED-CATALOGUE',
                note='Stock initial (onduleur Deye basse tension — prix à renseigner)',
            )
            created.append(nom)

        # ── Batterie Dyness haute tension — 16 kWh : prix vente RÉEL ──
        # (3 000 DH/kWh, fondateur) ; prix achat vide (non communiqué).
        for nom, sku, sell_ttc, qte, seuil in BATTERIE_DYNESS_HV:
            if (Produit.objects.filter(company=company, sku=sku).exists()
                    or Produit.objects.filter(
                        company=company, nom__iexact=nom,
                        is_archived=False).exists()):
                skipped.append(nom)
                continue
            produit = Produit.objects.create(
                company=company, nom=nom, sku=sku,
                categorie=get_categorie(classify_categorie(nom)),
                prix_achat=Decimal('0'),  # à renseigner par le fondateur
                prix_vente=ht(sell_ttc),
                quantite_stock=qte, seuil_alerte=seuil,
                tva=Decimal('20.00'),
                unite_stock='tranche',
            )
            MouvementStock.objects.create(
                company=company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE,
                quantite=qte, quantite_avant=0, quantite_apres=qte,
                reference='SEED-CATALOGUE',
                note='Stock initial (batterie Dyness haute tension — 16 kWh)',
            )
            created.append(nom)

        # ── Archivage des coffrets variateurs PLACEHOLDER (prix estimés) ──
        # Exception ponctuelle à la règle "additif uniquement", explicitement
        # autorisée par le fondateur (2026-06-12) : ces articles n'ont jamais
        # porté de vrais prix. Archivés (jamais supprimés), prix intacts.
        # PVOND (2026-08-18) — MÊME patron pour les deux ARTEFACTS onduleur
        # Huawei mono 10/12 kW (``ARTEFACTS_ONDULEUR_SKUS``) : archivés, donc
        # hors catalogue de composition, jamais supprimés.
        archived_count = Produit.objects.filter(
            company=company,
            sku__in=PLACEHOLDER_VFD_SKUS + ARTEFACTS_ONDULEUR_SKUS,
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

        # ── PV9/PV85 — Fiches techniques (valeurs datasheet constructeur) ──
        # Additif + idempotent : SKU absent du catalogue → ignoré. Produit SANS
        # fiche → la fiche est CRÉÉE complète (c'est ce qui répare une base de
        # production restée en arrière du catalogue : le cas RÉEL du bandeau
        # « Onduleur(s) non chiffrable(s) » du 18/08/2026).
        #
        # ORDRE FONDATEUR (18/08/2026) — « rends-moi facile de saisir les infos
        # des futurs onduleurs et panneaux ». Sur une fiche DÉJÀ existante, le
        # comportement PAR DÉFAUT est désormais COMBLER, jamais écraser : un
        # champ VIDE (NULL / chaîne vide) reçoit la valeur du catalogue, un
        # champ DÉJÀ RENSEIGNÉ est laissé tel quel. C'est ce qui rend sûr
        # l'appel du seeder à CHAQUE déploiement (scripts/deploy-prod.ps1) —
        # sans cette garde, un redéploiement écraserait silencieusement ce que
        # le fondateur vient de saisir à l'écran.
        #
        # PV85 garde sa raison d'être — faire atteindre une CORRECTION de
        # datasheet une base déjà seedée (le 10 kW triphasé passé de SG04LP3 à
        # SG05LP3 : 26 A/MPPT au lieu de 16 A) — mais cette porte est
        # maintenant EXPLICITE : `--reappliquer-fiches` repose les champs
        # déclarés par-dessus l'existant. Un run nu ne peut plus le faire par
        # accident.
        #
        # INTOUCHABLE dans LES DEUX modes : tout champ NON déclaré ici (PDF
        # téléversé, saisie manuelle sur un champ que le catalogue ne source
        # pas) et la fiche d'un produit absent de ce dictionnaire.
        from apps.stock.models import FicheTechnique
        reappliquer = bool(options.get('reappliquer_fiches'))
        fiches_techniques_created = 0
        fiches_techniques_updated = 0
        champs_combles = 0
        for sku, valeurs in FICHES_TECHNIQUES.items():
            produit = Produit.objects.filter(company=company, sku=sku).first()
            if not produit:
                continue  # SKU pas seedé par ce catalogue — rien à rattacher
            fiche = FicheTechnique.objects.filter(produit=produit).first()
            if fiche is None:
                FicheTechnique.objects.create(
                    company=company, produit=produit, **valeurs)
                fiches_techniques_created += 1
                continue
            modifies = []
            for champ, valeur in valeurs.items():
                actuel = getattr(fiche, champ)
                if actuel == valeur:
                    continue  # déjà à jour — aucune écriture (idempotence)
                if not reappliquer and not _fiche_champ_vide(actuel):
                    continue  # valeur SAISIE : elle appartient au fondateur
                modifies.append(champ)
            if not modifies:
                continue
            for champ in modifies:
                setattr(fiche, champ, valeurs[champ])
            fiche.save(update_fields=modifies)
            fiches_techniques_updated += 1
            champs_combles += len(modifies)

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

        # ── Correction de texte client (« pendent » → « pendant ») ──
        # Renomme le produit maintenance existant ; idempotent, ne touche
        # ni prix ni quantités. Les désignations des ANCIENNES lignes de
        # devis (documents historiques) ne sont pas réécrites.
        for produit in Produit.objects.filter(
                company=company, nom__contains='pendent 2 ans'):
            produit.nom = produit.nom.replace('pendent 2 ans', 'pendant 2 ans')
            produit.save(update_fields=['nom'])

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
            f"{fiches_techniques_created} fiches techniques créées, "
            f"{fiches_techniques_updated} fiches techniques complétées "
            f"({champs_combles} champs "
            f"{'ré-appliqués' if reappliquer else 'comblés'}), "
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
