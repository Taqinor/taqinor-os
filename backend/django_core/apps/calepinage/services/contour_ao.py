"""CAL240 — reprendre dans un calepinage le contour d'une toiture d'AO.

LE CONSTAT
----------
La conversion ENU ↔ repère local métrique est écrite depuis CAL31
(``apps/ao/services.py``) mais elle n'avait AUCUN consommateur dans ce sens :
la promesse d'« import bidirectionnel » (décision D4) restait lettre morte.
CAL241 a ouvert le sens calepinage → AO ; ce service ouvre l'autre.

SEUL LE CONTOUR VOYAGE
-----------------------
On écrit ``roof_layout['outline']`` et RIEN d'autre : les pans dessinés
(``zones``), les obstacles, les zones d'exclusion, les mesures et la variante
retenue restent EXACTEMENT ce qu'ils étaient. Côté AO, rien n'est écrit du
tout — ce service ne fait que LIRE, par ``apps.ao.selectors`` (jamais
``apps.ao.models``, jamais ``apps.ao.services``).

L'ÉCRITURE PASSE PAR LE SERVICE DE CONCEPTION
----------------------------------------------
``services.layout.enregistrer_layout`` (CAL13) est le seul chemin d'écriture
d'une conception : il recalcule l'empreinte par la fonction du dépôt et
dépose une VERSION quand — et seulement quand — la conception a changé. Un
second import à l'identique ne pollue donc pas l'historique.

LES TROIS REFUS, TOUS EN FRANÇAIS ET TOUS NOMMÉS
--------------------------------------------------
* **404** — toiture (ou affaire) d'une AUTRE société, ou inexistante : elle
  est INTROUVABLE, jamais « interdite » (un 403 confirmerait son existence) ;
* **409** — affaire déposée ou close : le motif est celui du serveur AO
  (``selectors.raison_conception_figee``, source unique de la phrase), pas
  une reformulation ;
* **400** — toiture sans ancre géographique (le champ à renseigner est
  NOMMÉ), ou toiture sans contour relevé.
"""
from __future__ import annotations


class ContourAoRefuse(ValueError):
    """Refus métier : message français, champ fautif nommé, statut HTTP.

    ``statut`` voyage avec le refus pour que la vue n'ait pas à re-déduire si
    c'est un 400, un 404 ou un 409 — la règle est ici, une seule fois.
    """

    def __init__(self, message, *, champ='', statut=400):
        super().__init__(message)
        self.champ = champ
        self.statut = statut


def importer_contour_ao(calepinage, *, toiture_id=None, appel_offre_id=None,
                        user=None):
    """Recopie le contour d'une toiture AO dans la conception du calepinage.

    Args:
        calepinage: le pivot qui REÇOIT — sa société fait foi (elle est celle
            de l'appelant, posée côté serveur par le viewset).
        toiture_id: la toiture AO source. À défaut, ``appel_offre_id`` (ou
            l'affaire déjà rattachée au calepinage) désigne l'affaire dont on
            prend la toiture de référence.
        user: l'auteur du geste — posé côté serveur, jamais lu d'un corps.

    Returns:
        ``{'outline', 'toiture', 'appel_offre', 'code_document',
        'roof_layout', 'layout_hash', 'inchange', 'version'}``.

    Raises:
        ContourAoRefuse: source introuvable (404), affaire figée (409),
            toiture sans ancre ou sans contour (400).
    """
    from apps.ao import selectors as selectors_ao

    from .layout import LayoutRefuse, enregistrer_layout

    if calepinage is None or not getattr(calepinage, 'pk', None):
        raise ContourAoRefuse(
            "Le calepinage n'est pas encore enregistré : impossible d'y "
            "reprendre un contour.", champ='calepinage')

    affaire_id = appel_offre_id or getattr(calepinage, 'appel_offre_id', None)
    if not toiture_id and not affaire_id:
        raise ContourAoRefuse(
            "Aucune source indiquée : précisez la toiture (« toiture ») ou "
            "l'affaire (« appel_offre ») dont le contour doit être repris.",
            champ='toiture')

    lu = selectors_ao.contour_ao_a_reprendre(
        calepinage.company, toiture_id=toiture_id, appel_offre_id=affaire_id)
    if not lu['trouve']:
        raise ContourAoRefuse(
            "Cette toiture d'appel d'offres est introuvable.",
            champ='toiture', statut=404)
    if lu['raison_lecture_seule']:
        raise ContourAoRefuse(lu['raison_lecture_seule'], champ='appel_offre',
                              statut=409)
    if lu['refus']:
        # Le refus « sans ancre géographique » est déjà écrit côté AO et il
        # NOMME son champ : le retraduire ici ferait deux formulations de la
        # même règle.
        raise ContourAoRefuse(lu['refus'], champ=lu['champ'])

    outline = lu['outline'] or []
    if len(outline) < 3:
        raise ContourAoRefuse(
            "Cette toiture d'appel d'offres ne porte aucun contour relevé : "
            "relevez son enveloppe avant de la reprendre.",
            champ='contour_local_m')

    ancien = calepinage.roof_layout \
        if isinstance(calepinage.roof_layout, dict) else {}
    # Copie de surface : on repose la MÊME conception, avec son seul contour
    # remplacé. Muter le dict en place priverait CAL13 de l'ancien document.
    conception = dict(ancien)
    conception['outline'] = [[float(lat), float(lng)] for lat, lng in outline]

    try:
        resultat = enregistrer_layout(calepinage, conception, user=user)
    except LayoutRefuse as refus:
        raise ContourAoRefuse(str(refus), champ=refus.champ or 'roof_layout')

    _journaliser(calepinage, lu, user=user)
    version = resultat['version']
    return {
        'outline': conception['outline'],
        'toiture': lu['toiture'],
        'appel_offre': lu['appel_offre'],
        'code_document': lu['code_document'],
        'roof_layout': calepinage.roof_layout,
        'layout_hash': resultat['layout_hash'] or None,
        'inchange': resultat['inchange'],
        'version': version.pk if version is not None else None,
    }


def _journaliser(calepinage, lu, *, user=None):
    """CAL26 — le GESTE est journalisé, pas seulement son effet.

    ``enregistrer_layout`` journalise déjà le changement de conception (ancien
    → nouveau nombre de modules) : ce qu'il ne dit pas, c'est D'OÙ vient le
    contour. Sans cette ligne, un lecteur du chatter voit une conception
    modifiée sans savoir qu'elle a été REPRISE d'un dossier d'appel d'offres.
    Journaliser ne fait jamais échouer le geste (le journal avale ses erreurs).
    """
    from .journal import noter

    source = lu['code_document'] or lu['designation'] or lu['toiture']
    noter(calepinage,
          "Contour repris de la toiture d'appel d'offres « %s » "
          "(affaire n° %s). Seule la géométrie de contour a été reprise : "
          "obstacles, cotes, zones et variante retenue sont intacts."
          % (source, lu['appel_offre']),
          user=user)
