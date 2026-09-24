"""CALX312 — l'export JSON VERSIONNÉ du projet et de ses résultats.

Le constat
==========
``io_layout.exporter_layout`` rend ``{roof_layout, layout_hash,
schema_version}`` et RIEN d'autre : ni le site, ni les équipements retenus, ni
le ``resultat``, ni les pertes, ni les avertissements. Un bureau d'études qui
reçoit ce fichier ne peut pas refaire le calcul ailleurs. Parité : PV*SOL 2026
(export JSON des données de projet ET des résultats de simulation).

La forme : le contrat ``contract_samples/export_projet.json`` (CALX293)
=======================================================================
``{format_version, produit_le, calepinage, site, equipements, roof_layout,
layout_hash, version_moteur, resultat, pertes, avertissements, provenance,
postes_pertes, variantes}`` — QUATORZE clés au format 2 (CALX370), TOUJOURS
présentes. Chaque bloc est LU, rien n'est recalculé :

* ``calepinage`` — identifiant, titre, client (``apps.crm.selectors``, borné
  à la société du calepinage) ;
* ``site`` — ``selectors.contexte_geographique`` (adresse, ville, repère et
  sa SOURCE) plus l'altitude et le fuseau déjà publiés par le bloc ``meteo``
  du résultat servi (``meteo.point.altitude_m``, ``meteo.heure.fuseau_site``) ;
* ``equipements`` — les quatre familles de
  ``services/equipements.equipements_du_calepinage``, TELLES QUELLES ;
* ``roof_layout``/``layout_hash`` — ``io_layout.exporter_layout`` (le document
  TEL QUEL) ; ``version_moteur`` — celle STOCKÉE avec l'empreinte ;
* ``resultat`` — la réponse de ``GET resultat/``
  (``services/electrique.resultat_calepinage``, fraîcheur CALX70 comprise),
  SON empreinte (``hash_entree``, ``version_moteur``) comprise ;
* ``pertes`` — la MÊME liste plate que ``resultat.pertes``, à la racine ;
* ``avertissements`` — ceux du résultat servi, précédés du motif d'export ;
* ``provenance`` (CALX314) — ``[{libelle, valeur}]`` composé par
  ``provenance_document.lignes_de_provenance``, la fonction PARTAGÉE avec la
  feuille ``Provenance`` du XLSX et le calque ``PROVENANCE`` du DXF ;
* ``postes_pertes`` (CALX370) — les postes SAISIS (``Calepinage.pertes``),
  TELS QUELS : l'entrée de la simulation, que la réimportation restitue ;
* ``variantes`` (CALX370) — ``[{nom, retenue, roof_layout, layout_hash,
  resultat}]``, la retenue en tête (``selectors.variantes``).

La réimportation (``importer_projet``, CALX370) est l'inverse de ce fichier,
dans CE module : voir la section qui la porte, en fin de fichier.

``format_version`` est un ENTIER du fichier (``FORMAT_VERSION``), jamais dérivé
d'une date ni du ``schema_version`` du document de pose ; ``produit_le`` est
l'horodatage RÉEL de la génération, en UTC (``…Z``).

Discipline du null
==================
Un calepinage NON SIMULÉ exporte ``resultat: null`` (jamais ``{}``, jamais un
résultat à moitié rempli) et ``pertes: []`` ; l'altitude et le fuseau, qui
viennent de la simulation, valent ``null`` ; le MOTIF est la première ligne
d'``avertissements``. Toutes les clés restent présentes.

Aucun montant (D5)
==================
Le pare-feu de la note de calcul (``note_calcul._cle_interdite``) PLUS la
famille ``prix_*``/``cout_*``/``marge_*`` du contrat sont appliqués au document
AVANT sérialisation : une clé de coût fait REFUSER l'export en la NOMMANT. Les
seules clés « marge » admises sont les jeux GÉOMÉTRIQUES déjà exemptés par la
garde de surface CAL122 (``marges``, ``marge_troncon_min``,
``marge_bande_min``).
"""
from __future__ import annotations

import copy
import datetime
import math
from decimal import Decimal

