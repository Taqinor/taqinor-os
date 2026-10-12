"""ZPUR9 — Rapport imprimable « analyse d'achats » (PDF), au-delà du
dashboard écran XPUR24.

INTERNE UNIQUEMENT (jamais un document client) : ce rapport imprime
`prix_achat`/montants d'achat, réservé admin/responsable. Réutilise
EXACTEMENT les mêmes sélecteurs d'agrégation que le dashboard XPUR24
(`analyse_achats_dashboard`) — aucun recalcul parallèle, les totaux
coïncident toujours avec l'écran.

Réutilise l'approche WeasyPrint legacy (Jinja2 → HTML → PDF) — JAMAIS le
moteur de devis premium (`apps/ventes/quote_engine/`), qui est réservé aux
PDF de devis CLIENT (règle #4 du CLAUDE.md)."""
from apps.ventes.utils.pdf import _company_context, _render_html, _html_to_pdf


def _en_date(valeur):
    """``date`` ISO (AAAA-MM-JJ) ou ``None`` si absente / illisible."""
    import datetime
    if isinstance(valeur, datetime.datetime):
        return valeur.date()
    if isinstance(valeur, datetime.date):
        return valeur
    try:
        return datetime.date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


def build_analyse_achats_context(
        company, *, date_debut=None, date_fin=None, nb_mois=6):
    """Contexte de rendu du rapport imprimable — réutilise
    `analyse_achats_dashboard` (XPUR24, jamais recalculé différemment)."""
    from django.utils import timezone
    from ..services import analyse_achats_dashboard

    data = analyse_achats_dashboard(
        company, date_debut=date_debut, date_fin=date_fin, nb_mois=nb_mois)
    context = _company_context(company=company)
    context['data'] = data
    # Le gabarit formate la période avec ``strftime`` : il lui faut des dates,
    # pas les chaînes brutes de la requête.
    context['date_debut'] = _en_date(date_debut)
    context['date_fin'] = _en_date(date_fin)
    context['genere_le'] = timezone.now()
    return context


def generate_analyse_achats_pdf(
        company, *, date_debut=None, date_fin=None, nb_mois=6):
    """Rend le rapport « analyse d'achats » en PDF (octets, non stocké).
    Document INTERNE — ne circule jamais côté client."""
    context = build_analyse_achats_context(
        company, date_debut=date_debut, date_fin=date_fin, nb_mois=nb_mois)
    html = _render_html('analyse_achats.html', context)
    return _html_to_pdf(html)
