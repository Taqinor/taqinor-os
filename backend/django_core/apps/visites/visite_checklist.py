"""VT1 — LA définition CODE de la checklist de visite technique terrain.

Source de vérité UNIQUE des catégories, des slots photo et des mesures
attendues. Le contrat partagé ``apps/visites/contract_samples/visite_terrain.json``
(PACT10) en est le miroir lisible : libellés, guides, ``requis``/``min_photos``
et codes de mesure sont écrits ICI et servis tels quels par
``selectors.contexte_visite_terrain``.

DEUX RÈGLES DURES (commande fondateur 2026-09-09/10) :

* **Aucun verdict automatique.** Ce module déclare QUELLES mesures sont
  attendues et sous quel libellé — jamais si une valeur est « suffisante ».
  Il n'existe ici AUCUN seuil (dégagement, pente, distance…) : le module MONTRE
  les mesures, le bureau d'études JUGE à la validation (VT3).
* **Zéro chiffre inventé.** ``min_photos`` est une exigence de CAPTURE (combien
  de vues le commercial doit ramener), pas une donnée technique dérivée.

La complétude est calculée SERVEUR à partir de ces déclarations : le front
AFFICHE la liste des manquants, il ne la reconstitue jamais.
"""
from __future__ import annotations

import re

# Natures de mesure acceptées (validation champ par champ côté API VT2).
NOMBRE = 'nombre'
BOOLEEN = 'booleen'
TEXTE = 'texte'
CHOIX = 'choix'
#: CIQ600 — liste d'éléments (trajets de câbles, zones de toiture) : la
#: déclaration porte ``forme`` (les champs d'UN élément).
LISTE = 'liste'
#: CIQ602 — entier (âge en années), objet imbriqué (étanchéité) et pièce
#: justificative (identifiant de pièce jointe ou référence texte).
ENTIER = 'entier'
OBJET = 'objet'
PIECE = 'piece'
#: CIQ660 — date ISO (``AAAA-MM-JJ``), ex. la consultation de la plateforme ANRE.
DATE = 'date'

# Types de manquants exposés dans le bloc ``completude`` du contrat.
MANQUE_PHOTO = 'photo'
MANQUE_PHOTO_A_REFAIRE = 'photo_a_refaire'
MANQUE_MESURE = 'mesure'


