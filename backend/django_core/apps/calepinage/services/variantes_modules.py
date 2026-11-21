"""ACAL594 — une variante par MODULE du stock, sur la même implantation.

Le service reproduit CÔTÉ SERVEUR ce que l'atelier écrit quand on change le
module de chaque pan (``roofPro11/moduleSelect.ts::ecrireModulesDansDocument``)
: ``modules[]``, ``zones[].geometry.moduleId``, ``zones[].geometry.kwc``,
``result.kwc`` et ``panelWatt``. Les positions des panneaux sont conservées ;
aucune production ni aucun kWc n'est recopié de la conception d'origine ;
aucune simulation n'est lancée (variante non simulée : résultat vide).

Un module dont les cotes (longueur × largeur) diffèrent de celles du module de
chaque pan rend le pavage faux : la variante est nommée « … — à re-poser » et
se refait dans l'atelier. Un pan qui ne désigne aucun module n'a pas de cotes
connues : on ne devine pas, la variante est « à re-poser ».
"""
from __future__ import annotations

import copy

from .io_layout import module_du_pan
from .modules_stock import (
    PREFIXE_ID, modules_disponibles_du_calepinage,
)
from .variantes import VarianteRefusee, creer_variante

SUFFIXE_A_REPOSER = ' — à re-poser'

__all__ = ['variante_pour_module', 'creer_variantes_par_module']


def _cotes(entree):
    if not isinstance(entree, dict):
        return None
    return entree.get('longueurMm'), entree.get('largeurMm')


def variante_pour_module(layout, module):
    """``(nouveau_layout, a_repaver)`` — ``layout`` copié, jamais modifié.

    ``module`` est une entrée ``modules[]`` complète (cotes et puissance).
    """
    document = copy.deepcopy(layout)
    a_repaver = False
    total_kwc = 0.0
    for zone in document.get('zones') or []:
        geometrie = zone.get('geometry') if isinstance(zone, dict) else None
        if not isinstance(geometrie, dict):
            continue
        actuel = module_du_pan(layout, zone)
        if _cotes(actuel) != _cotes(module) or actuel is None:
            a_repaver = True
        geometrie['moduleId'] = module['id']
        nombre = geometrie.get('count')
        if isinstance(nombre, (int, float)) and not isinstance(nombre, bool):
            geometrie['kwc'] = nombre * module['pmaxWc'] / 1000
            total_kwc += geometrie['kwc']
    document['modules'] = [dict(module)]
    document['panelWatt'] = module['pmaxWc']
    resultat = document.get('result')
    if isinstance(resultat, dict):
        resultat['kwc'] = total_kwc
        # Production d'une AUTRE puissance de module : jamais recopiée.
        resultat.pop('annualKwh', None)
    return document, a_repaver


def creer_variantes_par_module(calepinage, identifiants, produits, *,
                               user=None):
    """Crée une variante par module demandé ; tout ou rien.

    Args:
        identifiants: liste d'``id`` de module (``produit-<pk>``).
        produits: les produits module de la société (``produits_modules_qs``).

    Returns:
        ``[{'variante': CalepinageVariante, 'a_repaver': bool}]``.

    Raises:
        VarianteRefusee: ``modules`` nommé (fiche incomplète ou inconnue).
    """
    from django.db import transaction

    from .verrou import verifier_ecriture_autorisee

    verifier_ecriture_autorisee(calepinage, champ='variante')
    if (not isinstance(identifiants, list) or not identifiants
            or any(not isinstance(i, str) for i in identifiants)):
        raise VarianteRefusee(
            "« modules » est la liste des modules à comparer, chacun de la "
            f"forme « {PREFIXE_ID}<numéro> ».", champ='modules')
    layout = getattr(calepinage, 'roof_layout', None)
    if not isinstance(layout, dict) or not any(
            isinstance(z, dict) and isinstance(z.get('geometry'), dict)
            for z in layout.get('zones') or []):
        raise VarianteRefusee(
            "Ce calepinage n'a encore aucun pan dessiné : tracez la "
            "conception avant de comparer des modules.", champ='modules',
            etat=True)
    servis = {
        entree['module']['id']: entree
        for entree in modules_disponibles_du_calepinage(
            calepinage, produits)['modules']}
    choisis = []
    for identifiant in dict.fromkeys(identifiants):
        entree = servis.get(identifiant)
        if entree is None:
            raise VarianteRefusee(
                f"« {identifiant} » n'est pas un module du catalogue de la "
                "société.", champ='modules')
        if not entree['selectionnable']:
            raise VarianteRefusee(
                f"« {entree['module']['libelle']} » : {entree['motif']}",
                champ='modules')
        choisis.append(entree['module'])

    creees = []
    with transaction.atomic():
        for module in choisis:
            document, a_repaver = variante_pour_module(layout, module)
            nom = f"Module {module['libelle']}" + (
                SUFFIXE_A_REPOSER if a_repaver else '')
            variante = creer_variante(
                calepinage, nom=nom, roof_layout=document, user=user)
            creees.append({'variante': variante, 'a_repaver': a_repaver})
    return creees
