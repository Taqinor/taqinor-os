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
    KbArticle,
    KbArticleAcl,
    KbArticleLien,
    KbLecture,
    KbLectureObligatoire,
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
