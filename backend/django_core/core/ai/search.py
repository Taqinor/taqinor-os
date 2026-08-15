"""NTAI24 — Index sémantique CROSS-MODULE (fondation, sans app métier).

Un SEUL magasin (``core.models.SearchChunk``, pgvector) indexe les fiches de
tout l'ERP — lead, client, devis, installation, ticket, contrat, article de
base de connaissances — pour que la recherche globale (NTAI25) puisse répondre
« sur les DOCUMENTS/fiches » en CITANT ses sources, là où l'agent NL→SQL
existant répond sur des agrégats.

``core`` reste une couche de FONDATION
-------------------------------------
Ce module n'importe AUCUNE app métier. Les modèles indexables sont désignés par
CHAÎNE (``'crm.lead'``) dans :data:`SPECS_PAR_DEFAUT`, résolus paresseusement au
démarrage via ``django.apps``; les valeurs sont lues par ``getattr`` tolérant —
un champ renommé fait DÉGRADER l'extrait, jamais planter l'enregistrement.
Une app peut déclarer/raffiner sa propre spécification via
:func:`register_indexable` dans son ``apps.py`` ``ready()`` (même patron que
``core.search_registry``, dont la ROUTE est réutilisée pour les citations quand
l'app en a déclaré une).

Key-gated, ÉTEINT par défaut
----------------------------
* ``settings.AI_SEMANTIC_INDEX_ENABLED`` (défaut faux) — sans lui, AUCUNE ligne
  d'index n'est écrite : le comportement des écritures métier est
  byte-identique à avant.
* Fournisseur d'embeddings — sans lui, ``embedding`` reste NULL, aucun appel
  réseau n'est fait et la recherche retombe sur le PLEIN-TEXTE (mots-clés).

Tout est BEST-EFFORT : l'indexation ne lève jamais — indexer une fiche ne doit
jamais empêcher de l'enregistrer.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

#: Spécification d'un modèle indexable :
#:   ``titre``   — champs concaténés pour l'intitulé affiché dans une citation ;
#:   ``extrait`` — champs concaténés pour le texte cherché/embeddé ;
#:   ``module``  — périmètre (par défaut l'``app_label``).
#: Les noms de MODÈLES sont des CHAÎNES : aucune app métier n'est importée.
SPECS_PAR_DEFAUT = {
    'crm.lead': {
        'titre': ('nom', 'prenom', 'societe'),
        'extrait': ('societe', 'ville', 'email', 'telephone', 'adresse'),
    },
    'crm.client': {
        'titre': ('nom', 'prenom'),
        'extrait': ('email', 'telephone', 'adresse', 'ice'),
    },
    'ventes.devis': {
        'titre': ('reference',),
        'extrait': ('statut', 'note'),
    },
    'installations.installation': {
        'titre': ('reference',),
        'extrait': ('type_installation', 'site_ville', 'site_adresse'),
    },
    'sav.ticket': {
        'titre': ('reference',),
        'extrait': ('type', 'statut', 'description'),
    },
    'contrats.contrat': {
        'titre': ('reference', 'objet'),
        'extrait': ('type_contrat', 'statut', 'objet'),
    },
    'kb.kbarticle': {
        'titre': ('titre',),
        'extrait': ('categorie', 'tags', 'corps'),
    },
}

#: Longueur maximale de l'extrait stocké — on indexe de quoi retrouver une
#: fiche, pas de quoi recopier une base de connaissances entière.
EXTRAIT_MAX = 2000

#: Registre effectif {label -> spec}. Repeuplé à chaque démarrage de process.
_REGISTRY: dict = dict(SPECS_PAR_DEFAUT)

#: Fournisseur d'embeddings branché par le fondateur (None = no-op complet).
_EMBEDDING_PROVIDER = None


# ── Registre ────────────────────────────────────────────────────────────────

def register_indexable(label, *, titre=(), extrait=(), module=''):
    """Déclare (ou raffine) un modèle indexable, par CHAÎNE ``app.model``."""
    cle = str(label or '').lower()
    if not cle:
        raise ValueError('register_indexable: label requis (« app.model »).')
    if not titre and not extrait:
        raise ValueError(
            f'register_indexable({cle}): au moins un champ titre/extrait.')
    spec = {'titre': tuple(titre), 'extrait': tuple(extrait)}
    if module:
        spec['module'] = module
    _REGISTRY[cle] = spec
    return spec


def unregister_indexable(label):
    """Retire un modèle du registre (utile en test)."""
    _REGISTRY.pop(str(label or '').lower(), None)


def registered_labels():
    """Libellés ``app.model`` actuellement indexables (triés)."""
    return sorted(_REGISTRY)


def reset_registry():
    """Remet le registre à sa valeur par défaut (utile en test)."""
    _REGISTRY.clear()
    _REGISTRY.update(SPECS_PAR_DEFAUT)


# ── Gating (index + embeddings) ─────────────────────────────────────────────

def index_enabled() -> bool:
    """True si l'index sémantique est activé (``AI_SEMANTIC_INDEX_ENABLED``).

    ÉTEINT par défaut : sans clé IA, remplir un index que personne n'interroge
    ne rendrait service à personne et alourdirait chaque écriture.
    """
    from django.conf import settings
    return bool(getattr(settings, 'AI_SEMANTIC_INDEX_ENABLED', False))


def register_embedding_provider(provider):
    """Branche un fournisseur d'embeddings (objet avec ``embed(text)``).

    Tant qu'aucun fournisseur n'est branché, :func:`compute_embedding` est un
    no-op — aucun appel réseau, aucun coût, ``embedding`` reste NULL.
    """
    global _EMBEDDING_PROVIDER
    _EMBEDDING_PROVIDER = provider
    return provider


def clear_embedding_provider():
    """Débranche le fournisseur d'embeddings (utile en test)."""
    global _EMBEDDING_PROVIDER
    _EMBEDDING_PROVIDER = None


