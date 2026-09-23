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
layout_hash, version_moteur, resultat, pertes, avertissements, provenance}`` —
DOUZE clés, TOUJOURS présentes. Chaque bloc est LU, rien n'est recalculé :

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
  feuille ``Provenance`` du XLSX et le calque ``PROVENANCE`` du DXF.

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
]

#: Le numéro de FORMAT de ce fichier — un entier, incrémenté à la main quand
#: un bloc s'ajoute ; jamais une date, jamais le ``schema_version`` du layout.
FORMAT_VERSION = 1

#: Le code du document dans l'inventaire (contrat ``calepinage_documents``).
CODE_DOCUMENT = 'export_projet_json'

#: Les douze clés du contrat, dans l'ordre du fichier (``provenance`` :
#: CALX314).
CLES_DOCUMENT = ('format_version', 'produit_le', 'calepinage', 'site',
                 'equipements', 'roof_layout', 'layout_hash',
                 'version_moteur', 'resultat', 'pertes', 'avertissements',
                 'provenance')

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
    }
    verifier_aucun_montant(document)
    octets_de_projet(document)  # JSON strict, ou refus nommé
    return document
