"""NTOBS17 — export PDF générique du trust center (dossier d'appel d'offres).

Étend NTOBS10 (``core.trust_center``) : compile les ``TrustCenterEntry`` + la
dernière moyenne de disponibilité ``SlaSnapshot`` (TOUTES sociétés confondues,
ANONYMISÉE — jamais un nom ni un identifiant de société) en un document
commercial GÉNÉRIQUE, destiné à un dossier d'appel d'offres (RFP). Ce document
est HORS PÉRIMÈTRE de la règle #4 (CLAUDE.md) : la règle #4 ne concerne que
les PDF de devis CLIENT, jamais ce document commercial système sans donnée
société.

checked-facts-only : aucun chiffre n'est inventé — l'absence de
``SlaSnapshot`` omet simplement le bloc disponibilité plutôt que d'afficher
une valeur fabriquée.
"""
from __future__ import annotations

from html import escape

from django.utils import timezone


def _derniere_moyenne_sla():
    """(periode, moyenne_uptime_pct) du dernier mois où au moins un
    ``SlaSnapshot`` existe, moyenné sur TOUTES les sociétés — jamais une
    société identifiée. ``(None, None)`` si aucun snapshot n'existe encore."""
    from .sla import SlaSnapshot

    derniere_periode = (
        SlaSnapshot.objects.order_by('-periode')
        .values_list('periode', flat=True).first())
    if derniere_periode is None:
        return None, None

    valeurs = [
        float(v) for v in SlaSnapshot.objects
        .filter(periode=derniere_periode)
        .values_list('uptime_pct', flat=True)
    ]
    if not valeurs:
        return derniere_periode, None
    return derniere_periode, round(sum(valeurs) / len(valeurs), 4)


def _trust_center_html():
    from .trust_center import TrustCenterEntry

    entries = TrustCenterEntry.objects.all()
    periode, moyenne = _derniere_moyenne_sla()

    lignes = []
    for entree in entries:
        audit = (
            f' — dernier audit {entree.dernier_audit_le:%d/%m/%Y}'
            if entree.dernier_audit_le else '')
        description = (
            f'<br>{escape(entree.description)}' if entree.description else '')
        lignes.append(
            f'<li><strong>{escape(entree.get_categorie_display())}</strong> — '
            f'{escape(entree.titre)}{audit}{description}</li>')

    sla_bloc = ''
    if moyenne is not None:
        sla_bloc = (
            '<p>Disponibilité moyenne mesurée sur le parc '
            f'({periode:%B %Y}) : <strong>{moyenne}%</strong> '
            '(moyenne anonymisée, toutes sociétés confondues).</p>')

    return f"""<html><head><meta charset="utf-8"></head><body>
<h1>Dossier de confiance — Taqinor</h1>
<p>Généré le {timezone.now():%d/%m/%Y %H:%M}</p>
{sla_bloc}
<ul>{''.join(lignes) or '<li>Aucune entrée publiée pour le moment.</li>'}</ul>
</body></html>"""


def generer_pdf_trust_center():
    """Rend le PDF WeasyPrint générique (bytes) — aucune donnée société."""
    from .pdf import render_pdf

    return render_pdf(html=_trust_center_html())
