"""Articles et rôles du kit de POMPAGE semés par ``seed_catalogue`` — extrait
de ``seed_catalogue.py`` (fichier-mur), à l'identique pour ``OPTIONS_POMPAGE``.

À PRIX VIDE sauf les prix confirmés de ``PRIX_TTC_PVG3`` (D-ACAL-127) ; tant
que ``prix_vente`` vaut 0, un article est « prix à renseigner » et jamais
auto-chiffré (même garde que les pompes OSP). Additif, comme tout le seeder : un SKU ou un nom actif déjà
présent est sauté, jamais réécrit (prix, nom, rôle).
"""

from decimal import Decimal

# ── AGR104 — articles des OPTIONS du kit pompage (D-AGR-8), PRIX VIDES ───────
# Articles GÉNÉRIQUES, sans marque ni caractéristique inventée : le fondateur
# les renseigne (prix, fournisseur) ; tant que ``prix_vente`` vaut 0 ils sont
# « prix à renseigner » et jamais auto-chiffrés (même garde que les pompes OSP).
# ``role_pompage`` est DÉCLARÉ à la création (vocabulaire ROLES_POMPAGE, AGR100).
# (nom, sku, role_pompage, qte, seuil)
OPTIONS_POMPAGE = [
    ('Sonde de niveau (protection marche à sec)', 'SONDE-NIV', 'sonde_niveau', 20, 2),
    ("Compteur d'eau / débitmètre", 'CPT-EAU', 'compteur_eau', 20, 2),
    ('Câble de descente immergé (au mètre)', 'CAB-DESC-M', 'cable_descente', 5000, 200),
    ('Colonne de refoulement', 'COL-REF', 'colonne_refoulement', 20, 2),
    ('Clapet anti-retour', 'CLAP-AR', 'clapet', 20, 2),
    ('Tuyauterie (au mètre)', 'TUY-M', 'tuyauterie', 5000, 200),
    ('Bassin', 'BASSIN', 'bassin', 20, 2),
]

# D-ACAL-118 (fondateur 25/11/2026) — le kit minimum des NOUVEAUX devis de
# pompage : UN coffret de protection DC + un disjoncteur AC et un parafoudre AC
# entre le variateur et la pompe. Rôle pompage DÉCLARÉ à la création de ces
# articles du lot PVG3 (``seed_catalogue.CABLES_PROTECTIONS_VIDES``) ; une base
# existante le reçoit par les migrations stock 0162 et 0190, gardées sur « rôle
# vide ». Un article à prix 0 (le parafoudre AC) refuse le devis automatique
# de pompage en nommant l'article à chiffrer ; les autres sont chiffrés par
# ``PRIX_TTC_PVG3`` ci-dessous (D-ACAL-127).
ROLE_POMPAGE_PVG3 = {
    'COF-DC-2STR': 'protection_dc',
    **{sku: 'protection_ac' for sku in (
        'DISJ-AC-C-16-1P', 'DISJ-AC-C-20-1P', 'DISJ-AC-C-25-1P',
        'DISJ-AC-C-32-1P', 'DISJ-AC-C-16-4P', 'DISJ-AC-C-20-4P',
        'DISJ-AC-C-25-4P', 'DISJ-AC-C-32-4P', 'PARA-AC-T2')},
}

# D-ACAL-127 — Prix TTC lus sur mrelec.ma le 25/11/2026 — confirmés par le
# fondateur le 25/11/2026 (D-ACAL-127) : prix boutique, sans marge ajoutée.
# Stockés HT par ``seed_catalogue.ht`` (TVA 20 %), à la CRÉATION seulement : un
# article existant garde son prix (une base déjà semée les reçoit par la
# migration stock 0191, gardée sur « prix vide »). ``prix_achat`` reste vide.
PRIX_TTC_PVG3 = {
    # EATON Xpole « Disjoncteur Modulaire AC 2P » (1P+N, courbe C, 6 kA) —
    # https://mrelec.ma/products/disjoncteur-modulaire-ac-2p
    'DISJ-AC-C-16-1P': 80, 'DISJ-AC-C-20-1P': 80, 'DISJ-AC-C-25-1P': 80,
    'DISJ-AC-C-32-1P': 83,
    # CHINT NXB-63 « Disjoncteur modulaire 4P » (courbe non publiée sur la page)
    # — https://mrelec.ma/products/disjoncteur-modulaire-chint-4p-220v
    'DISJ-AC-C-16-4P': 128, 'DISJ-AC-C-20-4P': 132, 'DISJ-AC-C-25-4P': 136,
    'DISJ-AC-C-32-4P': 141,
    # Misterelec « Boite de jonction DC », 2 entrées, sur commande —
    # https://mrelec.ma/products/boite-de-jonction-dc
    'COF-DC-2STR': 2000,
    # D-ACAL-128 — prix donné par le fondateur le 25/11/2026 (aucune annonce
    # marocaine fiable lue) ; base existante : migration stock 0192.
    'PARA-AC-T2': 1000,
}

