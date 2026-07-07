"""YHARD4 — traduction du CONTENU saisi (i18n des données MAÎTRES), ≠ i18n de
l'interface (déjà livrée par N93/N94 via ``frontend/src/i18n/`` +
``parametres.TranslationOverride``).

Un client dont ``crm.Client.langue_document = 'ar'`` reçoit aujourd'hui quand
même des désignations produit / clauses de contrat / articles KB rédigés en
français — parce qu'aucune traduction de ces champs texte n'existe. Ce module
fournit le socle générique : le modèle ``core.models.ContentTranslation``
(company-scopé, contenttypes) + un sélecteur de lecture avec repli langue par
défaut.

Traduction MANUELLE stockée uniquement — AUCUN appel machine de traduction ici
(pas de dépendance réseau/payante). L'UI d'édition des variantes est un
follow-on hors périmètre : ce module expose seulement la lecture + l'écriture
programmatique (``set_translation``).

Aucune importation d'app métier : fondation pure (contrat import-linter
``core-foundation-is-a-base-layer``).
"""
from __future__ import annotations

from typing import Optional

DEFAULT_LOCALE = 'fr'


def translated_value(
    instance, field: str, locale: Optional[str], *, default_locale: str = DEFAULT_LOCALE,
) -> str:
    """Valeur du champ ``field`` sur ``instance`` dans ``locale``.

    Repli : si ``locale`` est absente/``None``/égale à ``default_locale``, ou
    si aucune variante n'existe pour cette langue, renvoie la valeur BRUTE du
    champ sur l'instance (comportement historique, octet-identique). Ne lève
    jamais — une app appelante peut toujours se rabattre sur le champ direct.
    """
    raw_value = getattr(instance, field, '') or ''

    if not locale or locale == default_locale:
        return raw_value

    from django.contrib.contenttypes.models import ContentType

    from .models import ContentTranslation

    company = getattr(instance, 'company', None)
    if company is None:
        return raw_value

    try:
        content_type = ContentType.objects.get_for_model(instance.__class__)
        translation = ContentTranslation.objects.filter(
            company=company, content_type=content_type,
            object_id=str(instance.pk), locale=locale, field=field,
        ).first()
    except Exception:  # noqa: BLE001 — lecture best-effort, jamais bloquant
        return raw_value

    if translation is None or not translation.value:
        return raw_value
    return translation.value


def set_translation(instance, field: str, locale: str, value: str, *, company=None):
    """Upsert la variante ``locale`` de ``field`` pour ``instance``.

    ``company`` est forcée par l'appelant (jamais déduite d'une entrée
    utilisateur non fiable) ; par défaut celle de l'instance si elle en porte
    une. Écrase toute variante existante pour la même clé
    ``(company, content_type, object_id, locale, field)``."""
    from django.contrib.contenttypes.models import ContentType

    from .models import ContentTranslation

    company = company or getattr(instance, 'company', None)
    if company is None:
        raise ValueError(
            "set_translation nécessite une société (fournie ou portée par l'instance).")

    content_type = ContentType.objects.get_for_model(instance.__class__)
    obj, _created = ContentTranslation.objects.update_or_create(
        company=company, content_type=content_type,
        object_id=str(instance.pk), locale=locale, field=field,
        defaults={'value': value},
    )
    return obj


def translations_for(instance) -> dict:
    """Toutes les variantes connues de ``instance``, groupées par
    ``{locale: {field: value}}`` — utile pour un futur écran d'édition."""
    from django.contrib.contenttypes.models import ContentType

    from .models import ContentTranslation

    company = getattr(instance, 'company', None)
    if company is None or instance.pk is None:
        return {}

    content_type = ContentType.objects.get_for_model(instance.__class__)
    qs = ContentTranslation.objects.filter(
        company=company, content_type=content_type, object_id=str(instance.pk))

    out: dict = {}
    for row in qs:
        out.setdefault(row.locale, {})[row.field] = row.value
    return out
