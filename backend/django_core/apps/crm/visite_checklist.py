"""VT1 — LA définition CODE de la checklist de visite technique terrain.

Source de vérité UNIQUE des catégories, des slots photo et des mesures
attendues. Le contrat partagé ``apps/crm/contract_samples/visite_terrain.json``
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


def categories():
    """Les catégories déclarées, dans l'ordre du wizard."""
    return CATEGORIES


def categorie(code):
    """La catégorie ``code``, ou ``None``."""
    for cat in CATEGORIES:
        if cat['categorie'] == code:
            return cat
    return None


def slots():
    """Tous les slots photo, à plat, avec leur catégorie."""
    plats = []
    for cat in CATEGORIES:
        for slot in cat['slots']:
            plats.append(dict(slot, categorie=cat['categorie']))
    return plats


def slot(code):
    """Le slot photo ``code`` (avec sa catégorie), ou ``None``."""
    for item in slots():
        if item['code'] == code:
            return item
    return None


def codes_slots():
    """L'ensemble des codes de slot connus (garde d'upload VT2)."""
    return {item['code'] for item in slots()}


def mesures(categorie_code):
    """Les mesures déclarées pour ``categorie_code`` (liste, jamais None)."""
    cat = categorie(categorie_code)
    return list(cat['mesures']) if cat else []


def mesure(categorie_code, code):
    """La déclaration de la mesure ``code`` dans sa catégorie, ou ``None``."""
    for champ in mesures(categorie_code):
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
