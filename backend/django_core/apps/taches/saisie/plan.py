"""Liste collée de « Planifier le projet » (reference/regles.md §1.10, fin) — pur, sans Django.

Autre grammaire que la saisie rapide, même paquet : une ligne finissant par
« : » ouvre une étape ; les lignes suivantes sont des tâches ; « - » ou « * »
sous une tâche en fait une sous-tâche ; « ◆ » ou « jalon: » en tête marque un
jalon ; les lignes vides sont ignorées. Rien n'est analysé en dates.
"""
import re

from apps.taches.saisie.collage import MAX_LIGNES, MESSAGE_TROP_DE_LIGNES
from apps.taches.saisie.normalisation import normaliser

_SOUS_TACHE = re.compile(r'[-*]\s+')
_JALON = re.compile(r'(?:◆\s*|jalon\s*:\s*)', re.IGNORECASE)


def _est_jalon(ligne):
    """`(titre, jalon)` : « ◆ » ou « jalon: » en tête (casse et accents ignorés)."""
    m = _JALON.match(normaliser(ligne))
    if m is None:
        return ligne, False
    return ligne[m.end():].strip(), True


def _etape(ligne):
    """Nom de l'étape si la ligne finit par « : », sinon None."""
    if not ligne.endswith((':', '：')):
        return None
    nom = ligne.rstrip(':：').strip()
    return nom or None


def _ajouter_ligne(sections, ligne):
    """Classe une ligne dans `sections` (tâche, sous-tâche ou jalon de la dernière étape)."""
    sous = _SOUS_TACHE.match(ligne)
    taches = sections[-1]['taches']
    if sous and taches:
        titre = ligne[sous.end():].strip()
        if titre:
            taches[-1]['sous_taches'].append(titre)
        return
    titre, jalon = _est_jalon(ligne)
    if sous:
        titre = ligne[sous.end():].strip()
    if titre:
        taches.append({'titre': titre, 'jalon': jalon, 'sous_taches': []})


def _retrait(brute):
    """Largeur du retrait de la ligne (une tabulation = 4 espaces)."""
    large = brute.expandtabs(4)
    return len(large) - len(large.lstrip())


def decouper_etapes(texte):
    """Le champ « Étapes » de « Planifier le projet » (R2-062) : une ligne NON indentée, sans puce ni jalon, EST une
    étape (un « : » final est toléré et retiré) ; ses lignes indentées ou à tiret en sont les tâches ; une puce plus
    en retrait que la tâche qui la précède en est la sous-tâche ; « ◆ » ou « jalon: » marque un jalon. Même forme que
    `decouper_plan`. Une étape sans tâche est gardée (« 3 étapes · 0 tâche »)."""
    sections = [{'nom': None, 'taches': []}]
    retrait_tache = None
    for brute in texte.splitlines():
        ligne = brute.strip()
        if not ligne:
            continue
        retrait = _retrait(brute)
        puce = _SOUS_TACHE.match(ligne)
        titre, jalon = _est_jalon(ligne[puce.end():].strip() if puce else ligne)
        if retrait == 0 and not puce and not jalon:
            nom = ligne.rstrip(':：').strip()
            if nom:
                sections.append({'nom': nom, 'taches': []})
                retrait_tache = None
            continue
        if not titre:
            continue
        taches = sections[-1]['taches']
        if puce and taches and retrait_tache is not None and retrait > retrait_tache:
            taches[-1]['sous_taches'].append(titre)
        else:
            taches.append({'titre': titre, 'jalon': jalon, 'sous_taches': []})
            retrait_tache = retrait
    if not sections[0]['taches']:
        sections = sections[1:]
    return {'sections': sections}


def decouper_plan(texte, mode='plan'):
    """`{'sections': [{'nom', 'taches': [{'titre', 'jalon', 'sous_taches'}]}]}`.

    Les tâches écrites avant toute étape vont dans une section de `nom` None.
    Une étape sans tâche est gardée (vide). `mode='etapes'` : la grammaire du champ « Étapes » (`decouper_etapes`).
    """
    if mode == 'etapes':
        return decouper_etapes(texte)
    sections = [{'nom': None, 'taches': []}]
    for brute in texte.splitlines():
        ligne = brute.strip()
        if not ligne:
            continue
        nom = _etape(ligne)
        if nom is not None and not _SOUS_TACHE.match(ligne):
            sections.append({'nom': nom, 'taches': []})
        else:
            _ajouter_ligne(sections, ligne)
    if not sections[0]['taches']:
        sections = sections[1:]
    return {'sections': sections}


def erreurs_limites_plan(texte):
    """200 lignes au plus : `{'texte': [message]}` ou `{}`."""
    nombre = sum(1 for ligne in texte.splitlines() if ligne.strip())
    if nombre > MAX_LIGNES:
        return {'texte': [MESSAGE_TROP_DE_LIGNES.format(n=nombre)]}
    return {}
