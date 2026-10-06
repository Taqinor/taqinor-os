"""ACAL259 — UN SEUL « modules posés / kWc » pour les livrables et écrans
du module (constats C-ACAL-118, C-ACAL-035).

Le constat
==========
Dix lecteurs comptaient le MÊME document chacun à sa façon : la
présentation compacte sommait ``geometry.kwc`` (le wattage de l'OUTIL,
720 W, pas la fiche du module), le journal ne lisait que ``result.panels``
(un champ au sol de 340 modules y valait « inconnu »), l'export de projet
ne lisait que ``geometry.count``, le comparatif de projets lisait le résumé
de l'atelier… Sur le calepinage QA-CAL-RT, le pack technique imprimait
36 modules / 25,56 kWc à un endroit et 30 / 21,6 à un autre.

La règle
========
:func:`mesures_du_document` est LA lecture, adossée aux deux primitives :

* le COMPTE est celui de ``ventes.pans_du_document`` (D08-T16, ACAL61) —
  pans de toit ET surfaces de pose ; ``neededPanels`` n'est jamais un compte
  posé (un pan non pavé vaut 0, avec son motif « non pavé ») ; un document
  dont AUCUN pan de toit n'est mesuré lit le résumé racine ``result``
  (même règle que ``ventes.lire_layout``, jamais additionné aux zones) ;
* le kWc est ``modules × pmax de la FICHE du module du pan`` — celui que
  publie ``chaines.bloc_pose`` (fiche du stock) dans le bloc ``pose`` du
  résultat servi quand il décrit CE document (même compte) ; à défaut, la
  fiche que le document déclare (``modules[].pmaxWc``, ``moduleWc`` d'une
  surface). JAMAIS ``panelWatt`` (wattage de l'outil) ni ``geometry.kwc`` :
  sans fiche connue, le kWc vaut ``None`` — jamais un nombre deviné.

Aucune écriture, aucune requête : lecture PURE.
"""
from __future__ import annotations

from .valeurs import nombre as _nombre

__all__ = ['MOTIF_NON_PAVE', 'mesures_du_document']

#: Le motif d'un pan dessiné mais non pavé (repris de ``pans_du_document``).
MOTIF_NON_PAVE = 'non pavé'

_CLES_COMPTE_RACINE = ('panels', 'count', 'nb_panneaux')


def _dict(valeur):
    return valeur if isinstance(valeur, dict) else {}


def _entier(valeur):
    nombre = _nombre(valeur)
    if nombre is None or nombre < 0:
        return None
    return int(round(nombre))


def _kwc_de_fiche(modules, puissance_wc):
    puissance = _nombre(puissance_wc)
    if not modules or not puissance or puissance <= 0:
        return None
    return round(modules * puissance / 1000.0, 3)


def _compte_racine(layout):
    racine = _dict(layout.get('result'))
    for cle in _CLES_COMPTE_RACINE:
        compte = _entier(racine.get(cle))
        if compte is not None:
            return compte
    return None


def _pose_du_resultat(resultat):
    """Le bloc ``pose`` (``chaines.bloc_pose``) du résultat, ou ``{}``."""
    return _dict(_dict(resultat).get('pose'))


