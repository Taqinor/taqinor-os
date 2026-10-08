"""Signaux du bus de l'acquisition (propriétaire acquisition).

SPL289 — extrait de ``core/events/__init__.py`` (move only). Ré-exporté
par ``from .acquisition import *`` dans ``core/events/__init__.py`` :
les émetteurs et abonnés continuent d'importer ``core.events``.
"""
import django.dispatch


# ADSDEEP17 — Émis quand un lead Meta Lead Ads est capturé par le webhook CRM
# EXISTANT (``apps/crm/webhooks.meta_lead_ads_webhook``, après
# ``create_lead_from_meta_lead_ads``). Permet à ``adsengine`` de matérialiser un
# ``MetaLeadMirror`` (leads PAR AD) sans que ``crm`` importe ``apps.adsengine``.
# Arguments : lead (crm.Lead), company, leadgen_id, ad_id, adset_id,
# campaign_id, form_id, created_time (str|None), is_organic (bool). Abonné dans
# ce repo : adsengine (apps/adsengine/receivers.py).
meta_lead_captured = django.dispatch.Signal()

# ACAL189 (C-ACAL-006, D06-T17) — Émis quand le tracé de toit d'un lead public
# ARRIVE APRÈS sa création : le webhook du site (``apps/crm/webhooks.py``,
# branche « renvoi < 60 s ») complète un lead qui n'avait AUCUN contour
# exploitable et en reçoit un (≥ 3 sommets). ``lead_created`` a déjà été émis
# sans tracé : sans ce second signal, le calepinage pré-tracé n'était jamais
# ouvert. Jamais émis pour un lead qui avait déjà un contour (aucun doublon).
# Arguments : lead (crm.Lead), company. Abonné dans ce repo : calepinage
# (apps/calepinage/receivers.py → reprendre_trace_public, idempotent par la
# porte unique ACAL182) — ``crm`` n'importe jamais ``apps.calepinage``.
lead_trace_toit_recu = django.dispatch.Signal()

__all__ = [
    'meta_lead_captured',
    'lead_trace_toit_recu',
]
