"""Selectors du module Portail client (``apps.portail``).

Point d'entrée des LECTURES cross-app du domaine portail (CLAUDE.md : les autres
apps lisent ``portail`` via ``apps.portail.selectors`` ou par string-FK, jamais
via ``apps.portail.models``).

À la sortie de compta (ODX12), les lecteurs internes de ``ComptePortailClient``
(les vues publiques tokenisées ``portail_mon_releve`` / ``portail_contester_
facture`` de compta, et le sélecteur lecture de ``apps.contrats``) continuent de
passer par le shim compta. Ce module est le point d'accès stable pour toute
future lecture fine — jamais un import direct de ``apps.portail.models`` depuis
l'extérieur.
"""
from .models import DemandeTicketPortail


# ── XSAV22 — Déflection KB sur le portail client ────────────────────────────

def demandes_ticket_count(company):
    """XSAV22 — Nombre total de demandes de ticket SAV soumises via le
    portail pour ``company``. Point d'entrée cross-app pour
    ``apps.sav.selectors.ratio_deflection_kb`` (jamais un import de
    ``apps.portail.models`` depuis sav)."""
    if company is None:
        return 0
    return DemandeTicketPortail.objects.filter(company=company).count()
