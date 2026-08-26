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
    # Prix fondateur 25/08/2026 : 17 000 → 15 000 TTC (migration stock 0131
    # recale les bases existantes, gardée par l'ancienne valeur).
    ('Onduleur hybride Deye 5kW Monophasé',    'OND-H-DEY-5M',   'Onduleurs', 15000, 12000, 500, 5),
    ('Onduleur hybride Deye 10kW Monophasé',   'OND-H-DEY-10M',  'Onduleurs', 28000, 24000, 500, 5),
    ('Onduleur hybride Deye 10kW Triphasé',    'OND-H-DEY-10T',  'Onduleurs', 28000, 24000, 500, 5),
    # PVLV2 (fondateur 21/08/2026, DÉFINITIF — « i only know 15 and 20kw on
    # LV, i dont even have them in high voltage ») : ces deux SKU historiques
    # SONT les modèles BASSE TENSION SG05LP3 du parc réel, avec leurs prix
    # d'origine. L'identification « SG01HP3 haute tension » (PVG4) était une
    # SUPPOSITION de recherche jamais validée par le fondateur — elle a créé
    # le 18/08 deux SKU doublons « Basse Tension » (OND-DEY-15K-LV/20K-LV),
    # désormais ARCHIVÉS (``ARTEFACTS_ONDULEUR_SKUS``). Fiches recalées sur la
    # datasheet SG05LP3 14-20K (migration stock 0126 pour les bases
    # existantes).
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
    # Prix fondateur 25/08/2026 : 17 000 → 14 000 TTC (migration stock 0131
    # recale les bases existantes, gardée par l'ancienne valeur).
    # BATHOMO (fondateur 26/08/2026, RECALÉ) — le fondateur n'a PAS archivé le
    # Dyness 10 kWh : il a mis sa QUANTITÉ DE STOCK à 0 via un mouvement de
    # stock (le vrai bug était que RIEN ne consultait le stock au chiffrage —
    # corrigé côté composition, cf. ``services.composition_residentielle`` /
    # ``_batterie_en_stock``, jamais ici). Le seeder n'a donc RIEN de
    # spécifique à faire pour ce SKU : une base qui le porte déjà est
    # retrouvée par SKU et SAUTÉE comme toute autre ligne (prix/quantité
    # jamais touchés) ; une société NEUVE le seed comme tout le catalogue,
    # stock normal inclus — quand le fondateur réapprovisionne sa quantité
    # réelle, la composition recommence à le proposer AUTOMATIQUEMENT, sans
    # redéploiement ni intervention côté catalogue. (Un run antérieur avait
    # ARCHIVÉ ce SKU par erreur — RETIRÉ par ce même correctif, le seeder ne
    # force plus jamais son statut.)
    ('Batterie Dyness 5 kWh',  'BAT-DEY-5',  'Batteries', 14000, 13000, 500, 5),
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
    # DC35/G2 (2026-08-20) — même patron que le renommage Dyness (fc883be2) :
    # la marque doit être visible dans le NOM du produit, pas seulement dans
    # ``FICHES[...]['marque']``. « (au mètre) » et le SKU sont INCHANGÉS.
    # DC35/G3 (2026-08-20, CI run 32320136461 shard 3) — SANS ESPACE avant
    # « mm² » (« 6mm² », pas « 6 mm² ») : DÉLIBÉRÉ, pas une coquille. Le
    # nom-jumeau AVEC espace ('Câble solaire Nexans 6 mm² (au mètre)') est
    # DÉJÀ pris par CAB-NEX-DC-6 (ligne ~72 ci-dessus, réglé 18/08). Le garde-
    # fou anti-doublon du seeder (plus bas, `nom__iexact` sur produits actifs)
    # SAUTE la création de tout produit dont le nom égale — insensible à la
    # casse — un produit déjà seedé : avec l'espace, CAB-6MM-M ne serait
    # JAMAIS créé (skip silencieux dès que CAB-NEX-DC-6 existe), faisant
    # échouer `Produit.objects.get(sku='CAB-6MM-M')` partout. L'absence
    # d'espace est l'orthographe D'ORIGINE de ce SKU (avant le renommage
    # Nexans) : elle reste le disambiguateur naturel entre les deux SKU
    # câble-6mm historiques, jamais une chaîne inventée.
    ('Câble solaire Nexans 6mm² (au mètre)', 'CAB-6MM-M', 13, 5000, 200, None, None, None),
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
ARTEFACTS_ONDULEUR_SKUS = [
    'OND-R-HUA-10M', 'OND-R-HUA-12M',
    # PVLV2 (fondateur 21/08/2026) — doublons nés de la fausse identification
    # « SG01HP3 haute tension » des 15/20 kW : le parc réel n'a QUE du basse
    # tension (OND-H-DEY-15T/20T = SG05LP3). Archivés, jamais supprimés.
    'OND-DEY-15K-LV', 'OND-DEY-20K-LV',
]

