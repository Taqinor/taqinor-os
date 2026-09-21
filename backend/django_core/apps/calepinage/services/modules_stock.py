"""CALX109 — les MODULES que la société peut réellement poser, avec leurs cotes.

LE CONSTAT
----------
L'atelier 3D ne connaît qu'UN module, écrit en dur avec ses cotes
(``apps/web/src/lib/roofPro2.ts`` : 2,384 × 1,303 × 0,033 m, 720 W) et
propagé dans tout le pavage (``apps/web/src/lib/estimatorBrainV2.ts``). Côté
serveur, les vraies cotes existent pourtant déjà : la fiche technique d'un
produit ``module`` porte ``longueur_mm``, ``largeur_mm``, ``epaisseur_mm``,
``poids_kg`` et ``pmax_wc`` (PV5, CAL111-114), lisibles par le sélecteur
cross-app ``apps.stock.selectors.dimensions_de_pose`` (CAL119) — un
sous-ensemble de ``specs_for_produit``, restreint à ce qu'une POSE demande.

CE QUE CE SERVICE PRODUIT
--------------------------
Le catalogue des modules de la société, DANS LA FORME DU DOCUMENT : chaque
entrée ``module`` est exactement une entrée ``modules[]`` du schéma v2
(``$defs/moduleDocument``, CALX82) — ``id``, ``produitId``, ``libelle``,
``longueurMm``, ``largeurMm``, ``epaisseurMm``, ``poidsKg``, ``pmaxWc``,
``source``. L'atelier écrit donc ce bloc TEL QUEL dans le document, sans
traduire de clés en chemin : c'est ce qui empêche deux graphies d'une même
cote d'apparaître (la faute que ``contract_samples/`` existe pour prévenir).

LA COMPLÉTUDE VOYAGE À CÔTÉ, PAS DEDANS
-----------------------------------------
``selectionnable`` et ``champs_manquants`` accompagnent l'entrée sans entrer
dans le document : ils décrivent la FICHE, pas le module. Une fiche à laquelle
il manque une cote de pavage est LISTÉE — le commercial doit voir qu'elle
existe et pourquoi elle est grisée — mais elle n'est PAS sélectionnable, et le
motif NOMME les champs manquants en français. Aucune cote n'est déduite d'une
autre, aucune puissance déduite d'une surface, aucun repli sur le module
d'hier : « non renseigné » n'est pas « zéro » (D-CALX 7).

AUCUN PRIX, AUCUNE MARGE
-------------------------
``dimensions_de_pose`` ne lit que la fiche technique — jamais
``Produit.prix_achat`` : ce service ne peut structurellement pas publier un
prix. Le calepinage ne calcule d'ailleurs jamais d'argent (D-CALX 5).
"""
from __future__ import annotations

from apps.stock.selectors import dimensions_de_pose

#: Les cotes SANS LESQUELLES on ne sait pas paver : longueur et largeur (la
#: maille), puissance unitaire (le kWc du pan). L'épaisseur et le poids sont
#: utiles au rendu 3D et au lestage, jamais au nombre de modules — leur absence
#: ne grise donc pas la fiche.
CHAMPS_REQUIS = ('longueurMm', 'largeurMm', 'pmaxWc')

#: Le nom FRANÇAIS de chaque champ, tel qu'il s'affiche dans le motif d'une
#: fiche incomplète — un commercial doit lire ce qui manque sur SA fiche
#: produit, pas un identifiant de champ.
LIBELLES_CHAMPS = {
    'longueurMm': 'la longueur (mm)',
    'largeurMm': 'la largeur (mm)',
    'epaisseurMm': "l'épaisseur (mm)",
    'poidsKg': 'le poids (kg)',
    'pmaxWc': 'la puissance crête (Wc)',
}

#: La provenance publiée pour toute entrée construite ici. Obligatoire au
#: schéma (CALX82) : sans elle, deux modèles renseignés par deux chemins
#: différents ne sont pas comparables.
SOURCE_FICHE = 'fiche produit'

#: Le préfixe de l'``id`` d'un module DANS le document. Stable pour un produit
#: donné : rouvrir un calepinage retrouve le même identifiant, donc les pans
#: qui le citent (``zones[].geometry.moduleId``) restent valides.
PREFIXE_ID = 'produit-'

#: Ce que dit la porte quand la société n'a aucune fiche module exploitable.
MOTIF_AUCUNE_FICHE = (
    "Aucune fiche technique « module » n'existe dans le catalogue de cette "
    'société : ajoutez le panneau au stock et renseignez sa fiche '
    '(longueur, largeur, puissance crête) pour pouvoir le calepiner.')

