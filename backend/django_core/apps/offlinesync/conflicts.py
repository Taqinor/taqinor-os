"""NTMOB2 — détection de CONFLIT de synchronisation (jamais d'écrasement).

Une opération mise en file hors-ligne décrit un monde que le terminal a lu à un
instant T. Si l'enregistrement cible a été modifié par UN AUTRE ACTEUR entre
cette lecture et le rejeu, appliquer l'op écraserait silencieusement le travail
de l'autre. NTMOB2 refuse ce silence : l'op est journalisée `conflit`, elle
n'est PAS appliquée, et un humain tranche explicitement (garder ma version /
garder celle du serveur / fusionner).

**Garde OPT-IN, par op.** La comparaison n'a lieu que si le terminal transmet
dans le payload la version qu'il avait lue (`base_version`, ou l'un de ses
synonymes). Sans cette clé, le comportement est EXACTEMENT celui de NTMOB1 —
aucun client existant ne change de comportement, aucune op ne se met à
« conflit » du jour au lendemain.

Ce module est PUR (aucun modèle, aucun accès base) : il compare deux versions.
"""
from django.utils import timezone
from django.utils.dateparse import parse_datetime

# Champs de version acceptés sur la cible, du plus explicite au plus général.
# `version` est un compteur entier quand un modèle en porte un ; sinon la date
# de dernière modification fait foi (`date_modification` est la convention des
# modèles métier de ce dépôt, `updated_at` celle de ``core.TimestampedModel``).
CHAMPS_VERSION = ('version', 'date_modification', 'updated_at')

# Clés acceptées dans le payload pour la version LUE par le terminal.
CLES_BASE = ('base_version', 'base_date_modification', 'base_updated_at')

MESSAGE = ("Conflit de synchronisation : cet enregistrement a été modifié "
           "ailleurs depuis votre mise en file. Choisissez la version à garder.")


def _texte(valeur):
    """Représentation comparable et JSON-sérialisable d'une version."""
    if valeur is None:
        return None
    if hasattr(valeur, 'isoformat'):
        return valeur.isoformat()
    return str(valeur)


def _en_aware(dt):
    if dt is not None and timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_default_timezone())
    return dt


def _a_la_milliseconde(dt):
    """Horodatage ramené à la MILLISECONDE (précision d'un aller-retour JSON).

    ``Date.toISOString()`` s'arrête à la milliseconde là où PostgreSQL et
    Django gardent la microseconde : sans cette normalisation, un terminal
    parfaitement à jour déclencherait un faux conflit à CHAQUE op. On tronque
    des deux côtés — jamais une tolérance en secondes, qui aurait avalé de
    VRAIS conflits."""
    dt = _en_aware(dt)
    return dt.replace(microsecond=(dt.microsecond // 1000) * 1000)


def _memes_versions(base, courante):
    """Deux versions décrivent-elles le MÊME état ?

    Égalité textuelle d'abord (cas nominal : le terminal renvoie la chaîne
    exacte qu'il a reçue). Sinon, si les DEUX se lisent comme des dates,
    comparaison à la milliseconde — un décalage de format (« +00:00 » vs « Z »),
    de fuseau ou de précision ne doit pas fabriquer un conflit. Une version
    illisible qui ne correspond pas au texte serveur est traitée comme
    DIFFÉRENTE : dans le doute, on demande un arbitrage, on n'écrase pas."""
    if base == courante:
        return True
    if base is None or courante is None:
        return False
    d_base, d_courante = parse_datetime(base), parse_datetime(courante)
    if d_base is None or d_courante is None:
        return False
    return _a_la_milliseconde(d_base) == _a_la_milliseconde(d_courante)


def version_courante(cible):
    """``(champ, valeur)`` de la version SERVEUR de la cible, ou ``(None, None)``
    quand l'objet ne porte aucun champ de version connu (la garde est alors
    inapplicable : on n'invente pas une version)."""
    for champ in CHAMPS_VERSION:
        valeur = getattr(cible, champ, None)
        if valeur not in (None, ''):
            return champ, _texte(valeur)
    return None, None


def version_base(payload):
    """Version que le TERMINAL avait lue avant de mettre l'op en file, ou None
    (le client n'a pas demandé la garde)."""
    for cle in CLES_BASE:
        valeur = (payload or {}).get(cle)
        if valeur not in (None, ''):
            return _texte(valeur)
    return None


def detecter(cible, payload):
    """``{champ, base, serveur}`` si la cible a bougé, sinon ``None``.

    ``None`` dans TOUS les cas où la garde ne s'applique pas : pas de version
    de base transmise, cible non résolue (le handler la refusera avec SON
    message), ou cible sans champ de version."""
    if cible is None:
        return None
    base = version_base(payload)
    if base is None:
        return None
    champ, courante = version_courante(cible)
    if champ is None or _memes_versions(base, courante):
        return None
    return {'champ': champ, 'base': base, 'serveur': courante}
