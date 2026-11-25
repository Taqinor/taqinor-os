"""Articles et rôles du kit de POMPAGE semés par ``seed_catalogue`` — extrait
de ``seed_catalogue.py`` (fichier-mur), à l'identique pour ``OPTIONS_POMPAGE``.

Tous à PRIX VIDE : le fondateur les chiffre ; tant que ``prix_vente`` vaut 0,
un article est « prix à renseigner » et jamais auto-chiffré (même garde que
les pompes OSP). Additif, comme tout le seeder : un SKU ou un nom actif déjà
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
# vide ». Prix toujours VIDES : tant qu'ils valent 0, le devis automatique de
# pompage est refusé en nommant l'article à chiffrer.
ROLE_POMPAGE_PVG3 = {
    'COF-DC-2STR': 'protection_dc',
    **{sku: 'protection_ac' for sku in (
        'DISJ-AC-C-16-1P', 'DISJ-AC-C-20-1P', 'DISJ-AC-C-25-1P',
        'DISJ-AC-C-32-1P', 'DISJ-AC-C-16-4P', 'DISJ-AC-C-20-4P',
        'DISJ-AC-C-25-4P', 'DISJ-AC-C-32-4P', 'PARA-AC-T2')},
}
