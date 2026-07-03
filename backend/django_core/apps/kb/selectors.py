"""Sélecteurs LECTURE SEULE de la Base de connaissances.

Point d'entrée cross-app : enrichissent les liens d'un article
(``KbArticleLien``) en appelant le sélecteur de l'app CIBLE quand elle en expose
un — jamais en important ses ``models``/``views`` (voir CLAUDE.md, frontière
cross-app). Tous les imports cross-app sont fonction-locaux pour éviter les
cycles. Quand une app cible n'a pas de sélecteur exploitable, on DÉGRADE
proprement : on renvoie le ``libelle`` mis en cache et les ids stockés, sans
rien importer.
"""
from django.db.models import Exists, OuterRef, Q

from .models import (
    KbArticleAcl,
    KbArticleLien,
    KbLecture,
    KbLectureObligatoire,
)


# ── Droits d'accès par rôle (KB7) ──────────────────────────────────────────

def visible_articles_qs(queryset, user):
    """Restreint un queryset d'articles aux articles VISIBLES pour ``user``.

    Règle RÉTRO-COMPATIBLE : un article SANS aucune ligne ACL reste visible de
    tous (comportement historique préservé — KB2/KB3 inchangés). Dès qu'au moins
    une ligne ACL de LECTURE existe pour un article, seuls les paliers listés
    peuvent le lire. Le palier ``admin`` (accesseur de rôle faisant autorité
    ``CustomUser.menu_tier``) passe TOUJOURS : un administrateur voit tout.

    Implémentée en une seule requête (pas de N+1) : un article passe s'il
    *n'a aucune* ACL de lecture, OU s'il a une ACL de lecture pour le palier de
    l'utilisateur. ``user`` peut être ``None`` (palier inconnu) : seuls les
    articles sans ACL restent alors visibles.
    """
    tier = getattr(user, 'menu_tier', None) if user is not None else None
    if tier == 'admin':
        return queryset
    # Article restreint en LECTURE = il porte au moins une ligne ACL de lecture.
    a_restriction = KbArticleAcl.objects.filter(
        article=OuterRef('pk'), niveau=KbArticleAcl.Niveau.LECTURE)
    qs = queryset.annotate(_kb_acl_restreint=Exists(a_restriction))
    if not tier:
        # Palier inconnu : seuls les articles sans restriction restent visibles.
        return qs.filter(_kb_acl_restreint=False)
    # Article autorisé pour CE palier = il porte une ligne ACL de lecture pour lui.
    autorise = a_restriction.filter(role=tier)
    return qs.annotate(_kb_acl_autorise=Exists(autorise)).filter(
        Q(_kb_acl_restreint=False) | Q(_kb_acl_autorise=True))


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