# BATHOMO (fondateur 26/08/2026, RECALÉ) — Dyness 10 kWh : PAS d'archivage
# forcé. Un premier passage avait traité ce SKU comme les ARTEFACTS ci-dessus
# (archivage forcé en fin de run), sur l'hypothèse que le fondateur l'avait
# retiré du catalogue. FAIT CORRIGÉ : il a mis sa QUANTITÉ DE STOCK à 0 (un
# mouvement de stock, pas un archivage) — « when it comes back, use it for
# bigger installations » : quand il réapprovisionne, le module doit redevenir
# utilisable AUTOMATIQUEMENT, sans repasser par le seeder. Un archivage forcé
# ici romprait exactement cette promesse (un produit archivé ne redevient
# jamais actif tout seul). La garde qui EXCLUT ce module tant que son stock
# est à 0 vit désormais côté composition (``apps.ventes.services.
# composition_residentielle`` / ``_batterie_en_stock`` — la racine du mélange
# 5+10 kWh électriquement interdit qui a motivé ce retrait est corrigée là,
# banques toujours homogènes) — JAMAIS ici, où seul l'idiome ARTEFACTS/
# PLACEHOLDER (archivage définitif, produits qui ne reviendront jamais) reste
# légitime.

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
# DC35/G2 (2026-08-20) — même renommage systémique que CAB-6MM-M ci-dessus :
# la marque Nexans doit être visible dans le NOM, pas seulement dans FICHES.
# (nom, sku, qte, seuil)
CABLES_PROTECTIONS_VIDES = [
    # Câbles solaires H1Z2Z2-K (DC, double isolation, résistant UV)
    ('Câble solaire Nexans H1Z2Z2-K 4 mm² (au mètre)',  'CAB-H1Z2Z2-4-M',  5000, 200),
    ('Câble solaire Nexans H1Z2Z2-K 6 mm² (au mètre)',  'CAB-H1Z2Z2-6-M',  5000, 200),
    ('Câble solaire Nexans H1Z2Z2-K 10 mm² (au mètre)', 'CAB-H1Z2Z2-10-M', 5000, 200),
    ('Câble solaire Nexans H1Z2Z2-K 16 mm² (au mètre)', 'CAB-H1Z2Z2-16-M', 5000, 200),
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

# ── PVLV2 — HISTORIQUE des SKU « Basse Tension » (créés 18/08, ARCHIVÉS
# 21/08/2026) ─────────────────────────────────────────────────────────────
# La recherche PVG4 avait identifié OND-H-DEY-15T/20T comme des SG01HP3
# « haute tension » — supposition jamais validée. Sur cette base fausse, deux
# SKU « jumeaux basse tension » (OND-DEY-15K-LV/20K-LV) ont été créés le
# 18/08. Le fondateur a tranché le 21/08 : « i only know 15 and 20kw on LV,
# i dont even have them in high voltage » — les SKU HISTORIQUES sont ses
# SG05LP3 basse tension, avec leurs prix d'origine ; les « jumeaux » sont
# des DOUBLONS, archivés via ``ARTEFACTS_ONDULEUR_SKUS`` (jamais supprimés),
# migration stock 0126 pour les bases existantes.

# ── Batterie HAUTE TENSION — 16 kWh (fondateur 18/08, IDENTITÉ 21/08) ──────
# Vendue PAR TRANCHE de 16 kWh, 3 000 DH/kWh (prix fondateur) → 48 000 DH TTC
# la tranche ; rack et control box inclus dans le prix.
# PVLV (21/08/2026) — le produit N'EST PAS une Dyness : la facture
# fournisseur Solarex S26/001708 (27/07/2026) le nomme « 16kWh BOS-B-Pro
# Battery Pack-deye » = module officiel **Deye BOS-B-Pack16-A3** (système
# BOS-B Pro-A3, 16,08 kWh réels, LiFePO4, 51,2 V/module, 314 Ah, empilage
# série 5-15 modules derrière control box BOS-B-PDU-2-A 200-1000 Vdc,
# garantie 10 ans publiée). C'est pourquoi aucune configuration Dyness ne
# faisait 16 kWh (Tower T14 = 14,21 / T17 = 17,76) — la recherche du 18/08
# cherchait la bonne valeur chez le mauvais fabricant. Le SKU historique
# BAT-DYN-HV-16 NE CHANGE PAS (appariement par SKU d'abord — même règle que
# Deyness→Dyness) ; nom/marque/fiche corrigés (migration stock 0127 pour les
# bases existantes). Prix ACHAT : 28 000 HT le pack (même facture).
# ⚠ APPARIEMENT ONDULEUR NON PROMIS : la liste officielle Deye des batteries
# approuvées (DY-HV(160-800)-028, 2025-08-09) apparie le BOS-B Pro aux
# onduleurs C&I 30-80 kW (BM3/BM4/EM6) ; les hybrides du catalogue sont TOUS
# en basse tension 48 V (SG05LP1/SG02LP1/SG05LP3, PVLV2) — ce système HV ne
# se compose donc JAMAIS automatiquement avec eux, et aucun document client
# ne prétend un appariement.
# ⚠ HAUTE TENSION : ne doit JAMAIS être choisie par l'auto-composition
# résidentielle BASSE TENSION (48 V, BAT-DEY-5/10) — garde posée côté
# apps/ventes/services.py (mot-clé « haute tension » exclu du vivier
# batterie, cf. ``_is_battery_basse_tension`` et le filtre dans
# ``composition_residentielle``) : le mot-clé RESTE dans le nom ci-dessous.
# (nom, sku, sell_ttc, qte, seuil)
BATTERIE_DEYE_HV = [
    ('Batterie Deye BOS-B Pro haute tension — 16 kWh', 'BAT-DYN-HV-16', 48000, 500, 5),
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
#
# PVFCH (fondateur 20/08/2026) — LA DESCRIPTION RACONTE, ELLE NE CHIFFRE PAS.
# Ces descriptions portaient des specs chiffrées qui vivent DÉJÀ dans un champ
# structuré de ``FicheTechnique`` (« 710 Wc » = ``pmax_wc``, « 51,2 V » =
# ``bat_v_nominal``, « rendement euro 97,0 % » = ``ond_rendement_euro_pct``,
# « plage 40-60 V » = ``ond_bat_v_min``/``ond_bat_v_max``, « ≈ −0,29 %/°C » =
# ``temp_coeff_pmax_pct_c``). Deux copies d'un même nombre finissent toujours
# par diverger — et c'est la copie en PROSE, celle que personne ne recalcule,
# qui part sur la fiche produit du PDF client.
#
# RÈGLE : un nombre reste dans la prose UNIQUEMENT si aucun champ ne le porte
# (rendement de module, dégradation annuelle, capacité d'une batterie sans
# fiche…). Supprimer un nombre qui n'a pas d'autre domicile le PERDRAIT — ce
# serait l'erreur symétrique. Le test ``test_pvfch_description_sans_specs``
# vérifie les deux sens.
FICHES = {
    # Onduleurs réseau Huawei (résidentiel ≤ 25 kW : 10 ans ; C&I : 5 ans ext.)
    **{sku: {
        'marque': 'Huawei',
        'garantie': ('Garantie constructeur 10 ans'
                     if sku in ('OND-R-HUA-5M', 'OND-R-HUA-10M', 'OND-R-HUA-10T',
                                'OND-R-HUA-12M', 'OND-R-HUA-15T', 'OND-R-HUA-20T',
                                'OND-R-HUA-25T')
                     else 'Garantie constructeur 5 ans (extensible jusqu\'à 20 ans)'),
        # Le rendement vit dans ``ond_rendement_euro_pct``, PAR RÉFÉRENCE
        # (97,8 à 98,4 % selon le palier) : la prose annonçait « 98,6 % » à
        # l'identique pour les dix, ce qui contredisait le champ de huit d'entre
        # elles.
        'description': ('Onduleur string on-grid Huawei SUN2000\n'
                        'Protection d\'arc intelligente AFCI, parafoudres DC/AC intégrés\n'
                        'Supervision temps réel via l\'application FusionSolar\n'
                        'Conforme IEC 62109, indice IP65 (pose intérieure/extérieure)'),
    } for sku in ('OND-R-HUA-5M', 'OND-R-HUA-10M', 'OND-R-HUA-10T', 'OND-R-HUA-12M',
                  'OND-R-HUA-15T', 'OND-R-HUA-20T', 'OND-R-HUA-25T', 'OND-R-HUA-50T',
                  'OND-R-HUA-100T', 'OND-R-HUA-150T')},
    # Onduleurs hybrides Deye
    # O1 (2026-08-20) — HARMONISATION : ce groupe affichait « Garantie
    # constructeur 10 ans » flat alors que les SKU LV 15K/20K plus bas (même
    # gamme SUN Series Hybrid, même constructeur) affichent la version nuancée
    # « 5 à 10 ans (selon site d'installation) ». Source : Deye, « SUN Series
    # Hybrid inverter 10-Year Limited Warranty for Installation in Europe »
    # (deyeinverter.com — couvre explicitement TOUTE la gamme SUN Series
    # Hybrid) + la datasheet technique SG05LP3/SG05LP1 elle-même : ligne
    # « Warranty : 5 Years/10 Years — the Warranty Period Depends the Final
    # Installation Site of Inverter ». Les deux groupes de SKU sont désormais
    # sur LA MÊME phrase, la plus honnête des deux.
    **{sku: {
        'marque': 'Deye',
        'garantie': 'Garantie constructeur 5 à 10 ans (selon site d\'installation)',
        # Rendement → ``ond_rendement_euro_pct`` (PVFCH). La tension NOMINALE
        # « 48 V » de la famille de batteries reste : ce n'est pas la PLAGE
        # (``ond_bat_v_min``/``ond_bat_v_max``), aucun champ ne la porte.
        # O3 (2026-08-20) — « < 4 ms » (bascule EPS/UPS) est RETIRÉ : aucune
        # datasheet Deye officielle consultée (SG05LP3 tri, SG05LP1 mono) ne
        # publie de valeur en ms pour ce temps de bascule ; seules des sources
        # tierces non vérifiées (forums) citent 4 ms ou 10 ms selon le modèle
        # — OMISSION plutôt qu'un chiffre non sourcé (aucun champ ne le
        # portait non plus : ce n'est pas un cas PVFCH, juste invérifiable).
        'description': ('Onduleur hybride Deye SUN-…SG\n'
                        'Compatible batteries lithium 48 V (BMS CAN/RS485)\n'
                        'Bascule secours (EPS/UPS) en cas de coupure réseau\n'
                        'Monitoring Wi-Fi via Solarman Smart / Deye Cloud'),
    } for sku in ('OND-H-DEY-5M', 'OND-H-DEY-10M', 'OND-H-DEY-10T',
                  'OND-H-DEY-15T', 'OND-H-DEY-20T')},
    # PVLV2 (21/08/2026) — les fiches commerciales des SKU doublons
    # OND-DEY-15K-LV/20K-LV sont retirées : produits ARCHIVÉS (cf.
    # ``ARTEFACTS_ONDULEUR_SKUS``) — les 15/20 kW réels (OND-H-DEY-15T/20T,
    # SG05LP3 basse tension) héritent de la fiche commune du groupe ci-dessus.
    'PAN-CS-710': {
        'marque': 'Canadien Solar',
        'garantie': '12 ans produit · 30 ans performance linéaire (87,4 %)',
        # « 710 Wc » → ``pmax_wc`` ; « ≈ −0,29 %/°C » → ``temp_coeff_pmax_pct_c``.
        # Le rendement du MODULE et la dégradation annuelle restent : aucun
        # champ de ``FicheTechnique`` ne les porte.
        'description': ('Module Canadian Solar TOPHiKu7, cellules N-type TOPCon\n'
                        'Rendement module jusqu\'à ≈ 22,9 %, dégradation ≤ 0,4 %/an\n'
                        'Excellent comportement à haute température\n'
                        'Certifié IEC 61215 / IEC 61730, fabricant Tier 1'),
    },
    'PAN-JK-710': {
        'marque': 'Jinko',
        'garantie': '12 ans produit · 30 ans performance linéaire (87,4 %)',
        # « 710 Wc » → ``pmax_wc``.
        'description': ('Module JinkoSolar Tiger Neo, N-type TOPCon\n'
                        'Rendement jusqu\'à ≈ 22,9 %, dégradation ≤ 0,4 %/an\n'
                        'Version bifaciale double verre disponible\n'
                        'Certifié IEC 61215 / IEC 61730'),
    },
    # O1/O3 (2026-08-20) — HARMONISATION avec la fiche web `batterie-dyness`
    # (apps/web/src/lib/fiches.ts + warranty.ts BATTERY_WARRANTY_YEARS) : ce
    # bloc affichait « Garantie 5 ans », une valeur introuvable dans AUCUN
    # document Dyness officiel (contradiction exacte relevée par l'audit — le
    # web affichait 10 ans pour le même produit DL5.0C). Les documents
    # officiels dyness.com trouvés donnent 10 ans (version Europe) ou 7 ans
    # (version Amériques/Pro) selon la région — jamais 5. Harmonisé sur 10 ans,
    # même valeur et même réserve régionale que le web.
    # « 90 % DoD » n'est PLUS répété ici (PVFCH) : ``bat_dod_pct`` = 90.0 sur
    # ces deux SKU dans FICHES_TECHNIQUES ci-dessous PORTE DÉJÀ ce nombre — le
    # texte le redisait à 80 %, en contradiction avec le champ structuré à
    # 90 %, exactement le genre de divergence prose/champ que PVFCH corrige.
    # Source du 90 % : datasheet officielle DL5.0C (dyness.com,
    # V1.0-20241011) — « Depth of Discharge (DOD): 90% », « Cycle Life[1]:
    # ≥6000 Cycles », note [1] « 0.2C Charging/Discharging, @25°C, 90% DOD ».
    # « ≥ 6 000 cycles » reste en prose : aucun champ ne porte le nombre de
    # cycles.
    **{sku: {
        'marque': 'Dyness',
        'garantie': 'Garantie 10 ans (variante régionale : 7 ans) · ≥ 6 000 cycles',
        # Trou comblé (20/08/2026, revue de la lane moteur) : la migration 0012
        # backfillait 120 mois sur les batteries EXISTANTES, mais le seeder ne
        # posait AUCUN garantie_mois — toute base neuve sortait à NULL et le
        # PDF omettait une garantie POURTANT réelle (dyness.com, DL5.0C ESS
        # 10-Year Limited Warranty — même source que le texte ci-dessus).
        'garantie_mois': 120,
        # « 51,2 V » → ``bat_v_nominal`` (les deux paliers ont leur fiche).
        'description': ('Batterie lithium LiFePO4 basse tension\n'
                        'Chimie fer-phosphate sûre et durable\n'
                        'BMS intégré CAN/RS485, compatible onduleurs hybrides Deye\n'
                        'Extensible en parallèle'),
    } for sku in ('BAT-DEY-5', 'BAT-DEY-10')},
    # PVFCH — « 51,2 V » et « 5 kWh » RESTENT en prose : cette référence n'a
    # PAS de ``FicheTechnique`` (absente de FICHES_TECHNIQUES, contrairement aux
    # Dyness). Les retirer perdrait la seule trace de ces deux valeurs. Le jour
    # où sa fiche est saisie, ils partent d'ici — pas avant.
    # O3 (2026-08-20) — ``garantie`` (un champ SÉPARÉ de la description
    # ci-dessus, cf. PVFCH) est en revanche RETIRÉ : « Lithium » est une
    # marque générique non vérifiable (aucun fabricant identifié) — la
    # garantie « 5 ans » et le « 80 % DoD » n'ont aucune source datasheet et
    # ne peuvent pas hériter de celle de Dyness (marque différente, non
    # confirmée identique). Champ retiré plutôt qu'un chiffre non sourcé
    # (même principe que BAT-DYN-HV-16 ci-dessous).
    'BAT-LIT-5': {
        'marque': 'Lithium',
        'description': ('Batterie lithium LiFePO4 basse tension 51,2 V, 5 kWh\n'
                        'BMS intégré, communication CAN/RS485'),
    },
    # O3 (2026-08-20) — « Gel » est une marque générique non vérifiable
    # (chimie plomb, sans rapport avec les batteries LFP ci-dessus) : la
    # garantie « 2 ans » n'a aucune source datasheet — champ retiré plutôt
    # qu'un chiffre non sourcé.
    'BAT-GEL-22': {
        'marque': 'Gel',
        'description': 'Batterie gel plomb étanche sans entretien, usage solaire',
    },
    # PVLV (21/08/2026) — IDENTITÉ ENFIN CONNUE : la facture fournisseur
    # Solarex S26/001708 (27/07/2026) nomme « 16kWh BOS-B-Pro Battery
    # Pack-deye » — c'est le module officiel Deye BOS-B-Pack16-A3 (système
    # BOS-B Pro-A3) : 16,08 kWh, LiFePO4, 51,2 V/module, 314 Ah, empilage
    # SÉRIE de 5 à 15 modules derrière une control box BOS-B-PDU-2-A
    # (200-1000 Vdc). Sources : deye.com « BOS-B Pro-A3 C&I ESS Solution » +
    # brochures officielles 2025-09-28 / 2025-12-11. Garantie 10 ans
    # PUBLIÉE (≥ 6000 cycles, EOL 70 %). La description ne fait AUCUNE
    # promesse d'appariement onduleur : Deye apparie officiellement ce
    # système aux onduleurs C&I 30-80 kW (liste DY-HV(160-800)-028) ; les
    # hybrides du catalogue sont tous en 48 V basse tension (PVLV2).
    'BAT-DYN-HV-16': {
        'marque': 'Deye',
        'garantie': 'Garantie constructeur 10 ans (≥ 6000 cycles, EOL 70 %)',
        'description': ('Batterie Deye BOS-B Pro haute tension, vendue par tranche de 16 kWh\n'
                        'Module BOS-B-Pack16-A3 : LiFePO4, 51,2 V, 314 Ah — empilage série '
                        'de 5 à 15 modules derrière control box BOS-B-PDU-2-A\n'
                        'Rack et control box inclus dans le prix de la tranche'),
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
    # Pompage — O3 (2026-08-20) : ces pompes n'ont aucune marque déclarée
    # (« pompe immergée/de surface » générique) donc aucune datasheet
    # constructeur à opposer à « Garantie constructeur 2 ans » — champ retiré
    # plutôt qu'un chiffre non sourcé.
    **{sku: {'description': _DESC_POMPE_IMM,
             } for sku in ('PMP-IMM-1.5M', 'PMP-IMM-3M', 'PMP-IMM-4T',
                           'PMP-IMM-5.5T', 'PMP-IMM-7.5T', 'PMP-IMM-10T')},
    **{sku: {'description': _DESC_POMPE_SUR,
             } for sku in ('PMP-SUR-1.5M', 'PMP-SUR-3T')},
    'CAB-6MM-M': {
        # DC35/G1 (2026-08-19) — le fondateur ne pose que du Nexans : la marque
        # doit être visible sur CHAQUE ligne câble, pas seulement dans le nom
        # du SKU récent CAB-NEX-DC-6. Faits vérifiés sur la datasheet Nexans
        # H1Z2Z2-K SUN PLUS (1,5 kV DC) : nexans.fr/en/products/Renewable/
        # Solar/Photovoltaic-Cables/Nexans-PV-38188.html.
        # DC35/G2 (2026-08-20) — le NOM du produit (CATALOGUE ci-dessus) porte
        # désormais lui aussi « Nexans » : la proposition affichait « Câble
        # solaire 6mm² » sans la marque nulle part dans la désignation.
        'marque': 'Nexans',
        'description': ('Câble solaire H1Z2Z2-K, conducteur cuivre étamé souple classe 5\n'
                        'Isolation et gaine réticulées sans halogène, tenue -40°C à 90°C\n'
                        'Tension 1,5/1,8 kV DC, conforme NF EN 50618 et CEI 62930 (prix au mètre)'),
    },
    # Variateurs VEICHI
    # O3 (2026-08-20) — aucune page de garantie corporate veichi.com trouvée ;
    # les seules mentions « 2 ans » circulant sont des fiches produit de
    # revendeurs tiers (Alibaba/made-in-china), et d'autres listings tiers
    # indiquent 18 mois pour la même famille — deux valeurs contradictoires,
    # aucune ne vient d'un document VEICHI officiel. Champ retiré plutôt qu'un
    # chiffre non sourcé.
    'VEI-SI22-AFF': {
        'marque': 'VEICHI',
        'description': ('Afficheur déporté pour variateur VEICHI SI22\n'
                        'Lecture des paramètres et défauts au pied du coffret'),
    },
    **{sku: {'marque': 'VEICHI',
             'description': _DESC_VEICHI,
             } for sku in ('VEI-SI22-2.2-220', 'VEI-SI23-2.2-220',
                           'VEI-SI23-2.2-380', 'VEI-SI23-4-380',
                           'VEI-SI23-5.5-380', 'VEI-SI23-7.5-380',
                           'VEI-SI23-11-380', 'VEI-SI23-15-380',
                           'VEI-SI23-18-380', 'VEI-SI23-22-380',
                           'VEI-SI23-30-380', 'VEI-SI23-37-380',
                           'VEI-SI23-45-380', 'VEI-SI23-55-380',
                           'VEI-SI23-75-380')},
    # Pompes OSP série 30 — O3 (2026-08-20) : « OSP » n'est pas une marque
    # identifiable publiquement (aucune page constructeur, aucun document de
    # garantie trouvé) — « Garantie constructeur 2 ans » n'a donc aucune
    # source vérifiable. Champ retiré plutôt qu'un chiffre non sourcé.
    **{sku: {'marque': 'OSP',
             'description': _DESC_OSP,
             } for sku in ('PMP-OSP-30-8', 'PMP-OSP-30-11', 'PMP-OSP-30-13',
                           'PMP-OSP-30-15', 'PMP-OSP-30-16', 'PMP-OSP-30-17',
                           'PMP-OSP-30-20', 'PMP-OSP-30-21', 'PMP-OSP-30-25',
                           'PMP-OSP-30-26', 'PMP-OSP-30-35')},
    # ── PVG3 — Câbles & protections (descriptions FR courtes) ──
    # DC35/G1 (2026-08-19) — même marque Nexans que CAB-6MM-M/CAB-NEX-* ci-
    # dessus : un seul câble solaire réellement posé, plusieurs SKU historiques
    # pour la même section commerciale.
    'CAB-H1Z2Z2-4-M': {
        'marque': 'Nexans',
        'description': 'Câble solaire H1Z2Z2-K 4 mm², double isolation, résistant UV, conforme NF EN 50618 (au mètre)',
    },
    'CAB-H1Z2Z2-6-M': {
        'marque': 'Nexans',
        'description': 'Câble solaire H1Z2Z2-K 6 mm², double isolation, résistant UV, conforme NF EN 50618 (au mètre)',
    },
    'CAB-H1Z2Z2-10-M': {
        'marque': 'Nexans',
        'description': 'Câble solaire H1Z2Z2-K 10 mm², double isolation, résistant UV, conforme NF EN 50618 (au mètre)',
    },
    'CAB-H1Z2Z2-16-M': {
        'marque': 'Nexans',
        'description': 'Câble solaire H1Z2Z2-K 16 mm², double isolation, résistant UV, conforme NF EN 50618 (au mètre)',
    },
    # ── Câbles Nexans 6 mm² AU MÈTRE (règle fondateur 18/08) — SKU récents de
    # CATALOGUE (ligne 68 plus haut) : absents de FICHES jusqu'ici, donc SANS
    # description ni marque appliquée malgré « Nexans » dans leur NOM.
    'CAB-NEX-DC-6': {
        'marque': 'Nexans',
        'description': ('Câble solaire H1Z2Z2-K, conducteur cuivre étamé souple classe 5\n'
                        'Isolation et gaine réticulées sans halogène, tenue -40°C à 90°C\n'
                        'Tension 1,5/1,8 kV DC, conforme NF EN 50618 et CEI 62930 (prix au mètre)'),
    },
    'CAB-NEX-TER-6': {
        'marque': 'Nexans',
        'description': 'Câble de terre Nexans 6 mm², liaison de mise à la terre (prix au mètre)',
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
# PVLV2 (fondateur 21/08/2026) — l'« incompatibilité métier » anciennement
# signalée ici était FAUSSE : elle reposait sur l'identification SG01HP3
# haute tension des 15/20 kW (supposition PVG4) et sur l'idée que la gamme
# basse tension s'arrêtait à 12 kW. La datasheet officielle SG05LP3 14-20K
# (240601) prouve le contraire et le fondateur a tranché : ses 15/20 kW sont
# des SG05LP3 basse tension — l'appairage OND-H-DEY-15T/20T + BAT-DEY-5/10
# (fenêtre 40-60 V, batterie 51,2 V) est le parc RÉEL. Les paliers Huawei mono
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
    # G4 (2026-08-19) — CORRIGÉ : le fondateur a tranché le 15/08 (déjà posé
    # côté apps/web/src/lib/fiches.ts:211-215) « génération réellement en
    # pose = SG05 ; mono = gamme SG05LP1 » — le SG04LP1 ci-dessous survivait
    # ENCORE côté ERP/PDF (c'est ce que le fondateur voit sur ses devis).
    # Datasheet OFFICIELLE deyeinverter.com,
    # datasheet_sun-(3.6-8)k-sg05lp1-eu_230731_en.pdf (2023-07-31), famille
    # SUN-3.6/5/6/7.6/8K-SG05LP1-EU — le 5 kW y figure nommément. Suffixe
    # « (-SM2) » laissé en supposition (comme avant) : la datasheet officielle
    # ne montre que « -EU » sans variante de révision.
    'OND-H-DEY-5M': 'Deye SUN-5K-SG05LP1-EU(-SM2)',      # deyeinverter.com datasheet_sun-(3.6-8)k-sg05lp1-eu_230731_en.pdf
    # G4 — INCHANGÉ : la gamme SG05LP1 confirmée le 15/08 s'arrête à 8 kW
    # (famille SUN-3.6/5/6/7.6/8K-SG05LP1-EU, même datasheet 230731 ci-dessus).
    # Une révision « AM2-P » plus récente (manual_sun-3.6-10k-sg05lp1-eu-am2-p
    # _20250812_en.pdf) semble étendre la gamme jusqu'à 10 kW, mais c'est un
    # produit/suffixe DIFFÉRENT (AM2-P, pas EU/EU-SM2) — pas un fait assez net
    # pour re-sourcer ce SKU sans trancher fondateur (cf. rapport G4). Le 10M
    # reste donc en SG02LP1, modèle déjà supposé, INCHANGÉ.
    'OND-H-DEY-10M': 'Deye SUN-10K-SG02LP1-EU-AM3',      # nastechsolar datasheet — divergence plage MPPT
    # PV85 — TRANCHÉ PAR LE FONDATEUR (2026-08-15) : le 10 kW triphasé du
    # catalogue est un SG05LP3 (révision SM2), PAS le SG04LP3 supposé en PVG4.
    # Seul SKU dont le modèle est CONFIRMÉ (cf. MODELES_CONFIRMES_FONDATEUR).
    'OND-H-DEY-10T': 'Deye SUN-10K-SG05LP3-EU-SM2',      # deyeinverter.com datasheet 2024-09 + manuel 2025-11
    # PVLV2 (fondateur 21/08/2026, DÉFINITIF — « i only know 15 and 20kw on
    # LV ») : les identifications SG01HP3 « haute tension » (PVG4, supposées
    # depuis solarhouse.bg/pretapower) étaient FAUSSES — le parc réel est la
    # famille basse tension SG05LP3 14-20K, même datasheet que le 10T.
    'OND-H-DEY-15T': 'Deye SUN-15K-SG05LP3-EU-SM2',      # deyeinverter.com datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf (2024-06-01)
    'OND-H-DEY-20T': 'Deye SUN-20K-SG05LP3-EU-SM2',      # même datasheet, colonne 20K
    'BAT-DEY-5': 'Dyness DL5.0C',                        # dyness.com DL5.0C datasheet
    # PVCOMPAT (2026-08-21) — tranché entre Pro et G2 par les fiches
    # OFFICIELLES dyness.com : les valeurs seedées (DoD 90 %, 9,216 kWh
    # utilisables, 103 kg) sont EXACTEMENT celles du Powerbox Pro
    # (DynessPowerboxPro datasheet 20241231-EN) — le G2 publie 95 % / 9,728.
    # Modèle toujours « supposé » (pas confirmé fondateur), source resserrée.
    'BAT-DEY-10': 'Dyness Powerbox Pro 10.24',           # dyness.com Powerbox Pro datasheet (20241231-EN)
    # PVLV (21/08/2026) — identité posée par la facture fournisseur Solarex
    # S26/001708 (« 16kWh BOS-B-Pro Battery Pack-deye ») + fiches officielles
    # deye.com ; le suffixe -A3 exact reste une identification recherche,
    # d'où « supposé » et pas « confirmé fondateur ».
    'BAT-DYN-HV-16': 'Deye BOS-B-Pack16-A3 (BOS-B Pro-A3)',  # deye.com BOS-B Pro-A3 + facture Solarex 27/07/2026
}
# PV85 — SKU dont le modèle constructeur n'est PLUS une supposition : le
# fondateur a tranché. Leur addendum de description dit « Modèle confirmé
# fondateur : … » (pas « supposé … — à confirmer »), et c'est cette mention
# qui autorise le moteur électrique à NOMMER l'appareil sur le schéma.
# PVLV2 (21/08/2026) — les 15/20 kW CONFIRMÉS par le fondateur : basse
# tension SG05LP3 (« i only know 15 and 20kw on LV »), famille dont il a
# lui-même donné le modèle le 18/08.
MODELES_CONFIRMES_FONDATEUR = ('OND-H-DEY-10T', 'OND-H-DEY-15T', 'OND-H-DEY-20T')

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
    # Deye BASSE TENSION 48 V — familles SG05LP1 / SG02LP1 / SG05LP3.
    # Sources : G4 (2026-08-19) datasheet OFFICIELLE deyeinverter.com
    # datasheet_sun-(3.6-8)k-sg05lp1-eu_230731_en.pdf (2023-07-31), « Battery
    # Voltage Range (V) : 40-60 » PARTAGÉE par toute la famille SG05LP1
    # (identique à l'ancienne valeur SG04LP1 — re-confirmée, pas recopiée) ;
    # datasheet SG02LP1-EU-AM3 (liriksolar) ; datasheet officielle
    # deyeinverter.com datasheet_sun-3-12k-sg05lp3-eu-sm2_240927_en.pdf
    # (2024-09-27) et datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf
    # (2024-06-01) — la fenêtre 40-60 V y est donnée PARTAGÉE par toute la
    # famille SG05LP3.
    'OND-H-DEY-5M': (40, 60),
    'OND-H-DEY-10M': (40, 60),
    'OND-H-DEY-10T': (40, 60),
    # PVLV2 (fondateur 21/08/2026) — les 15/20 kW sont eux aussi des SG05LP3
    # BASSE TENSION (l'ancienne plage 160-700 V venait de la fausse
    # identification SG01HP3) : fenêtre 40-60 V PARTAGÉE par toute la famille
    # SG05LP3, même datasheet 14-20K que ci-dessus — les Dyness 51,2 V s'y
    # accrochent, exactement le parc réel du fondateur.
    'OND-H-DEY-15T': (40, 60),
    'OND-H-DEY-20T': (40, 60),
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
        # H5 (2026-08-19) — RE-SOURCÉ intégralement (colonne 710 W, page 2)
        # sur la datasheet OFFICIELLE JKM710-735N-66HL5-BDV-Z3-EU
        # (jinkosolar.eu/wp-content/uploads/2025/04/
        # JKM710-735N-66HL5-BDV-Z3-EU.pdf) : Vmp 40,65 V / Imp 17,47 A /
        # Voc 48,73 V / Isc 18,53 A / rendement STC 22,86 % — jusqu'ici
        # ABSENTS de FicheTechnique malgré une fiche déjà lue par le moteur
        # électrique (specs_for_produit) pour tout autre panneau du
        # catalogue. Dimensions 2384×1303×33 mm, 37,5 kg — MÊME datasheet.
        'pmax_wc': Decimal('710.00'),
        'voc_v': Decimal('48.73'),
        'isc_a': Decimal('18.53'),
        'vmp_v': Decimal('40.65'),
        'imp_a': Decimal('17.47'),
        'rendement_pct': Decimal('22.86'),
        'longueur_mm': 2384,
        'largeur_mm': 1303,
        'epaisseur_mm': 33,
        'poids_kg': Decimal('37.50'),
        'techno_cellule': 'N-type TOPCon (Tiger Neo)',
        'bifacial': True,
        'temp_coeff_pmax_pct_c': Decimal('-0.290'),
        'temp_coeff_voc_pct_c': Decimal('-0.250'),
    },
    # ── PVG4 — Onduleurs réseau Huawei (valeurs SOURCÉES uniquement ; tout
    # champ interpolé/« non confirmé »/divergent selon la source reste NULL
    # — voir docs/PLAN2.md PVG4 pour le détail par palier). ──
    'OND-R-HUA-5M': {
        # L-22A (2026-08-24) — « change both inverter of 5kw to increase their
        # mppt current to more then 20A so they accept the canadian solar
        # pannels ». Les DEUX bornes de courant d'entrée MPPT valent 22,0 A
        # (le plancher qui respecte « plus de 20 A ») : valeur DÉCLARÉE
        # fondateur 24/08/2026 — remplace l'identification datasheet qui
        # refusait les panneaux 710 Wc (Isc 18,59 A) ; à recaler sur référence
        # constructeur exacte si fournie. Ancienne valeur : 12,5 A d'Imp
        # admissible (SUN2000-5KTL-L1) — sous l'Imp 17,59 A d'une SEULE chaîne
        # de 710 Wc, donc écrêtage permanent annoncé. L'Isc admissible n'avait
        # JAMAIS été seedé (champ NULL, le noyau retombait alors sur la borne
        # d'Imp en simple ALERTE) : il est désormais DÉCLARÉ, pas déduit.
        # Les autres champs de cette fiche restent ceux de la datasheet.
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('90.0'), 'ond_mppt_v_max': Decimal('560.0'),
        'ond_v_max_abs': Decimal('600.0'), 'ond_i_max_mppt_a': Decimal('22.0'),
        'ond_ac_kw': Decimal('5'), 'ond_phases': 1,
        'ond_rendement_euro_pct': Decimal('97.8'),
        'ond_isc_max_mppt_a': Decimal('22.0'),
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
    #
    # L-DECH (fondateur 24/08/2026) — « mais l'onduleur aussi a un max de
    # charge et de décharge, cherche bien et rajoute aussi ces numéros ».
    #
    # LA CONVENTION DE TENSION, UNE FOIS POUR LES CINQ (le détail par SKU se
    # limite ensuite aux ampères et à l'URL). Les datasheets Deye publient ces
    # bornes en AMPÈRES dans le bloc « Battery Input Data », avec une plage de
    # port 40-60 V (« 48 V low voltage battery ») mais AUCUNE tension nominale.
    # On convertit donc à 51,2 V — la tension nominale des packs Dyness que ce
    # même catalogue quote (``bat_v_nominal``), donc le point de
    # fonctionnement RÉEL de l'installation. Ce choix est délibéré et unique :
    # le moteur compare ces deux bornes par un ``min()`` (Σ packs vs port), et
    # deux conventions de tension différentes rendraient cette comparaison
    # fausse. Convertir à 48 V donnerait une borne plus basse, mais à une
    # tension qu'aucune batterie du catalogue n'a.
    #
    # DANS LES CINQ DATASHEETS, « Max. Charging Current » et « Max.
    # Discharging Current » sont DEUX lignes distinctes portant la MÊME valeur
    # pour chaque colonne-modèle — ce n'est pas une ligne unique dédoublée
    # ici : les deux champs sont bien lus séparément, ils coïncident.
    #
    # DEUX DE CES CINQ CHIFFRES ÉTAIENT DÉJÀ DANS CE FICHIER, en commentaire
    # « NON seedés faute de champ sur FicheTechnique » (120 A pour le 5M,
    # 210 A pour le 10T) : la recherche du 24/08 les retrouve à l'identique
    # sur les datasheets officielles. Ils ont enfin un champ.
    'OND-H-DEY-5M': {
        # G4 (2026-08-19) — RE-SOURCÉ intégralement sur la datasheet OFFICIELLE
        # deyeinverter.com datasheet_sun-(3.6-8)k-sg05lp1-eu_230731_en.pdf
        # (2023-07-31), colonne SUN-5K-SG05LP1-EU (table lue en entier, pas de
        # valeur SG04LP1 reconduite) :
        #   • MPPT Voltage Range 150-425 V, 2 trackers, 1+1 chaîne — INCHANGÉS
        #     par rapport à l'ancienne fiche SG04LP1 (même plage, re-vérifiée
        #     sur la nouvelle source, pas recopiée sans preuve).
        #   • PV Input Current « 13+13 A » (famille 3.6/5/6K) = 13 A PAR MPPT
        #     — valeur SUPPLANTÉE le 24/08/2026, cf. L-22A ci-dessous.
        #   • Rated PV Input Voltage « 370 (125-500) V » ⇒ tension DC MAX
        #     ABSOLUE = 500 V, PAS 600 V (c'était l'ancienne valeur SG04LP1,
        #     jamais vérifiée sur une fiche SG05LP1 — CORRIGÉE ici).
        #   • Rated AC Output Active Power 5000 W = 5 kW, monophasé — INCHANGÉ.
        #   • Efficiency : Max. 97,60 % / Euro 96,50 % / MPPT 99,90 % (valeurs
        #     PARTAGÉES par toute la famille SG05LP1) — le champ ne porte que
        #     le rendement EURO, INCHANGÉ par rapport à l'ancienne fiche.
        #   • PVOND-H (2026-08-19) — DEUX champs enfin saisissables, comblés
        #     sur la MÊME datasheet : Start-up Voltage 125 V (partagée par
        #     toute la famille) → tension de démarrage ; Max. PV Isc(A)
        #     « 17+17 » (famille 3.6/5/6K) → 17 A d'Isc max par MPPT —
        #     valeur SUPPLANTÉE le 24/08/2026, cf. L-22A ci-dessous.
        # NON seedés faute de champ sur FicheTechnique (jamais inventé) :
        # Max. Continuous AC Passthrough 35 A, poids 24 kg, IP65.
        # L-DECH (24/08/2026) — « Max. Charging/Discharging Current » 120 A,
        # relu sur la MÊME datasheet officielle citée ci-dessus
        # (datasheet_sun-(3.6-8)k-sg05lp1-eu_230731_en.pdf, colonne SUN-5K) :
        # ce chiffre était déjà écrit ici « faute de champ », il en a un.
        # 120 A × 51,2 V = 6,144 kW → 6,14.
        #
        # L-22A (2026-08-24) — « change both inverter of 5kw to increase their
        # mppt current to more then 20A so they accept the canadian solar
        # pannels ». Les DEUX bornes de courant d'entrée MPPT passent à 22,0 A
        # (le plancher qui respecte « plus de 20 A ») : valeur DÉCLARÉE
        # fondateur 24/08/2026 — remplace l'identification datasheet qui
        # refusait les panneaux 710 Wc (Isc 18,59 A) ; à recaler sur référence
        # constructeur exacte si fournie. Les deux anciennes valeurs
        # (13,0 A d'Imp admissible / 17,0 A d'Isc, famille SUN-3.6/5/6K-SG05LP1
        # -EU) restent écrites ci-dessus : ce n'est PAS un chiffre inventé qui
        # remplace un chiffre sourcé, c'est une DÉCLARATION de matériel qui
        # remplace une IDENTIFICATION de modèle jamais confirmée à l'achat.
        # Les autres champs de cette fiche restent ceux de la datasheet.
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('150.0'), 'ond_mppt_v_max': Decimal('425.0'),
        'ond_v_max_abs': Decimal('500.0'), 'ond_i_max_mppt_a': Decimal('22.0'),
        'ond_ac_kw': Decimal('5'), 'ond_phases': 1,
        'ond_rendement_euro_pct': Decimal('96.5'),
        'ond_v_demarrage_v': Decimal('125.0'), 'ond_isc_max_mppt_a': Decimal('22.0'),
        'ond_bat_max_charge_kw': Decimal('6.14'),
        'ond_bat_max_decharge_kw': Decimal('6.14'),
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
        # Rendement euro 97,0 % (même famille basse tension 48 V que le
        # SG05LP3 triphasé seedé ici — OND-H-DEY-10T, rendement euro publié
        # 97,0 %. G4 (2026-08-19) : le SG05LP1 MONOPHASÉ, lui, publie 96,5 %
        # — cf. OND-H-DEY-5M ci-dessus — donc PAS repris ici comme référence).
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('150.0'), 'ond_mppt_v_max': Decimal('425.0'),
        'ond_v_max_abs': Decimal('600.0'), 'ond_i_max_mppt_a': Decimal('26.0'),
        'ond_ac_kw': Decimal('10'), 'ond_phases': 1,
        'ond_rendement_euro_pct': Decimal('97.0'),
        # L-DECH (24/08/2026) — datasheet OFFICIELLE deyeinverter.com
        # datasheet_sun-7.6-12kk-sg02lp1-eu-am2_240927_en.pdf (2024-09-27,
        # « kk » est une coquille dans le nom de fichier CHEZ DEYE), famille
        # SUN-7.6/8K-AM2 + SUN-10/12K-AM3 : colonne SUN-10K, charge et
        # décharge 220 A. 220 A × 51,2 V = 11,264 kW → 11,26.
        'ond_bat_max_charge_kw': Decimal('11.26'),
        'ond_bat_max_decharge_kw': Decimal('11.26'),
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
    # PVOND-H (2026-08-19) — tension de démarrage (160 V) et Isc max
    # (39 A/MPPT, révision actuelle 2 chaînes) désormais SEEDÉES : ces deux
    # valeurs étaient déjà SOURCÉES ci-dessus mais restaient en commentaire
    # faute de champ sur FicheTechnique.
    # NON seedés faute de champ sur FicheTechnique (jamais inventé) :
    # rendement MAX 97,6 % (le champ est le rendement EURO), poids 35,2 kg.
    # L-DECH (24/08/2026) — les 210 A charge/décharge qui figuraient ici
    # « faute de champ » sont CONFIRMÉS sur la datasheet officielle
    # deyeinverter.com datasheet_sun-3-12k-sg05lp3-eu-sm2_240927_en.pdf
    # (2024-09-27, colonne SUN-10K) et enfin seedés :
    # 210 A × 51,2 V = 10,752 kW → 10,75.
    # La PLAGE BATTERIE 40-60 V, elle, n'est plus perdue : PVOND la loge en
    # DONNÉE sur la description (``PLAGE_BATTERIE_ONDULEUR`` plus haut) ET,
    # depuis PVOND-H, sur le champ dédié (même dict, fusionné plus bas).
    'OND-H-DEY-10T': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('200.0'), 'ond_mppt_v_max': Decimal('650.0'),
        'ond_v_max_abs': Decimal('800.0'), 'ond_i_max_mppt_a': Decimal('26.0'),
        'ond_ac_kw': Decimal('10'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('97.0'),
        'ond_v_demarrage_v': Decimal('160.0'), 'ond_isc_max_mppt_a': Decimal('39.0'),
        'ond_bat_max_charge_kw': Decimal('10.75'),
        'ond_bat_max_decharge_kw': Decimal('10.75'),
    },
    # PVLV2 (fondateur 21/08/2026, DÉFINITIF) — ces deux SKU sont les modèles
    # BASSE TENSION SUN-15K/20K-SG05LP3-EU-SM2 (« i only know 15 and 20kw on
    # LV ») : les anciennes valeurs SG01HP3 « haute tension » seedées ici
    # venaient d'une supposition de recherche (PVG4) jamais validée. Source
    # UNIQUE des valeurs ci-dessous : deyeinverter.com
    # datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf (2024-06-01), table
    # PARTAGÉE famille 14-20K (relecture directe 21/08/2026) :
    # MPPT 160-650 V · 800 V DC max · 2 trackers (2/2+1 chaînes) · courant PV
    # asymétrique 36+20 A → 20 A retenu (règle prudente, tracker faible) ·
    # Isc maxi 54+30 A → 30 A retenu (même règle) · démarrage 160 V ·
    # Euro 97,0 % · plage batterie 40-60 V (cf. PLAGE_BATTERIE_ONDULEUR).
    # La migration stock 0126 recale les fiches des bases existantes (champ
    # par champ, uniquement là où la valeur est encore l'ancienne seedée).
    # L-DECH (24/08/2026) — MÊME datasheet 14-20K, bloc « Battery Input
    # Data » : charge = décharge, mais les DEUX COLONNES DIFFÈRENT — 280 A
    # pour le SUN-15K, 350 A pour le SUN-20K. Aucune valeur n'est reportée de
    # l'une à l'autre (à 51,2 V : 14,336 → 14,34 kW et 17,92 kW).
    'OND-H-DEY-15T': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('160.0'), 'ond_mppt_v_max': Decimal('650.0'),
        'ond_v_max_abs': Decimal('800.0'), 'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('15'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('97.0'),
        'ond_v_demarrage_v': Decimal('160.0'),
        'ond_isc_max_mppt_a': Decimal('30.0'),
        'ond_bat_max_charge_kw': Decimal('14.34'),
        'ond_bat_max_decharge_kw': Decimal('14.34'),
    },
    'OND-H-DEY-20T': {
        'type_fiche': 'onduleur', 'ond_n_mppt': 2,
        'ond_mppt_v_min': Decimal('160.0'), 'ond_mppt_v_max': Decimal('650.0'),
        'ond_v_max_abs': Decimal('800.0'), 'ond_i_max_mppt_a': Decimal('20.0'),
        'ond_ac_kw': Decimal('20'), 'ond_phases': 3,
        'ond_rendement_euro_pct': Decimal('97.0'),
        'ond_v_demarrage_v': Decimal('160.0'),
        'ond_isc_max_mppt_a': Decimal('30.0'),
        'ond_bat_max_charge_kw': Decimal('17.92'),
        'ond_bat_max_decharge_kw': Decimal('17.92'),
    },
    # ── PVG4 — Batteries Dyness ──
    'BAT-DEY-5': {
        'type_fiche': 'batterie',
        'bat_kwh_nominal': Decimal('5.12'), 'bat_kwh_usable': Decimal('4.60'),
        'bat_dod_pct': Decimal('90.0'), 'bat_v_nominal': Decimal('51.2'),
        # 75 A continu × 51,2 V ≈ 3,84 kW (valeur constructeur, dyness.com).
        'bat_max_charge_kw': Decimal('3.84'),
        # L-DECH (24/08/2026) — datasheet OFFICIELLE Dyness DL5.0C,
        # https://dyness.com/Public/Uploads/uploadfile/files/20250318/
        # DynessDL5.0Cdatasheet20250228EN.pdf (version 20250228-EN), ligne
        # « Max. Charge/Discharge Current » : « Charge 75 A / Discharge 100 A ».
        # 100 A × 51,2 V = 5,12 kW.
        # ⇒ RÈGLE GÉNÉRALE FONDATEUR CONFIRMÉE À L'AMPÈRE PRÈS (« en général
        #   c'est 100 A multiplié par les 52 V » ≈ 5,1 kW).
        # ⇒ ET ELLE PROUVE POURQUOI ON NE DÉDUIT JAMAIS LA DÉCHARGE DE LA
        #   CHARGE : ce pack accepte 75 A et en rend 100. Les deux champs sont
        #   sourcés séparément, jamais recopiés l'un dans l'autre.
        # NON seedé (aucun champ, jamais inventé) : pic 110 A pendant 15 s —
        # un pic de quinze secondes ne borne pas une rafale de trente minutes,
        # c'est le CONTINU qui fait foi ici.
        'bat_max_decharge_kw': Decimal('5.12'),
    },
    'BAT-DEY-10': {
        'type_fiche': 'batterie',
        'bat_kwh_nominal': Decimal('10.24'),
        # Source : 9.216 kWh usable, arrondi aux 2 décimales du champ.
        'bat_kwh_usable': Decimal('9.22'),
        'bat_dod_pct': Decimal('90.0'), 'bat_v_nominal': Decimal('51.2'),
        # 100 A × 51,2 V = 5,12 kW (valeur constructeur).
        'bat_max_charge_kw': Decimal('5.12'),
        # L-DECH (24/08/2026) — datasheet OFFICIELLE Dyness Powerbox Pro,
        # https://www.dyness.com/Public/Uploads/uploadfile/files/20250102/
        # PowerboxProdatasheetEN20241231-432.pdf (version 20241231-EN, celle
        # déjà citée par ce seeder) : 100 A × 51,2 V = 5,12 kW.
        # ⇒ RÈGLE GÉNÉRALE FONDATEUR CONFIRMÉE (100 A × ~52 V).
        # NUANCE À DIRE À VOIX HAUTE — cette datasheet ne publie PAS deux
        # lignes « max charge » / « max décharge » distinctes comme le DL5.0C :
        # son seul champ de courant est « Recommended Charge/Discharge
        # Current » = 100 A (label COMBINÉ, couvrant donc explicitement la
        # décharge), cohérent avec la « Nominal Power » 5,12 kW publiée juste
        # à côté. C'est EXACTEMENT la valeur dont ce seeder tire déjà
        # ``bat_max_charge_kw`` ci-dessus : la retenir aussi en décharge est
        # la lecture cohérente du même chiffre publié, et elle est
        # CONSERVATRICE (un courant recommandé est inférieur ou égal au
        # maximum). Aucune valeur « max » distincte n'a été trouvée sur les
        # versions officielles EU et AU/NZ ; les 150 A annoncés par certains
        # REVENDEURS n'apparaissent dans AUCUN document Dyness et ne sont donc
        # PAS retenus. À recaler si Dyness publie un jour la ligne « max ».
        'bat_max_decharge_kw': Decimal('5.12'),
    },
    # PVLV (21/08/2026) — Deye BOS-B-Pack16-A3 (système BOS-B Pro-A3),
    # identifié par la facture Solarex S26/001708 + fiches officielles
    # deye.com (brochures 2025-09-28 / 2025-12-11).
    # ``bat_v_nominal`` DÉLIBÉRÉMENT OMIS : 51,2 V est la tension du MODULE,
    # jamais celle que voit l'onduleur — le système empile 5 à 15 modules EN
    # SÉRIE derrière la control box BOS-B-PDU-2-A (200-1000 Vdc) et Deye ne
    # publie pas la fenêtre système exacte. Poser 51,2 ici ferait entrer ce
    # composant HV dans la fenêtre 40-60 V des onduleurs BASSE tension (la
    # règle data-driven prime sur le mot-clé dès que la donnée existe,
    # ``services._batterie_compatible``) — un contresens physique. Sans
    # tension nominale, le repli mot-clé « haute tension » garde ce produit
    # HORS de toute auto-composition, conforme à la liste officielle Deye qui
    # n'approuve PAS le BOS-B Pro sur la famille AM2 15/20 kW (cf. bandeau
    # BATTERIE_DEYE_HV — décision fondateur en attente).
    # ``bat_kwh_usable`` omis : Deye ne publie pas de valeur par module
    # (seulement un ratio système ≈ 90 %).
    'BAT-DYN-HV-16': {
        'type_fiche': 'batterie',
        'bat_kwh_nominal': Decimal('16.08'),
        'bat_dod_pct': Decimal('90.0'),   # « Recommend DoD: 90 % » (officiel)
        # 180 A × 51,2 V = 9,216 kW par module (courant max officiel).
        'bat_max_charge_kw': Decimal('9.22'),
        # L-DECH (24/08/2026) — brochure OFFICIELLE deyeinverter.com
        # « BOS-B Pro-A3 series » du 2025-09-28 : le module BOS-B-Pack16-A3
        # publie UN SEUL champ combiné « Nominal Charge/Discharge Current »
        # = 180 A (au niveau système : « Recommend 157 A / Max 180 A », même
        # valeur combinée, aucune séparation charge vs décharge). Deye ne
        # publie donc pas deux grandeurs distinctes ici : 180 A × 51,2 V
        # = 9,216 kW s'applique aux deux sens, exactement comme la charge
        # déjà seedée ci-dessus.
        # ⚠ ÉCART ASSUMÉ VS LA RÈGLE GÉNÉRALE FONDATEUR (100 A × 52 V) : ce
        #   pack haute tension publie 180 A, presque le double. LA DATASHEET
        #   FAIT FOI — c'est un module de 16 kWh, pas un mural de 5 ou 10 kWh,
        #   et la règle des 100 A décrit ces derniers (elle est vérifiée à
        #   l'ampère près sur les deux Dyness ci-dessus). Écart SIGNALÉ au
        #   fondateur, jamais lissé.
        # RAPPEL : ce produit reste HORS de toute auto-composition (aucune
        # ``bat_v_nominal`` — cf. le commentaire PVLV ci-dessus), donc cette
        # valeur ne borne aucun devis aujourd'hui ; elle est fichée pour le
        # jour où la décision fondateur sur les HV tombera.
        'bat_max_decharge_kw': Decimal('9.22'),
    },
}

# ── PVOND-H (fondateur 19/08/2026) — même donnée, fusionnée dans le champ
# DÉDIÉ ─────────────────────────────────────────────────────────────────────
# ``PLAGE_BATTERIE_ONDULEUR`` (plus haut) reste la SEULE source de vérité de
# la plage de tension batterie — inchangée, toujours écrite en ligne marquée
# de la description pour la lecture RÉTRO-COMPATIBLE côté moteur
# (``plage_batterie_onduleur``, ``apps/stock/selectors.py``, repli si le
# champ dédié est vide). Cette fusion ADDITIVE pousse la MÊME valeur dans le
# nouveau bloc structuré de ``FicheTechnique`` (``ond_bat_aucune``/
# ``ond_bat_v_min``/``ond_bat_v_max``) pour les onduleurs qui ont déjà une
# entrée ci-dessus — jamais une deuxième saisie à maintenir en parallèle, un
# seul dictionnaire (``PLAGE_BATTERIE_ONDULEUR``) qui alimente les DEUX
# mécanismes. Les deux SKU Huawei mono ARTEFACTS (10M/12M, sans entrée
# ci-dessus) restent hors de cette fusion, comme de tout le reste du seeder.
#
# ⚠ NUANCE ``ond_bat_aucune`` (BooleanField, jamais NULL) — même doctrine que
# le 0/Decimal('0') du docstring de ``_fiche_champ_vide`` : ``False`` EST une
# valeur, pas un « vide ». Sur une base DÉJÀ seedée avant cette migration,
# chaque fiche onduleur existante reçoit ``ond_bat_aucune=False`` (défaut de
# colonne) AVANT le premier run de ce seeder — la garde « combler seulement
# le vide » ne le réécrira donc PAS en ``True`` pour les dix onduleurs réseau
# tant que ``--reappliquer-fiches`` n'est pas passé une fois (même mécanisme
# que PV85 : « faire atteindre une correction à une base déjà seedée »). Les
# TROIS champs numériques (``ond_v_demarrage_v``/``ond_isc_max_mppt_a``/
# ``ond_bat_v_min``/``ond_bat_v_max``, tous ``null=True``) n'ont PAS ce
# problème : une fiche existante les porte à ``None`` jusqu'ici, donc
# ``_fiche_champ_vide`` les comble normalement, sans drapeau, au prochain
# déploiement. Un produit CRÉÉ après cette migration n'a de toute façon
# jamais ce problème (la fiche est créée avec ``ond_bat_aucune`` déjà posé).
for _sku_plage, _plage_fusion in PLAGE_BATTERIE_ONDULEUR.items():
    if _sku_plage not in FICHES_TECHNIQUES:
        continue
    if _plage_fusion is None:
        FICHES_TECHNIQUES[_sku_plage]['ond_bat_aucune'] = True
    else:
        _bas_fusion, _haut_fusion = _plage_fusion
        FICHES_TECHNIQUES[_sku_plage]['ond_bat_v_min'] = Decimal(str(_bas_fusion))
        FICHES_TECHNIQUES[_sku_plage]['ond_bat_v_max'] = Decimal(str(_haut_fusion))


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


# ── L-FORFAIT (ordre fondateur 24/08/2026) — BARÈME FORFAITAIRE AU PANNEAU ──
# « chaque case de installation, tableau AC/DC et accessoires devra avoir une
# partie fixe et une par panneau que je pourrai changer par la suite ».
#
# Ces trois lignes ne se vendent pas à l'unité : leur montant est une DROITE en
# nombre de panneaux, ``prix_fixe_ht + prix_par_panneau_ht × nb_panneaux`` (DH
# HT), lue par ``apps.ventes.services.prix_forfait_ht``. Le barème vit ICI et
# dans le stock — plus aucun chiffre en dur dans le code de composition.
#
#   · Installation — chiffres BRUTS du fondateur : 2 000 fixe + 250/panneau.
#     Ancrages conservés : 8 panneaux → 4 000 HT, 16 → 6 000 HT ; l'entre-deux
#     se lisse désormais (10 → 4 500 HT) au lieu de sauter par marches.
#   · Accessoires — DÉRIVÉ de l'ancienne règle (1 000 TTC par bloc de 5 kWc,
#     soit 833,33 HT à 8 panneaux et 1 666,67 HT à 16) : aucune part fixe,
#     1 000/1,20/8 = 104,1666…/panneau, PUIS ÷ 2 (« reduce the price of
#     accesoirs by half »). 52,0833 — et non 52,08 — garde la MOITIÉ EXACTE
#     aux deux ancrages.
#   · Tableau De Protection AC/DC — même dérivation (1 500 TTC/bloc ⇒ 1 250 HT
#     à 8 panneaux, 2 500 HT à 16) : 1 500/1,20/8 = 156,25/panneau EXACT, PUIS
#     + 30 % (« add 30% to tableau DC AC total price ») = 203,125.
#
# Le ``prix_vente`` catalogue de ces trois SKU est LAISSÉ TEL QUEL : il n'est
# plus ce qui les tarife, mais l'effacer casserait le garde « produit sans
# prix » qui les exclurait du kit.
BAREMES_FORFAIT = {
    'INST-CAT': (Decimal('2000'), Decimal('250')),
    'ACC-CAT': (Decimal('0'), Decimal('52.0833')),
    'TAB-PROT': (Decimal('0'), Decimal('203.1250')),
}


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

        # PVLV (21/08/2026) — le bloc « onduleurs Deye basse tension à prix
        # vides » a disparu : les deux SKU LV vivent dans ``CATALOGUE`` avec
        # leurs prix fondateur (le transfert sur bases existantes est
        # l'affaire de la migration stock 0126, pas du seeder).

        # ── Batterie Deye BOS-B Pro haute tension — 16 kWh : prix RÉELS ──
        # (3 000 DH/kWh, fondateur). PVLV (21/08/2026) — prix ACHAT désormais
        # COMMUNIQUÉ : facture fournisseur Solarex Maroc S26/001708 du
        # 27/07/2026 — « 16kWh BOS-B-Pro Battery Pack » à 28 000 DH HT le pack
        # (33 600 TTC). Le pack SEUL : la control box HV (11 200 HT) et les
        # racks/câbles (6 000 HT) de la même facture couvrent une pile de 6
        # packs et ne sont PAS amortis ici (l'amortissement dépend de la
        # taille de pile — au fondateur d'ajuster s'il le souhaite).
        for nom, sku, sell_ttc, qte, seuil in BATTERIE_DEYE_HV:
            if (Produit.objects.filter(company=company, sku=sku).exists()
                    or Produit.objects.filter(
                        company=company, nom__iexact=nom,
                        is_archived=False).exists()):
                skipped.append(nom)
                continue
            produit = Produit.objects.create(
                company=company, nom=nom, sku=sku,
                categorie=get_categorie(classify_categorie(nom)),
                # PVLV — 28 000 HT le pack 16 kWh (facture Solarex S26/001708).
                prix_achat=ht(Decimal('33600')),
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
        # BATHOMO (2026-08-26, RECALÉ) — le Dyness 10 kWh (``BAT-DEY-10``)
        # N'EST PLUS dans cette liste : ce n'est PAS un artefact qui ne
        # reviendra jamais (le fondateur l'a seulement mis à 0 en stock, un
        # mouvement, pas un archivage — « when it comes back, use it for
        # bigger installations »). Sa garde d'exclusion vit côté composition
        # (stock-gating batterie, ``apps.ventes.services``), jamais ici.
        archived_count = Produit.objects.filter(
            company=company,
            sku__in=(PLACEHOLDER_VFD_SKUS + ARTEFACTS_ONDULEUR_SKUS),
            is_archived=False).update(is_archived=True)

        # ── Fiches commerciales : mise à jour ADDITIVE des seuls champs
        #    descriptifs (marque/description/garantie) — jamais prix/quantités ──
        fiches_updated = 0
        for sku, fiche in FICHES.items():
            produit = Produit.objects.filter(company=company, sku=sku).first()
            if not produit:
                continue
            # `garantie_mois` (structuré, lu par theme.warranties_for) suit le
            # même contrat de ré-application que le texte de garantie.
            for field in ('marque', 'description', 'garantie', 'garantie_mois'):
                if field in fiche:
                    setattr(produit, field, fiche[field])
            produit.save(update_fields=[
                f for f in ('marque', 'description', 'garantie', 'garantie_mois')
                if f in fiche])
            fiches_updated += 1

        # ── L-FORFAIT — barème forfaitaire au panneau (cf. BAREMES_FORFAIT) ──
        # ADDITIF au sens le plus strict : on ne pose le barème que si les DEUX
        # champs sont VIDES. Dès que le fondateur a saisi l'une des deux parts
        # au stock, le seeder n'y touche plus JAMAIS — y compris au
        # redéploiement, où il tourne à chaque fois (scripts/deploy-prod.ps1).
        # Poser 0 est une SAISIE (Accessoires n'a pas de part fixe) : c'est
        # pourquoi le test porte sur ``is None``, jamais sur la fausseté.
        baremes_poses = 0
        for sku, (fixe, par_panneau) in BAREMES_FORFAIT.items():
            produit = Produit.objects.filter(company=company, sku=sku).first()
            if not produit:
                continue
            if (produit.prix_fixe_ht is not None
                    or produit.prix_par_panneau_ht is not None):
                continue
            produit.prix_fixe_ht = fixe
            produit.prix_par_panneau_ht = par_panneau
            produit.save(
                update_fields=['prix_fixe_ht', 'prix_par_panneau_ht'])
            baremes_poses += 1

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
            f"{baremes_poses} barèmes forfaitaires posés (au panneau), "
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
