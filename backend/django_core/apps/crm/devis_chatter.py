"""Trace CRM des événements de devis (ouvert, rouvert, envoyé, corrigé) (SPL18, extrait de crm/services.py : déplacement
pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from . import stages
from .fiche_funnel import reprendre_lead
from .leads_score import recompute_lead_score
from .models import Lead, LeadActivity
from .activity import journal_systeme

#: CADV89 (D-CADV-4) — le silence au bout duquel une réouverture réveille un lead
#: parqué ; en deçà, note et score seulement.
REOUVERTURE_REVEIL_JOURS = 30
_NOTES_OUVERTURE = ('Le client a ouvert le devis', 'Le client a rouvert le devis')


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
    journal_systeme(
        company=lead.company, lead=lead,
        kind=LeadActivity.Kind.NOTE,
        body=f"Le client a ouvert le devis {devis_reference}")
    # RÈGLE FONDATEUR 07/09/2026 — plus d'avance de funnel AUTOMATIQUE sur
    # l'ouverture (YLEAD10 débranché) : le funnel ne bouge que sur une
    # réponse confirmée de Meryem. La note et la notification restent.
    # CAD133 — le score, lui, se recalcule À L'INSTANT : sans cela le badge
    # mentirait jusqu'au passage nocturne, et la file du jour classerait un
    # client qui vient d'ouvrir sa proposition comme s'il n'avait rien fait.
    recompute_lead_score(lead)


def _reveil_du(lead):
    """CADV89 — lead en Nurture ou Standby dont la dernière ouverture connue de sa
    proposition date d'au moins ``REOUVERTURE_REVEIL_JOURS`` jours. Lu AVANT la note
    de cette ouverture-ci. Sans ouverture connue, aucun silence n'est prouvé."""
    lead.refresh_from_db(fields=['parc_etat'])
    if lead.parc_etat not in (Lead.ParcEtat.NURTURE, Lead.ParcEtat.STANDBY):
        return False
    derniere = (lead.activites
                .filter(Q(body__startswith=_NOTES_OUVERTURE[0])
                        | Q(body__startswith=_NOTES_OUVERTURE[1]))
                .order_by('-created_at').values_list('created_at', flat=True).first())
    return (derniere is not None and timezone.now() - derniere
            >= datetime.timedelta(days=REOUVERTURE_REVEIL_JOURS))


def _reveiller_lead_parque(lead):
    """CADV89 — la touche « Proposition rouverte — appeler » (qui refuse d'elle-même
    opposés, perdus, archivés et signés : rien n'est alors changé), la sortie de
    parcage vers FOLLOW_UP, et les réveils annulés : le dossier ne dort plus."""
    from .cadence_plan import arreter_cadence
    from .cadence_signaux import SIGNAL_PROPOSITION_ROUVERTE, poser_touche_signal

    with transaction.atomic():
        if poser_touche_signal(lead, SIGNAL_PROPOSITION_ROUVERTE) is None:
            return
        arreter_cadence(lead, user=None, motif='proposition rouverte',
                        cadences=['reveil'])
        reprendre_lead(lead, None, stages.FOLLOW_UP)


def noter_devis_reouvert(devis_reference: str, lead, vues=None) -> None:
    """QJ1bis (fondateur 07/09/2026) — Consigne une RÉOUVERTURE du devis dans
    le chatter du lead : chaque retour du client sur sa proposition doit
    rester lisible dans l'historique (les notifications s'effacent, le
    chatter reste). Appelé par ``public_views._notify_open`` sur toute
    ouverture publique au-delà de la première, hors fenêtre de
    sessionisation. ``vues`` (compteur ShareLink) contextualise sans jamais
    être inventé — omis s'il est inconnu.
    CADV89 — après un long silence, réveille le lead parqué (``_reveil_du``)."""
    reveil = _reveil_du(lead)
    suffixe = f' — {int(vues)}ᵉ consultation' if vues and int(vues) > 1 else ''
    journal_systeme(
        company=lead.company, lead=lead,
        kind=LeadActivity.Kind.NOTE,
        body=f"Le client a rouvert le devis {devis_reference}{suffixe}")
    if reveil:
        _reveiller_lead_parque(lead)
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
    journal_systeme(
        company=lead.company, lead=lead,
        kind=LeadActivity.Kind.NOTE,
        body=f"Devis {devis_reference} envoyé par email")


def noter_devis_corrige(devis_reference: str, lead, resume: str = '') -> None:
    """QJR518 — reflet sur le chatter du LEAD d'une correction après envoi
    d'un devis (même patron que ``noter_devis_envoye`` : appelé par
    ``apps.ventes``, jamais d'import des models crm depuis ventes ; note
    système, best-effort — l'appelant catche toute exception)."""
    detail = f' ({resume})' if resume else ''
    journal_systeme(
        company=lead.company, lead=lead,
        kind=LeadActivity.Kind.NOTE,
        body=f"Devis {devis_reference} corrigé après envoi{detail}")
