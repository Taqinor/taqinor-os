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

# Natures de mesure acceptées (validation champ par champ côté API VT2).
NOMBRE = 'nombre'
BOOLEEN = 'booleen'
TEXTE = 'texte'
CHOIX = 'choix'

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

#: AGR412 — les gabarits de visite (``VisiteTerrain.gabarit``).
GABARIT_TOITURE = 'toiture'
GABARIT_POINT_EAU = 'point_eau'
_PAR_GABARIT = {
    GABARIT_TOITURE: CATEGORIES,
    GABARIT_POINT_EAU: CATEGORIES_POINT_EAU,
}


def categories(gabarit=GABARIT_TOITURE):
    """Les catégories du ``gabarit``, dans l'ordre du wizard (toiture par
    défaut : un gabarit inconnu retombe sur la checklist historique)."""
    return _PAR_GABARIT.get(gabarit or GABARIT_TOITURE, CATEGORIES)


def categorie(code, gabarit=GABARIT_TOITURE):
    """La catégorie ``code`` du ``gabarit``, ou ``None``."""
    for cat in categories(gabarit):
        if cat['categorie'] == code:
            return cat
    return None


def slots(gabarit=GABARIT_TOITURE):
    """Tous les slots photo du ``gabarit``, à plat, avec leur catégorie."""
    plats = []
    for cat in categories(gabarit):
        for slot in cat['slots']:
            plats.append(dict(slot, categorie=cat['categorie']))
    return plats


def slot(code, gabarit=None):
    """Le slot photo ``code`` (avec sa catégorie), ou ``None``.

    ``gabarit=None`` cherche dans TOUS les gabarits (libellé d'une photo
    quelle que soit la visite) ; sinon dans celui-là seulement."""
    gabarits = ([gabarit] if gabarit else list(_PAR_GABARIT))
    for nom in gabarits:
        for item in slots(nom):
            if item['code'] == code:
                return item
    return None


def codes_slots(gabarit=GABARIT_TOITURE):
    """L'ensemble des codes de slot du ``gabarit`` (garde d'upload VT2)."""
    return {item['code'] for item in slots(gabarit)}


def mesures(categorie_code, gabarit=GABARIT_TOITURE):
    """Les mesures déclarées pour ``categorie_code`` (liste, jamais None)."""
    cat = categorie(categorie_code, gabarit)
    return list(cat['mesures']) if cat else []


def mesure(categorie_code, code, gabarit=GABARIT_TOITURE):
    """La déclaration de la mesure ``code`` dans sa catégorie, ou ``None``."""
    for champ in mesures(categorie_code, gabarit):
        if champ['code'] == code:
            return champ
    return None


def mesure_requise(champ, valeurs):
    """La mesure ``champ`` est-elle exigée compte tenu des ``valeurs`` saisies ?

    ``sauf_si`` dispense une mesure quand un autre champ de la même catégorie
    est vrai (seul cas aujourd'hui : la pente d'un TOIT PLAT n'existe pas).
    Aucune autre conditionnalité — et surtout aucun seuil de jugement.
    """
    if not champ.get('requis'):
        return False
    dispense = champ.get('sauf_si')
    if dispense and bool((valeurs or {}).get(dispense)):
        return False
    return True