#: Catégories de la visite, dans l'ORDRE du wizard commercial.
#: ``slots`` = tuiles photo ; ``mesures`` = champs saisis.
CATEGORIES = [
    {
        'categorie': 'toiture',
        'libelle': 'Toiture',
        'slots': [
            {
                'code': 'toiture_vue_generale',
                'libelle': 'Vue générale du toit',
                'guide': ('Cadrer tout le pan de toit utile, si possible '
                          "depuis un point haut."),
                'requis': True,
                'min_photos': 2,
            },
            {
                'code': 'toiture_obstacles',
                'libelle': 'Obstacles et ombrages',
                'guide': ('Cheminées, antennes, arbres, bâtiments voisins qui '
                          'portent ombre.'),
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'longueur_m', 'libelle': 'Longueur de la zone utile (m)',
             'nature': NOMBRE, 'requis': True},
            {'code': 'largeur_m', 'libelle': 'Largeur de la zone utile (m)',
             'nature': NOMBRE, 'requis': True},
            # Requise SAUF toit plat : un toit plat n'a pas de pente à relever
            # (voir ``mesure_requise``) — jamais une valeur inventée à 0.
            {'code': 'pente_deg', 'libelle': 'Pente du toit (°)',
             'nature': NOMBRE, 'requis': True, 'sauf_si': 'toit_plat'},
            {'code': 'toit_plat', 'libelle': 'Toit plat',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'orientation', 'libelle': 'Orientation du pan',
             'nature': CHOIX, 'requis': True,
             'choix': ['nord', 'nord_est', 'est', 'sud_est', 'sud',
                       'sud_ouest', 'ouest', 'nord_ouest']},
            {'code': 'type_couverture', 'libelle': 'Type de couverture',
             'nature': CHOIX, 'requis': True,
             'choix': ['tuile', 'tole', 'bac_acier', 'beton', 'fibrociment',
                       'autre']},
            {'code': 'etat_couverture', 'libelle': 'État de la couverture',
             'nature': CHOIX, 'requis': True,
             'choix': ['bon', 'moyen', 'mauvais']},
            {'code': 'obstacles_notes', 'libelle': 'Notes sur les obstacles',
             'nature': TEXTE, 'requis': False},
        ],
    },
    {
        'categorie': 'tableau',
        'libelle': 'Tableau électrique',
        'slots': [
            {
                'code': 'tableau_ouvert',
                'libelle': 'Tableau ouvert (disjoncteurs visibles)',
                'guide': 'Capot ouvert, calibres lisibles.',
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'calibre_disjoncteur_a',
             'libelle': 'Calibre du disjoncteur principal (A)',
             'nature': NOMBRE, 'requis': True},
            {'code': 'type_alimentation', 'libelle': 'Type d’alimentation',
             'nature': CHOIX, 'requis': True, 'choix': ['mono', 'tri']},
            {'code': 'emplacements_libres',
             'libelle': 'Emplacements libres au tableau',
             'nature': NOMBRE, 'requis': True},
        ],
    },
    {
        'categorie': 'local_onduleur',
        'libelle': 'Emplacement onduleur',
        'slots': [
            {
                'code': 'onduleur_mur',
                'libelle': "Mur d'installation prévu",
                'guide': "Le mur entier, avec l'espace libre autour.",
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'largeur_mur_cm', 'libelle': 'Largeur du mur libre (cm)',
             'nature': NOMBRE, 'requis': True},
            {'code': 'hauteur_mur_cm', 'libelle': 'Hauteur du mur libre (cm)',
             'nature': NOMBRE, 'requis': True},
            {'code': 'profondeur_degagement_cm',
             'libelle': 'Profondeur de dégagement devant le mur (cm)',
             'nature': NOMBRE, 'requis': True},
            {'code': 'distance_tableau_m',
             'libelle': 'Distance jusqu’au tableau électrique (m)',
             'nature': NOMBRE, 'requis': True},
            {'code': 'local_abrite', 'libelle': 'Local abrité',
             'nature': BOOLEEN, 'requis': True},
            {'code': 'local_ventile', 'libelle': 'Local ventilé',
             'nature': BOOLEEN, 'requis': True},
        ],
    },
    {
        'categorie': 'cheminement',
        'libelle': 'Cheminement des câbles',
        'slots': [
            {
                'code': 'cheminement_parcours',
                'libelle': 'Parcours toit → onduleur',
                'guide': ('Photos du trajet prévu des câbles (optionnel).'),
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'longueur_estimee_m',
             'libelle': 'Longueur estimée du cheminement (m)',
             'nature': NOMBRE, 'requis': False},
        ],
    },
    {
        'categorie': 'general',
        'libelle': 'Général',
        'slots': [
            {
                'code': 'general_facade',
                'libelle': 'Façade du bâtiment',
                'guide': "Vue d'ensemble depuis la rue.",
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [],
    },
]


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

#: CIQ600 (D-CIQ-5, contrat CIQ5 ``visite_terrain.json`` → ``gabarit_ci``) —
#: la visite d'un site PROFESSIONNEL (lead commercial ou industriel) : socle
#: commun + BT. Elle REMPLACE le gabarit résidentiel (toit_plat, local
#: onduleur…). Les zones de toiture (CIQ602) et le supplément MT (CIQ660)
#: s'y ajoutent. Mêmes règles dures : AUCUN seuil, AUCUN verdict.
CATEGORIES_CI = [
    {
        # CIQ602 — LISTE de zones (un pan ou un bâtiment chacune), avec sa
        # complétude par zone. Photos au niveau de la catégorie (contrat).
        'categorie': 'toiture_ci',
        'libelle': 'Toiture',
        'slots': [
            {
                'code': 'toiture_vue_generale',
                'libelle': 'Vue générale de la toiture',
                'guide': ('Cadrer toute la toiture, si possible depuis un '
                          'point haut.'),
                'requis': True,
                'min_photos': 2,
            },
            {
                'code': 'toiture_structure_dessous',
                'libelle': 'Structure vue du dessous',
                'guide': 'Pannes, fermes ou portiques, vus depuis le bâtiment.',
                'requis': True,
                'min_photos': 1,
            },
            {
                'code': 'toiture_etancheite',
                'libelle': "Étanchéité (optionnel)",
                'guide': "Relevés d'étanchéité, joints, points d'eau.",
                'requis': False,
                'min_photos': 1,
            },
            {
                'code': 'toiture_lanterneaux',
                'libelle': 'Lanterneaux et exutoires (optionnel)',
                'guide': 'Les ouvertures en toiture et leur état.',
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'zones_toiture',
             'libelle': 'Zones de toiture (une par pan / bâtiment)',
             'nature': LISTE, 'requis': True, 'id_prefixe': 'z',
             # Surface : surface utile, OU longueur ET largeur.
             'un_groupe_parmi': [['surface_utile_m2'],
                                 ['longueur_m', 'largeur_m']],
             'forme': [
                 {'code': 'libelle', 'libelle': 'Nom de la zone',
                  'nature': TEXTE, 'requis': True},
                 {'code': 'batiment', 'libelle': 'Bâtiment',
                  'nature': TEXTE, 'requis': False},
                 {'code': 'longueur_m', 'libelle': 'Longueur (m)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'largeur_m', 'libelle': 'Largeur (m)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'surface_utile_m2',
                  'libelle': 'Surface utile (m²)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'pente_deg', 'libelle': 'Pente (°)',
                  'nature': NOMBRE, 'requis': True},
                 {'code': 'orientation', 'libelle': 'Orientation du pan',
                  'nature': CHOIX, 'requis': True,
                  'choix': ['nord', 'nord_est', 'est', 'sud_est', 'sud',
                            'sud_ouest', 'ouest', 'nord_ouest']},
                 {'code': 'couverture', 'libelle': 'Type de couverture',
                  'nature': CHOIX, 'requis': True,
                  'choix': ['bac_acier', 'beton', 'fibrociment', 'tole',
                            'tuile', 'autre']},
                 {'code': 'age_ans', 'libelle': 'Âge de la couverture (ans)',
                  'nature': ENTIER, 'requis': False},
                 {'code': 'structure', 'libelle': 'Structure porteuse',
                  'nature': CHOIX, 'requis': True,
                  'choix': ['portique', 'ferme', 'dalle', 'autre']},
                 {'code': 'portee_pannes_m',
                  'libelle': 'Portée des pannes (m)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'entraxe_pannes_m',
                  'libelle': 'Entraxe des pannes (m)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'epaisseur_bac_mm',
                  'libelle': 'Épaisseur du bac (mm)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'etancheite', 'libelle': 'Étanchéité',
                  'nature': OBJET, 'requis': False,
                  'forme': [
                      {'code': 'type', 'libelle': "Type d'étanchéité",
                       'nature': TEXTE, 'requis': False},
                      {'code': 'age_ans', 'libelle': "Âge de l'étanchéité (ans)",
                       'nature': ENTIER, 'requis': False},
                      {'code': 'sous_garantie',
                       'libelle': "Étanchéité sous garantie",
                       'nature': BOOLEEN, 'requis': False},
                  ]},
                 {'code': 'lanterneaux_exutoires',
                  'libelle': 'Lanterneaux et exutoires',
                  'nature': TEXTE, 'requis': False},
                 {'code': 'ligne_de_vie_existante',
                  'libelle': 'Ligne de vie existante',
                  'nature': BOOLEEN, 'requis': False},
                 # DÉCLARÉE seulement, avec sa pièce : l'application ne juge
                 # jamais que la charge « suffit ».
                 {'code': 'charge_admissible_declaree_kg_m2',
                  'libelle': 'Charge admissible déclarée (kg/m²)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'charge_admissible_piece',
                  'libelle': ('Pièce justifiant la charge admissible '
                              '(bureau de contrôle ou propriétaire)'),
                  'nature': PIECE, 'requis': False,
                  'requis_si': 'charge_admissible_declaree_kg_m2'},
                 {'code': 'fibrociment',
                  'libelle': 'Amiante possible — diagnostic requis',
                  'nature': BOOLEEN, 'requis': False},
             ]},
        ],
    },
    {
        'categorie': 'tableau_general',
        'libelle': 'Tableau général (TGBT)',
        'slots': [
            {
                'code': 'tgbt_ouvert',
                'libelle': 'TGBT ouvert (appareil de tête et départs)',
                'guide': 'Capot ouvert, calibres et étiquettes lisibles.',
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'calibre_a',
             'libelle': "Calibre de l'appareil de tête (A)",
             'unite': 'A', 'nature': NOMBRE, 'requis': True},
            {'code': 'depart_disponible',
             'libelle': 'Départ disponible pour le PV',
             'nature': BOOLEEN, 'requis': True},
            {'code': 'regime_neutre', 'libelle': 'Régime de neutre',
             'nature': CHOIX, 'requis': False,
             'choix': ['TT', 'TN', 'IT', 'inconnu']},
            {'code': 'parafoudre_existant', 'libelle': 'Parafoudre existant',
             'nature': BOOLEEN, 'requis': False},
        ],
    },
    {
        'categorie': 'comptage',
        'libelle': 'Comptage',
        'slots': [
            {
                'code': 'comptage_plaque',
                'libelle': 'Plaque du compteur',
                'guide': 'Plaque lisible : type, calibre, puissance.',
                'requis': True,
                'min_photos': 1,
            },
            {
                'code': 'comptage_contrat',
                'libelle': 'Contrat ou facture (optionnel)',
                'guide': 'La page du contrat qui porte la puissance souscrite.',
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'type_compteur', 'libelle': 'Type de compteur',
             'nature': TEXTE, 'requis': True},
            {'code': 'niveau_tension_constate',
             'libelle': 'Niveau de tension constaté',
             'nature': CHOIX, 'requis': True,
             'choix': ['bt', 'mt', 'inconnu']},
            {'code': 'puissance_souscrite_kva_constatee',
             'libelle': 'Puissance souscrite constatée (plaque / contrat)',
             'unite': 'kVA', 'nature': NOMBRE, 'requis': False},
        ],
    },
    {
        'categorie': 'cheminement',
        'libelle': 'Cheminement des câbles',
        'slots': [
            {
                'code': 'cheminement_parcours',
                'libelle': 'Parcours toit → onduleur',
                'guide': 'Photos du trajet prévu des câbles (optionnel).',
                'requis': False,
                'min_photos': 1,
            },
        ],
        'mesures': [
            # Longueurs DC et AC REQUISES : au moins un trajet porte chacune.
            {'code': 'trajets', 'libelle': 'Trajets de câbles',
             'nature': LISTE, 'requis': True,
             'au_moins_un': ['longueur_dc_m', 'longueur_ac_m'],
             'forme': [
                 {'code': 'libelle', 'libelle': 'Trajet', 'nature': TEXTE,
                  'requis': False},
                 {'code': 'longueur_dc_m', 'libelle': 'Longueur DC (m)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'longueur_ac_m', 'libelle': 'Longueur AC (m)',
                  'nature': NOMBRE, 'requis': False},
             ]},
        ],
    },
    {
        'categorie': 'acces_securite',
        'libelle': 'Accès et sécurité',
        'slots': [
            {
                'code': 'acces_toiture',
                'libelle': 'Accès à la toiture',
                'guide': 'Escalier, échelle, trappe : comment on monte.',
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'escalier', 'libelle': "Escalier d'accès",
             'nature': BOOLEEN, 'requis': False},
            {'code': 'echelle', 'libelle': 'Échelle nécessaire',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'nacelle', 'libelle': 'Nacelle nécessaire',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'grue_possible', 'libelle': 'Grue possible',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'horaires_acces', 'libelle': "Horaires d'accès au site",
             'nature': TEXTE, 'requis': False},
            {'code': 'zones_fragiles',
             'libelle': 'Zones fragiles (lanterneaux, bac corrodé…)',
             'nature': TEXTE, 'requis': False},
        ],
    },
    {
        'categorie': 'autres_autorisations',
        'libelle': 'Autres autorisations',
        'slots': [],
        'mesures': [
            {'code': 'texte',
             'libelle': ('Autres autorisations à confirmer avec le client '
                         '(décret 2.25.100 art. 26)'),
             'nature': TEXTE, 'requis': False},
        ],
    },
    {
        'categorie': 'general',
        'libelle': 'Général',
        'slots': [
            {
                'code': 'general_facade',
                'libelle': 'Façade du bâtiment',
                'guide': "Vue d'ensemble depuis la rue.",
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [],
    },
]

#: CIQ651 — les catégories commerciales du moteur (``Lead.CategorieCommerciale``,
#: gardé identique par ``test_ciq651_site_commerce``).
CATEGORIES_COMMERCIALES = [
    'hotel', 'restaurant', 'commerce', 'bureau', 'sante', 'ecole', 'hammam',
    'boulangerie', 'froid', 'autre']

#: CIQ651 — types de circuit critique déclarés (choix du contrat CIQ5).
CIRCUITS_CRITIQUES = ['froid', 'medical', 'informatique', 'cuisine', 'autre']

CATEGORIE_SITE_COMMERCE = 'site_commerce'
SLOT_ACCORD_PROPRIETAIRE = 'accord_proprietaire'


def _categorie_site_commerce(requise, locataire):
    """CIQ651 — la catégorie ``site_commerce`` du gabarit ``ci`` : requise pour
    un lead ``commercial``, facultative sinon. La pièce « accord du
    propriétaire » n'est servie que pour un lead LOCATAIRE (lu par
    ``crm.selectors``, jamais ressaisi). Que des faits déclarés ou observés."""
    slots = [{
        'code': 'secours_existant',
        'libelle': ('Secours existant (groupe, onduleur UPS, inverseur) '
                    '(optionnel)'),
        'guide': ("Plaque ou vue du groupe, de l'onduleur UPS ou de "
                  "l'inverseur de source."),
        'requis': False,
        'min_photos': 1,
    }]
    if locataire:
        slots.append({
            'code': SLOT_ACCORD_PROPRIETAIRE,
            'libelle': 'Accord du propriétaire (optionnel)',
            'guide': 'Pièce signée du propriétaire : le lead est locataire.',
            'requis': False,
            'min_photos': 1,
        })
    return {
        'categorie': CATEGORIE_SITE_COMMERCE,
        'libelle': 'Site commerce',
        'slots': slots,
        'mesures': [
            {'code': 'categorie', 'libelle': 'Catégorie du site',
             'nature': CHOIX, 'requis': requise,
             'choix': list(CATEGORIES_COMMERCIALES)},
            {'code': 'horaires_constates',
             'libelle': "Horaires et jours d'ouverture",
             'nature': TEXTE, 'requis': requise},
            {'code': 'equipements_principaux',
             'libelle': 'Équipements principaux',
             'nature': TEXTE, 'requis': False},
            {'code': 'circuits_critiques', 'libelle': 'Circuits critiques',
             'nature': LISTE, 'requis': False,
             'forme': [
                 {'code': 'circuit', 'libelle': 'Circuit critique',
                  'nature': CHOIX, 'requis': True,
                  'choix': list(CIRCUITS_CRITIQUES)},
                 {'code': 'precision', 'libelle': 'Précision',
                  'nature': TEXTE, 'requis': False},
             ]},
            {'code': 'secours_groupe', 'libelle': 'Groupe électrogène existant',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'secours_ups', 'libelle': 'Onduleur UPS existant',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'secours_inverseur',
             'libelle': 'Inverseur de source existant',
             'nature': BOOLEEN, 'requis': False},
            {'code': 'acces_pendant_ouverture',
             'libelle': "Contraintes d'accès pendant l'ouverture",
             'nature': TEXTE, 'requis': False},
            {'code': 'besoin_continuite_service',
             'libelle': 'Besoin de continuité de service',
             'nature': BOOLEEN, 'requis': requise},
        ],
    }


#: CIQ660 (contrat CIQ5 ``gabarit_ci_supplement_mt``) — le SUPPLÉMENT d'un site
#: raccordé en MOYENNE tension, servi quand ``comptage.niveau_tension_constate``
#: vaut ``mt``. Que des faits : aucun seuil, aucun verdict, aucune alerte cos φ.
CATEGORIES_CI_MT = [
    {
        'categorie': 'poste_mt',
        'libelle': 'Poste de livraison et TGBT',
        'slots': [
            {
                'code': 'cellule_mt',
                'libelle': 'Cellule MT et sa protection',
                'guide': 'Cellule et protection existantes, plaque lisible.',
                'requis': True,
                'min_photos': 1,
            },
            {
                'code': 'transformateur_plaque',
                'libelle': 'Plaque du transformateur',
                'guide': 'Puissance et tension lisibles sur la plaque.',
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'cellule_protection',
             'libelle': 'Cellule et protection existantes',
             'nature': TEXTE, 'requis': True},
            {'code': 'transformateurs', 'libelle': 'Transformateurs',
             'nature': LISTE, 'requis': True,
             'forme': [
                 {'code': 'nb', 'libelle': 'Nombre', 'nature': ENTIER,
                  'requis': True},
                 {'code': 'kva', 'libelle': 'Puissance (kVA)',
                  'nature': NOMBRE, 'requis': True},
             ]},
            {'code': 'tgbt_courant_assigne_a',
             'libelle': 'TGBT : courant assigné (A)', 'unite': 'A',
             'nature': NOMBRE, 'requis': False},
            {'code': 'tgbt_jeu_de_barres', 'libelle': 'TGBT : jeu de barres',
             'nature': TEXTE, 'requis': False},
        ],
    },
    {
        'categorie': 'factures_mt',
        'libelle': 'Factures MT et cos φ',
        'slots': [
            {
                'code': 'factures_mt',
                'libelle': 'Les 12 dernières factures (registres)',
                'guide': 'Registres pointe / pleines / creuses lisibles.',
                'requis': True,
                'min_photos': 1,
            },
        ],
        'mesures': [
            {'code': 'registres',
             'libelle': ('12 factures : registres pointe / pleines / creuses '
                         '(photos)'),
             'nature': LISTE, 'requis': False,
             'forme': [
                 {'code': 'mois', 'libelle': 'Mois (AAAA-MM)',
                  'nature': TEXTE, 'requis': False},
                 {'code': 'pointe_kwh', 'libelle': 'Pointe (kWh)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'pleines_kwh', 'libelle': 'Pleines (kWh)',
                  'nature': NOMBRE, 'requis': False},
                 {'code': 'creuses_kwh', 'libelle': 'Creuses (kWh)',
                  'nature': NOMBRE, 'requis': False},
             ]},
            {'code': 'cos_phi_constate', 'libelle': 'cos φ constaté',
             'nature': NOMBRE, 'requis': False},
            # Un cos φ sans sa SOURCE est refusé (CIQ660) ; ``inconnu`` est
            # une source valide.
            {'code': 'source_cos_phi', 'libelle': 'Source du cos φ',
             'nature': CHOIX, 'requis': False,
             'requis_si': 'cos_phi_constate',
             'choix': ['facture', 'mesure', 'inconnu']},
        ],
    },
    {
        'categorie': 'reactif_secours',
        'libelle': 'Compensation et groupe électrogène',
        'slots': [],
        'mesures': [
            {'code': 'condensateurs_kvar',
             'libelle': 'Batterie de condensateurs (kvar)', 'unite': 'kvar',
             'nature': NOMBRE, 'requis': False},
            {'code': 'condensateurs_etat',
             'libelle': 'État de la batterie de condensateurs',
             'nature': TEXTE, 'requis': False},
            {'code': 'groupe_kva', 'libelle': 'Groupe électrogène (kVA)',
             'unite': 'kVA', 'nature': NOMBRE, 'requis': False},
            {'code': 'groupe_inverseur', 'libelle': 'Inverseur de source',
             'nature': BOOLEEN, 'requis': False},
        ],
    },
    {
        'categorie': 'charges_principales',
        'libelle': 'Charges principales',
        'slots': [],
        'mesures': [
            {'code': 'charges',
             'libelle': ('Charges principales (moteurs, variateurs, fours, '
                         'soudage)'),
             'nature': LISTE, 'requis': False,
             'forme': [
                 {'code': 'libelle', 'libelle': 'Charge', 'nature': TEXTE,
                  'requis': True},
                 {'code': 'puissance_kw', 'libelle': 'Puissance (kW)',
                  'nature': NOMBRE, 'requis': False},
             ]},
        ],
    },
    {
        'categorie': 'reseau_assurance',
        'libelle': 'Réseau et assurance',
        'slots': [],
        'mesures': [
            {'code': 'poste_source', 'libelle': 'Poste source',
             'nature': TEXTE, 'requis': False},
            # Saisie MANUELLE : aucun scraping de la plateforme (règle #5).
            {'code': 'capacite_poste_source',
             'libelle': ('Capacité lue sur la plateforme ANRE (saisie '
                         'manuelle, aucun scraping — règle #5)'),
             'nature': TEXTE, 'requis': False},
            {'code': 'capacite_consultee_le',
             'libelle': 'Date de consultation de la plateforme',
             'nature': DATE, 'requis': False},
            {'code': 'assureur', 'libelle': 'Assureur du site',
             'nature': TEXTE, 'requis': False},
            {'code': 'exigences_assureur_piece',
             'libelle': "Exigences écrites de l'assureur",
             'nature': PIECE, 'requis': False},
            {'code': 'compartimentage_sprinklers',
             'libelle': 'Compartimentage / sprinklers',
             'nature': TEXTE, 'requis': False},
            {'code': 'profil_charge_mesure_fichier',
             'libelle': 'Fichier de profil de charge mesuré (facultatif)',
             'nature': PIECE, 'requis': False},
        ],
    },
]


#: AGR412 — les gabarits de visite (``VisiteTerrain.gabarit``).
GABARIT_TOITURE = 'toiture'
GABARIT_POINT_EAU = 'point_eau'
GABARIT_CI = 'ci'
_PAR_GABARIT = {
    GABARIT_TOITURE: CATEGORIES,
    GABARIT_POINT_EAU: CATEGORIES_POINT_EAU,
    GABARIT_CI: CATEGORIES_CI,
}


_VARIANTES_CI = {}


def _variante_ci(commerce, mt, locataire):
    """La liste de catégories ``ci`` pour (``commerce`` : ``None`` | ``'requise'``
    | ``'facultative'``, ``mt``, ``locataire``) ; mémorisée, jamais mutée."""
    cle = (commerce, mt, bool(locataire and commerce))
    if cle not in _VARIANTES_CI:
        liste = list(CATEGORIES_CI)
        if commerce:
            liste.insert(0, _categorie_site_commerce(
                commerce == 'requise', cle[2]))
        if mt:
            liste.extend(CATEGORIES_CI_MT)
        _VARIANTES_CI[cle] = liste
    return _VARIANTES_CI[cle]


def categories(gabarit=GABARIT_TOITURE, niveau=None, type_lead=None,
               locataire=False):
    """Les catégories du ``gabarit``, dans l'ordre du wizard (toiture par
    défaut : un gabarit inconnu retombe sur la checklist historique).

    Seul le gabarit ``ci`` varie : ``niveau`` = la mesure
    ``comptage.niveau_tension_constate`` (``mt`` ajoute le supplément MT,
    CIQ660 ; ``bt``, ``inconnu`` ou ``None`` servent le socle) ; ``type_lead``
    (``commercial`` → catégorie ``site_commerce`` requise, tout autre type
    renseigné → facultative, ``None`` → absente) et ``locataire`` (ajoute la
    pièce « accord du propriétaire », CIQ651)."""
    if (gabarit or GABARIT_TOITURE) != GABARIT_CI:
        return _PAR_GABARIT.get(gabarit or GABARIT_TOITURE, CATEGORIES)
    commerce = None
    if type_lead:
        commerce = 'requise' if type_lead == 'commercial' else 'facultative'
    mt = niveau == 'mt'
    if commerce is None and not mt:
        return CATEGORIES_CI
    return _variante_ci(commerce, mt, locataire)


def categorie(code, gabarit=GABARIT_TOITURE, **contexte):
    """La catégorie ``code`` du ``gabarit``, ou ``None``."""
    for cat in categories(gabarit, **contexte):
        if cat['categorie'] == code:
            return cat
    return None


def slots(gabarit=GABARIT_TOITURE, **contexte):
    """Tous les slots photo du ``gabarit``, à plat, avec leur catégorie."""
    plats = []
    for cat in categories(gabarit, **contexte):
        for slot in cat['slots']:
            plats.append(dict(slot, categorie=cat['categorie']))
    return plats


#: Tout ce que le gabarit ``ci`` peut servir (libellé d'une photo quelle que
#: soit la visite).
_CONTEXTE_CI_COMPLET = {'niveau': 'mt', 'type_lead': 'commercial',
                        'locataire': True}


def slot(code, gabarit=None):
    """Le slot photo ``code`` (avec sa catégorie), ou ``None``.

    ``gabarit=None`` cherche dans TOUS les gabarits (libellé d'une photo
    quelle que soit la visite) ; sinon dans celui-là seulement."""
    gabarits = ([gabarit] if gabarit else list(_PAR_GABARIT))
    for nom in gabarits:
        contexte = _CONTEXTE_CI_COMPLET if nom == GABARIT_CI else {}
        for item in slots(nom, **contexte):
            if item['code'] == code:
                return item
    return None


def codes_slots(gabarit=GABARIT_TOITURE, **contexte):
    """L'ensemble des codes de slot du ``gabarit`` (garde d'upload VT2)."""
    return {item['code'] for item in slots(gabarit, **contexte)}


def mesures(categorie_code, gabarit=GABARIT_TOITURE, **contexte):
    """Les mesures déclarées pour ``categorie_code`` (liste, jamais None)."""
    cat = categorie(categorie_code, gabarit, **contexte)
    return list(cat['mesures']) if cat else []


def mesure(categorie_code, code, gabarit=GABARIT_TOITURE, **contexte):
    """La déclaration de la mesure ``code`` dans sa catégorie, ou ``None``."""
    for champ in mesures(categorie_code, gabarit, **contexte):
        if champ['code'] == code:
            return champ
    return None


def mesure_requise(champ, valeurs):
    """La mesure ``champ`` est-elle exigée compte tenu des ``valeurs`` saisies ?

    ``sauf_si`` dispense une mesure quand un autre champ de la même catégorie
    est vrai (seul cas aujourd'hui : la pente d'un TOIT PLAT n'existe pas).
    Aucune autre conditionnalité — et surtout aucun seuil de jugement.
    """
    lie = champ.get('requis_si')
    if lie and (valeurs or {}).get(lie) not in (None, ''):
        # CIQ660 — exigée dès que l'autre champ est saisi (un cos φ exige sa
        # source), même si elle n'est pas requise par ailleurs.
        return True
    if not champ.get('requis'):
        return False
    dispense = champ.get('sauf_si')
    if dispense and bool((valeurs or {}).get(dispense)):
        return False
    return True


#: CIQ603 — UN seul vocabulaire de type de toiture entre la visite et le lead :
#: code de couverture de la visite → code ``Lead.TypeToiture``. Aucun code
#: renommé, aucune donnée migrée : la table traduit à la lecture (relevé
#: déclaré/constaté CIQ606, remontée au lead CIQ607). Un code ajouté d'un seul
#: côté fait échouer ``test_ciq603_vocabulaire_toiture``.
CORRESPONDANCE_TOITURE_LEAD = {
    'tuile': 'tuiles',
    'tole': 'tole_metal',
    'bac_acier': 'bac_acier',
    'beton': 'terrasse_beton',
    'fibrociment': 'fibrociment',
    'autre': 'autre',
}


def toiture_lead_depuis_visite(code):
    """Le code ``Lead.TypeToiture`` qui correspond au code de couverture
    ``code`` de la visite, ou ``None`` si le code est inconnu."""
    return CORRESPONDANCE_TOITURE_LEAD.get(code)


def toiture_visite_depuis_lead(code):
    """Le code de couverture de la visite qui correspond au code
    ``Lead.TypeToiture`` ``code`` (table réciproque), ou ``None``."""
    for visite, lead in CORRESPONDANCE_TOITURE_LEAD.items():
        if lead == code:
            return visite
    return None


#: CIQ601 — clé, DANS ``mesures[categorie]``, de l'état « non relevé » :
#: ``{clé_de_mesure: motif}``. Réservée au gabarit ``ci``.
CLE_NON_RELEVES = '_non_releves'

#: CIQ601 — motifs FERMÉS (contrat ``non_releves_motifs``) et leur libellé
#: lisible dans le récap : « non vérifié (<libellé>) ».
MOTIFS_NON_RELEVE = {
    'acces_refuse': 'accès refusé',
    'dangereux': 'dangereux',
    'site_ferme': 'site fermé',
    'a_faire_par_electricien': 'à faire par un électricien',
    'non_applicable': 'non applicable',
}

_CLE_NON_RELEVE = re.compile(
    r'^([a-z0-9_]+)(?:\[([^\]]+)\])?(?:\.([a-z0-9_]+))?$')


def decouper_cle_non_releve(cle):
    """``(mesure, id_element, champ)`` d'une clé « non relevé », ou ``None``.

    ``calibre_a`` → ``('calibre_a', None, None)`` ;
    ``trajets.longueur_dc_m`` → ``('trajets', None, 'longueur_dc_m')`` ;
    ``zones_toiture[z1].pente_deg`` → ``('zones_toiture', 'z1', 'pente_deg')``.
    """
    trouve = _CLE_NON_RELEVE.match(cle or '')
    return trouve.groups() if trouve else None


def libelle_cle_non_releve(connus, cle):
    """Le libellé lisible de la clé « non relevé » ``cle`` d'après les mesures
    ``connus`` (``{code: déclaration}``), ou ``None`` si la clé est inconnue."""
    morceaux = decouper_cle_non_releve(cle)
    if morceaux is None:
        return None
    mesure_code, ident, champ = morceaux
    declaration = connus.get(mesure_code)
    if declaration is None:
        return None
    if ident is None and champ is None:
        return declaration['libelle']
    if declaration['nature'] != LISTE:
        return None
    sous = {s['code']: s for s in declaration['forme']}
    if champ is None or champ not in sous:
        return None
    return f"{declaration['libelle']} — {sous[champ]['libelle']}"


def etat_obsolete(cle, propres):
    """Une valeur vient-elle d'être saisie (``propres`` = valeurs validées de
    CET enregistrement) pour la clé « non relevé » ``cle`` ? Alors l'état est
    effacé : la mesure a été relevée."""
    morceaux = decouper_cle_non_releve(cle)
    if morceaux is None:
        return False
    mesure_code, ident, champ = morceaux
    if mesure_code not in propres:
        return False
    valeur = propres[mesure_code]
    if champ is None:
        return valeur not in (None, '', [])
    for element in valeur or []:
        if ident is not None and element.get('id') != ident:
            continue
        if element.get(champ) not in (None, ''):
            return True
    return False


def liste_manquants(champ, elements):
    """CIQ600 — ce qui manque dans une mesure ``LISTE`` : liste de
    ``(code, libelle)``. Une liste vide manque en bloc quand elle est requise ;
    sinon chaque champ requis d'un élément, puis la règle ``au_moins_un``
    (au moins un élément porte chacun des champs cités)."""
    elements = [el for el in (elements or []) if isinstance(el, dict)]
    manque = []
    if not elements:
        if champ.get('requis'):
            manque.append((champ['code'], champ['libelle']))
        return manque
    for index, element in enumerate(elements, start=1):
        repere = element.get('id') or str(index)
        nom = element.get('libelle') or f'élément {index}'
        for sous in champ['forme']:
            valeur = element.get(sous['code'])
            vide = valeur is None or valeur == ''
            exigee = bool(sous.get('requis'))
            # ``requis_si`` : exigé seulement quand l'autre champ est saisi
            # (une charge déclarée exige sa pièce).
            lie = sous.get('requis_si')
            if lie and element.get(lie) not in (None, ''):
                exigee = True
            if exigee and vide:
                manque.append((
                    f"{champ['code']}[{repere}].{sous['code']}",
                    f"{champ['libelle']} — {nom} : {sous['libelle']}"))
        groupes = champ.get('un_groupe_parmi')
        if groupes and not any(
                all(element.get(code) not in (None, '') for code in groupe)
                for groupe in groupes):
            manque.append((
                f"{champ['code']}[{repere}].{groupes[0][0]}",
                f"{champ['libelle']} — {nom} : surface utile (ou longueur "
                'et largeur)'))
    formes = {sous['code']: sous for sous in champ['forme']}
    for code in champ.get('au_moins_un') or []:
        if not any(el.get(code) not in (None, '') for el in elements):
            manque.append((
                f"{champ['code']}.{code}",
                f"{champ['libelle']} : {formes[code]['libelle']} "
                '(au moins un trajet)'))
    return manque
