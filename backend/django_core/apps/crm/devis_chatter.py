"""Trace CRM des événements de devis (ouvert, rouvert, envoyé, corrigé) (SPL18, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from .leads_score import recompute_lead_score
from .models import LeadActivity


def noter_devis_ouvert(devis_reference: str, lead) -> None:
    """QJ1 — Consigne « Le client a ouvert le devis » dans le chatter du lead.

    Appelé par ``public_views.py`` uniquement à la PREMIÈRE ouverture du lien
    public. Best-effort : les appelants catchent toute exception.
    ``lead`` doit être un objet Lead avec company_id ; ``devis_reference`` est
    la référence textuelle du devis (pas d'import ventes ici).

    YLEAD10 — après la note, avance aussi l'étape du lead vers FOLLOW_UP
    (fast-lane comportemental : une forte intention — l'ouverture de la
    proposition — sort le lead du parking). Distinct de QJ5 (re-stage sur
    staleness TEMPORELLE) : ici le déclencheur est un COMPORTEMENT observé.
    """
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Le client a ouvert le devis {devis_reference}")
    # RÈGLE FONDATEUR 07/09/2026 — plus d'avance de funnel AUTOMATIQUE sur
    # l'ouverture (YLEAD10 débranché) : le funnel ne bouge que sur une
    # réponse confirmée de Meryem. La note et la notification restent.
    # CAD133 — le score, lui, se recalcule À L'INSTANT : sans cela le badge
    # mentirait jusqu'au passage nocturne, et la file du jour classerait un
    # client qui vient d'ouvrir sa proposition comme s'il n'avait rien fait.
    recompute_lead_score(lead)


def noter_devis_reouvert(devis_reference: str, lead, vues=None) -> None:
    """QJ1bis (fondateur 07/09/2026) — Consigne une RÉOUVERTURE du devis dans
    le chatter du lead : chaque retour du client sur sa proposition doit
    rester lisible dans l'historique (les notifications s'effacent, le
    chatter reste). Appelé par ``public_views._notify_open`` sur toute
    ouverture publique au-delà de la première, hors fenêtre de
    sessionisation. ``vues`` (compteur ShareLink) contextualise sans jamais
    être inventé — omis s'il est inconnu."""
    suffixe = f' — {int(vues)}ᵉ consultation' if vues and int(vues) > 1 else ''
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Le client a rouvert le devis {devis_reference}{suffixe}")
    # CAD133 — revenir sur sa proposition est le signal de comportement le
    # plus fort : le score monte À L'INSTANT, pas au passage nocturne.
    recompute_lead_score(lead)


def noter_devis_envoye(devis_reference: str, lead) -> None:
    """ZSAL5 — Consigne « Devis DEV-… envoyé par email » dans le chatter du
    lead. Appelé par ``apps.ventes`` (jamais d'import des models crm depuis
    ventes) quand l'action d'envoi de devis (QJ14) réussit. ``lead`` doit
    être un objet Lead avec company_id ; ``devis_reference`` est la
    référence textuelle du devis (pas d'import ventes ici). Note système
    (``user=None``), best-effort — l'appelant catche toute exception."""
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Devis {devis_reference} envoyé par email")


def noter_devis_corrige(devis_reference: str, lead, resume: str = '') -> None:
    """QJR518 — reflet sur le chatter du LEAD d'une correction après envoi
    d'un devis (même patron que ``noter_devis_envoye`` : appelé par
    ``apps.ventes``, jamais d'import des models crm depuis ventes ; note
    système, best-effort — l'appelant catche toute exception)."""
    detail = f' ({resume})' if resume else ''
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=f"Devis {devis_reference} corrigé après envoi{detail}")