__all__ = [
    'FORMAT_VERSION', 'CODE_DOCUMENT', 'CLES_DOCUMENT', 'CLES_SITE',
    'FAMILLES_EQUIPEMENT', 'MOTIF_SANS_CONCEPTION', 'MOTIF_NON_SIMULE',
    'ExportProjetRefuse', 'horodatage_utc', 'cle_de_montant',
    'verifier_aucun_montant', 'octets_de_projet', 'resultat_servi',
    'document_de_projet',
    # CALX370 — la réimportation.
    'FORMATS_IMPORTABLES', 'CLES_VARIANTE', 'BLOCS_REPRIS', 'BLOCS_IGNORES',
    'ImportProjetRefuse', 'importer_projet',
]

#: Le numéro de FORMAT de ce fichier — un entier, incrémenté à la main quand
#: un bloc s'ajoute ; jamais une date, jamais le ``schema_version`` du layout.
#: CALX370 — 2 : ``postes_pertes`` et ``variantes`` rejoignent le fichier (le
#: projet se RÉIMPORTE, il ne se lit plus seulement).
FORMAT_VERSION = 2

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'export_projet_json'

#: Les clés du contrat, dans l'ordre du fichier (``provenance`` : CALX314 ;
#: ``postes_pertes``/``variantes`` : CALX370, format 2).
CLES_DOCUMENT = ('format_version', 'produit_le', 'calepinage', 'site',
                 'equipements', 'roof_layout', 'layout_hash',
                 'version_moteur', 'resultat', 'pertes', 'avertissements',
                 'provenance', 'postes_pertes', 'variantes')

#: CALX370 — les clés d'une variante exportée, dans l'ordre du fichier.
CLES_VARIANTE = ('nom', 'retenue', 'roof_layout', 'layout_hash', 'resultat')

#: Les clés du bloc ``site``.
CLES_SITE = ('adresse', 'ville', 'pin', 'altitude_m', 'fuseau',
             'source_repere')

#: Les familles d'équipement exportées (``services/equipements.FAMILLES``).
FAMILLES_EQUIPEMENT = ('panneau', 'onduleur', 'batterie', 'optimiseur')

MOTIF_SANS_CONCEPTION = ("Aucune conception enregistrée : ce calepinage n'a "
                         "jamais été posé.")
MOTIF_NON_SIMULE = ("Aucune simulation servie pour cette conception : "
                    "« resultat » vaut null et « pertes » est vide — jamais un "
                    "résultat à moitié rempli.")

#: La famille de clés de montant nommée par le contrat CALX293.
PREFIXES_DE_MONTANT = ('prix_', 'cout_', 'marge_')
MOTS_NUS_DE_MONTANT = ('prix', 'cout', 'marge')

#: Les jeux GÉOMÉTRIQUES du moteur — exemptés PAR NOM EXACT (garde CAL122).
CLES_GEOMETRIQUES_EXEMPTEES = frozenset({
    'marges', 'marge_troncon_min', 'marge_bande_min',
})

#: Sentinelle « lire en base » — distingue « non fourni » de ``None``.
_LIRE = object()


