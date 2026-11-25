"""Articles et rôles du kit de POMPAGE semés par ``seed_catalogue`` — extrait
de ``seed_catalogue.py`` (fichier-mur), à l'identique pour ``OPTIONS_POMPAGE``.

À PRIX VIDE sauf les prix confirmés de ``PRIX_TTC_PVG3`` (D-ACAL-127) ; tant
que ``prix_vente`` vaut 0, un article est « prix à renseigner » et jamais
auto-chiffré (même garde que les pompes OSP). Additif, comme tout le seeder : un SKU ou un nom actif déjà
présent est sauté, jamais réécrit (prix, nom, rôle).
"""

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
