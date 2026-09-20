"""NTOBS23 — fuseau horaire d'AFFICHAGE par tenant pour les horodatages du
groupe Fiabilité (``IncidentPublic``/``SlaSnapshot``/``MaintenanceWindow`` —
NTOBS1/3/9). Ces timestamps sont stockés en UTC (standard Django) mais
affichés bruts aujourd'hui : cet utilitaire les reformate dans le fuseau
choisi par la société (``apps.parametres.models_company.CompanyProfile.
timezone_affichage``, défaut ``Africa/Casablanca``, éditable en Paramètres
généraux — PAS seulement Fiabilité).

``core`` reste une couche de FONDATION : ``apps.parametres`` EST une app de
fondation exemptée (CLAUDE.md, contrat import-linter
``core-foundation-is-a-base-layer`` — ``core.** -> apps.parametres.**`` est
dans la liste ``ignore_imports``), donc un import direct de
``CompanyProfile`` est autorisé ici (même exemption déjà exploitée par
``core.usage_limits._usage_utilisateurs``).
"""
from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone as dj_timezone

#: Repli historique — comportement inchangé pour toute société sans réglage
#: explicite (``CompanyProfile`` absent, champ vide, ou app indisponible).
DEFAULT_TIMEZONE = 'Africa/Casablanca'


def _company_timezone_name(company):
    """Nom IANA du fuseau d'affichage de ``company`` (``DEFAULT_TIMEZONE`` si
    ``company`` est ``None`` ou n'a pas de ``CompanyProfile``/réglage)."""
    if company is None:
        return DEFAULT_TIMEZONE
    try:
        from apps.parametres.models_company import CompanyProfile
    except ImportError:  # pragma: no cover — apps.parametres toujours présente
        return DEFAULT_TIMEZONE

    profile = CompanyProfile.objects.filter(company=company).first()
    nom = getattr(profile, 'timezone_affichage', None) if profile else None
    return nom or DEFAULT_TIMEZONE


def to_company_tz(dt, company):
    """Convertit ``dt`` (datetime, idéalement AWARE en UTC) vers le fuseau
    d'affichage de ``company``. ``dt`` ``None`` -> ``None`` (jamais planter
    sur une donnée manquante). Un nom de fuseau invalide/inconnu retombe sur
    ``DEFAULT_TIMEZONE`` — jamais une exception remontée à l'appelant."""
    if dt is None:
        return None

    tz_name = _company_timezone_name(company)
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo(DEFAULT_TIMEZONE)

    if dj_timezone.is_naive(dt):
        dt = dj_timezone.make_aware(dt, ZoneInfo('UTC'))
    return dt.astimezone(tz)
