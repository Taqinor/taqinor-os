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


def _controles_croises(document):
    """Les refus que le vocabulaire JSON Schema ne sait pas exprimer.

    Un seul endroit, appelé par ``valider_document`` juste après le schéma :
    les écrans et l'import HTTP héritent donc des mêmes refus, nommés de la
    même façon, sans qu'aucun d'eux ne recode une règle.
    """
    _refuser_module_inconnu(document)


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