class ExportProjetRefuse(ValueError):
    """L'export refuse de sortir, et il NOMME la donnée en cause."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def horodatage_utc(moment=None):
    """``'2026-09-23T10:00:00Z'`` — l'instant de production, en UTC.

    ``moment`` est fourni par l'appelant (rendu reproductible) ; à défaut,
    ``timezone.now()`` — un instant AWARE, jamais un constructeur naïf.
    """
    if moment is None:
        from django.utils import timezone

        moment = timezone.now()
    return moment.astimezone(datetime.timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%SZ')


# ── Le pare-feu de montants ─────────────────────────────────────────────────

def cle_de_montant(cle):
    """Vrai si ``cle`` nomme un montant — pare-feu de la note + contrat."""
    from .note_calcul import _cle_interdite

    texte = str(cle).lower()
    if texte in CLES_GEOMETRIQUES_EXEMPTEES:
        return False
    if _cle_interdite(cle):
        return True
    return (texte in MOTS_NUS_DE_MONTANT
            or any(texte.startswith(p) for p in PREFIXES_DE_MONTANT))


def _chemins(noeud, chemin, predicat):
    """Les chemins des clés (ou feuilles) qui satisfont ``predicat``."""
    trouves = []
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            complet = '%s.%s' % (chemin, cle) if chemin else str(cle)
            if predicat(cle, valeur):
                trouves.append(complet)
            trouves.extend(_chemins(valeur, complet, predicat))
    elif isinstance(noeud, (list, tuple)):
        for rang, valeur in enumerate(noeud):
            trouves.extend(_chemins(valeur, '%s[%d]' % (chemin, rang),
                                    predicat))
    return trouves


def verifier_aucun_montant(document):
    """Refuse un document qui porte une clé de montant — en la NOMMANT."""
    trouves = sorted(_chemins(document, '',
                              lambda cle, _valeur: cle_de_montant(cle)))
    if trouves:
        raise ExportProjetRefuse(
            "Export du projet refusé : le document porte des grandeurs de "
            "coût — %s. Aucun montant n'entre dans un document du "
            "calepinage." % ', '.join(trouves), champ=trouves[0])
    return document


def _non_fini(_cle, valeur):
    if isinstance(valeur, float):
        return not math.isfinite(valeur)
    if isinstance(valeur, Decimal):
        return not valeur.is_finite()
    return False


def octets_de_projet(document):
    """Le document en JSON STRICT (utf-8) — le rendu même de la vue.

    ``JSONRenderer`` de DRF (encodeur du dépôt, ``allow_nan=False``) : une
    valeur non finie fait REFUSER l'export en nommant son chemin, jamais un
    ``NaN`` qu'un lecteur JSON strict rejetterait.
    """
    from rest_framework.renderers import JSONRenderer

    try:
        return JSONRenderer().render(document)
    except ValueError as erreur:
        chemins = _chemins(document, '', _non_fini) or ['resultat']
        raise ExportProjetRefuse(
            "Export du projet refusé : une valeur non finie (NaN ou infini) "
            "ne s'écrit pas en JSON strict — %s." % ', '.join(chemins),
            champ=chemins[0]) from erreur


# ── Les blocs, LUS ──────────────────────────────────────────────────────────

def _texte(valeur):
    return str(valeur).strip() if valeur is not None else ''


def _bloc_calepinage(calepinage):
    """``{id, titre, client: {id, nom} | None}`` — le client LU au CRM."""
    client = None
    company = getattr(calepinage, 'company', None)
    client_id = getattr(calepinage, 'client_id', None)
    if company is not None and client_id:
        from apps.crm.selectors import client_label

        nom = client_label(company, client_id)
        if nom is not None:
            client = {'id': client_id, 'nom': nom}
    return {'id': getattr(calepinage, 'pk', None),
            'titre': _texte(getattr(calepinage, 'titre', '')),
            'client': client}


def _au_chemin(source, *cles):
    for cle in cles:
        if not isinstance(source, dict):
            return None
        source = source.get(cle)
    return source


def _bloc_site(contexte, resultat):
    """Le site : repère SOURCÉ, altitude et fuseau LUS dans la météo servie."""
    contexte = contexte if isinstance(contexte, dict) else {}
    meteo = (resultat or {}).get('meteo') if isinstance(resultat, dict) \
        else None
    return {
        'adresse': contexte.get('adresse'),
        'ville': contexte.get('ville'),
        'pin': copy.deepcopy(contexte.get('pin')),
        'altitude_m': _au_chemin(meteo, 'point', 'altitude_m'),
        'fuseau': _au_chemin(meteo, 'heure', 'fuseau_site'),
        'source_repere': contexte.get('source'),
    }


def _bloc_equipements(equipements):
    equipements = equipements if isinstance(equipements, dict) else {}
    return {famille: copy.deepcopy(equipements.get(famille))
            for famille in FAMILLES_EQUIPEMENT}


def resultat_servi(calepinage):
    """La réponse de ``GET resultat/`` — ou le refus, champ NOMMÉ."""
    from .electrique import TemperaturesInvalides, resultat_calepinage

    try:
        return resultat_calepinage(calepinage)
    except TemperaturesInvalides as refus:
        raise ExportProjetRefuse(
            str(refus), champ=getattr(refus, 'champ', '') or 'temperatures'
        ) from refus


def document_de_projet(calepinage, *, moment=None, resultat=_LIRE,
                       site=None, equipements=None):
    """Le document d'export, forme du contrat ``export_projet.json``.

    Args:
        calepinage: le pivot (borné société par la vue).
        moment: l'instant de production (``produit_le``) — ``now`` à défaut.
        resultat / site / equipements: déjà lus par l'appelant (essais sans
            base) — sinon LUS ici. ``resultat=None`` : aucun résultat servi.

    Raises:
        ExportProjetRefuse: une clé de montant, une valeur non finie, ou des
            températures illisibles — champ NOMMÉ.
    """
    from .. import selectors
    from .equipements import equipements_du_calepinage
    from .io_layout import exporter_layout
    from .provenance_document import lignes_de_provenance, lignes_json

    layout = exporter_layout(calepinage)
    avertissements = []
    if not layout['roof_layout']:
        # Rien n'a jamais été posé : rien à calculer, et on ne le calcule pas.
        servi = None
        avertissements.append(MOTIF_SANS_CONCEPTION)
    else:
        servi = resultat_servi(calepinage) if resultat is _LIRE else resultat
    simule = isinstance(servi, dict) and servi.get('simule') is True
    if layout['roof_layout'] and not simule:
        avertissements.append(MOTIF_NON_SIMULE)
    if isinstance(servi, dict):
        avertissements.extend(str(a) for a in servi.get('avertissements') or ()
                              if str(a).strip())

    if site is None:
        site = selectors.contexte_geographique(calepinage)
    if equipements is None:
        equipements = equipements_du_calepinage(calepinage)

    resultat_exporte = copy.deepcopy(servi) if simule else None
    pertes = (resultat_exporte or {}).get('pertes')
    document = {
        'format_version': FORMAT_VERSION,
        'produit_le': horodatage_utc(moment),
        'calepinage': _bloc_calepinage(calepinage),
        'site': _bloc_site(site, resultat_exporte),
        'equipements': _bloc_equipements(equipements),
        'roof_layout': copy.deepcopy(layout['roof_layout']) or None,
        'layout_hash': layout['layout_hash'] or None,
        'version_moteur': _texte(getattr(calepinage, 'version_moteur', ''))
        or None,
        'resultat': resultat_exporte,
        'pertes': copy.deepcopy(pertes) if isinstance(pertes, list) else [],
        'avertissements': avertissements,
        # CALX314 — LA composition partagée avec le XLSX et le DXF.
        'provenance': lignes_json(lignes_de_provenance(calepinage)),
        # CALX370 — ce que la RÉIMPORTATION restitue au-delà du document de
        # pose : les postes SAISIS (l'entrée de la simulation, ``pertes``
        # ci-dessus restant la liste SERVIE) et les variantes.
        'postes_pertes': _bloc_postes_pertes(calepinage),
        'variantes': _bloc_variantes(calepinage),
    }
    verifier_aucun_montant(document)
    octets_de_projet(document)  # JSON strict, ou refus nommé
    return document


# ── CALX370 — les blocs de la réimportation ─────────────────────────────────

def _bloc_postes_pertes(calepinage):
    """Les postes de pertes SAISIS (``Calepinage.pertes``, CAL139), TELS QUELS.

    Ils ont été validés à l'écriture (``services/pertes.enregistrer_pertes``)
    et le seront de nouveau à la réimportation : rien n'est normalisé ici.
    """
    postes = getattr(calepinage, 'pertes', None)
    return copy.deepcopy(postes) if isinstance(postes, list) else []


def _bloc_variantes(calepinage):
    """Les variantes du calepinage, la RETENUE en tête (``selectors``).

    Un pivot sans société (essais sans base) n'a aucune variante à lire.
    """
    from .. import selectors

    if getattr(calepinage, 'company', None) is None \
            or not getattr(calepinage, 'pk', None):
        return []
    lignes = []
    for variante in selectors.variantes(calepinage):
        resultat = getattr(variante, 'resultat', None)
        lignes.append({
            'nom': _texte(getattr(variante, 'nom', '')),
            'retenue': bool(getattr(variante, 'retenue', False)),
            'roof_layout': copy.deepcopy(getattr(variante, 'roof_layout',
                                                 None)),
            'layout_hash': getattr(variante, 'layout_hash', '') or None,
            'resultat': (copy.deepcopy(resultat)
                         if isinstance(resultat, dict) else None),
        })
    return lignes


# ═══════════════════════════════════════════════════════════════════════════
# CALX370 — RÉIMPORTER le fichier de projet
# ═══════════════════════════════════════════════════════════════════════════
#
# UN SEUL MODULE D'EXPORT, ET SON INVERSE ICI. Le fichier réimporté est celui
# que ``document_de_projet`` écrit (``GET export-projet.json/``, CALX312) :
# aucun second format, aucun second export. Le document de pose SEUL garde son
# propre aller-retour (``io_layout``, CAL216/CALX28) : cette réimportation ne
# le duplique pas, elle l'ENVELOPPE — chaque ``roof_layout`` du fichier passe
# par ``io_layout.valider_document``, et un refus NOMME son chemin complet
# (``roof_layout.zones.0.vertices``, ``variantes[1].roof_layout.…``).
#
# TOUT EST VALIDÉ AVANT LA PREMIÈRE ÉCRITURE (``_analyser_projet``, pur) ;
# l'écriture passe ensuite, dans UNE transaction, par les chemins uniques du
# module : ``services/creation.py`` (le pivot, rattaché à un lead ou un client
# de la société d'ARRIVÉE), ``services/layout.py::enregistrer_layout`` (le
# document, version et journal compris), ``services/pertes.enregistrer_pertes``
# et ``services/variantes.creer_variante``/``retenir_variante``.
#
# CE QUI N'EST JAMAIS REPRIS DU FICHIER : la société, l'auteur et tous les
# identifiants (calepinage, client, produits) — le serveur les REPOSE ; le
# ``resultat`` de simulation, les équipements, le site et la provenance — ils
# décrivent la société de DÉPART (son matériel, son stock) et la simulation se
# relance dans la société d'arrivée. Chaque bloc ignoré est NOMMÉ dans la
# réponse, avec son motif.

#: Les versions du fichier que cette réimportation sait relire. Une version
#: inconnue est REFUSÉE en la nommant — jamais « au mieux ».
FORMATS_IMPORTABLES = (1, 2)

#: Les blocs du fichier que la réimportation ÉCRIT.
BLOCS_REPRIS = ('roof_layout', 'postes_pertes', 'variantes')

#: Les blocs LUS mais jamais écrits, et pourquoi (réponse de l'import).
BLOCS_IGNORES = (
    ('resultat', "La simulation se relance dans la société d'arrivée : un "
                 'résultat calculé ailleurs ne décrit ni son matériel ni son '
                 'stock.'),
    ('equipements', "Les produits désignés appartiennent au catalogue de la "
                    "société de départ : choisissez-les dans le vôtre."),
    ('site', "Le repère du site est relu du lead ou du client de rattachement "
             '(et de l’épingle du document de pose).'),
    ('provenance', 'La provenance se recompose à chaque document produit.'),
    ('calepinage', 'Identifiants et client de la société de départ : le '
                   "serveur rattache le projet au lead ou au client indiqué."),
)

#: Le motif d'un fichier au format 1 (antérieur à CALX370).
MOTIF_FORMAT_1 = (
    'Fichier au format 1 : il ne porte ni postes de pertes saisis ni '
    'variantes — les postes repris sont ceux de la liste « pertes » servie, '
    'et aucune variante n’est créée.')


class ImportProjetRefuse(ValueError):
    """La réimportation refuse le fichier — et NOMME le chemin fautif."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _chemin_layout(prefixe, champ):
    """``roof_layout`` + le chemin rendu par ``io_layout`` (jamais ``<racine>``)."""
    champ = str(champ or '')
    if champ in ('', '<racine>', 'roof_layout'):
        return prefixe
    return '%s.%s' % (prefixe, champ)


