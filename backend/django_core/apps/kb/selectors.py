"""Sélecteurs LECTURE SEULE de la Base de connaissances.

Point d'entrée cross-app : enrichissent les liens d'un article
(``KbArticleLien``) en appelant le sélecteur de l'app CIBLE quand elle en expose
un — jamais en important ses ``models``/``views`` (voir CLAUDE.md, frontière
cross-app). Tous les imports cross-app sont fonction-locaux pour éviter les
cycles. Quand une app cible n'a pas de sélecteur exploitable, on DÉGRADE
proprement : on renvoie le ``libelle`` mis en cache et les ids stockés, sans
rien importer.
"""
import re

from django.db.models import Exists, OuterRef, Q

from .models import (
    BlocReutilisable,
    KbArticle,
    KbArticleAcl,
    KbArticleChunk,
    KbArticleLien,
    KbLecture,
    KbLectureObligatoire,
    KbParcoursArticle,
    KbParcoursAssignation,
    KbRechercheVide,
)


# ── Droits d'accès par rôle (KB7) + sections XKB9 ───────────────────────────

def visible_articles_qs(queryset, user):
    """Restreint un queryset d'articles aux articles VISIBLES pour ``user``.

    RÉTRO-COMPATIBLE (KB7, ``visibilite='workspace'``) : un article SANS
    aucune ligne ACL de rôle reste visible de tous (comportement historique
    préservé — KB2/KB3 inchangés). Dès qu'au moins une ligne ACL de LECTURE
    par-RÔLE existe pour un article ``workspace``, seuls les paliers listés
    peuvent le lire.

    XKB9 — sections additionnelles, évaluées AVANT la règle KB7 ci-dessus
    (qui ne s'applique qu'aux articles ``workspace``) :
      * ``prive`` — visible du SEUL auteur (notes personnelles) ;
      * ``partage`` — visible des membres listés en ACL nominative
        (``utilisateur``) + l'auteur.

    Le palier ``admin`` (``CustomUser.menu_tier``) passe TOUJOURS, quelle que
    soit la section : un administrateur voit tout. Implémentée sans N+1
    (annotations ``Exists``/``Q`` composées en une seule requête). ``user``
    peut être ``None`` (palier inconnu) : seuls les articles ``workspace``
    sans ACL restent alors visibles (aucun privé/partagé, aucun user-id).
    """
    tier = getattr(user, 'menu_tier', None) if user is not None else None
    if tier == 'admin':
        return queryset
    user_id = getattr(user, 'id', None) if user is not None else None

    # Article restreint en LECTURE (workspace) = il porte au moins une ligne
    # ACL de lecture PAR-RÔLE.
    a_restriction_role = KbArticleAcl.objects.filter(
        article=OuterRef('pk'), niveau=KbArticleAcl.Niveau.LECTURE,
        role__gt='')
    a_acl_utilisateur = KbArticleAcl.objects.filter(
        article=OuterRef('pk'), niveau=KbArticleAcl.Niveau.LECTURE,
        utilisateur_id=user_id)
    qs = queryset.annotate(
        _kb_acl_restreint=Exists(a_restriction_role),
        _kb_membre_partage=Exists(a_acl_utilisateur))

    workspace_visible = Q(visibilite=KbArticle.Visibilite.WORKSPACE)
    if tier:
        autorise = a_restriction_role.filter(role=tier)
        qs = qs.annotate(_kb_acl_autorise=Exists(autorise))
        workspace_visible &= (
            Q(_kb_acl_restreint=False) | Q(_kb_acl_autorise=True))
    else:
        workspace_visible &= Q(_kb_acl_restreint=False)

    prive_visible = Q(visibilite=KbArticle.Visibilite.PRIVE)
    partage_visible = Q(visibilite=KbArticle.Visibilite.PARTAGE)
    if user_id:
        prive_visible &= Q(auteur_id=user_id)
        partage_visible &= (Q(auteur_id=user_id) | Q(_kb_membre_partage=True))
    else:
        # Utilisateur inconnu : ni privé ni partagé n'est visible.
        prive_visible &= Q(pk__isnull=True)
        partage_visible &= Q(pk__isnull=True)

    return qs.filter(workspace_visible | prive_visible | partage_visible)