#: Ce que dit la porte quand des fiches existent mais qu'aucune n'est complète.
MOTIF_AUCUNE_COMPLETE = (
    "Aucune fiche « module » du catalogue ne porte les cotes nécessaires au "
    'calepinage : complétez la longueur, la largeur et la puissance crête sur '
    'la fiche technique du panneau.')

__all__ = ['CHAMPS_REQUIS', 'LIBELLES_CHAMPS', 'SOURCE_FICHE', 'PREFIXE_ID',
           'modules_disponibles_du_calepinage']


def _nombre(valeur):
    """Un ``float`` JSON-sûr, ou ``None`` — jamais un ``Decimal`` sérialisé.

    Une cote non finie (``NaN``/infini, qu'une importation bancale peut poser)
    vaut ``None`` : le schéma v2 exige un nombre strictement positif, et une
    valeur illisible est une valeur NON RENSEIGNÉE, jamais une valeur corrigée.
    """
    if valeur is None:
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        return None
    return nombre if nombre > 0 else None


def _identifiant_module(produit_id):
    """L'``id`` STABLE d'un module du catalogue dans le document (CALX82)."""
    return '%s%s' % (PREFIXE_ID, produit_id)


def _libelle(produit):
    """Le libellé FRANÇAIS affiché dans le sélecteur — jamais vide."""
    nom = (getattr(produit, 'nom', '') or '').strip()
    if nom:
        return nom
    return 'Module %s' % getattr(produit, 'pk', '')


def _entree_module(produit):
    """Une entrée ``{module, selectionnable, champs_manquants, motif}``.

    ``module`` est une entrée ``modules[]`` du schéma v2, prête à écrire dans
    le document. Chaque cote vaut sa valeur de fiche ou ``None`` — jamais une
    dimension standard supposée. Lecture PURE : aucun accès base au-delà de
    l'attribut ``fiche_technique`` déjà résolu par le sélecteur.
    """
    cotes = dimensions_de_pose(produit)
    module = {
        'id': _identifiant_module(getattr(produit, 'pk', None)),
        'produitId': getattr(produit, 'pk', None),
        'libelle': _libelle(produit),
        'longueurMm': _nombre(cotes.get('longueur_mm')),
        'largeurMm': _nombre(cotes.get('largeur_mm')),
        'epaisseurMm': _nombre(cotes.get('epaisseur_mm')),
        'poidsKg': _nombre(cotes.get('poids_kg')),
        'pmaxWc': _nombre(cotes.get('puissance_wc')),
        'source': SOURCE_FICHE,
    }
    manquants = [champ for champ in CHAMPS_REQUIS if module[champ] is None]
    motif = None
    if manquants:
        motif = ('Fiche incomplète : %s %s renseignée%s sur la fiche '
                 'technique de ce produit. Complétez-la pour pouvoir le '
                 'calepiner.' % (
                     ', '.join(LIBELLES_CHAMPS[champ] for champ in manquants),
                     "n'est pas" if len(manquants) == 1 else 'ne sont pas',
                     '' if len(manquants) == 1 else 's'))
    return {
        'module': module,
        'selectionnable': not manquants,
        'champs_manquants': manquants,
        'motif': motif,
    }


def modules_disponibles_du_calepinage(calepinage, produits):
    """CALX109 — le contrat ``calepinage_modules_disponibles.json`` COMPLET.

    ``produits`` est l'itérable des produits MODULE de la société, servi par
    ``apps.stock.selectors.produits_modules_qs`` (la vue le passe ; ce service
    ne requête rien, ce qui le rend appelable SANS base). Toujours les quatre
    mêmes clés — un écran qui reçoit parfois quatre clés et parfois deux finit
    par tester l'absence (leçon PACT10).

    ``motif_liste_vide`` vaut ``None`` dès qu'un module est sélectionnable ; il
    NOMME sinon ce qui manque, et l'atelier affiche CE motif-là — il n'en
    invente aucun et ne retombe sur aucun module par défaut en silence.
    """
    entrees = [_entree_module(produit) for produit in (produits or [])]
    selectionnables = [entree for entree in entrees if entree['selectionnable']]
    if selectionnables:
        motif = None
    elif entrees:
        motif = MOTIF_AUCUNE_COMPLETE
    else:
        motif = MOTIF_AUCUNE_FICHE
    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'modules': entrees,
        'champs_requis': list(CHAMPS_REQUIS),
        'motif_liste_vide': motif,
    }