def _valider_layout(document, prefixe):
    """Un document de pose, validé par ``io_layout`` — ou ``None``."""
    from .io_layout import ImportLayoutRefuse, valider_document

    if document is None:
        return None
    try:
        valider_document(document)
    except ImportLayoutRefuse as refus:
        chemin = _chemin_layout(prefixe, refus.champ)
        raise ImportProjetRefuse(
            'Fichier de projet refusé au champ « %s » : %s'
            % (chemin, refus), champ=chemin) from refus
    return copy.deepcopy(document)


def _valider_postes(postes, cle):
    """Les postes de pertes, validés par ``services/pertes`` — chemin nommé."""
    from .pertes import PertesInvalides, valider_postes

    if postes is None:
        return []
    try:
        return valider_postes(postes)
    except PertesInvalides as refus:
        champ = str(refus.champ or '')
        if champ.startswith('pertes'):
            chemin = cle + champ[len('pertes'):]
        else:
            rangs = [rang for rang, poste in enumerate(postes)
                     if isinstance(poste, dict)
                     and str(poste.get('poste') or '').strip() == champ]
            chemin = ('%s[%d]' % (cle, rangs[-1]) if rangs
                      else cle)
        raise ImportProjetRefuse(
            'Fichier de projet refusé au champ « %s » : %s'
            % (chemin, refus), champ=chemin) from refus