def acls_for_article(article):
    """Lignes ACL d'un article (QuerySet scopé société, ordonné par id)."""
    return KbArticleAcl.objects.filter(
        article=article, company=article.company).order_by('id')


def resume_lecture(article):
    """Résumé de lecture d'un article : nombre de lecteurs + qui (KB7).

    Renvoie ``{nombre, lecteurs: [{utilisateur, nom, lu_le}, ...]}`` scopé
    société. Lecture seule ; sert au tableau de bord « qui a lu cet article ».
    """
    lectures = (KbLecture.objects
                .filter(article=article, company=article.company)
                .select_related('utilisateur')
                .order_by('-lu_le', '-id'))
    lecteurs = []
    for lecture in lectures:
        utilisateur = lecture.utilisateur
        lecteurs.append({
            'utilisateur': utilisateur.id if utilisateur else None,
            'nom': (utilisateur.get_full_name() or utilisateur.get_username())
            if utilisateur else '',
            'lu_le': lecture.lu_le,
        })
    return {'nombre': len(lecteurs), 'lecteurs': lecteurs}


def peut_editer(article, user):
    """XKB14 — ``user`` peut-il déverrouiller/éditer un article verrouillé ?

    Le palier ``admin`` passe toujours. Sinon, il faut une ligne ACL
    d'ÉDITION explicite pour le palier de l'utilisateur OU son id nominatif
    (XKB9). Sans aucune ligne ACL d'édition pour cet article, PERSONNE
    d'autre que l'admin ne peut déverrouiller (le verrou protège vraiment).
    """
    tier = getattr(user, 'menu_tier', None) if user is not None else None
    if tier == 'admin':
        return True
    user_id = getattr(user, 'id', None) if user is not None else None
    qs = KbArticleAcl.objects.filter(
        article=article, niveau=KbArticleAcl.Niveau.EDITION)
    if tier:
        qs = qs.filter(Q(role=tier) | Q(utilisateur_id=user_id))
    else:
        qs = qs.filter(utilisateur_id=user_id) if user_id else qs.none()
    return qs.exists()


# ── XKB16 — Statistiques KB & recherches infructueuses ──────────────────────

def rapport_top_consultes(company, limit=10):
    """XKB16 — Articles les PLUS consultés d'une société (``vues`` décroissant).

    Renvoie ``[{id, titre, vues}, ...]``. Scopé société, lecture seule.
    """
    qs = (KbArticle.objects.filter(company=company)
          .order_by('-vues', '-id')[:limit])
    return [{'id': a.id, 'titre': a.titre, 'vues': a.vues} for a in qs]


def rapport_moins_consultes(company, limit=10):
    """XKB16 — Articles les MOINS consultés d'une société (``vues`` croissant).

    Renvoie ``[{id, titre, vues}, ...]``. Scopé société, lecture seule.
    """
    qs = (KbArticle.objects.filter(company=company)
          .order_by('vues', 'id')[:limit])
    return [{'id': a.id, 'titre': a.titre, 'vues': a.vues} for a in qs]


def rapport_lacunes_connaissance(company, limit=50):
    """XKB16 — « Lacunes de connaissance » : termes cherchés jamais servis.

    Regroupe ``KbRechercheVide`` par ``terme`` (insensible à la casse),
    compte les occurrences, trie par fréquence décroissante — les termes les
    plus demandés en premier (priorité de rédaction). Scopé société.
    """
    from django.db.models import Count
    from django.db.models.functions import Lower

    qs = (KbRechercheVide.objects
          .filter(company=company)
          .annotate(terme_norm=Lower('terme'))
          .values('terme_norm')
          .annotate(occurrences=Count('id'))
          .order_by('-occurrences', 'terme_norm')[:limit])
    return [
        {'terme': row['terme_norm'], 'occurrences': row['occurrences']}
        for row in qs
    ]


