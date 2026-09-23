"""CALX307 — la SOCIÉTÉ choisit les sections incluses dans ses rapports.

Le constat
==========
``ParametresCalepinage`` porte déjà les réglages du module (gabarits de
disposition, dégagements, zones types, presets — CAL45 et ses extensions)
mais aucun réglage DOCUMENTAIRE : le rapport d'étude (CALX297) imprime
toujours les neuf sections déclarées par ``rapport_etude.json`` (CALX292),
comme la note de calcul imprimait ses six sections EN DUR
(``note_calcul.py:473-506``). Parité : PV*SOL (les chapitres du rapport se
cochent dans un arbre) et PVsyst (« Report options »).

Le schéma, et où il vit
========================
``ParametresCalepinage.documents`` est une section JSON comme les onze
autres, mais RANGÉE PAR CODE DE DOCUMENT : ``{code_document: {sections:
[codes], langue: null}}``. Aujourd'hui seul ``rapport_etude``
(``services.rapport.CODE_DOCUMENT`` == ``parametres_cles.CODE_RAPPORT_ETUDE``)
y range quelque chose ; un futur document du module (note de calcul,
présentation compacte…) range sa PROPRE configuration sous SON code, dans
cette MÊME section — jamais un nouveau champ par document.

L'ÉQUIVALENCE EST LA RÈGLE (D12)
=================================
Un réglage ABSENT — société jamais passée par l'écran, ``documents`` vide,
ou ``sections`` valant ``null`` — produit EXACTEMENT le rapport
d'aujourd'hui : ``sections_retenues`` rend alors ``None``, et
``construire_rapport(calepinage, sections=None)`` imprime TOUTES les
sections déclarées, dans l'ordre du contrat — c'est son comportement PAR
DÉFAUT, inchangé. Aucune société existante ne voit son rapport bouger tant
qu'elle n'a rien décoché.

DEUX REFUS, TOUJOURS EN NOMMANT LE FAUTIF
==========================================
* un code qui n'existe pas dans ``rapport_etude.json`` — la même règle que
  ``services.rapport._codes_retenus`` applique déjà à une sélection passée
  en argument (``sections=``) ; ici, à une sélection LUE en base ;
* le retrait d'une section ``obligatoire`` du contrat (la garde, le site,
  le système, la chaîne de pertes, la production, le régime de preuve,
  l'annexe des hypothèses) — CE refus est NOUVEAU : ``construire_rapport``
  ne l'impose pas lui-même (un appelant peut lui demander un
  sous-ensemble ad hoc, par ex. un aperçu partiel), mais la SÉLECTION
  PERSISTÉE D'UNE SOCIÉTÉ ne peut pas amputer le rapport de ce que le
  contrat juge indispensable.

``valider_selection`` lève ``services.rapport.RapportRefuse`` — l'EXACTE
exception que ``views/documents.py`` sait déjà convertir en 400 nommant le
champ (``except RapportRefuse as refus: Response({refus.champ: ...})``) :
brancher ce module sur l'endpoint n'ouvrira pas un second vocabulaire
d'erreur. ``ParametresCalepinage.clean()`` la capture et la reformule en
``ValidationError`` Django, pour que l'écriture normale des réglages
(``services/parametres.enregistrer_parametres`` → ``full_clean``) la
refuse au même titre que les onze autres sections.

Crochet posé pour le fold (M4)
===============================
Ce module ne branche RIEN lui-même : ``views/documents.py`` (deux lanes y
travaillent) doit encore lire
``sections_retenues(parametres_de_societe_brute(calepinage.company))``
et le passer à ``rendre_rapport(calepinage, sections=…)`` pour que le choix
de la société soit RENDU — voir le rapport de lane pour le détail.
"""
from __future__ import annotations

from . import RapportRefuse, sections_declarees
from ..parametres_cles import CODE_RAPPORT_ETUDE

__all__ = ['configuration_document', 'valider_selection', 'sections_retenues']


def configuration_document(parametres, *, code=CODE_RAPPORT_ETUDE):
    """La configuration BRUTE ``{sections, langue}`` de ``code``, ou ``{}``.

    Une LECTURE PURE : ``parametres`` est un ``ParametresCalepinage`` (ou
    toute donnée qui porte un attribut ``documents`` — une société sans
    réglage passe ``None``, aucune valeur n'est fabriquée). Rien n'est
    validé ici ; ``sections_retenues`` s'en charge.
    """
    documents = getattr(parametres, 'documents', None) if parametres \
        is not None else None
    documents = documents if isinstance(documents, dict) else {}
    config = documents.get(code)
    return config if isinstance(config, dict) else {}


def valider_selection(codes, *, declarees=None):
    """``codes`` VALIDÉS contre le contrat, dans l'ordre du contrat.

    Args:
        codes: les codes DEMANDÉS (une liste — l'appelant a déjà vérifié
            qu'il s'agit bien d'une liste, ``sections_retenues`` le fait).
        declarees: ``sections_declarees()`` par défaut — passable pour les
            essais purs.

    Raises:
        RapportRefuse: un code inconnu (``champ='sections'``, le(s) code(s)
            inconnu(s) nommé(s)), ou une section ``obligatoire`` retirée
            (``champ`` = le premier code obligatoire manquant).
    """
    declarees = declarees if declarees is not None else sections_declarees()
    connus = {section['code'] for section in declarees}
    demandes = [str(code) for code in codes or ()]

    inconnus = [code for code in demandes if code not in connus]
    if inconnus:
        codes_connus = ', '.join(section['code'] for section in declarees)
        raise RapportRefuse(
            "Section(s) de rapport inconnue(s) : %s — sections déclarées : "
            "%s." % (', '.join(inconnus), codes_connus), champ='sections')

    retenus = set(demandes)
    manquantes = [
        section['code'] for section in declarees
        if section.get('obligatoire') and section['code'] not in retenus]
    if manquantes:
        raise RapportRefuse(
            "Section(s) obligatoire(s) retirée(s) du rapport : %s — une "
            "section obligatoire du contrat ne peut pas être décochée."
            % ', '.join(manquantes), champ=manquantes[0])

    # L'ORDRE du contrat prime, comme ``services.rapport._codes_retenus`` :
    # une société qui coche ``['pertes', 'garde']`` reçoit un rapport où la
    # garde précède quand même les pertes.
    return [section['code'] for section in declarees
            if section['code'] in retenus]


def sections_retenues(parametres, *, code=CODE_RAPPORT_ETUDE, declarees=None):
    """Les codes à imprimer pour ``parametres``, ou ``None`` (D12).

    ``None`` se passe TEL QUEL à ``construire_rapport(sections=…)`` : c'est
    sa valeur par défaut, donc le rapport d'aujourd'hui, octet pour octet.

    Raises:
        RapportRefuse: ``sections`` saisi n'est pas une liste, un code est
            inconnu, ou une section obligatoire a été décochée
            (``valider_selection``).
    """
    config = configuration_document(parametres, code=code)
    codes = config.get('sections')
    if codes is None:
        return None
    if not isinstance(codes, list):
        raise RapportRefuse(
            "Le réglage « sections » du document « %s » doit être une "
            "liste de codes (reçu : %s)." % (code, type(codes).__name__),
            champ='sections')
    return valider_selection(codes, declarees=declarees)