def _valider_variantes(variantes):
    """Les variantes du fichier, validées une par une — chemin nommé."""
    if variantes is None:
        return []
    if not isinstance(variantes, list):
        raise ImportProjetRefuse(
            'Fichier de projet refusé au champ « variantes » : une liste est '
            'attendue (reçu : %s).' % type(variantes).__name__,
            champ='variantes')
    propres = []
    retenues = []
    for rang, variante in enumerate(variantes):
        chemin = 'variantes[%d]' % rang
        if not isinstance(variante, dict):
            raise ImportProjetRefuse(
                'Fichier de projet refusé au champ « %s » : un objet est '
                'attendu (reçu : %s).' % (chemin, type(variante).__name__),
                champ=chemin)
        nom = _texte(variante.get('nom'))
        if not nom:
            raise ImportProjetRefuse(
                'Fichier de projet refusé au champ « %s.nom » : une variante '
                'sans nom ne se reconnaît pas dans la comparaison.' % chemin,
                champ='%s.nom' % chemin)
        retenue = variante.get('retenue', False)
        if not isinstance(retenue, bool):
            raise ImportProjetRefuse(
                'Fichier de projet refusé au champ « %s.retenue » : vrai ou '
                'faux est attendu.' % chemin, champ='%s.retenue' % chemin)
        resultat = variante.get('resultat')
        if resultat is not None and not isinstance(resultat, dict):
            raise ImportProjetRefuse(
                'Fichier de projet refusé au champ « %s.resultat » : un objet '
                'ou null est attendu.' % chemin,
                champ='%s.resultat' % chemin)
        if retenue:
            retenues.append(chemin)
        propres.append({
            'nom': nom,
            'retenue': retenue,
            'roof_layout': _valider_layout(variante.get('roof_layout'),
                                           '%s.roof_layout' % chemin),
            'resultat': copy.deepcopy(resultat),
        })
    if len(retenues) > 1:
        raise ImportProjetRefuse(
            'Fichier de projet refusé au champ « %s.retenue » : une seule '
            'variante peut être retenue (déjà : %s).'
            % (retenues[1], retenues[0]), champ='%s.retenue' % retenues[1])
    return propres