# ── XKB15 — Favoris & récents ────────────────────────────────────────────────

def recents_pour_utilisateur(user, limit=10):
    """XKB15 — Articles récemment consultés par ``user`` (depuis
    ``KbLecture.lu_le``), les plus récents en premier. Strictement personnel :
    ne remonte QUE les lectures de l'utilisateur courant. Renvoie une liste de
    dicts ``{id, titre, statut, lu_le}``."""
    if user is None or not getattr(user, 'id', None):
        return []
    lectures = (KbLecture.objects
                .filter(utilisateur=user)
                .select_related('article')
                .order_by('-lu_le', '-id')[:limit])
    return [
        {
            'id': lecture.article.id,
            'titre': lecture.article.titre,
            'statut': lecture.article.statut,
            'lu_le': lecture.lu_le,
        }
        for lecture in lectures
    ]


# ── XKB14 — Vérification, péremption & verrou ───────────────────────────────

def rapport_peremption(company):
    """XKB14 — Articles PÉRIMÉS d'une société : ``verifie_jusqua`` dépassée
    OU jamais vérifiés et non modifiés/non lus depuis longtemps.

    Renvoie une liste de dicts ``{id, titre, verifie_jusqua}`` triée par
    ``date_modification`` croissante (le plus ancien d'abord — le plus
    urgent à re-revoir). Scopé société. Lecture seule.
    """
    from django.utils import timezone
    now = timezone.now()
    qs = (KbArticle.objects
          .filter(company=company, verifie_jusqua__isnull=False,
                  verifie_jusqua__lt=now)
          .order_by('date_modification'))
    return [
        {'id': a.id, 'titre': a.titre, 'verifie_jusqua': a.verifie_jusqua}
        for a in qs
    ]


# ── XKB11 — Liens internes article↔article + rétroliens ────────────────────

def retroliens(article):
    """XKB11 — Articles qui pointent VERS ``article`` (liens entrants).

    Recherche inverse scopée société : tous les ``KbArticleLien`` de type
    ``ARTICLE`` dont ``cible_id == article.id`` dans la MÊME société, avec le
    libellé/statut de l'article SOURCE (celui qui porte le lien). Évite le
    contenu orphelin — affiché en panneau sur la fiche article. Lecture
    seule, pas de N+1 (une seule requête + ``select_related``).
    """
    liens = (KbArticleLien.objects
             .filter(
                 company=article.company,
                 type_cible=KbArticleLien.TypeCible.ARTICLE,
                 cible_id=article.id)
             .select_related('article')
             .order_by('article_id'))
    out = []
    seen = set()
    for lien in liens:
        source = lien.article
        if source.id in seen:
            continue
        seen.add(source.id)
        out.append({
            'id': source.id,
            'titre': source.titre,
            'statut': source.statut,
        })
    return out


# ── XKB10 — Éditeur Markdown : sommaire auto ────────────────────────────────

_ATX_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*#*\s*$')


def sommaire_article(article):
    """XKB10 — Sommaire auto : liste des titres Markdown (ATX ``#``…``######``)
    du corps de l'article, dans l'ordre d'apparition.

    Renvoie ``[{niveau, texte}, ...]``. Pas de dépendance markdown côté
    serveur (pas de nouvelle dépendance payante) : un simple parseur de ligne
    suffit pour l'extraction de titres ATX, qui est le seul besoin du
    sommaire. Ne s'applique qu'aux articles ``corps_format == 'markdown'`` —
    un article texte brut renvoie un sommaire vide (aucun titre structuré).
    """
    if article.corps_format != KbArticle.CorpsFormat.MARKDOWN:
        return []
    sommaire = []
    for ligne in (article.corps or '').splitlines():
        m = _ATX_HEADING_RE.match(ligne.strip())
        if m:
            sommaire.append({
                'niveau': len(m.group(1)),
                'texte': m.group(2).strip(),
            })
    return sommaire


