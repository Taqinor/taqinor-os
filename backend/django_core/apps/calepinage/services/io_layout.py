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


def valider_document(document):
    """Valide ``document`` contre le schéma v2 (CAL232) — refuse en NOMMANT
    le CHEMIN du champ fautif.

    Raises:
        ImportLayoutRefuse: document qui n'est pas un objet, ou qui viole le
            schéma.
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
