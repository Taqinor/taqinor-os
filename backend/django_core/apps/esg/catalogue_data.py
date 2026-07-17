"""Référentiel GRI-lite (NTESG3) — données statiques du catalogue seedé.

Liste fixe (~27 indicateurs) inspirée de standards GRI usuels — jamais
présentée comme une certification GRI (voir ``reference_gri`` sur le modèle,
affichée « inspiré de »). Purement déclarative : aucune dépendance Django ici
pour rester importable par le management command ET les tests sans setup
lourd.
"""

# (code, libelle, pilier, unite_attendue, reference_gri)
GRI_LITE_CATALOGUE = [
    # ── Environnement ────────────────────────────────────────────────────
    ('E1', "Consommation d'énergie totale", 'environnement', 'kWh', 'GRI 302-1'),
    ('E2', 'Émissions GES Scope 1', 'environnement', 'tCO2e', 'GRI 305-1'),
    ('E3', 'Émissions GES Scope 2', 'environnement', 'tCO2e', 'GRI 305-2'),
    ('E4', 'Émissions GES Scope 3', 'environnement', 'tCO2e', 'GRI 305-3'),
    ('E5', 'Émissions GES totales', 'environnement', 'tCO2e', 'GRI 305'),
    ('E6', 'Déchets générés', 'environnement', 'kg', 'GRI 306-3'),
    ('E7', 'Déchets valorisés/recyclés', 'environnement', 'kg', 'GRI 306-4'),
    ('E8', "Consommation d'eau", 'environnement', 'm3', 'GRI 303-5'),
    ('E9', 'Consommation de carburant (flotte)', 'environnement', 'litres',
     'GRI 302-1'),
    ('E10', "Part d'énergie renouvelable", 'environnement', '%', 'GRI 302-1'),
    # ── Social ───────────────────────────────────────────────────────────
    ('S1', 'Effectif total', 'social', 'personnes', 'GRI 401-1'),
    ('S2', 'Taux de rotation du personnel', 'social', '%', 'GRI 401-1'),
    ('S3', 'Taux de fréquence des accidents du travail', 'social',
     'ratio', 'GRI 403-9'),
    ('S4', 'Taux de gravité des accidents du travail', 'social',
     'ratio', 'GRI 403-9'),
    ('S5', 'Nombre d\'accidents du travail', 'social', 'nombre', 'GRI 403-9'),
    ('S6', "Heures de formation par employé", 'social', 'heures',
     'GRI 404-1'),
    ('S7', "Part de femmes dans l'effectif", 'social', '%', 'GRI 405-1'),
    ('S8', "Part de femmes dans l'encadrement", 'social', '%', 'GRI 405-1'),
    ('S9', "Taux d'absentéisme", 'social', '%', 'Interne'),
    ('S10', "Nombre de presqu'accidents", 'social', 'nombre', 'GRI 403-9'),
    # ── Gouvernance ──────────────────────────────────────────────────────
    ('G1', 'Politique anti-corruption en vigueur', 'gouvernance',
     'oui/non', 'GRI 205-2'),
    ('G2', 'Incidents de non-conformité réglementaire', 'gouvernance',
     'nombre', 'GRI 419-1'),
    ('G3', "Heures de formation éthique/anti-corruption", 'gouvernance',
     'heures', 'GRI 205-2'),
    ('G4', 'Part de fournisseurs évalués RSE', 'gouvernance', '%', 'Interne'),
    ('G5', 'Non-conformités environnementales ouvertes', 'gouvernance',
     'nombre', 'GRI 307-1'),
    ('G6', 'Litiges commerciaux en cours', 'gouvernance', 'nombre', 'Interne'),
    ('G7', 'Politique de confidentialité/protection des données en vigueur',
     'gouvernance', 'oui/non', 'GRI 418-1'),
]
