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
from .models import ComptePortailClient, DemandeTicketPortail


# ── AUD138 — État d'activation du compte portail d'un client ────────────────

def compte_portail_client_actif(company_id, client_id):
    """AUD138 — Tri-état de l'accès portail d'un client, SANS import modèle.

    Renvoie ``True`` (compte portail actif), ``False`` (compte portail
    explicitement RÉVOQUÉ) ou ``None`` (aucun compte portail enregistré).

    La distinction ``False``/``None`` est volontaire : la révocation est un
    ACTE tracé sur une ligne existante (``ComptePortailClient.actif``), alors
    que l'absence de ligne veut simplement dire que le client n'a jamais eu de
    magic-link — son compte utilisateur JWT (mécanisme primaire NTPRT2) reste
    seul juge. Un appelant qui traiterait ``None`` comme un refus fermerait le
    portail à tous les comptes provisionnés avant FG228.

    Point d'entrée cross-app LECTURE SEULE (``apps.roles.permissions`` le lit
    pour la garde de portée) — jamais un import de ``apps.portail.models``.
    """
    if not company_id or not client_id:
        return None
    return (
        ComptePortailClient.objects
        .filter(company_id=company_id, client_id=client_id)
        .values_list('actif', flat=True)
        .first()
    )


# ── XSAV22 — Déflection KB sur le portail client ────────────────────────────

def demandes_ticket_count(company):
    """XSAV22 — Nombre total de demandes de ticket SAV soumises via le
    portail pour ``company``. Point d'entrée cross-app pour
    ``apps.sav.selectors.ratio_deflection_kb`` (jamais un import de
    ``apps.portail.models`` depuis sav)."""
    if company is None:
        return 0
    return DemandeTicketPortail.objects.filter(company=company).count()
