"""Module posé sur chaque pan (ACAL264 / ACAL358 / ACAL359).

Sorti de ``electrique.py`` (fichier mur : il ne grossit plus). Aucune écriture,
aucune lecture cross-app ici hors ``apps.ventes.services.pans_du_document`` et —
R7-N2 — ``apps.stock.selectors.get_produit_scoped`` (le module posé existe-t-il au
catalogue de la société ?).
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


def _comptes_des_modules_poses(document, *, sans_existants=False):
    """``{produit_id: modules posés}`` des pans posés avec un produit du catalogue
    (ordre des pans du document). ``sans_existants`` écarte les pans « existant »
    (ACAL573, jamais pavés par l'atelier). Lecture pure."""
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
    return comptes


def _produit_du_module_pose(document, *, sans_existants=False):
    """T4-B4-007 — le ``produit_id`` du module CHOISI à l'étape Panneaux : celui
    qui couvre le PLUS de modules posés (``geometry.moduleId`` →
    ``modules[].produitId``), ou ``None`` (aucun pan posé avec un produit du
    catalogue). Lecture pure ; rien n'est supposé. ``sans_existants``
    (D-ACAL-169) écarte les pans « existant » (ACAL573) ; FAUX par défaut :
    les autres appelants lisent ce qu'ils lisaient."""
    comptes = _comptes_des_modules_poses(document, sans_existants=sans_existants)
    if not comptes:
        return None
    return max(comptes, key=lambda cle: comptes[cle])


#: T4-B4-007 — provenance du module CHOISI à l'étape Panneaux (posé sur les pans),
#: quand ni désignation explicite ni ligne de devis n'existe (ACAL56 :
#: ``electrique.PROVENANCE_EXPLICITE`` / ``PROVENANCE_DEVIS`` sont les deux autres).
PROVENANCE_POSE = 'pose'


def _module_pose_qui_prime(document, conception, company=None):
    """R7-N2 (module posé) — le module POSÉ qui remplace celui de la ``conception``
    dans le calcul électrique, ou ``None`` (la conception garde la main).

    Le module posé = celui qui couvre le plus de modules des pans posés, pans
    « existant » écartés (même règle que ``suivi_module_pose``). ``None`` quand :
    rien n'est posé ; le module de la conception est posé et couvre AUTANT de
    modules que le premier (égalité : la conception, comme ``simulation._module_pose``
    garde le défaut) ; le module posé est introuvable au catalogue de ``company``
    (alerte ACAL358 « chaîné avec le défaut » inchangée). Toit MIXTE : le module
    dominant est le module du calcul, chaque pan d'un autre produit garde sa
    propre fiche (ACAL264, ``fiches_modules``)."""
    comptes = _comptes_des_modules_poses(document, sans_existants=True)
    if not comptes:
        return None
    dominant = max(comptes, key=lambda cle: comptes[cle])
    if conception not in (None, '') and any(
            str(cle) == str(conception) and nombre == comptes[dominant]
            for cle, nombre in comptes.items()):
        return None
    if company is not None:
        from apps.stock.selectors import get_produit_scoped

        try:
            if get_produit_scoped(company, dominant) is None:
                return None
        except (TypeError, ValueError):
            return None
    return dominant


def repli_materiel(role, du_devis, calepinage, *, company=None):
    """T4-B4-007 / R7-N2 — ``(identifiant, provenance)`` d'un rôle sans désignation
    explicite. Module : le module POSÉ sur le toit d'abord (``'pose'``,
    :func:`_module_pose_qui_prime` — « ce qui est posé est la vérité du
    calepinage »), sinon celui de la conception (``'devis'``, rendu ``'moteur'`` par
    l'appelant), sinon le module posé sur un pan « existant » (règle d'avant), sinon
    ``(None, 'devis')`` (absent). Autres rôles : la conception, inchangé."""
    identifiant = (du_devis or {}).get(role)
    if role != 'module':
        return identifiant, 'devis'
    document = getattr(calepinage, 'roof_layout', None)
    pose = _module_pose_qui_prime(document, identifiant, company)
    if pose is None and identifiant in (None, ''):
        pose = _produit_du_module_pose(document)
    if pose is not None:
        return pose, PROVENANCE_POSE
    return identifiant, 'devis'
