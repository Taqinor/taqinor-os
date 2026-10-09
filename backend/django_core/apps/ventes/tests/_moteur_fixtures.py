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
    # QJR162 — le moteur LÈVE désormais quand les totaux canoniques manquent
    # (il ne fabrique plus de chaîne de totaux à taux unique). ``build_quote_data``
    # sert TOUJOURS ``totaux_all`` ; la fixture le sert donc aussi, aligné sur
    # ``all_items`` ci-dessus (l'option « sans », par défaut).
    d.setdefault("totaux_all", d["totaux_sans"])
    d.update(surcharges)
    # QJR623 — ``build_quote_data`` sert TOUJOURS les montants des cases
    # « Modalités de paiement » (au centime, par option) ; le moteur ne fait
    # plus que les imprimer. La fixture les sert donc aussi, calculés par la
    # MÊME fonction du builder, après les surcharges (totaux / termes).
    if "montants_tranches" not in d:
        from apps.ventes.quote_engine.builder import repartition_paiement
        termes = d.get("payment_terms") or {}
        d["montants_tranches"] = {
            branche: repartition_paiement(
                float(d.get(f"total_{branche}") or 0), termes)
            for branche in ("sans", "avec")}
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


def etude_ci_au_kwc_servi(data):
    """AMOT62 — aligne l'étude C&I GREFFÉE (contrat ``etude_ci_preview.json``,
    calculée pour 55 kWc) sur le kWc de l'option que ``data`` SERT : la
    synthèse n'imprime production et taux que d'une étude qui décrit
    l'installation servie (garde 2 %). Mute et renvoie ``data``."""
    from apps.ventes.quote_engine.ci import synthese

    etude_ci = (data.get("etude") or {}).get("etude_ci")
    if etude_ci:
        kwc = synthese._systeme(
            data, {}, synthese._option_servie(data))["kwc"]
        etude_ci["taille"] = dict(etude_ci.get("taille") or {},
                                  retenue_kwc=kwc)
    return data