def embedding_enabled() -> bool:
    """True si un fournisseur d'embeddings est réellement branché."""
    return _EMBEDDING_PROVIDER is not None


def compute_embedding(texte):
    """Embedding de ``texte``, ou None (no-op sans fournisseur).

    Ne lève jamais : un fournisseur en panne fait retomber l'index sur le
    plein-texte au lieu de casser une écriture métier.
    """
    if not texte or _EMBEDDING_PROVIDER is None:
        return None
    try:
        vecteur = _EMBEDDING_PROVIDER.embed(texte)
    except Exception:  # noqa: BLE001 - best-effort.
        logger.warning('core.ai.search: embedding indisponible', exc_info=True)
        return None
    from core.models import SEARCH_EMBEDDING_DIM

    if not vecteur or len(vecteur) != SEARCH_EMBEDDING_DIM:
        return None
    return list(vecteur)


# ── Construction du texte indexé ────────────────────────────────────────────

def _valeurs(instance, champs):
    """Valeurs non vides des ``champs`` (getattr TOLÉRANT, jamais d'exception)."""
    out = []
    for champ in champs:
        try:
            valeur = getattr(instance, champ, None)
        except Exception:  # noqa: BLE001 - propriété métier en erreur.
            continue
        if valeur in (None, ''):
            continue
        texte = str(valeur).strip()
        if texte and texte not in out:
            out.append(texte)
    return out


def construire_fiche(instance):
    """(titre, extrait, module) d'une instance indexable, ou None.

    Renvoie None si le modèle n'est pas déclaré indexable — le point d'entrée
    unique qui décide « cet objet a-t-il sa place dans l'index ? ».
    """
    label = getattr(getattr(instance, '_meta', None), 'label_lower', '')
    spec = _REGISTRY.get(label)
    if spec is None:
        return None
    titre = ' '.join(_valeurs(instance, spec.get('titre', ())))[:255]
    extrait = ' — '.join(_valeurs(instance, spec.get('extrait', ())))
    module = spec.get('module') or instance._meta.app_label
    return titre, extrait[:EXTRAIT_MAX], module


# ── Indexation ──────────────────────────────────────────────────────────────

def indexer(instance) -> bool:
    """(Ré)indexe UNE instance. Renvoie True si une ligne a été écrite.

    BEST-EFFORT : ne lève jamais. No-op quand l'index est éteint, quand le
    modèle n'est pas déclaré indexable, ou quand l'objet n'a pas de société
    (l'index serait alors non scopable).
    """
    if not index_enabled():
        return False
    try:
        fiche = construire_fiche(instance)
        if fiche is None:
            return False
        company_id = getattr(instance, 'company_id', None)
        if not company_id:
            return False
        titre, extrait, module = fiche
        if not titre and not extrait:
            return False

        from core.models import SearchChunk

        SearchChunk.objects.update_or_create(
            company_id=company_id,
            content_type=instance._meta.label_lower,
            object_id=instance.pk,
            defaults={
                'titre': titre,
                'extrait': extrait,
                'module': module,
                'embedding': compute_embedding(f'{titre}\n{extrait}'),
            },
        )
        return True
    except Exception:  # noqa: BLE001 - indexer ne casse jamais une écriture.
        logger.warning('core.ai.search: indexation impossible', exc_info=True)
        return False