def _modules_du_document(document):
    """Le nombre de modules POSÉS (``zones[].geometry.count``), ou ``None``."""
    if not isinstance(document, dict):
        return None
    total = None
    for zone in document.get('zones') or ():
        geometrie = zone.get('geometry') if isinstance(zone, dict) else None
        compte = (geometrie or {}).get('count') \
            if isinstance(geometrie, dict) else None
        if isinstance(compte, (int, float)) and not isinstance(compte, bool):
            total = (total or 0) + int(compte)
    return total


def _analyser_projet(document):
    """Valide TOUT le fichier, sans rien écrire — le plan de réimportation.

    Returns:
        ``{format_version, titre, roof_layout, postes, variantes,
        avertissements}`` : exactement ce qui sera écrit.

    Raises:
        ImportProjetRefuse: le premier défaut, son chemin NOMMÉ — version
            inconnue, clé de coût, document de pose invalide, poste ou
            variante illisible.
    """
    if not isinstance(document, dict):
        raise ImportProjetRefuse(
            'Le fichier de projet doit être un objet JSON (reçu : %s).'
            % type(document).__name__, champ='projet')
    version = document.get('format_version')
    if isinstance(version, bool) or version not in FORMATS_IMPORTABLES:
        raise ImportProjetRefuse(
            'Fichier de projet refusé : « format_version » vaut %s, une '
            'version que ce serveur ne sait pas relire (versions lues : %s). '
            'Réexportez le projet depuis une version à jour.'
            % (_json_court(version),
               ', '.join(str(v) for v in FORMATS_IMPORTABLES)),
            champ='format_version')

    montants = sorted(_chemins(document, '',
                               lambda cle, _valeur: cle_de_montant(cle)))
    if montants:
        raise ImportProjetRefuse(
            'Fichier de projet refusé : il porte des grandeurs de coût — %s. '
            "Aucun montant n'entre dans un calepinage."
            % ', '.join(montants), champ=montants[0])

    avertissements = []
    if version == 1:
        postes = _valider_postes(document.get('pertes'), 'pertes')
        variantes = []
        avertissements.append(MOTIF_FORMAT_1)
    else:
        postes = _valider_postes(document.get('postes_pertes'),
                                 'postes_pertes')
        variantes = _valider_variantes(document.get('variantes'))

    bloc = document.get('calepinage')
    titre = _texte((bloc or {}).get('titre')) if isinstance(bloc, dict) else ''
    return {
        'format_version': version,
        'titre': titre,
        'roof_layout': _valider_layout(document.get('roof_layout'),
                                       'roof_layout'),
        'postes': postes,
        'variantes': variantes,
        'avertissements': avertissements,
    }