# ── XKB8 — Arborescence d'articles (pages imbriquées) ──────────────────────

def arbre_articles(queryset):
    """XKB8 — Construit l'arbre (liste de dicts imbriqués) d'un queryset
    d'articles DÉJÀ scopé société + visibilité (``visible_articles_qs``).

    Renvoie la liste des racines (``parent`` absent du queryset visible, y
    compris un parent existant mais invisible pour l'utilisateur — dégrade
    proprement en le traitant comme racine plutôt que de faire planter
    l'arbre), chacune portant une clé ``enfants`` triée par ``(ordre, id)``,
    récursivement. Une seule requête (pas de N+1) : le queryset est
    matérialisé une fois puis assemblé en mémoire.
    """
    articles = list(queryset.order_by('ordre', 'id'))
    by_id = {a.id: a for a in articles}
    children_of = {}
    roots = []
    for article in articles:
        if article.parent_id and article.parent_id in by_id:
            children_of.setdefault(article.parent_id, []).append(article)
        else:
            roots.append(article)

    def _node(article):
        enfants = children_of.get(article.id, [])
        return {
            'id': article.id,
            'titre': article.titre,
            'statut': article.statut,
            'parent': article.parent_id,
            'ordre': article.ordre,
            'enfants': [_node(e) for e in enfants],
        }

    return [_node(a) for a in roots]


# ── XKB7 — Lecture obligatoire ─────────────────────────────────────────────

def _assignees_for_role(company, role_cible):
    """Utilisateurs actifs de la société dont le palier ``menu_tier`` égale
    ``role_cible``. Lecture seule, jamais d'import cross-app (authentication
    est une app fondation, importable directement — voir CLAUDE.md)."""
    from authentication.models import CustomUser
    return [
        u for u in CustomUser.objects.filter(company=company, is_active=True)
        if u.menu_tier == role_cible
    ]


def assignees_for_assignation(assignation):
    """Liste des utilisateurs concernés par UNE ligne ``KbLectureObligatoire``.

    Un utilisateur explicite → liste à un élément. Un palier de rôle → tous les
    utilisateurs actifs de la société portant ce palier (``menu_tier``).
    """
    if assignation.utilisateur_id:
        return [assignation.utilisateur]
    if assignation.role_cible:
        return _assignees_for_role(assignation.company, assignation.role_cible)
    return []


def rapport_conformite_article(article):
    """XKB7 — Rapport de conformité de lecture obligatoire d'un article.

    Renvoie ``{article, lus: [...], non_lus: [...]}`` : pour chaque assignation
    (utilisateur explicite ou palier de rôle résolu en utilisateurs), classe
    chacun des concernés comme lu (a une ``KbLecture``) ou non-lu. Un même
    utilisateur concerné par plusieurs assignations n'apparaît qu'une fois.
    Scopé société via ``article.company``.
    """
    assignations = (KbLectureObligatoire.objects
                    .filter(article=article, company=article.company)
                    .select_related('utilisateur'))
    lecteurs_ids = set(
        KbLecture.objects.filter(article=article, company=article.company)
        .values_list('utilisateur_id', flat=True))
    vus, lus, non_lus = set(), [], []
    for assignation in assignations:
        for user in assignees_for_assignation(assignation):
            if user.id in vus:
                continue
            vus.add(user.id)
            entry = {
                'utilisateur': user.id,
                'nom': user.get_full_name() or user.get_username(),
                'echeance': assignation.echeance,
            }
            if user.id in lecteurs_ids:
                lus.append(entry)
            else:
                non_lus.append(entry)
    return {'article': article.id, 'lus': lus, 'non_lus': non_lus}


