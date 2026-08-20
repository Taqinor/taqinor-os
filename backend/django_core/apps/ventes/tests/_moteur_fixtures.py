"""Fixtures PURES des tests « document RENDU » du moteur de devis.

Le préfixe ``_`` garde ce module hors de la découverte Django (``test*.py``) :
il ne porte aucun test, seulement les fabriques de données et les deux
raccourcis de rendu HTML utilisés par ``test_moteur_zero_invention``.

POURQUOI DU HTML ET PAS DES FONCTIONS : l'audit du 18/08/2026 a laissé passer
un « 87,4 % » codé en dur parce que tous les tests interrogeaient des
fonctions, jamais le document. Ici on rend le HTML EXACT qui part chez
WeasyPrint (legacy) ou dans le gabarit résidentiel, puis on y cherche — ou on
y refuse — une chaîne. Aucune BD, aucun WeasyPrint : exécutable sur l'hôte.
"""

from apps.ventes.quote_engine import generate_devis_premium as legacy
from apps.ventes.quote_engine.residential import (
    render as residential_render,
    renderer as residential_renderer,
    sample_data,
)


def donnees_legacy(variante="deux", **surcharges):
    """Dict d'entrée du moteur legacy, forme ``build_quote_data``.

    Part de l'échantillon résidentiel (la même composition que le renderer
    redessiné) et complète les seules clés que le legacy exige en plus.
    """
    d = dict(sample_data.build(variante))
    d.setdefault("eco_s_monthly", list(d["eco_a_monthly"]))
    d.setdefault("eco_a_cumul", d["eco_a_ann"])
    d.setdefault("scenario", "Les deux (Sans + Avec)")
    d.setdefault("all_items", list(d["sans_items"]))
    d.update(surcharges)
    return d


def html_legacy(variante="deux", **surcharges):
    """HTML EXACT envoyé à WeasyPrint par le moteur legacy (3 pages)."""
    return legacy.render_html_for(donnees_legacy(variante, **surcharges))


def html_onepage(**surcharges):
    """HTML EXACT du format UNE PAGE."""
    surcharges.setdefault("pdf_mode", "onepage")
    return legacy.render_html_for(donnees_legacy("deux", **surcharges))


def html_residentiel(variante="deux", **surcharges):
    """HTML EXACT du renderer résidentiel redessiné (page 1 / options / trust)."""
    d = residential_renderer._augment(donnees_residentiel(variante, **surcharges))
    return residential_render.build_html(d)


def donnees_residentiel(variante="deux", **surcharges):
    d = dict(sample_data.build(variante))
    d.update(surcharges)
    return d
