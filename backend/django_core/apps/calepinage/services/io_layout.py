"""CAL216 — import/export JSON du document ``roof_layout``.

DEUX PORTES CONTRÔLÉES, LÀ OÙ IL N'Y EN AVAIT AUCUNE
---------------------------------------------------------
Le schéma est déjà un JSON pur et documenté
(``contract_samples/roof_layout_v2.schema.json``, publié par CAL232) et AO
stocke un layout brut NON VALIDÉ (``apps/ao/models.py:213-216``) — aucune
porte d'import/export CONTRÔLÉE n'existait. Ce module en pose deux :

* ``exporter_layout`` rend le document TEL QUEL — aucune transformation,
  aucun champ retiré ;
* ``importer_layout`` valide STRICTEMENT contre le schéma v2 AVANT
  d'écrire, et refuse en NOMMANT le chemin du champ fautif (jamais un
  message générique).

UN SEUL CHEMIN D'ÉCRITURE, HÉRITÉ
--------------------------------------
``importer_layout`` enregistre par ``services.layout.enregistrer_layout`` —
LE chemin unique du document de conception (CAL13). Elle hérite donc, sans
code dupliqué, du verrou après envoi du devis (CAL207, 409) et de
l'historisation par version (CAL8).
"""
from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    'ImportLayoutRefuse', 'VERSION_SCHEMA', 'exporter_layout',
    'valider_document', 'importer_layout',
]

#: Numéro de version du schéma v2 publié (CAL232) — celui que ``exporter_
#: layout`` annonce, jamais recalculé depuis le document lui-même (un
#: document ancien peut ne porter aucune clé ``version``).
VERSION_SCHEMA = 2

_CHEMIN_SCHEMA = (Path(__file__).resolve().parent.parent
                  / 'contract_samples' / 'roof_layout_v2.schema.json')
_schema_charge = None


def _schema():
    """Le schéma v2, chargé UNE fois (fichier committé, immuable en cours
    de process)."""
    global _schema_charge

    if _schema_charge is None:
        with open(_CHEMIN_SCHEMA, encoding='utf-8') as fichier:
            _schema_charge = json.load(fichier)
    return _schema_charge


