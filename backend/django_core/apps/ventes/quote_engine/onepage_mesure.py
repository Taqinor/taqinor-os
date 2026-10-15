"""CAD177 — mesure du dernier bloc (ligne de conditions) du une-page.

Quand WeasyPrint jette la fin du flux de la zone ``overflow:hidden`` hors de la
page A4, la ligne de conditions est présente dans le HTML mais absente de la
page composée : on la mesure alors sur la page de mesure haute, au lieu de
déclarer à tort que le document tient (nocturne 14/10, AMOT20).
"""
from html import unescape


def bas_avec_conditions(page, html, formes, bas_totaux, html_cls):
    from . import generate_devis_premium as G
    bas_fin = G._bas_bloc_fin(page)
    if bas_totaux is None:
        return bas_totaux
    if bas_fin is not None:
        return max(bas_totaux, bas_fin)
    if any(f in html + unescape(html) for f in G._formes_bloc_fin()):
        bas_haute = G._bas_totaux_page_haute(html_cls, html, formes)
        if bas_haute is not None:
            return max(bas_totaux, bas_haute)
    return bas_totaux
