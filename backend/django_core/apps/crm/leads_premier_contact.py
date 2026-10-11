"""Premier contact des leads (SPL6, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from django.utils import timezone

from . import stages


def marquer_premier_contact(lead, *, when=None) -> bool:
    """MRY19 — LA pose de ``first_contacted_at``. Une seule, partout.

    Quatre endroits l'écrivaient à la main, avec quatre conditions
    LÉGÈREMENT différentes (dont deux qui exigeaient l'étape NEW) : un lead
    saisi à la main, déjà CONTACTED, ne recevait donc JAMAIS d'horodatage —
    et sortait silencieusement du KPI de premier contact. Ici la règle est
    unique et sans condition d'étape : si le champ est vide, on le pose.

    Idempotente — jamais un écrasement. Renvoie True si la pose a eu lieu.
    Best-effort : ne lève jamais."""
    try:
        if lead is None or getattr(lead, 'first_contacted_at', None):
            return False
        lead.first_contacted_at = when or timezone.now()
        lead.save(update_fields=['first_contacted_at'])
        return True
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return False


def maybe_set_first_contacted_at(old_lead, new_lead):
    """Pose ``first_contacted_at`` quand le stage quitte NEW.

    Signature INCHANGÉE (appelée par ``LeadViewSet.perform_update``) ; MRY19
    délègue simplement à ``marquer_premier_contact`` — plus aucune seconde
    règle qui pourrait diverger."""
    try:
        if old_lead.stage == stages.NEW and new_lead.stage != stages.NEW:
            marquer_premier_contact(new_lead)
    except Exception:
        pass


def lead_sla_hours(company) -> int:
    """Retourne le délai SLA (heures) configuré pour la société. 24 par défaut."""
    if company is None:
        return 24
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
        if profile is not None:
            return profile.lead_sla_hours
    except Exception:
        pass
    return 24


def callback_sla_hours(company) -> int:
    """QW4 — Délai SLA (heures) d'un RAPPEL demandé (``contact_preference=
    phone_ok``), plus SERRÉ que le SLA générique de premier contact
    (``lead_sla_hours``) : la moitié, plancher 2 h. AUCUN nouveau champ
    société (on reste dans `apps/crm`, pas de dépendance nouvelle sur
    `parametres`) — dérivé du SLA générique déjà configurable. 0 (SLA
    générique désactivé) désactive aussi le SLA rappel."""
    generic = lead_sla_hours(company)
    if not generic:
        return 0
    return max(2, generic // 2)