def mesures_du_document(layout, resultat=None):
    """LE compte « modules posés / kWc » d'un document de pose.

    Args:
        layout: le document ``roof_layout`` v2 (``None`` accepté).
        resultat: le résultat SERVI (``selectors.resultat_servi`` /
            ``electrique.resultat_calepinage``) ou stocké — seul son bloc
            ``pose`` est lu, et SEULEMENT s'il décrit ce document (même
            compte de modules) ; ``None`` pour une lecture du document seul.

    Returns:
        ``{'modules', 'kwc', 'nombre_pans', 'pans'}`` — ``modules`` vaut
        ``None`` quand ni le document ni le résultat ne disent rien (jamais
        un 0 supposé) ; ``pans`` = ``[{pan, kind, modules, kwc, azimut_deg,
        inclinaison_deg, motif}]`` dans l'ordre du document, pans non pavés
        compris (0 module, ``kwc`` ``None``, motif « non pavé »).
    """
    from apps.ventes.services import pans_du_document

    layout = _dict(layout)
    pose = _pose_du_resultat(resultat)
    pans = []
    for pan in pans_du_document(layout):
        modules = int(pan.get('modules') or 0)
        pans.append({
            'pan': str(pan.get('libelle')),
            'kind': pan.get('kind') or 'toit',
            'modules': modules,
            # La fiche que le DOCUMENT déclare — jamais panelWatt ni
            # geometry.kwc (le wattage de l'outil).
            'kwc': _kwc_de_fiche(modules, pan.get('module_wc')),
            'azimut_deg': _nombre(pan.get('azimut_deg')),
            'inclinaison_deg': _nombre(pan.get('inclinaison_deg')),
            'motif': (MOTIF_NON_PAVE if modules <= 0 else ''),
            '_mesure': pan.get('source') != 'aucune',
        })

    toit = [p for p in pans if p['kind'] == 'toit']
    surfaces = [p for p in pans if p['kind'] != 'toit']
    toit_mesure = any(p['_mesure'] for p in toit)
    if toit_mesure:
        compte_toit = sum(p['modules'] for p in toit)
        kwc_toit = _somme_connue([p for p in toit if p['modules'] > 0])
    else:
        # Aucun pan de toit mesuré : le résumé racine (le toit seul), jamais
        # additionné aux zones — même règle que ``ventes.lire_layout``.
        compte_toit = _compte_racine(layout)
        kwc_toit = (_nombre(_dict(layout.get('result')).get('kwc'))
                    if compte_toit else None)
        if compte_toit == 0:
            kwc_toit = None
    compte_surfaces = sum(p['modules'] for p in surfaces)
    kwc_surfaces = _somme_connue([p for p in surfaces if p['modules'] > 0])

    if compte_toit is None and not surfaces:
        modules = None
    else:
        modules = (compte_toit or 0) + compte_surfaces

    if modules is not None and modules > 0:
        parts = []
        if compte_toit:
            parts.append(kwc_toit)
        if compte_surfaces:
            parts.append(kwc_surfaces)
        kwc = (round(sum(parts), 3)
               if parts and all(part is not None for part in parts) else None)
    else:
        kwc = None

    # Le bloc ``pose`` du résultat — la FICHE DU STOCK (``bloc_pose``) — fait
    # foi quand il décrit CE document : même compte de modules.
    total_pose = _entier(pose.get('total_modules'))
    if modules is None and total_pose is not None:
        modules = total_pose
    if total_pose is not None and total_pose == modules:
        kwc_pose = _nombre(pose.get('kwc'))
        if kwc_pose is not None:
            kwc = kwc_pose
        _kwc_par_pan_de_la_pose(pans, pose)

    for pan in pans:
        pan.pop('_mesure', None)
    return {
        'modules': modules,
        'kwc': kwc if modules else None,
        'nombre_pans': len(pans),
        'pans': pans,
    }


def _somme_connue(pans):
    """La somme des kWc des pans PAVÉS, ``None`` si l'un n'a pas de fiche."""
    if not pans:
        return None
    valeurs = [p['kwc'] for p in pans]
    if any(valeur is None for valeur in valeurs):
        return None
    return round(sum(valeurs), 3)


def _kwc_par_pan_de_la_pose(pans, pose):
    """Les kWc PAR PAN de ``bloc_pose`` — ses pans sont les pans PAVÉS du
    document, dans le même ordre (``chaines.pans_poses``) ; repris seulement
    quand chaque compte concorde."""
    lignes = [ligne for ligne in pose.get('pans') or ()
              if isinstance(ligne, dict)]
    paves = [pan for pan in pans if pan['modules'] > 0]
    if len(lignes) != len(paves):
        return
    for pan, ligne in zip(paves, lignes):
        if _entier(ligne.get('modules')) != pan['modules']:
            return
    for pan, ligne in zip(paves, lignes):
        kwc = _nombre(ligne.get('kwc'))
        if kwc is not None:
            pan['kwc'] = kwc
