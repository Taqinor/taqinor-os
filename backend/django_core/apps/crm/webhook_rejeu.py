"""Rejeu QX16 d'un payload du webhook site (extrait de webhooks.py, C20).

Code déplacé tel quel (`replay_website_lead_payload`) ; les helpers du mapping
restent dans `webhooks.py`, importés à l'appel (un `patch` de
`apps.crm.webhooks._map_and_link_lead` reste effectif)."""
import logging

from django.db import transaction

# Même canal de journal que le webhook (déplacé tel quel).
logger = logging.getLogger('apps.crm.webhooks')


def replay_website_lead_payload(raw):
    """QX16 — Rejoue un ``WebsiteLeadPayload`` non traité/en erreur à travers
    EXACTEMENT le même mapping que le webhook (``_map_and_link_lead``, source
    unique de vérité — jamais une seconde implémentation qui pourrait
    diverger). Résout la société DEPUIS le payload déjà stocké (jamais du
    payload brut re-résolu — ``raw.company`` a été posée côté serveur à la
    réception initiale ; si elle manquait, on retombe sur ``_resolve_company``
    comme le ferait un nouveau POST).

    Renvoie ``(ok: bool, detail: str, lead)``. Ne lève jamais — capte toute
    exception et la consigne sur ``raw.error`` comme le fait la vue webhook,
    pour que le rejeu reste rejouable indéfiniment (jamais une exception
    remontée casse l'appelant HTTP)."""
    from .webhooks import (
        _map_and_link_lead, _mettre_en_file_devis_automatique, _resolve_company)

    # AACQ30 — rejeu IDEMPOTENT et fidèle au webhook, à n'importe quel délai.
    payload = raw.payload if isinstance(raw.payload, dict) else {}
    if payload.get('event_type'):
        return False, "Ping d'engagement : jamais rejoué en lead.", None
    echec = None
    with transaction.atomic():
        # ACNC55 — relecture SOUS VERROU : un 2e « Rejouer » simultané voit la
        # ligne déjà rattachée par le 1er (jamais deux leads / deux devis).
        raw = type(raw).objects.select_for_update().get(pk=raw.pk)
        if raw.lead_id:
            return (True, f'Déjà rattaché au lead #{raw.lead_id} — aucun '
                          f'nouveau lead.', raw.lead)
        if raw.processed:
            return (False, "Événement déjà traité : la soumission d'origine a "
                           "déjà sa fiche.", None)
        company = raw.company or _resolve_company()
        if company is None:
            return False, 'Aucune Company résolue — rejeu impossible.', None
        try:
            with transaction.atomic():
                lead, created, detail, _extra = _map_and_link_lead(
                    raw, raw.payload, company)
        except Exception as exc:  # noqa: BLE001 — même contrat que la vue webhook (D-ENF22-BLE001)
            logger.error(
                'replay_website_lead_payload: mapping échoué (payload #%s)',
                raw.pk, exc_info=exc)
            echec = exc
    if echec is not None:
        raw.error = f'{type(echec).__name__}: {echec}'
        raw.save(update_fields=['error'])
        return False, f'Rejeu échoué : {echec}', None
    if created:  # hors du bloc atomique (garde DELAY_IN_ATOMIC)
        try:
            _mettre_en_file_devis_automatique(lead, company)
        except Exception:  # noqa: BLE001 — le rejeu ne lève jamais (D-ENF22-BLE001)
            logger.exception(
                'replay_website_lead_payload: devis auto non mis en file '
                '(payload #%s)', raw.pk)
    return True, detail, lead
