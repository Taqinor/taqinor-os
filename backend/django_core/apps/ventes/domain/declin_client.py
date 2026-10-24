"""ADEV98 (L3 lien public, 24/10/2026) — « Décliner / demander un délai ».

Le client dit NON (ou « pas maintenant ») depuis sa proposition, avec un motif
fermé — prix, délai, concurrent, projet reporté, autre (texte) — au lieu de
disparaître. Le motif est consigné au chatter du devis ET du lead (services
CRM, jamais ses modèles) et le responsable du lead (repli : créateur du devis)
est notifié. AUCUN statut n'est écrit (règle #4) : le vendeur décide ensuite
(relance, révision, refus) — le devis reste « envoyé ».
"""
import logging

logger = logging.getLogger(__name__)

#: Motifs FERMÉS (clé envoyée par la page → libellé du chatter).
MOTIFS_DECLIN = {
    'prix': 'le prix',
    'delai': 'besoin de plus de temps (délai)',
    'concurrent': 'une offre concurrente',
    'projet_reporte': 'projet reporté',
    'autre': 'autre raison',
}

MESSAGE_MOTIF_INVALIDE = ('Choisissez un motif (prix, délai, concurrent, projet '
                          'reporté ou autre — précisez « autre »).')


def motif_valide(motif, texte):
    """Vrai pour un motif de :data:`MOTIFS_DECLIN` (``autre`` exige un texte)."""
    return motif in MOTIFS_DECLIN and (motif != 'autre' or bool(texte))


def note_declin(devis, motif, texte):
    """La phrase du chatter (devis ET lead) — le texte client tel quel, borné."""
    note = (f'Le client décline la proposition {devis.reference} — motif : '
            f'{MOTIFS_DECLIN[motif]}')
    if texte:
        note += f' : « {texte[:2000]} »'
    return note + '. Aucun statut changé : à vous de relancer, réviser ou refuser.'


def enregistrer_declin(devis, *, motif, texte=''):
    """Consigne le déclin (devis + lead) et notifie le responsable. Chaque
    écriture est best-effort et journalisée : la réponse du client ne se perd
    jamais dans une erreur interne. Ne lève jamais."""
    from apps.ventes import activity
    note = note_declin(devis, motif, texte)
    try:
        activity.log_devis_note(devis, None, note)
    except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
        logger.warning('ADEV98 : note devis non posée (%s)', devis.reference, exc_info=True)
    lead = getattr(devis, 'lead', None)
    try:
        if lead is not None:
            from apps.crm.services import ajouter_note_lead
            ajouter_note_lead(company=devis.company, lead_id=lead.pk,
                              user=None, body=note)
    except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
        logger.warning('ADEV98 : note lead non posée (%s)', devis.reference, exc_info=True)
    _notifier_declin(devis, lead, note)


def _notifier_declin(devis, lead, note):
    try:
        from apps.crm.services import (
            lead_notification_recipients, user_and_superior_recipients,
        )
        from apps.notifications.services import notify_many
        destinataires = (lead_notification_recipients(lead) if lead is not None
                         else user_and_superior_recipients(
                             getattr(devis, 'created_by', None), devis.company))
        if not destinataires:
            return
        notify_many(
            destinataires, 'client_contact_request',
            f'Le client décline la proposition — {devis.reference}',
            body=note,
            link=(f'/crm/leads?lead={lead.pk}' if lead is not None
                  else f'/ventes/devis?devis={devis.pk}'),
            company=devis.company)
    except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
        logger.warning('ADEV98 : notification de déclin non partie (%s)',
                       devis.reference, exc_info=True)
