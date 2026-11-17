"""La confidentialité, en UN seul endroit (reference/regles.md « La confidentialité », donnees.md inv. 8, 38).

- `est_confidentielle(obj)` : une tâche l'est par son drapeau, celui de son projet, de son parent ou du
  projet de son parent (héritage 4 voies) ; un projet par son seul drapeau.
- `nom_pour(obj, usage, reglages=None)` : le SEUL chemin d'un titre de tâche ou d'un nom de projet vers
  un texte servi. `reglages` = la `ReglagesRythme` déjà lue par l'appelant (`titres_*`) : aucune requête
  par appel. Sans elle, les défauts du modèle s'appliquent (rien n'est lu en base).

L'appelant charge `projet`, `parent` et `parent__projet` (`select_related`) : ici, rien n'est relu.
"""
from apps.taches.models.projets import Projet
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import Tache

ECRAN = 'ecran'
ASSISTANT = 'assistant'
FLUX = 'flux'
TUILE = 'tuile'
NOTIFICATION = 'notification'
SIRI = 'siri'
USAGES = (ECRAN, ASSISTANT, FLUX, TUILE, NOTIFICATION, SIRI)

TACHE_CONFIDENTIELLE = 'Tâche confidentielle'
PROJET_CONFIDENTIEL = 'Projet confidentiel'
TACHE_SANS_TITRE = 'Tâche'
SIRI_TACHE_CONFIDENTIELLE = 'une tâche'
SIRI_PROJET_CONFIDENTIEL = 'un projet'
SIRI_LONGUEUR = 60

#: Ce que devient une tâche confidentielle hors de l'écran (la notification rend `None`).
_TACHE_CONFIDENTIELLE_PAR_USAGE = {
    ASSISTANT: TACHE_CONFIDENTIELLE,
    FLUX: TACHE_CONFIDENTIELLE,
    TUILE: TACHE_CONFIDENTIELLE,
    NOTIFICATION: None,
    SIRI: SIRI_TACHE_CONFIDENTIELLE,
}
#: Ce que devient un projet confidentiel hors de l'écran.
_PROJET_CONFIDENTIEL_PAR_USAGE = {
    ASSISTANT: PROJET_CONFIDENTIEL,
    NOTIFICATION: None,
    SIRI: SIRI_PROJET_CONFIDENTIEL,
}
#: Interrupteur de `ReglagesRythme` qui permet le titre d'une tâche ordinaire, par usage.
_INTERRUPTEUR_TITRE = {
    FLUX: 'titres_calendrier',
    TUILE: 'titres_tuile',
    NOTIFICATION: 'titres_notifications',
}


def _projet_confidentiel(tache):
    return bool(tache.projet_id) and bool(tache.projet.confidentiel)


def est_confidentielle(obj):
    """Confidentialité EFFECTIVE (invariant 8) d'une `Tache` ou d'un `Projet`."""
    if isinstance(obj, Projet):
        return bool(obj.confidentiel)
    if obj.confidentiel or _projet_confidentiel(obj):
        return True
    if not obj.parent_id:
        return False
    parent = obj.parent
    return bool(parent.confidentiel) or _projet_confidentiel(parent)


def _titre_permis(usage, reglages):
    champ = _INTERRUPTEUR_TITRE.get(usage)
    if champ is None:
        return True
    return bool(getattr(reglages if reglages is not None else ReglagesRythme(), champ))


def _pour_tache(tache, usage, reglages):
    if usage == ECRAN:
        return tache.titre
    if est_confidentielle(tache):
        return _TACHE_CONFIDENTIELLE_PAR_USAGE[usage]
    if not _titre_permis(usage, reglages):
        return None if usage == NOTIFICATION else TACHE_SANS_TITRE
    return tache.titre[:SIRI_LONGUEUR] if usage == SIRI else tache.titre


def _pour_projet(projet, usage, reglages):
    if usage in (FLUX, TUILE):
        return None  # aucun projet au flux ni à la tuile
    if usage == ECRAN:
        return projet.nom
    if projet.confidentiel:
        return _PROJET_CONFIDENTIEL_PAR_USAGE[usage]
    if not _titre_permis(usage, reglages):
        return None
    return projet.nom[:SIRI_LONGUEUR] if usage == SIRI else projet.nom


def nom_pour(obj, usage, reglages=None):
    """Titre ou nom de `obj` tel qu'il peut être servi pour `usage` ; `None` = rien à servir."""
    if usage not in USAGES:
        raise ValueError(f'usage inconnu : {usage!r}')
    if isinstance(obj, Tache):
        return _pour_tache(obj, usage, reglages)
    if isinstance(obj, Projet):
        return _pour_projet(obj, usage, reglages)
    raise TypeError(f'nom_pour : objet non pris en charge ({type(obj).__name__})')