def _json_court(valeur):
    """La valeur telle qu'elle apparaît dans le fichier (pour un refus)."""
    import json

    try:
        return json.dumps(valeur, ensure_ascii=False)[:40]
    except (TypeError, ValueError):
        return repr(valeur)[:40]


def _resume(plan, *, calepinage=None, ecrit, avertissements=()):
    """La réponse de la réimportation — forme ``calepinage_projet_json``."""
    retenue = next((v['nom'] for v in plan['variantes'] if v['retenue']),
                   None)
    return {
        'calepinage': getattr(calepinage, 'pk', None),
        'titre': (_texte(getattr(calepinage, 'titre', ''))
                  if calepinage is not None else plan['titre']),
        'format_version': plan['format_version'],
        'ecrit': ecrit,
        'modules': _modules_du_document(plan['roof_layout']),
        'postes_pertes': len(plan['postes']),
        'variantes': len(plan['variantes']),
        'variante_retenue': retenue,
        'repris': list(BLOCS_REPRIS),
        'ignores': [{'bloc': bloc, 'motif': motif}
                    for bloc, motif in BLOCS_IGNORES],
        'avertissements': list(plan['avertissements']) + list(avertissements),
    }


def importer_projet(document, company, *, user=None, lead_id=None,
                    client_id=None, titre='', apercu=False):
    """Réimporte le fichier de projet dans ``company`` — un NOUVEAU calepinage.

    Args:
        document: le fichier (``document_de_projet``, format 1 ou 2).
        company: la société d'ARRIVÉE — posée par le serveur, jamais lue du
            fichier ni du corps de requête.
        user: l'auteur, posé par le serveur.
        lead_id / client_id: le rattachement dans la société d'arrivée
            (exactement un des deux) — les identifiants du fichier désignent
            la société de départ et ne sont jamais repris.
        titre: remplace le titre du fichier quand il est fourni.
        apercu: ``True`` valide TOUT et rend ce qui SERAIT écrit, sans
            écrire quoi que ce soit.

    Returns:
        le résumé (forme ``contract_samples/calepinage_projet_json.json``).

    Raises:
        ImportProjetRefuse: le fichier ou le rattachement est refusé, chemin
            NOMMÉ ; rien n'a été écrit.
    """
    plan = _analyser_projet(document)
    if (titre or '').strip():
        plan['titre'] = titre.strip()
    if bool(lead_id) == bool(client_id):
        raise ImportProjetRefuse(
            'Indiquez le lead OU le client de votre société auquel rattacher '
            'le projet importé (un seul des deux).', champ='lead')
    if apercu:
        return _resume(plan, ecrit=False)

    from django.db import transaction

    from .creation import CreationRefusee, creer_pour_client, creer_pour_lead
    from .layout import LayoutRefuse, enregistrer_layout
    from .pertes import enregistrer_pertes

    avertissements = []
    try:
        with transaction.atomic():
            if lead_id:
                calepinage = creer_pour_lead(lead_id, company, user=user,
                                             titre=plan['titre'])
            else:
                calepinage = creer_pour_client(client_id, company, user=user,
                                               titre=plan['titre'])
            if plan['roof_layout'] is not None:
                enregistrer_layout(
                    calepinage, plan['roof_layout'], user=user,
                    libelle='Import du fichier de projet')
            if plan['postes']:
                enregistrer_pertes(calepinage, plan['postes'])
            avertissements.extend(
                _creer_variantes(calepinage, plan['variantes'], user=user))
    except CreationRefusee as refus:
        champ = refus.champ or ('lead' if lead_id else 'client')
        raise ImportProjetRefuse(str(refus), champ=champ) from refus
    except LayoutRefuse as refus:
        raise ImportProjetRefuse(
            str(refus), champ=refus.champ or 'roof_layout') from refus
    return _resume(plan, calepinage=calepinage, ecrit=True,
                   avertissements=avertissements)


