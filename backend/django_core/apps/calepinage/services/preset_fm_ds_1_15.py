"""CIQ136 — préréglage « FM Global DS 1-15 (avril 2026) », SOURCÉ.

Données seulement (aucune fonction) : chargé par
``services.degagements.normaliser_contraintes_site`` UNIQUEMENT quand
l'assureur déclaré du projet est FM Global, jamais par défaut. Tenu hors de
``degagements.py`` pour que ce module-là reste sans aucun littéral de largeur
(garde de surface CALX402) : chaque chiffre ici porte la section qui le fonde.
"""

#: FM Global Property Loss Prevention Data Sheet 1-15 « Roof-Mounted Solar
#: Photovoltaic Panels » (avril 2026), §2.1.1.4 B-E (relevé W5-12) : champs
#: ≤ 46 × 46 m, allées de 1,2 m entre champs, 1,2 m des joints de dilatation,
#: 1,8 m des lanterneaux. Chaque valeur porte la section qui la fonde.
DOCUMENT_FM = ('FM Global Data Sheet 1-15 « Roof-Mounted Solar Photovoltaic '
               'Panels » (avril 2026)')
PRESET_FM_DS_1_15 = {
    'assureur': 'fm_global',
    'degagements_m': {'lanterneau': 1.8, 'joint_dilatation': 1.2},
    'ilot_max_m': {'longueur': 46.0, 'largeur': 46.0},
    'allee_ilot_m': 1.2,
    'source': {'document': DOCUMENT_FM, 'date': '2026-04',
               'reference': '§2.1.1.4 B-E'},
    'regles': {
        'lanterneau': 'DS 1-15 §2.1.1.4 — 1,8 m des lanterneaux',
        'joint_dilatation': 'DS 1-15 §2.1.1.4 — 1,2 m des joints de '
                            'dilatation',
        'ilot_max_m': 'DS 1-15 §2.1.1.4 — champs ≤ 46 × 46 m',
        'allee_ilot_m': 'DS 1-15 §2.1.1.4 — allées de 1,2 m entre champs',
    },
}