# D-ACAL-129 (fondateur 25/11/2026, « Yes, 780 V for 380 V models ») — fiches
# techniques « variateur de pompage » des variateurs VEICHI, valeurs PUBLIÉES
# par le constructeur seulement :
#   · SI22 220 V — manuel « si22-solar-pump-inverter-manual-simple-v1-0.pdf »,
#     §2, tableau p. 2 : entrée DC max 400 V, Voc recommandée 360-400 V ;
#   · SI23 220 V (D3) — manuel « si23-solar-pump-inverter-manual-complete.pdf »,
#     §1.4 « Technical Specification » p. 4 : entrée DC max 450 V, Voc
#     recommandée 360-430 V ;
#   · SI23 380 V (D5, T3) — même tableau : 800 V imprimé, le manuel fixe le
#     déclenchement logiciel de surtension à 780 VDC → 780 V retenu par le
#     fondateur pour TOUS les 380 V ; Voc recommandée 620-750 V.
# https://www.veichi.com/d/file/download/solar-water-pump-inverter/si22-solar-pump-inverter-manual-simple-v1-0.pdf
# https://www.veichi.com/d/file/download/solar-water-pump-inverter/si23-solar-pump-inverter-manual-complete.pdf
# Le constructeur ne publie NI fenêtre MPPT min/max NI courant d'entrée DC :
# ``ond_mppt_v_min``/``ond_mppt_v_max``/``ond_i_max_mppt_a`` restent VIDES.
# Une fiche est CRÉÉE seulement pour un variateur qui n'en a aucune (jamais
# une fiche existante complétée ni réécrite) ; base existante : migration 0193.
_FICHE_SI22_220 = {'ond_v_max_abs': Decimal('400.0'),
                   'var_voc_reco_min_v': Decimal('360.0'),
                   'var_voc_reco_max_v': Decimal('400.0')}
_FICHE_SI23_220 = {'ond_v_max_abs': Decimal('450.0'),
                   'var_voc_reco_min_v': Decimal('360.0'),
                   'var_voc_reco_max_v': Decimal('430.0')}
_FICHE_SI23_380 = {'ond_v_max_abs': Decimal('780.0'),
                   'var_voc_reco_min_v': Decimal('620.0'),
                   'var_voc_reco_max_v': Decimal('750.0')}
FICHES_VARIATEURS_VEICHI = {
    'VEI-SI22-2.2-220': _FICHE_SI22_220,
    'VEI-SI23-2.2-220': _FICHE_SI23_220,
    **{'VEI-SI23-%s-380' % kw: _FICHE_SI23_380 for kw in (
        '2.2', '4', '5.5', '7.5', '11', '15', '18', '22', '30', '37', '45',
        '55', '75')},
}


def semer_fiches_variateurs(company, Produit, FicheTechnique):
    """D-ACAL-129 — crée la fiche ``variateur_pompage`` des variateurs VEICHI
    de la société qui n'ont AUCUNE fiche ; rend le nombre de fiches créées."""
    crees = 0
    for sku, valeurs in FICHES_VARIATEURS_VEICHI.items():
        produit = Produit.objects.filter(company=company, sku=sku).first()
        if produit is None or FicheTechnique.objects.filter(
                produit=produit).exists():
            continue
        FicheTechnique.objects.create(
            company=company, produit=produit,
            type_fiche='variateur_pompage', **valeurs)
        crees += 1
    return crees


def tension_pompe(nom):
    """D-ACAL-129 (fondateur 25/11/2026, « Yes: 220 V / 380 V ») — la tension
    d'une petite pompe du lot POMPAGE : 220 V monophasée, 380 V triphasée,
    phase lue par la MÊME fonction que le kit (``alimentation_produit``) ;
    ``None`` quand la phase n'est pas lisible."""
    from core.pompage.selection import (
        TENSION_MONO_V, TENSION_TRI_V, alimentation_produit)
    return {'mono': TENSION_MONO_V, 'tri': TENSION_TRI_V}.get(
        alimentation_produit({'nom': nom}))


# D-ACAL-130 — prix confirmés par le fondateur le 25/11/2026 (D-ACAL-130) —
# pose : barème de l'installation résidentielle (2 000 HT + 250 HT par
# panneau). Le kit lit ``prix_fixe_ht``/``prix_par_panneau_ht``
# (``core.pompage.kit.bareme_saisi``) : ``prix_vente`` reste 0, ce qui garde
# l'article hors du devis résidentiel (``_has_price``). À la création
# seulement ; base existante : migration stock 0195.
BAREME_POMPAGE = {
    'INST-PMP': {'prix_fixe_ht': Decimal('2000'),
                 'prix_par_panneau_ht': Decimal('250')},
}


# D-ACAL-130 — prix confirmés par le fondateur le 25/11/2026 (D-ACAL-130) —
# structure : valeur de CI-STRUCT-PLAT-LEST (540 DH TTC par panneau, la
# quantité du kit étant le nombre de panneaux). TTC, stocké HT par
# ``seed_catalogue.ht`` à la création seulement ; base existante : migration
# stock 0196.
PRIX_TTC_POMPAGE = {
    'STR-SOL-PMP': 540,
}
