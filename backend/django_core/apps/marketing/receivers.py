"""Récepteurs d'événements du module Marketing (``apps.marketing``).

XMKT1 — sortie automatique des séquences de relance. À l'acceptation OU au
refus d'un devis lié à un lead, sort ce lead de toute séquence de relance
active : les séquences sont pilotées sur l'intention commerciale de
conversion, plus pertinente une fois le devis tranché.

``marketing`` n'importe jamais ``apps.ventes`` : l'instance devis transite par
les arguments du signal ``core.events`` (M6). Le service métier
``sortir_inscriptions_pour_lead`` vit encore dans ``apps.compta.services``
(ré-export transitoire ODX9, à re-loger en ODX22) — importé paresseusement
pour éviter tout cycle au chargement des apps.
"""

from django.dispatch import receiver

from core.events import devis_accepted, devis_refused


# ── XMKT1 — sortie automatique des séquences de relance ────────────────────

@receiver(devis_accepted,
          dispatch_uid="marketing_sortir_sequence_on_devis_accepted")
def _sortir_sequence_on_devis_accepted(sender, devis, user, ancien_statut,
                                       **kwargs):
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    from apps.marketing.services import sortir_inscriptions_pour_lead
    sortir_inscriptions_pour_lead(
        devis.company, lead_id, motif='devis_accepte')


@receiver(devis_refused,
          dispatch_uid="marketing_sortir_sequence_on_devis_refused")
def _sortir_sequence_on_devis_refused(sender, devis, user, motif_refus,
                                      **kwargs):
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id:
        return
    from apps.marketing.services import sortir_inscriptions_pour_lead
    sortir_inscriptions_pour_lead(
        devis.company, lead_id, motif='devis_refuse')