def liens_for_article(article):
    """Liens d'un article (QuerySet scopé société, ordonné par id).

    Lecture seule. La société est portée par l'article : on filtre aussi sur
    ``article.company`` par sécurité même si le FK ``article`` la garantit déjà.
    """
    return KbArticleLien.objects.filter(
        article=article, company=article.company).order_by('id')


def articles_pour_cible(company, type_cible, cible_id):
    """Articles liés à une cible (produit/équipement/type d'intervention).

    Recherche inverse scopée société : pour un écran SAV / chantier qui demande
    « quels articles sont liés au produit X », renvoie la liste des articles
    rattachés à ``(type_cible, cible_id)`` sous forme de dicts
    ``{id, titre, statut}``. Lecture seule, jamais d'import cross-app.
    """
    liens = (KbArticleLien.objects
             .filter(company=company, type_cible=type_cible, cible_id=cible_id)
             .select_related('article')
             .order_by('article_id'))
    out = []
    seen = set()
    for lien in liens:
        article = lien.article
        if article.id in seen:
            continue
        seen.add(article.id)
        out.append({
            'id': article.id,
            'titre': article.titre,
            'statut': article.statut,
        })
    return out


def _label_produit(company, cible_id):
    """Libellé enrichi d'un produit via ``stock.selectors`` (ou None).

    Import fonction-local : on ne touche JAMAIS ``stock.models`` directement.
    Renvoie le ``nom`` du produit scopé société, ou None si l'app ne peut pas
    l'enrichir (produit absent / hors société / sélecteur indisponible).
    """
    try:
        from apps.stock import selectors as stock_selectors
    except Exception:  # pragma: no cover - défensif (app absente)
        return None
    try:
        produit = stock_selectors.get_produit_scoped(company, cible_id)
    except Exception:  # pragma: no cover - défensif (cible introuvable)
        return None
    if produit is None:
        return None
    return getattr(produit, 'nom', None) or None


# Enrichisseurs par type de cible. Une entrée n'existe QUE si l'app cible expose
# un sélecteur de lecture exploitable : `equipement` (sav) n'a pas de
# selectors.py aujourd'hui et `type_intervention` n'a pas d'app cible → ces deux
# types dégradent au libellé stocké, sans aucun import.
_ENRICHERS = {
    KbArticleLien.TypeCible.PRODUIT: _label_produit,
}


def liens_enrichis(article):
    """Liste de dicts {id, type_cible, cible_id, libelle, source} d'un article.

    Pour chaque lien : si l'app cible expose un enrichisseur, on s'en sert pour
    récupérer un libellé frais (``source='live'``) ; sinon — ou si
    l'enrichissement renvoie vide — on retombe sur le ``libelle`` stocké
    (``source='stored'``). Aucune exception ne remonte : un enrichisseur qui
    échoue dégrade au libellé stocké.
    """
    out = []
    for lien in liens_for_article(article):
        libelle = lien.libelle
        source = 'stored'
        enricher = _ENRICHERS.get(lien.type_cible)
        if enricher is not None:
            try:
                fresh = enricher(lien.company, lien.cible_id)
            except Exception:  # pragma: no cover - défensif
                fresh = None
            if fresh:
                libelle = fresh
                source = 'live'
        out.append({
            'id': lien.id,
            'type_cible': lien.type_cible,
            'cible_id': lien.cible_id,
            'libelle': libelle,
            'source': source,
        })
    return out


# ── XKB20 — Récupération RAG des articles KB, respectueuse des ACL ─────────