def desindexer(instance) -> int:
    """Retire une instance de l'index (à sa suppression). Ne lève jamais."""
    try:
        label = getattr(getattr(instance, '_meta', None), 'label_lower', '')
        company_id = getattr(instance, 'company_id', None)
        if not label or not company_id or instance.pk is None:
            return 0

        from core.models import SearchChunk

        supprimes, _ = SearchChunk.objects.filter(
            company_id=company_id, content_type=label,
            object_id=instance.pk).delete()
        return supprimes
    except Exception:  # noqa: BLE001 - best-effort.
        logger.warning('core.ai.search: désindexation impossible',
                       exc_info=True)
        return 0


# ── Recherche (vectorielle, avec repli plein-texte) ─────────────────────────

_MOT_RE = re.compile(r"[\w'À-ÿ]{3,}", re.UNICODE)


def _mots(question):
    return [m.lower() for m in _MOT_RE.findall(question or '')][:8]


def _route_pour(label, object_id):
    """Route frontend de la fiche, si l'app en a déclaré une (NTPLT31).

    On n'INVENTE jamais d'URL : sans route déclarée dans
    ``core.search_registry``, la citation porte ``content_type`` + ``object_id``
    et c'est l'appelant qui construit le lien.
    """
    try:
        from core.search_registry import get_entry

        entree = get_entry(label)
        if entree is None or not getattr(entree, 'route', ''):
            return None
        return entree.route.replace('{id}', str(object_id))
    except Exception:  # noqa: BLE001
        return None


def _serialiser(chunk, *, score=None):
    return {
        'content_type': chunk.content_type,
        'object_id': chunk.object_id,
        'module': chunk.module,
        'titre': chunk.titre,
        'extrait': chunk.extrait,
        'route': _route_pour(chunk.content_type, chunk.object_id),
        'score': score,
    }


def rechercher(company, question, *, limit=10, modules=None):
    """Cherche des fiches de ``company`` proches de ``question``.

    Chemin VECTORIEL quand un fournisseur d'embeddings est branché ET que la
    question s'embedde ; sinon REPLI PLEIN-TEXTE sur titre/extrait (mots-clés).
    TOUJOURS scopé société — aucun appel ne peut renvoyer la fiche d'un autre
    tenant. Renvoie une liste de dicts sérialisables.
    """
    from core.models import SearchChunk

    if company is None or not str(question or '').strip():
        return []
    base = SearchChunk.objects.filter(company=company)
    if modules:
        base = base.filter(module__in=list(modules))

    vecteur = compute_embedding(question)
    if vecteur is not None:
        try:
            from pgvector.django import CosineDistance

            proches = (base.exclude(embedding=None)
                       .annotate(distance=CosineDistance('embedding', vecteur))
                       .order_by('distance')[:limit])
            resultats = [
                _serialiser(c, score=round(1.0 - float(c.distance), 4))
                for c in proches
            ]
            if resultats:
                return resultats
        except Exception:  # noqa: BLE001 - repli plein-texte, jamais d'erreur.
            logger.warning('core.ai.search: recherche vectorielle indisponible',
                           exc_info=True)

    from django.db.models import Q

    mots = _mots(question)
    if not mots:
        return []
    filtre = Q()
    for mot in mots:
        filtre |= Q(titre__icontains=mot) | Q(extrait__icontains=mot)
    return [_serialiser(c) for c in base.filter(filtre)[:limit]]


# ── Branchement des signaux (fait par ``core.apps.CoreConfig.ready``) ───────

def _on_saved(sender, instance, **kwargs):
    indexer(instance)


def _on_deleted(sender, instance, **kwargs):
    desindexer(instance)


def connect_signals():
    """Branche ``post_save``/``post_delete`` sur les modèles indexables.

    Ne connecte QUE des modèles réellement installés (un libellé introuvable est
    ignoré) : une connexion vers un modèle absent serait signalée par le check
    Django ``models.E022``. Idempotent grâce aux ``dispatch_uid``.
    """
    from django.apps import apps as django_apps
    from django.db.models.signals import post_delete, post_save

    connectes = []
    for label in registered_labels():
        try:
            modele = django_apps.get_model(label)
        except Exception:  # noqa: BLE001 - app non installée : on ignore.
            continue
        if modele is None:
            continue
        post_save.connect(_on_saved, sender=modele,
                          dispatch_uid=f'core.ai.search.save.{label}')
        post_delete.connect(_on_deleted, sender=modele,
                            dispatch_uid=f'core.ai.search.delete.{label}')
        connectes.append(label)
    return connectes
