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


class PhotosPrechargeesListeMixin:
    """APRF40 — la LISTE des interventions (liste, kanban) dépose sur chaque
    intervention de la page ses pièces jointes, chargées en UNE requête
    `Attachment` (`precharger_photos`, APRF37) : `photos_obligatoires_manquantes`
    ne relance plus une requête par intervention. Hors liste, rien ne change.

    La shot-list de chaque société de la page est lue UNE fois ici et déposée
    dans la mémo ``_shotlist_cache`` du sérialiseur (AUD324) : le court-circuit
    de ``precharger_photos`` la relit au lieu d'une seconde requête."""

    def get_serializer(self, *args, **kwargs):
        if kwargs.get('many') and args and getattr(self, 'action', None) == 'list':
            from .field_services import active_shotlist, precharger_photos
            args = (list(args[0]),) + args[1:]
            shotlists = {cid: active_shotlist(cid)
                         for cid in {i.company_id for i in args[0]}
                         if cid is not None}
            precharger_photos(args[0], shotlists=shotlists)
            serializer = super().get_serializer(*args, **kwargs)
            serializer.context.setdefault('_shotlist_cache', {}).update(shotlists)
            return serializer
        return super().get_serializer(*args, **kwargs)