class ImportLayoutRefuse(ValueError):
    """Erreur métier sur un import, message français, champ fautif nommé.

    ``champ`` porte le CHEMIN JSON (``'zones.0.vertices'``) — pas seulement
    le nom du champ racine — pour que l'écran pointe l'endroit exact.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def exporter_layout(calepinage):
    """Le document ``roof_layout`` TEL QUEL, avec le numéro de version du
    schéma. Lecture PURE.

    Returns:
        ``{'roof_layout', 'layout_hash', 'schema_version'}`` —
        ``roof_layout`` vaut ``None`` (jamais ``{}``) si aucun document n'a
        encore été enregistré.
    """
    if calepinage is None:
        return {'roof_layout': None, 'layout_hash': '',
                'schema_version': VERSION_SCHEMA}
    return {
        'roof_layout': calepinage.roof_layout,
        'layout_hash': calepinage.layout_hash or '',
        'schema_version': VERSION_SCHEMA,
    }


def _refuser_module_inconnu(document):
    """CALX82 — un pan ne peut pas désigner un modèle absent de ``modules[]``.

    JSON Schema sait contraindre une NATURE, pas comparer deux endroits d'un
    même document : le renvoi ``zones[].geometry.moduleId`` -> ``modules[].id``
    se contrôle donc ici, APRÈS la validation de schéma (les natures sont donc
    déjà sûres), et le refus NOMME le chemin du champ fautif.
    """
    catalogue = document.get('modules')
    connus = set()
    if isinstance(catalogue, list):
        connus = {entree.get('id') for entree in catalogue
                  if isinstance(entree, dict)
                  and isinstance(entree.get('id'), str)}
    zones = document.get('zones')
    if not isinstance(zones, list):
        return
    for rang, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        geometrie = zone.get('geometry')
        if not isinstance(geometrie, dict):
            continue
        modele = geometrie.get('moduleId')
        if modele is None or modele in connus:
            continue
        chemin = f'zones.{rang}.geometry.moduleId'
        inventaire = ', '.join(sorted(connus)) or 'aucun'
        raise ImportLayoutRefuse(
            f'Document refusé au champ « {chemin} » : le module '
            f'« {modele} » ne figure pas dans « modules » '
            f'(modèles déclarés : {inventaire}).', champ=chemin)


def _refuser_numero_de_module_double(document):
    """CALX83 — deux modules d'un MÊME pan ne peuvent pas partager ``n``.

    ``uniqueItems`` compare des ÉLÉMENTS entiers, pas une propriété d'objet :
    l'unicité du numéro stable se contrôle donc ici. Un doublon rendrait le
    numéro inutilisable pour ce à quoi il sert — citer un module précis dans
    un rapport d'ombrage ou sur un plan de pose.
    """
    zones = document.get('zones')
    if not isinstance(zones, list):
        return
    for rang, zone in enumerate(zones):
        if not isinstance(zone, dict):
            continue
        geometrie = zone.get('geometry')
        if not isinstance(geometrie, dict):
            continue
        modules = geometrie.get('panels')
        if not isinstance(modules, list):
            continue
        vus = {}
        for place, module in enumerate(modules):
            if not isinstance(module, dict):
                continue
            numero = module.get('n')
            if not isinstance(numero, int) or isinstance(numero, bool):
                continue
            if numero in vus:
                chemin = f'zones.{rang}.geometry.panels.{place}.n'
                raise ImportLayoutRefuse(
                    f'Document refusé au champ « {chemin} » : le numéro de '
                    f'module {numero} est déjà porté par '
                    f'« zones.{rang}.geometry.panels.{vus[numero]}.n » — sur '
                    f'un même pan, un numéro désigne UN module et un seul.',
                    champ=chemin)
            vus[numero] = place


def _refuser_parcelle_trop_courte(document):
    """ACAL232 - une parcelle de moins de 3 sommets est refusee a l'import.

    Le schema la refuse deja (``minItems: 3``) mais sous le chemin
    ``parcelle.vertices`` ; le refus NOMME ici ``roof_layout.parcelle``, le
    champ que l'ecran sait pointer. Controle fait AVANT la validation du
    schema.
    """
    parcelle = document.get('parcelle')
    sommets = parcelle.get('vertices') if isinstance(parcelle, dict) else None
    if isinstance(sommets, list) and len(sommets) < 3:
        raise ImportLayoutRefuse(
            "Document refusé au champ « roof_layout.parcelle » : une "
            "parcelle exige au moins 3 sommets [lng, lat] "
            f"(reçu : {len(sommets)}).", champ='roof_layout.parcelle')


def _controles_croises(document):
    """Les refus que le vocabulaire JSON Schema ne sait pas exprimer.

    Un seul endroit, appelé par ``valider_document`` juste après le schéma :
    les écrans et l'import HTTP héritent donc des mêmes refus, nommés de la
    même façon, sans qu'aucun d'eux ne recode une règle.
    """
    _refuser_module_inconnu(document)
    _refuser_numero_de_module_double(document)
    _refuser_contour_croise(document)


def _refuser_contour_croise(document):
    """ACAL76 — un document IMPORTÉ ne peut porter aucun contour croisé.

    Pans, obstacles polygonaux et zones d'exclusion : le test est celui du
    noyau (``core.calepinage.geometrie.est_polygone_simple``), via le
    collecteur unique ``services.layout.contours_croises`` — jamais recodé.
    """
    from .layout import contours_croises, message_contour_croise

    croises = contours_croises(document)
    if croises:
        chemin = croises[0][0]
        raise ImportLayoutRefuse(message_contour_croise(chemin), champ=chemin)


def valider_document(document):
    """Valide ``document`` contre le schéma v2 (CAL232) — refuse en NOMMANT
    le CHEMIN du champ fautif.

    Raises:
        ImportLayoutRefuse: document qui n'est pas un objet, qui viole le
            schéma, ou dont un renvoi interne ne pointe rien
            (``_controles_croises``).
    """
    import jsonschema

    if not isinstance(document, dict):
        raise ImportLayoutRefuse(
            'Le document importé doit être un objet '
            f'(reçu : {type(document).__name__}).', champ='roof_layout')
    # ACAL86 — un ``battery`` BOOLÉEN historique est normalisé À LA LECTURE
    # (le lecteur unique ventes ``battery_du_document``) : on valide une
    # COPIE superficielle, le document de l'appelant n'est jamais modifié.
    if isinstance(document.get('battery'), bool):
        from apps.ventes.services import battery_du_document
        document = dict(document, battery=battery_du_document(document))
    _refuser_parcelle_trop_courte(document)
    try:
        jsonschema.validate(document, _schema())
    except jsonschema.exceptions.ValidationError as erreur:
        chemin = '.'.join(str(segment) for segment in erreur.absolute_path)
        chemin = chemin or '<racine>'
        raise ImportLayoutRefuse(
            f'Document refusé au champ « {chemin} » : {erreur.message}.',
            champ=chemin) from erreur
    _controles_croises(document)


def importer_layout(calepinage, document, *, user=None):
    """Valide STRICTEMENT ``document`` puis l'enregistre par le chemin
    d'écriture unique (``services.layout.enregistrer_layout``).

    Raises:
        ImportLayoutRefuse: document invalide contre le schéma v2.
        services.layout.LayoutRefuse: calepinage non enregistré.
        services.verrou.VerrouilleRefuse (409): calepinage verrouillé
            (devis lié envoyé) — hérité, jamais recodé.
    """
    valider_document(document)

    from .layout import enregistrer_layout

    return enregistrer_layout(calepinage, document, user=user)
