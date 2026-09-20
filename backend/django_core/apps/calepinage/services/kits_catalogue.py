"""CAL198/CAL246 + SOLMVP15 — le catalogue des kits de pose, PROPRE au module.

D'OÙ IL VIENT
-------------
Le catalogue vivait dans une table du module d'appels d'offres
(``KitCalepinage``, AOF26), que l'atelier LISAIT par le seul ``selectors.py`` de
cette app. Ce module-là sort du produit : sa table part avec lui. Le catalogue,
lui, RESTE — c'est une capacité de l'atelier (l'écran « Bibliothèque », le kit de
pose de ``services/kits.py``, la clé ``kits`` de
``GET /api/django/calepinage/parametres/``), et une capacité de l'atelier ne
disparaît pas parce qu'une autre app s'en va.

OÙ IL VIT MAINTENANT, ET POURQUOI LÀ
------------------------------------
Dans la section ``presets`` des réglages société (``ParametresCalepinage``,
CAL45), sous la clé ``kits`` — exactement comme les jeux MAISON de
``services/presets.py`` vivent sous ``presets.jeux``. C'est un document de
réglage, pas une nouvelle table : **aucune migration**, aucun modèle, aucun
champ (les sections SONT des colonnes : en ajouter une aurait été une
migration). L'écriture passe par le SEUL chemin d'écriture du domaine
(``PUT /calepinage/parametres/`` → ``services.parametres.enregistrer_parametres``
sur la section ``presets``) ; il n'y a donc toujours qu'un chemin d'écriture.

ATTENTION, UNE FOIS POUR TOUTES : ``enregistrer_parametres`` remplace la
SECTION fournie, pas la clé. Un écrivain de la section ``presets`` doit donc
RELIRE la section et n'en changer que sa clé — c'est ce que fait
``services/presets._section`` pour ``jeux``, et ce que tout futur écrivain de
``kits`` doit faire. Écrire ``{'presets': {'kits': …}}`` seul effacerait les
jeux maison, et l'inverse effacerait le catalogue.

LA FORME PUBLIÉE NE BOUGE PAS D'UN CHAMP
----------------------------------------
Les lignes rendues portent les MÊMES clés, dans le même ordre, que celles que
l'atelier recevait avant (contrat committé ``contract_samples/
parametres_calepinage.json``) : ``id, code, libelle, mode, modules_par_kit,
pas_rangee_m, longueur_pente_m, faitage_m, emprise_transversale_m,
puissance_module_w, inclinaison_deg, orientation_modules, actif, produit_id,
produit_archive``. L'écran n'a rien à réapprendre.

AUCUNE VALEUR INVENTÉE
----------------------
Un champ de géométrie absent est publié ``None`` et NOMMÉ comme absent — jamais
un ``0`` qui se lirait comme une mesure, jamais la cote d'un autre kit (c'est
exactement le défaut que CAL169 avait fondu). Un ``produit_id`` qui pointe un
produit ARCHIVÉ est SIGNALÉ (``produit_archive``), jamais silencieusement ignoré :
le kit reste utilisable, l'écran décide quoi en faire — comportement d'avant,
strictement préservé.
"""
from __future__ import annotations

#: Clé, DANS la section ``presets``, qui porte le catalogue de kits de pose.
CLE_KITS = 'kits'

#: Les clés publiées, dans l'ordre du contrat. Une ligne rendue les porte
#: TOUTES — une clé absente serait une forme que l'écran devrait deviner.
CHAMPS_PUBLIES = (
    'id', 'code', 'libelle', 'mode', 'modules_par_kit', 'pas_rangee_m',
    'longueur_pente_m', 'faitage_m', 'emprise_transversale_m',
    'puissance_module_w', 'inclinaison_deg', 'orientation_modules', 'actif',
    'produit_id', 'produit_archive',
)

#: Les cotes en mètres : publiées en ``float``, ou ``None`` si absentes.
_CHAMPS_METRES = ('pas_rangee_m', 'longueur_pente_m', 'faitage_m',
                  'emprise_transversale_m', 'inclinaison_deg')

#: Les comptes entiers : publiés en ``int``, ou ``None`` si absents.
_CHAMPS_ENTIERS = ('modules_par_kit', 'puissance_module_w')

__all__ = ['CLE_KITS', 'CHAMPS_PUBLIES', 'kits_de_societe']


def _flottant(valeur):
    """``float`` du réglage, ou ``None`` — jamais un défaut."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _entier(valeur):
    """``int`` du réglage, ou ``None`` — jamais un défaut."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _texte(valeur):
    return valeur.strip() if isinstance(valeur, str) else ''


def kits_de_societe(company, *, actifs_seulement=True):
    """Le catalogue des kits de pose de ``company``, lecture PURE.

    Args:
        company: la société — jamais lue d'un corps de requête. ``None`` rend
            une liste VIDE (jamais « tous les kits »).
        actifs_seulement: ne rend que les kits ``actif`` (défaut). Le
            constructeur de kit de pose, lui, lit AUSSI les inactifs : un kit
            désactivé après qu'un calepinage l'a utilisé doit rester lisible.

    Returns:
        ``[{id, code, libelle, …, produit_id, produit_archive}, …]``, triées
        par ``code`` — l'ordre d'avant.
    """
    from ..selectors import parametres_de_societe

    if company is None:
        return []
    presets = parametres_de_societe(company).get('presets') or {}
    brut = presets.get(CLE_KITS)
    if not isinstance(brut, list):
        return []

    lignes = []
    for regle in brut:
        if not isinstance(regle, dict):
            continue
        ligne = {
            'id': regle.get('id'),
            'code': _texte(regle.get('code')),
            'libelle': _texte(regle.get('libelle')),
            'mode': _texte(regle.get('mode')),
            'orientation_modules': _texte(regle.get('orientation_modules')),
            'actif': bool(regle.get('actif', True)),
            'produit_id': regle.get('produit_id') or None,
            'produit_archive': False,
        }
        for champ in _CHAMPS_METRES:
            ligne[champ] = _flottant(regle.get(champ))
        for champ in _CHAMPS_ENTIERS:
            ligne[champ] = _entier(regle.get(champ))
        if actifs_seulement and not ligne['actif']:
            continue
        lignes.append({champ: ligne[champ] for champ in CHAMPS_PUBLIES})

    _marquer_produits_archives(company, lignes)
    lignes.sort(key=lambda ligne: ligne['code'])
    return lignes


def _marquer_produits_archives(company, lignes):
    """``produit_archive`` résolu sur le catalogue stock — SIGNALÉ, jamais tu.

    Un ``produit_id`` introuvable dans la société laisse ``produit_archive``
    faux : on ne prétend pas qu'un produit absent est archivé (ce serait
    affirmer quelque chose qu'on ne sait pas).
    """
    from apps.stock.selectors import get_produit_scoped

    for ligne in lignes:
        if not ligne['produit_id']:
            continue
        produit = get_produit_scoped(company, ligne['produit_id'])
        if produit is None:
            continue
        ligne['produit_archive'] = bool(getattr(produit, 'is_archived', False))