def _creer_variantes(calepinage, variantes, *, user=None):
    """Crée les variantes par le chemin UNIQUE (``services/variantes``).

    Toutes naissent non retenues ; la retenue du fichier est ensuite
    basculée par ``retenir_variante`` — le SEUL chemin d'écriture de
    ``retenue`` (CAL9), feu vert du bureau d'études compris (CAL206). Un refus
    de ce feu vert n'arrête pas l'import : la variante est créée NON retenue
    et l'avertissement le dit, plutôt que de perdre le projet entier.
    """
    from rest_framework.exceptions import ValidationError

    from .variantes import VarianteRefusee, creer_variante, retenir_variante

    avertissements = []
    for rang, ligne in enumerate(variantes):
        try:
            variante = creer_variante(
                calepinage, nom=ligne['nom'],
                roof_layout=ligne['roof_layout'],
                resultat=ligne['resultat'], user=user)
        except VarianteRefusee as refus:
            chemin = 'variantes[%d].%s' % (rang, refus.champ or 'nom')
            raise ImportProjetRefuse(
                'Fichier de projet refusé au champ « %s » : %s'
                % (chemin, refus), champ=chemin) from refus
        if not ligne['retenue']:
            continue
        try:
            retenir_variante(variante)
        except (VarianteRefusee, ValidationError) as refus:
            detail = getattr(refus, 'detail', None) or str(refus)
            avertissements.append(
                'La variante « %s » était retenue dans le fichier ; elle ne '
                "l'est pas ici : %s" % (ligne['nom'], _texte_du_refus(detail)))
    return avertissements


def _texte_du_refus(detail):
    """Le premier message lisible d'un refus DRF (dict/list) ou d'un texte."""
    if isinstance(detail, dict):
        for valeur in detail.values():
            return _texte_du_refus(valeur)
        return ''
    if isinstance(detail, (list, tuple)):
        return _texte_du_refus(detail[0]) if detail else ''
    return str(detail)