def retrieve_chunks(user, query, *, limit=5):
    """XKB20 — Outil de récupération RAG : top-k fragments d'articles KB pour
    une question, RESPECTUEUX DES ACL.

    Calqué sur ``ged.selectors.retrieve_chunks`` (FG352) : renvoie les
    ``limit`` fragments (``KbArticleChunk``) les plus proches de la question
    par distance cosinus dans le MÊME magasin pgvector partagé. Les fragments
    sont bornés DÈS LE PREMIER JOUR aux articles que ``user`` peut VOIR — via
    ``visible_articles_qs`` (KB7 ACL par-rôle + XKB9 sections
    workspace/privé/partagé) — jamais un fragment d'un article restreint pour
    un utilisateur non autorisé.

    KEY-GATED no-op : sans clé d'embedding ou si la question n'est pas
    vectorisable, renvoie une liste vide (aucun appel réseau, aucun coût). Le
    résultat est une liste de ``KbArticleChunk`` (plus proche d'abord),
    chacun annoté de ``distance``. Import fonction-local de ``apps.ged`` :
    lecture d'un SERVICE (jamais ses models/views) pour réutiliser le MÊME
    provider d'embedding — pas de second pipeline RAG.
    """
    from apps.ged import services as ged_services

    if not ged_services.embedding_enabled():
        return []
    if not query or not str(query).strip():
        return []
    vec = ged_services.compute_embedding(str(query))
    if vec is None:
        return []
    from pgvector.django import CosineDistance

    # ACL DÈS LE PREMIER JOUR : ne considère que les articles visibles pour
    # cet utilisateur (KB7 + XKB9), jamais toute la table. ``visible_articles_qs``
    # ne fait PAS elle-même le scoping société (elle attend un queryset déjà
    # borné, comme les autres appelants) — on le pose ici en premier pour
    # empêcher toute fuite cross-société (un admin d'une autre société ne doit
    # JAMAIS voir les fragments d'une société qui n'est pas la sienne).
    company_id = getattr(user, 'company_id', None)
    base_qs = KbArticle.objects.filter(company_id=company_id) \
        if company_id is not None else KbArticle.objects.none()
    visible_ids = visible_articles_qs(
        base_qs, user).values_list('id', flat=True)
    base = (KbArticleChunk.objects
            .select_related('article')
            .filter(article_id__in=visible_ids, embedding__isnull=False))
    return list(base.annotate(distance=CosineDistance('embedding', vec))
                .order_by('distance')[:max(1, int(limit))])


# ── XKB22 — Parcours de lecture d'intégration ───────────────────────────────

def articles_ordonnes_parcours(parcours):
    """XKB22 — Articles ORDONNÉS d'un parcours (QuerySet, scopé société)."""
    return (KbParcoursArticle.objects
            .filter(parcours=parcours, company=parcours.company)
            .select_related('article')
            .order_by('ordre', 'id'))


def progression_parcours(assignation):
    """XKB22 — Progression ARTICLE PAR ARTICLE d'une assignation de parcours.

    Se déduit en LECTURE SEULE des ``KbLecture`` déjà existantes de
    l'utilisateur assigné sur chaque article ordonné du parcours — aucun
    second mécanisme de suivi. Renvoie un dict :
    ``{parcours, utilisateur, articles: [{article, titre, ordre, lu, lu_le}],
    nombre_lus, nombre_total, complet}``. Scopé société via
    ``assignation.company``.
    """
    membres = articles_ordonnes_parcours(assignation.parcours)
    lectures = {
        lecture.article_id: lecture.lu_le
        for lecture in KbLecture.objects.filter(
            utilisateur=assignation.utilisateur,
            article__in=[m.article_id for m in membres])
    }
    articles = []
    nombre_lus = 0
    for membre in membres:
        lu_le = lectures.get(membre.article_id)
        if lu_le is not None:
            nombre_lus += 1
        articles.append({
            'article': membre.article_id,
            'titre': membre.article.titre,
            'ordre': membre.ordre,
            'lu': lu_le is not None,
            'lu_le': lu_le,
        })
    nombre_total = len(articles)
    return {
        'parcours': assignation.parcours_id,
        'utilisateur': assignation.utilisateur_id,
        'articles': articles,
        'nombre_lus': nombre_lus,
        'nombre_total': nombre_total,
        'complet': nombre_total > 0 and nombre_lus == nombre_total,
    }


