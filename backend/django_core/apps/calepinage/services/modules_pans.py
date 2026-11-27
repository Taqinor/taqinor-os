"""Module posé sur chaque pan (ACAL264 / ACAL358 / ACAL359).

Sorti de ``electrique.py`` (fichier mur : il ne grossit plus). Aucune écriture,
aucune lecture cross-app ici hors ``apps.ventes.services.pans_du_document``.
"""
from __future__ import annotations


def produits_des_pans(document, materiel):
    """ACAL264/358 — les ``produit_id`` posés qui DIFFÈRENT du défaut."""
    from apps.ventes.services import pans_du_document

    defaut = ((materiel or {}).get('produits') or {}).get('module')
    produits = []
    for pan in pans_du_document(document):
        produit_id = pan.get('produit_id')
        if (produit_id in (None, '') or int(pan.get('modules') or 0) <= 0
                or str(produit_id) == str(defaut)
                or produit_id in produits):
            continue
        produits.append(produit_id)
    return produits


def produits_sans_fiche(company, document, materiel, fiches):
    """ACAL358 — un produit désigné sans fiche résolue (introuvable ou d'une
    autre société) : son pan est chaîné avec le défaut, et l'alerte le dit."""
    if company is None or not isinstance(document, dict):
        return ()
    return tuple(p for p in produits_des_pans(document, materiel)
                 if p not in (fiches or {}))


def modules_par_pan_servis(calepinage, materiel, resolu, fiches, manquants,
                           nombre):
    """ACAL359 — le module RÉELLEMENT posé sur chaque pan (relu à chaque GET,
    jamais persisté) ; mêmes règles que l'alerte d'ACAL358."""
    from .chaines import modules_par_pan

    module = materiel.get('module') or {}
    defaut = {'produit_id': module.get('produit_id'),
              'designation': module.get('designation'),
              'pmax_wc': nombre((resolu.get('module') or {}).get('pmax_wc')),
              'fiche_complete': module.get('fiche_complete')}
    return modules_par_pan(
        getattr(calepinage, 'roof_layout', None), defaut, fiches, manquants)


def _produit_du_module_pose(document, *, sans_existants=False):
    """T4-B4-007 — le ``produit_id`` du module CHOISI à l'étape Panneaux : celui
    qui couvre le PLUS de modules posés (``geometry.moduleId`` →
    ``modules[].produitId``), ou ``None`` (aucun pan posé avec un produit du
    catalogue). Lecture pure ; rien n'est supposé. ``sans_existants``
    (D-ACAL-169) écarte les pans « existant » (ACAL573) ; FAUX par défaut :
    les autres appelants lisent ce qu'ils lisaient."""
    from apps.ventes.services import pans_du_document

    comptes = {}
    for pan in pans_du_document(document):
        produit_id = pan.get('produit_id')
        modules = int(pan.get('modules') or 0)
        if sans_existants and pan.get('existant'):
            continue
        if produit_id in (None, '') or modules <= 0:
            continue
        comptes[produit_id] = comptes.get(produit_id, 0) + modules
    if not comptes:
        return None
    return max(comptes, key=lambda cle: comptes[cle])


#: T4-B4-007 — provenance du module CHOISI à l'étape Panneaux (posé sur les pans),
#: quand ni désignation explicite ni ligne de devis n'existe (ACAL56 :
#: ``electrique.PROVENANCE_EXPLICITE`` / ``PROVENANCE_DEVIS`` sont les deux autres).
PROVENANCE_POSE = 'pose'


def repli_materiel(role, du_devis, calepinage):
    """T4-B4-007 — ``(identifiant, provenance)`` d'un rôle sans désignation
    explicite : la ligne du devis lié (``'devis'``), sinon — pour le module
    seulement — le module posé à l'étape Panneaux (``'pose'``), sinon
    ``(None, 'devis')`` (le rôle est absent, comme avant)."""
    identifiant = (du_devis or {}).get(role)
    if identifiant in (None, '') and role == 'module':
        pose = _produit_du_module_pose(getattr(calepinage, 'roof_layout', None))
        if pose is not None:
            return pose, PROVENANCE_POSE
    return identifiant, 'devis'


def _module_pose_de_la_planche(conception, materiel, document):
    """ACAL1910 + R7-N2 — ``{designation[, pmax_wc]}`` du module POSÉ dominant
    (``simulation._fiche_du_module_pose``) à porter sur le module de la planche
    (``conception.entree.module``), ou ``{}`` (rien à changer : aucun pan d'un
    autre produit, module posé = défaut, ou nom identique).

    Défaut du 26/11 : la planche nommait le 715 W posé mais imprimait « n × 710 Wc »,
    la puissance du défaut. La puissance suit désormais le NOM — même fiche — sauf
    quand un pan posé SANS module (``pan.module`` absent) prendrait la puissance du
    défaut dans ``chaines.bloc_pose`` : la ligne d'aujourd'hui y est gardée, comme
    quand la fiche posée ne publie pas de puissance. Lecture pure ; ``materiel``
    (d'où se calculent les empreintes) n'est jamais modifié."""
    from .simulation import _fiche_du_module_pose

    fiches = (materiel or {}).get('fiches_modules') or {}
    if not fiches:
        return {}
    pose = _fiche_du_module_pose(materiel, document)
    nom = next((str(f.get('designation') or '') for f in fiches.values()
                if isinstance(f, dict) and dict(f.get('specs') or {}) == dict(pose)), '')
    if not nom or nom == conception.entree.module.designation:
        return {}
    champs = {'designation': nom}
    try:
        puissance = float((pose or {}).get('pmax_wc'))
    except (TypeError, ValueError):
        return champs
    pans = getattr(conception, 'pans', None) or ()
    if puissance > 0 and all(getattr(getattr(pan, 'module', None), 'pmax_wc', None)
                             for pan in pans if int(getattr(pan, 'modules', 0) or 0) > 0):
        champs['pmax_wc'] = puissance
    return champs
