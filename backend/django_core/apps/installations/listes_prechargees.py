"""Lectures des LISTES d'installations sur données préchargées (APRF39-APRF40).

Les écrans de liste (atelier d'assemblage, kanban/calendrier des interventions)
sérialisent N objets : chaque calcul par ligne doit lire le cache préchargé par
la vue au lieu de relancer une requête par objet. Les appels UNITAIRES (fiche,
PDF) gardent leur chemin : sans cache préchargé, chaque helper retombe sur la
requête d'origine.
"""


def prechargee(instance, nom):
    """Vrai si la relation inverse `nom` de `instance` a été préchargée."""
    return nom in getattr(instance, '_prefetched_objects_cache', {})


def relation(instance, nom, *select, frais=False):
    """Objets de la relation `nom` : le cache préchargé quand il existe (et que
    l'appelant ne vient pas d'y écrire — `frais`), sinon la requête d'origine
    avec `select_related(*select)`."""
    gestionnaire = getattr(instance, nom)
    if prechargee(instance, nom) and not frais:
        return gestionnaire.all()
    return gestionnaire.select_related(*select).all()


def totaux_temps_memo(serializer, ordre):
    """APRF39 — `totaux_temps_ordre` calculé UNE fois par ordre et par
    sérialiseur (le prévu puis le réel lisent le même résultat)."""
    cache = serializer.__dict__.setdefault('_totaux_temps_cache', {})
    if ordre.pk not in cache:
        from .services import totaux_temps_ordre
        cache[ordre.pk] = totaux_temps_ordre(ordre)
    return cache[ordre.pk]
