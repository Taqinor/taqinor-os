"""CAL197 — presets de conception PROPRES au module (section ``presets`` de
``ParametresCalepinage``, CAL45 — aucun nouveau modèle).

UNE SEULE SOURCE, JAMAIS UNE COPIE VENUE D'AILLEURS
----------------------------------------------------
Ce module range les presets PROPRES à l'atelier dans la section ``presets``
des réglages société (``selectors.presets_de_societe``).

SOLMVP15 — il y avait une SECONDE source, lue côte à côte : les presets de
portee société du module d'appels d'offres, jamais copiés dans la section du
module. Ce module-là sort du produit, sa table part avec lui : il n'en reste
qu'une source. Les jeux maison sont intacts — rien n'a été perdu ni copié.

Aucune valeur codée en dur : ce service ne pose AUCUN défaut, il range ce
qu'on lui donne et refuse ce qui est incomplet, en NOMMANT le champ fautif.
"""
from __future__ import annotations

from .approbation import CLE_EXIGEE

#: Clé, DANS la section ``presets``, qui porte la liste des jeux MAISON.
CLE_JEUX = 'jeux'

#: La section des réglages société que ce module porte (CAL45).
SECTION = 'presets'

__all__ = [
    'PresetInvalide', 'CLE_JEUX', 'SECTION', 'CLE_APPROBATION_EXIGEE',
    'jeux_de_societe', 'enregistrer_jeu', 'retirer_jeu',
    'normaliser_section_presets',
]

#: CALX348 — la clé, DANS la section ``presets``, qui exige l'approbation
#: (CALX347) avant de retenir une variante. Source UNIQUE :
#: ``services/approbation.py::CLE_EXIGEE`` (qui la LIT) ; ce module-ci la
#: VALIDE à l'écriture (``normaliser_section_presets``). Off par défaut : une
#: société qui n'a jamais réglé cette option retrouve le comportement
#: d'aujourd'hui.
CLE_APPROBATION_EXIGEE = CLE_EXIGEE


class PresetInvalide(ValueError):
    """Erreur métier sur un preset, message français, champ fautif nommé."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def jeux_de_societe(company):
    """Les presets PROPRES au module (section ``presets.jeux``), lecture pure.

    ÉQUIVALENCE GARANTIE : une société qui n'a jamais rien réglé reçoit une
    liste VIDE — comportement d'aujourd'hui, strictement inchangé.
    """
    from ..selectors import parametres_de_societe

    presets = parametres_de_societe(company).get('presets') or {}
    jeux = presets.get(CLE_JEUX)
    return jeux if isinstance(jeux, list) else []


def enregistrer_jeu(company, jeu):
    """Ajoute, ou REMPLACE (par ``id``), un jeu MAISON de marges/espacements/
    dégagements de l'atelier.

    ``jeu`` doit porter ``id`` et ``nom`` non vides — refusé sinon, en
    NOMMANT le champ. Le reste du contenu (marges, espacements, dégagements)
    n'est jamais validé ici : ce service range ce que l'atelier lui envoie,
    il n'invente ni ne recale aucune valeur.
    """
    from .parametres import enregistrer_parametres

    if not isinstance(jeu, dict):
        raise PresetInvalide('Un preset de conception doit être un objet.',
                             champ='jeu')
    identifiant = jeu.get('id')
    identifiant = identifiant.strip() if isinstance(identifiant, str) else ''
    nom = jeu.get('nom')
    nom = nom.strip() if isinstance(nom, str) else ''
    if not identifiant:
        raise PresetInvalide(
            'Un preset de conception doit porter un identifiant (« id »).',
            champ='id')
    if not nom:
        raise PresetInvalide(
            'Un preset de conception doit porter un nom (« nom »).',
            champ='nom')

    existants = jeux_de_societe(company)
    restants = [ligne for ligne in existants if ligne.get('id') != identifiant]
    restants.append(dict(jeu, id=identifiant, nom=nom))
    enregistrer_parametres(company, {'presets': _section(company, restants)})
    return restants


def retirer_jeu(company, preset_id):
    """Retire le jeu MAISON ``preset_id`` — refuse s'il est introuvable, en
    nommant le champ."""
    from .parametres import enregistrer_parametres

    existants = jeux_de_societe(company)
    restants = [ligne for ligne in existants if ligne.get('id') != preset_id]
    if len(restants) == len(existants):
        raise PresetInvalide(
            f'Preset de conception introuvable : « {preset_id} ».',
            champ='id')
    enregistrer_parametres(company, {'presets': _section(company, restants)})
    return restants


def _section(company, jeux):
    """La section ``presets`` ENTIÈRE, avec ``jeux`` remplacé — jamais réduite.

    ``enregistrer_parametres`` REMPLACE la section fournie (mise à jour
    partielle au niveau SECTION, pas au niveau clé). Écrire ``{'jeux': …}``
    seul effacerait donc TOUTES les autres clés de la section — dont le
    catalogue de kits de pose (``presets.kits``, SOLMVP15). On relit la section
    et on n'en change QUE ``jeux``.
    """
    from ..selectors import parametres_de_societe

    section = dict(parametres_de_societe(company).get('presets') or {})
    section[CLE_JEUX] = jeux
    return section


def normaliser_section_presets(valeur):
    """CALX348 — la section ``presets`` VALIDÉE, sans rien retrancher.

    La section range des jeux maison, le catalogue de kits, l'interrupteur
    du feu vert (CAL206)… : ce normaliseur n'en touche AUCUNE clé. Il ne
    valide que ``approbation_exigee`` : un BOOLÉEN, ou rien. Une valeur d'une
    autre nature (« oui », 1, une liste) est REFUSÉE en nommant le champ —
    jamais interprétée : un « oui » accepté en silence laisserait croire à
    la société que l'approbation est exigée alors que la lecture stricte
    (``approbation.approbation_exigee``, ``is True``) la tient pour éteinte.

    Raises:
        ReglageInvalide: ``approbation_exigee`` n'est pas un booléen.
    """
    from .parametres import ReglageInvalide

    if not isinstance(valeur, dict) or CLE_APPROBATION_EXIGEE not in valeur:
        return valeur
    exigee = valeur[CLE_APPROBATION_EXIGEE]
    if exigee is None or isinstance(exigee, bool):
        return valeur
    raise ReglageInvalide(
        "« Approbation exigée » se règle par oui ou non (booléen) "
        f"(reçu : {type(exigee).__name__}).",
        champ=CLE_APPROBATION_EXIGEE)
