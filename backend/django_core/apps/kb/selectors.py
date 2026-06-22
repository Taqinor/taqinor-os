"""Sélecteurs LECTURE SEULE de la Base de connaissances.

Point d'entrée cross-app : enrichissent les liens d'un article
(``KbArticleLien``) en appelant le sélecteur de l'app CIBLE quand elle en expose
un — jamais en important ses ``models``/``views`` (voir CLAUDE.md, frontière
cross-app). Tous les imports cross-app sont fonction-locaux pour éviter les
cycles. Quand une app cible n'a pas de sélecteur exploitable, on DÉGRADE
proprement : on renvoie le ``libelle`` mis en cache et les ids stockés, sans
rien importer.
"""
from .models import KbArticleLien


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