def assignations_pour_utilisateur(company, utilisateur):
    """XKB22 — Assignations de parcours d'UN utilisateur (scopé société).

    Sert à l'écran RH (« statut de complétion visible RH ») via ce sélecteur
    UNIQUEMENT — ``rh`` ne lit jamais les models/views de ``kb`` directement.
    """
    return (KbParcoursAssignation.objects
            .filter(company=company, utilisateur=utilisateur)
            .select_related('parcours')
            .order_by('-date_creation', '-id'))


# ── ZGED11 — Propriétés d'article (héritage) + vues d'items ────────────────

def proprietes_effectives(article):
    """ZGED11 — Propriétés RÉSOLUES d'un article : les siennes propres,
    complétées par celles de ses ANCÊTRES pour toute clé qu'il ne définit
    pas lui-même (héritage — « partagées par tous les sous-articles »).

    L'ancêtre le PLUS PROCHE gagne pour une clé donnée (un sous-article peut
    surcharger localement une propriété héritée sans la redéfinir sur tous
    les niveaux). Borné à 1000 remontées pour ne jamais boucler sur des
    données corrompues (même garde que ``validate_parent``/anti-cycle).
    """
    effectives = {}
    cursor = article.parent
    for _ in range(1000):
        if cursor is None:
            break
        for cle, val in (cursor.proprietes or {}).items():
            effectives.setdefault(cle, val)
        cursor = cursor.parent
    # Les propriétés PROPRES de l'article gagnent toujours sur l'hérité.
    effectives.update(article.proprietes or {})
    return effectives


def items_parcours_vue(queryset, *, vue, propriete=None):
    """ZGED11 — Sous-articles d'un queryset (DÉJÀ scopé société+visibilité)
    rendus comme une COLLECTION structurée pour une ``vue`` donnée.

    * ``liste``/``cartes`` : chaque item porte ses ``proprietes_effectives``
      (aucun regroupement) — le frontend rend les deux à partir des MÊMES
      données, seule la disposition change.
    * ``kanban`` : regroupé par la valeur de ``propriete`` (une propriété de
      type ``choice`` typiquement, ex. « Statut ») — une clé ``'__aucune__'``
      accueille les items sans cette propriété renseignée.
    * ``calendrier`` : ne garde que les items dont ``propriete`` (typiquement
      une propriété ``date``) est renseignée, groupés par cette valeur.

    Renvoie une liste de dicts ``{id, titre, proprietes, groupe?}`` (vue
    liste/cartes) ou un dict ``{groupe: [items...]}`` (kanban/calendrier).
    """
    items = []
    for article in queryset.order_by('ordre', 'id'):
        effectives = proprietes_effectives(article)
        items.append({
            'id': article.id,
            'titre': article.titre,
            'proprietes': effectives,
        })

    if vue in ('liste', 'cartes'):
        return items

    if vue == 'kanban':
        groupes = {}
        for item in items:
            valeur = item['proprietes'].get(propriete) if propriete else None
            cle = valeur if valeur not in (None, '') else '__aucune__'
            groupes.setdefault(cle, []).append(item)
        return groupes

    if vue == 'calendrier':
        groupes = {}
        for item in items:
            valeur = item['proprietes'].get(propriete) if propriete else None
            if valeur in (None, ''):
                continue
            groupes.setdefault(valeur, []).append(item)
        return groupes

    return items


# ── ZGED12 — Presse-papiers Knowledge (blocs réutilisables) ─────────────────

def blocs_visibles(company, user):
    """ZGED12 — Blocs visibles pour ``user`` : ses blocs PERSONNELS + tous les
    blocs SOCIÉTÉ (scopé société, jamais cross-tenant)."""
    from django.db.models import Q
    user_id = getattr(user, 'id', None)
    qs = BlocReutilisable.objects.filter(company=company)
    return qs.filter(
        Q(portee=BlocReutilisable.Portee.SOCIETE)
        | Q(portee=BlocReutilisable.Portee.PERSONNEL, created_by_id=user_id))


