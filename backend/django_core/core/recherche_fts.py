"""NTPLT32 — entretien des colonnes plein-texte ``search_vector`` (FTS Postgres).

Les 7 entités de la recherche globale (``apps/reporting/search.py``) portent
``search_vector`` (``core.champs_plateforme.RechercheFTSMixin``) + un index GIN.
Ce module en est l'UNIQUE écrivain :

* :data:`ENTITES` — par modèle (libellé ``'app.model'``, jamais d'import d'app :
  couche de FONDATION), les colonnes texte indexées et leur poids (A > B > C).
  Les coordonnées personnelles (téléphone, e-mail) n'y entrent JAMAIS : la
  recherche les réserve aux rôles ``client_pii_voir`` (APFS24), un index commun
  les rendrait trouvables par tous.
* :func:`connecter` (appelé par ``CoreConfig.ready``) — ``post_save`` de chaque
  entité → recalcul du vecteur de LA ligne après la validation de la
  transaction (``on_commit``, patron GED11 : ``UPDATE`` d'une colonne, aucun
  signal, aucun ``auto_now``). Une écriture bornée (``update_fields``) qui ne
  touche aucune colonne indexée ne recalcule rien. Un échec d'indexation est
  journalisé, jamais remonté : l'écriture métier est déjà validée, la ligne
  garde son ancien vecteur.
* :func:`indexer` — recalcul ensembliste d'un lot de clés (signal ET commande
  ``rebuild_search_index``, mêmes expressions SQL : jamais deux recettes).

Accents : la config 'french' ne les retire pas (« Élodie » ≠ « elodie »). Plutôt
que l'extension ``unaccent`` (droits de création non garantis en production,
cf. STKCAT27), le texte passe par ``translate()`` — fonction NATIVE de
PostgreSQL, IMMUTABLE — avec la même table que :func:`sans_accents` côté
requête : vecteur et requête sont normalisés à l'identique.
"""
import logging
import re
import unicodedata

from django.db import transaction
from django.db.models import F, Func, TextField, Value

logger = logging.getLogger(__name__)

CONFIG_FTS = 'french'

#: Colonnes indexées par entité — (champ, poids). Les clés suivent
#: ``core.platform`` / ``reporting.search._SEARCH_SPECS`` (minuscules).
ENTITES = {
    'crm.lead': (('nom', 'A'), ('prenom', 'A'), ('client_ref', 'A'),
                 ('client_ref_provisoire', 'A'), ('societe', 'B'),
                 ('ville', 'C')),
    'crm.client': (('nom', 'A'), ('prenom', 'A')),
    'ventes.devis': (('reference', 'A'),),
    'facturation.facture': (('reference', 'A'),),
    'installations.installation': (('reference', 'A'),),
    'sav.equipement': (('numero_serie', 'A'),),
    'sav.ticket': (('reference', 'A'), ('description', 'C')),
}

_LETTRES_ACCENTUEES = (
    'àáâãäåçèéêëìíîïñòóôõöùúûüýÿ'
    'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝ')
ACCENTS = _LETTRES_ACCENTUEES
SANS_ACCENTS = ''.join(
    unicodedata.normalize('NFD', c)[0] for c in _LETTRES_ACCENTUEES)
_TABLE = str.maketrans(ACCENTS, SANS_ACCENTS)


def sans_accents(texte):
    """Côté Python, la MÊME table que le ``translate()`` SQL des vecteurs."""
    return (texte or '').translate(_TABLE)


def _texte_normalise(champ):
    return Func(F(champ), Value(ACCENTS), Value(SANS_ACCENTS),
                function='translate', output_field=TextField())


def expression_vecteur(champs):
    """``setweight(to_tsvector('french', translate(col)), poids) || …``."""
    from django.contrib.postgres.search import SearchVector

    vecteur = None
    for champ, poids in champs:
        partie = SearchVector(_texte_normalise(champ), config=CONFIG_FTS,
                              weight=poids)
        vecteur = partie if vecteur is None else vecteur + partie
    return vecteur


def champs_de(modele):
    """Les colonnes indexées de ``modele``, ou ``None`` s'il n'est pas FTS."""
    return ENTITES.get(modele._meta.label_lower)


def indexer(modele, pks, using=None):
    """Recalcule ``search_vector`` des lignes ``pks`` (une requête). Rend le
    nombre de lignes écrites."""
    champs = champs_de(modele)
    if not champs or not pks:
        return 0
    qs = modele._base_manager.filter(pk__in=list(pks))
    if using:
        qs = qs.using(using)
    return qs.update(search_vector=expression_vecteur(champs))


def _indexer_sans_echec(modele, pk, using):
    try:
        indexer(modele, [pk], using=using)
    except Exception:  # noqa: BLE001 — l'écriture métier est déjà validée (D-ENF22-BLE001)
        logger.warning('recherche_fts : indexation de %s #%s échouée (vecteur '
                       'inchangé)', modele._meta.label, pk, exc_info=True)


def _apres_sauvegarde(sender, instance, created=False, update_fields=None,
                      raw=False, using=None, **kwargs):
    if raw:  # chargement de fixtures : la commande de reconstruction s'en charge
        return
    champs = champs_de(sender)
    if not champs:
        return
    if update_fields is not None and not (
            {nom for nom, _ in champs} & set(update_fields)):
        return
    pk = instance.pk
    transaction.on_commit(lambda: _indexer_sans_echec(sender, pk, using),
                          using=using)


def connecter():
    """Branche ``post_save`` sur chaque entité installée qui porte la colonne.
    Idempotent (``dispatch_uid``) ; un libellé absent est ignoré."""
    from django.apps import apps as django_apps
    from django.db.models.signals import post_save

    connectes = []
    for label in ENTITES:
        try:
            modele = django_apps.get_model(label)
        except LookupError:
            continue
        if not any(f.name == 'search_vector' for f in modele._meta.concrete_fields):
            continue
        post_save.connect(_apres_sauvegarde, sender=modele,
                          dispatch_uid=f'core.recherche_fts.{label}')
        connectes.append(label)
    return connectes


def modeles(app_label=None):
    """Les modèles FTS installés (filtrés par app), pour la reconstruction."""
    from django.apps import apps as django_apps

    sortie = []
    for label in ENTITES:
        if app_label and label.split('.', 1)[0] != app_label:
            continue
        try:
            sortie.append(django_apps.get_model(label))
        except LookupError:
            continue
    return sortie


_JETON = re.compile(r'[^\W_]+')
_JETONS_MAX = 8


def requete_prefixe(q):
    """``SearchQuery`` brute ``mot1:* & mot2:*`` (frappe instantanée : chaque
    mot vaut pour son préfixe, racinisé par la config 'french' — pluriels
    compris), ou ``None`` si ``q`` ne porte aucun mot. Les jetons ne gardent que
    lettres et chiffres : aucun opérateur tsquery ne passe."""
    from django.contrib.postgres.search import SearchQuery

    jetons = _JETON.findall(sans_accents(q).lower())[:_JETONS_MAX]
    if not jetons:
        return None
    return SearchQuery(' & '.join(f'{j}:*' for j in jetons),
                       search_type='raw', config=CONFIG_FTS)
