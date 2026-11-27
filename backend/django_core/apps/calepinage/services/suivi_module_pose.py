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
désignation y est le module par défaut, ``chaines.bloc_pose``).

R7-N2 (module posé, 26/11) — une entrée SANS désignation suit aussi : la lecture y
prend le module de la CONCEPTION du lead (``equipements.materiel_de_la_conception``)
avant le module posé ; quand ce module n'est posé sur AUCUN pan, l'enregistrement
écrit ``module_produit`` = le module posé dominant — seulement un produit ACTIF de
la société de famille « module » (``equipements._produit_actif``) — et le chatter
le dit (« suivait <module de la conception> »). Sans conception, rien n'est écrit
(la lecture prend déjà le module posé).

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


def _module_a_suivre(document, entree, conception=None):
    """Le ``produit_id`` qui doit remplacer la désignation stockée, ou ``None``.

    Lecture pure (aucune base) : ``document`` = la conception (``roof_layout``),
    ``entree`` = l'entrée électrique stockée. R7-N2 — ``conception`` = le
    ``produit_id`` du module de la conception du lead, que la lecture prend quand
    rien n'est stocké : il est jugé comme une désignation stockée."""
    from .equipements import pans_du_document
    from .modules_pans import _produit_du_module_pose

    stocke = entree.get('module_produit') if isinstance(entree, dict) else None
    if stocke in (None, ''):
        stocke = conception
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


def _module_de_la_conception(calepinage):
    """R7-N2 — le ``produit_id`` du module de la conception courante du lead (celui
    que la lecture prend sans désignation), ou ``None``."""
    from .equipements import materiel_de_la_conception

    return (materiel_de_la_conception(calepinage).get('produits') or {}).get('module')


def _module_actif(company, identifiant):
    """R7-N2 — ``identifiant`` s'il est un MODULE actif de ``company``, sinon ``None``."""
    from .equipements import _produit_actif

    try:
        return _produit_actif(company, int(identifiant), 'module')
    except (TypeError, ValueError):
        return None


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
    ancien = (entree or {}).get('module_produit') if isinstance(entree, dict) else None
    ancien = None if ancien in (None, '') else ancien
    conception = None if ancien is not None else _module_de_la_conception(calepinage)
    identifiant = _module_a_suivre(document, entree, conception)
    if identifiant is None:
        return None
    company = getattr(calepinage, 'company', None)
    if ancien is None and _module_actif(company, identifiant) is None:
        return None  # R7-N2 : jamais un produit archivé, d'une autre famille ou société
    produit = _produit(company, identifiant)
    if produit is None:
        return None

    def _suivre(frais):
        courante = dict(frais.get(CLE_ENTREE) or {})
        if (courante.get('module_produit') or None) != ancien:
            return None  # désignation changée entre-temps : la saisie gagne
        courante['module_produit'] = produit.pk
        frais[CLE_ENTREE] = courante
        return produit.pk

    if modifier_resultat(calepinage, _suivre) is None:
        return None
    suivi = ancien if ancien is not None else conception  # ce que l'étape Électrique suivait
    nom_ancien = _designation(_produit(company, suivi)) or '#%s' % suivi
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
