"""D-ACAL-169 (point 3) — l'entrée électrique SUIT le module posé sur le toit.

Défaut vu le 26/11 : l'entrée stockée portait un module 710 W
(``entree_electrique.module_produit``) alors que tous les pans posaient des
715 W ; l'étape Électrique, le contrôle des chaînes et le schéma calculaient
avec un panneau absent du toit, et le moteur du lead recevait ce 710 W imposé
(``ventes.conception.porte_calepinage.designations_du_calepinage``).

LA RÈGLE (enregistrement d'une conception qui a CHANGÉ, même transaction) :
une désignation ``module_produit`` posée sur AUCUN pan qui porte des modules,
alors qu'un module du catalogue est posé, est remplacée par le module posé
dominant (``modules_pans._produit_du_module_pose``, la règle existante) ; le
chatter le dit. Restent intacts : un module encore posé sur un pan (toit
mixte), un toit sans module posé, un pan posé sans produit du catalogue (la
désignation y est le module par défaut, ``chaines.bloc_pose``), une entrée sans
désignation (la lecture prend déjà le module posé).

Les LECTURES ne changent pas : un calepinage enregistré garde son panneau
jusqu'à son prochain enregistrement de conception (D-ACAL-169 point 4 :
« rien d'existant n'est recalculé »). Les calepinages concernés se LISTENT en
lecture seule (:func:`_lister_calepinages_au_module_divergent`).

Sorti de ``electrique.py`` et ``layout.py`` (le premier est un fichier mur).
"""
from __future__ import annotations

#: La phrase du chatter — celle de la décision D-ACAL-169, mot pour mot.
PHRASE_SUIVI = ("Le module de l'étape Électrique suivait « %s » ; il suit "
                "maintenant « %s », posé sur le toit.")


def _module_a_suivre(document, entree):
    """Le ``produit_id`` qui doit remplacer la désignation stockée, ou ``None``.

    Lecture pure (aucune base) : ``document`` = la conception (``roof_layout``),
    ``entree`` = l'entrée électrique stockée."""
    from apps.ventes.services import pans_du_document

    from .modules_pans import _produit_du_module_pose

    stocke = entree.get('module_produit') if isinstance(entree, dict) else None
    if stocke in (None, ''):
        return None
    # Un pan « existant » (ACAL573) n'est jamais pavé par l'atelier : il ne
    # porte pas le module de l'étape Électrique et ne compte pas ici.
    poses = [pan for pan in pans_du_document(document)
             if int(pan.get('modules') or 0) > 0 and not pan.get('existant')]
    if not poses or any(pan.get('produit_id') in (None, '') for pan in poses):
        return None
    if any(str(pan.get('produit_id')) == str(stocke) for pan in poses):
        return None
    return _produit_du_module_pose(document, sans_existants=True)


def _produit(company, identifiant):
    from apps.stock.selectors import get_produit_scoped

    try:
        return get_produit_scoped(company, identifiant)
    except (TypeError, ValueError):
        return None


def suivre_le_module_pose(calepinage, document, *, user=None):
    """Appelé par ``layout.enregistrer_layout`` DANS sa transaction, pour une
    conception qui a changé. Rend ``{'ancien', 'nouveau'}`` quand l'entrée a
    suivi, sinon ``None`` (rien n'est écrit). Un module posé introuvable dans le
    catalogue de la société ne remplace rien."""
    from .electrique import CLE_ENTREE, _designation
    from .journal import journaliser_module_suivi
    from .resultat import modifier_resultat

    resultat = getattr(calepinage, 'resultat', None)
    entree = resultat.get(CLE_ENTREE) if isinstance(resultat, dict) else None
    identifiant = _module_a_suivre(document, entree)
    if identifiant is None:
        return None
    company = getattr(calepinage, 'company', None)
    produit = _produit(company, identifiant)
    if produit is None:
        return None
    ancien = entree.get('module_produit')

    def _suivre(frais):
        courante = dict(frais.get(CLE_ENTREE) or {})
        if courante.get('module_produit') != ancien:
            return None  # désignation changée entre-temps : la saisie gagne
        courante['module_produit'] = produit.pk
        frais[CLE_ENTREE] = courante
        return produit.pk

    if modifier_resultat(calepinage, _suivre) is None:
        return None
    nom_ancien = _designation(_produit(company, ancien)) or '#%s' % ancien
    nom_nouveau = _designation(produit) or '#%s' % produit.pk
    journaliser_module_suivi(calepinage, ancien=nom_ancien, nouveau=nom_nouveau,
                             phrase=PHRASE_SUIVI % (nom_ancien, nom_nouveau),
                             user=user)
    return {'ancien': ancien, 'nouveau': produit.pk}


def _lister_calepinages_au_module_divergent(lignes):
    """Lecture seule (D-ACAL-169) — les ``id`` des calepinages dont la
    désignation stockée ne suit pas le toit. ``lignes`` = itérable de
    ``(id, roof_layout, resultat)`` ; aucune donnée client n'est rendue.

    Invocation (``manage.py shell``, rien n'est écrit) ::

        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.suivi_module_pose import (
            _lister_calepinages_au_module_divergent as lister)
        print(lister(Calepinage.objects.values_list(
            'pk', 'roof_layout', 'resultat').iterator()))
    """
    from .electrique import CLE_ENTREE

    concernes = []
    for pk, document, resultat in lignes:
        entree = resultat.get(CLE_ENTREE) if isinstance(resultat, dict) else None
        if _module_a_suivre(document, entree) is not None:
            concernes.append(pk)
    return concernes
