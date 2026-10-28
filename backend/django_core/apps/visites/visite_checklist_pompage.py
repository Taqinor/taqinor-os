"""AGV2 — gabarit « relevé du point d'eau » (lead AGRICOLE), déplacé tel quel de
``visite_checklist.py`` (qui le ré-exporte : toute référence existante tient).
"""
from __future__ import annotations

# Natures de mesure : mêmes valeurs que ``visite_checklist`` (recopiées ici pour
# éviter un import circulaire, ``visite_checklist`` important ce module).
NOMBRE = 'nombre'
BOOLEEN = 'booleen'
TEXTE = 'texte'
CHOIX = 'choix'


#: AGR412 (D-AGR-4, contrat AGR5 ``visite_terrain.json`` →
#: ``gabarit_point_eau``) — la visite « relevé du point d'eau » d'un lead
#: AGRICOLE. Elle REMPLACE les catégories toiture/tableau/local_onduleur/
#: cheminement : un technicien sur un forage n'invente plus de mesures de toit.
#: Mêmes deux règles dures : AUCUN seuil, AUCUN verdict ; ``sauf_si`` rend une
#: mesure requise facultative quand le technicien coche l'impossibilité.
#: ``unite`` est portée à part (les libellés sont ceux du contrat).
CATEGORIES_POINT_EAU = [
    {
        'categorie': 'point_eau',
        'libelle': "Point d'eau",
        'slots': [
            {
                'code': 'point_eau_tete_forage',
                'libelle': 'Tête de forage',
                'guide': ('La tête du forage ou du puits, couvercle ouvert si '
                          'possible.'),
                'requis': True,
                'min_photos': 1,
            },
            {
                'code': 'point_eau_bassin',
                'libelle': 'Bassin',
                'guide': 'Le bassin ou le réservoir existant (optionnel).',
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'source_eau', 'libelle': "Source d'eau",
             'nature': CHOIX, 'requis': True,
             'choix': ['puits', 'forage', 'bassin', 'riviere']},
            {'code': 'niveau_statique_m',
             'libelle': 'Niveau statique (pompe arrêtée)', 'unite': 'm',
             'nature': NOMBRE, 'requis': True,
             'sauf_si': 'niveau_non_mesurable'},
            {'code': 'niveau_non_mesurable',
             'libelle': 'Niveau non mesurable sur place',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'niveau_dynamique_m',
             'libelle': 'Niveau dynamique (pompe en marche)', 'unite': 'm',
             'nature': NOMBRE, 'requis': False},
            {'code': 'debit_mesure_m3h', 'libelle': 'Débit mesuré',
             'unite': 'm³/h', 'nature': NOMBRE, 'requis': True,
             'sauf_si': 'debit_non_mesurable'},
            {'code': 'debit_non_mesurable',
             'libelle': 'Débit non mesurable sur place',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'debit_methode',
             'libelle': 'Méthode de mesure du débit',
             'nature': CHOIX, 'requis': False,
             'choix': ['essai_pompage', 'seau_chronometre', 'compteur',
                       'declaration_foreur']},
            {'code': 'profondeur_forage_m', 'libelle': 'Profondeur du forage',
             'unite': 'm', 'nature': NOMBRE, 'requis': False},
            {'code': 'diametre_tubage_mm', 'libelle': 'Diamètre du tubage',
             'unite': 'mm', 'nature': NOMBRE, 'requis': False},
            {'code': 'hauteur_refoulement_m',
             'libelle': 'Hauteur de refoulement', 'unite': 'm',
             'nature': NOMBRE, 'requis': False},
            {'code': 'longueur_conduite_m',
             'libelle': 'Longueur de la conduite', 'unite': 'm',
             'nature': NOMBRE, 'requis': False},
            {'code': 'diametre_conduite_mm',
             'libelle': 'Diamètre de la conduite', 'unite': 'mm',
             'nature': NOMBRE, 'requis': False},
            {'code': 'bassin_volume_m3', 'libelle': 'Volume du bassin',
             'unite': 'm³', 'nature': NOMBRE, 'requis': False},
        ],
    },
    {
        'categorie': 'pompe_existante',
        'libelle': 'Pompe existante',
        'slots': [
            {
                'code': 'pompe_plaque',
                'libelle': 'Plaque de la pompe',
                'guide': ('La plaque signalétique lisible : kW, tension, '
                          'phases (optionnel).'),
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'pompe_presente',
             'libelle': 'Une pompe est-elle déjà installée ?',
             'nature': BOOLEEN, 'requis': True},
            {'code': 'pompe_actuelle_type',
             'libelle': 'Type de la pompe actuelle',
             'nature': CHOIX, 'requis': False,
             'choix': ['immergee', 'surface', 'ne_sait_pas']},
            {'code': 'pompe_actuelle_cv',
             'libelle': 'Puissance de la pompe actuelle', 'unite': 'CV',
             'nature': NOMBRE, 'requis': False},
            {'code': 'pompe_actuelle_kw',
             'libelle': 'Puissance plaque de la pompe actuelle',
             'unite': 'kW', 'nature': NOMBRE, 'requis': False},
            {'code': 'tension_v', 'libelle': 'Tension de la pompe actuelle',
             'unite': 'V', 'nature': NOMBRE, 'requis': False},
            {'code': 'alimentation',
             'libelle': 'Alimentation de la pompe actuelle',
             'nature': CHOIX, 'requis': False, 'choix': ['mono', 'tri']},
        ],
    },
    {
        'categorie': 'electricite',
        'libelle': 'Électricité',
        'slots': [
            {
                'code': 'electricite_coffret',
                'libelle': 'Coffret électrique',
                'guide': ('Le coffret ou le compteur sur place '
                          '(optionnel).'),
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'electricite_sur_place',
             'libelle': 'Électricité sur place',
             'nature': CHOIX, 'requis': True,
             'choix': ['aucune', 'monophase', 'triphase', 'ne_sait_pas']},
        ],
    },
    {
        'categorie': 'site_pv',
        'libelle': 'Emplacement des panneaux',
        'slots': [
            {
                'code': 'site_pv_emplacement',
                'libelle': 'Emplacement prévu des panneaux',
                'guide': ('Deux vues de la zone de pose au sol, depuis deux '
                          'côtés.'),
                'requis': True,
                'min_photos': 2,
            },
        ],
        'mesures': [
            {'code': 'distance_forage_champ_m',
             'libelle': 'Distance forage → zone de pose', 'unite': 'm',
             'nature': NOMBRE, 'requis': True},
            {'code': 'type_pose', 'libelle': 'Type de pose',
             'nature': CHOIX, 'requis': False, 'choix': ['sol', 'ombriere']},
            {'code': 'cloture', 'libelle': 'Zone clôturée',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'gardiennage', 'libelle': 'Site gardé',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'ombrage_notes',
             'libelle': 'Ombrages (arbres, bâtiments)',
             'nature': TEXTE, 'requis': False},
        ],
    },
    {
        'categorie': 'administratif',
        'libelle': 'Administratif',
        'slots': [
            {
                'code': 'admin_autorisation_abh',
                'libelle': 'Autorisation ABH',
                'guide': ("Le document d'autorisation de prélèvement "
                          '(optionnel).'),
                'requis': False,
                'min_photos': 1,
            },
            {
                'code': 'admin_compteur_eau',
                'libelle': "Compteur d'eau",
                'guide': "Le compteur d'eau du forage (optionnel).",
                'requis': False,
                'min_photos': 1,
            },
            {
                'code': 'admin_justificatifs_energie',
                'libelle': 'Justificatifs butane / gasoil',
                'guide': ("Factures ou bons d'achat de carburant "
                          '(optionnel).'),
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'autorisation_prelevement',
             'libelle': 'Autorisation de prélèvement ABH',
             'nature': CHOIX, 'requis': True,
             'choix': ['oui', 'non', 'en_cours', 'ne_sait_pas']},
            {'code': 'autorisation_numero',
             'libelle': "Numéro d'autorisation",
             'nature': TEXTE, 'requis': False},
            {'code': 'autorisation_debit_l_s', 'libelle': 'Débit autorisé',
             'unite': 'L/s', 'nature': NOMBRE, 'requis': False},
            {'code': 'autorisation_volume_m3_an',
             'libelle': 'Volume annuel autorisé', 'unite': 'm³/an',
             'nature': NOMBRE, 'requis': False},
            {'code': 'compteur_eau',
             'libelle': "Compteur d'eau sur le forage",
             'nature': BOOLEEN, 'requis': True},
            {'code': 'justificatif_foncier',
             'libelle': 'Justificatif foncier',
             'nature': TEXTE, 'requis': False},
            {'code': 'foreur_permis',
             'libelle': 'Permis du foreur (forage neuf)',
             'nature': TEXTE, 'requis': False},
        ],
    },
    {
        'categorie': 'general',
        'libelle': 'Général',
        'slots': [
            {
                'code': 'general_exploitation',
                'libelle': "Vue d'ensemble de l'exploitation",
                'guide': ("L'exploitation entière : forage, champ, zone de "
                          'pose.'),
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [],
    },
]