# ── ZMFG5 — Pré-remplissage des instructions d'intervention SAV ────────────

def article_pour_mot_cle(company, user, texte_recherche, *, limit=1):
    """ZMFG5 — Article(s) KB pertinent(s) pour un texte de recherche (ex. le
    type/nom d'une cause de panne SAV), pour pré-remplir l'onglet
    « Instructions » d'un ticket. Recherche par correspondance de mots-clés
    SIMPLE sur titre + corps (aucune dépendance à un provider d'embedding —
    fonctionne sans clé, contrairement à ``retrieve_chunks``), restreinte aux
    articles VISIBLES pour ``user`` (KB7/XKB9) et PUBLIÉS.

    Renvoie une liste de dicts légers ``[{'id', 'titre', 'extrait'}, …]``
    (jamais l'objet ORM, pour ne pas fuiter le modèle hors de l'app) — vide
    si le texte est vide ou qu'aucun article ne correspond (dégradation
    propre, no-op)."""
    texte = (texte_recherche or '').strip()
    if not texte:
        return []
    mots = {m for m in re.findall(r"[a-zà-ÿ0-9]{3,}", texte.lower())}
    if not mots:
        return []

    qs = visible_articles_qs(
        KbArticle.objects.filter(
            company=company, statut=KbArticle.Statut.PUBLIE),
        user,
    )
    scored = []
    for art in qs:
        hay = f'{art.titre} {art.corps}'.lower()
        score = sum(1 for mot in mots if mot in hay)
        if score > 0:
            scored.append((score, art))
    scored.sort(key=lambda pair: (-pair[0], -pair[1].pk))
    return [
        {'id': art.id, 'titre': art.titre, 'extrait': (art.corps or '')[:500]}
        for _score, art in scored[:max(1, int(limit))]
    ]


# ── XSAV22 — Déflection KB sur le portail client ────────────────────────────

def suggestions_portail(company, texte, *, limit=5):
    """XSAV22 — Articles KB à suggérer sur le formulaire d'ouverture de
    ticket du portail client, pendant la saisie du sujet.

    Point d'entrée cross-app pour ``apps.portail``/``apps.compta`` (frontière
    CLAUDE.md — jamais un import direct de ``apps.kb.models``) : le client
    portail n'est PAS un ``user`` ERP (pas de rôle/ACL KB7), donc restreint
    à la whitelist EXPLICITE ``visible_portail=True`` (défaut FAUX — un
    article n'apparaît sur le portail qu'après opt-in manuel) ET publié
    (``statut=PUBLIE``). Recherche simple ``icontains`` titre/corps (même
    mécanique que ``KbArticleViewSet.search_fields``, KB3).

    Renvoie une liste de dicts légers ``[{'id', 'titre', 'extrait'}, …]`` —
    jamais l'objet ORM. Vide si le texte est vide (dégradation propre, pas
    d'exception)."""
    texte = (texte or '').strip()
    if not texte or company is None:
        return []
    qs = (KbArticle.objects
          .filter(company=company, statut=KbArticle.Statut.PUBLIE,
                  visible_portail=True)
          .filter(Q(titre__icontains=texte) | Q(corps__icontains=texte))
          .order_by('-consultations_portail_ticket', '-vues', 'id'))
    return [
        {'id': art.id, 'titre': art.titre, 'extrait': (art.corps or '')[:500]}
        for art in qs[:max(1, int(limit))]
    ]


def consultations_portail_total(company):
    """XSAV22 — Somme des consultations d'articles KB déclenchées depuis le
    portail, SCOPÉE à ``company`` (jamais d'agrégat cross-tenant). Point
    d'entrée pour ``apps.sav.selectors.ratio_deflection_kb`` (ratio de
    déflection)."""
    if company is None:
        return 0
    from django.db.models import Sum
    total = (KbArticle.objects.filter(company=company)
             .aggregate(total=Sum('consultations_portail_ticket'))['total'])
    return total or 0
