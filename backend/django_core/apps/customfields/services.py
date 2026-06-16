"""Logique métier des champs personnalisés : dérivation de slug et validation
des valeurs contre leurs définitions (type + obligatoire + appartenance choix).

Réutilisé par les sérialiseurs de crm.Lead / crm.Client / stock.Produit pour
valider et fusionner le JSON `custom_fields` lors des écritures et lectures.
"""
from datetime import date, datetime

from django.utils.text import slugify

from .models import (
    CustomFieldDefinition,
    TYPE_TEXT, TYPE_NUMBER, TYPE_DATE, TYPE_CHOICE, TYPE_BOOLEAN,
)


def derive_field_key(label, company, module, exclude_pk=None):
    """Dérive un slug stable et unique par (company, module) depuis le libellé.

    Le slug est généré CÔTÉ SERVEUR (jamais accepté du corps de la requête) ;
    en cas de collision on suffixe _2, _3, …
    """
    base = slugify(label, allow_unicode=False).replace('-', '_')[:50] or 'champ'
    candidate = base
    n = 2
    while True:
        qs = CustomFieldDefinition.objects.filter(
            company=company, module=module, field_key=candidate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        candidate = f'{base}_{n}'
        n += 1


def active_definitions(company, module):
    """Définitions actives d'un module pour une société, triées par ordre."""
    if company is None:
        return CustomFieldDefinition.objects.none()
    return CustomFieldDefinition.objects.filter(
        company=company, module=module, active=True).order_by('order', 'id')


def _coerce_number(value):
    if isinstance(value, bool):
        raise ValueError('Un nombre est attendu.')
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        v = value.strip().replace(',', '.')
        try:
            f = float(v)
        except ValueError:
            raise ValueError('Valeur numérique invalide.')
        return int(f) if f.is_integer() else f
    raise ValueError('Valeur numérique invalide.')


def _coerce_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ('true', '1', 'oui', 'yes'):
            return True
        if v in ('false', '0', 'non', 'no', ''):
            return False
    if value in (0, 1):
        return bool(value)
    raise ValueError('Valeur oui/non invalide.')


def _coerce_date(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, str):
        v = value.strip()
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Date invalide (format attendu AAAA-MM-JJ).')
        return v
    raise ValueError('Date invalide.')


def _is_empty(value):
    return value is None or (isinstance(value, str) and value.strip() == '')


def validate_custom_fields(company, module, incoming, existing=None, partial=False):
    """Valide et nettoie un dict de valeurs `custom_fields` pour un module.

    - incoming : valeurs reçues du client (dict ou None).
    - existing : valeurs déjà en base (pour le PATCH partiel / champs requis).
    - partial : si True (PATCH), seuls les champs présents dans `incoming` sont
      validés ; les champs requis absents ne sont pas exigés.

    Renvoie un dict {field_key: valeur normalisée}. Lève ValueError(message FR)
    en cas de problème (le sérialiseur le remonte en erreur DRF).
    Les clés inconnues (sans définition active) sont ignorées silencieusement.
    """
    incoming = incoming or {}
    existing = existing or {}
    if not isinstance(incoming, dict):
        raise ValueError('Les champs personnalisés doivent être un objet.')

    defs = list(active_definitions(company, module))
    result = {} if not partial else dict(existing)

    errors = {}
    for d in defs:
        key = d.field_key
        provided = key in incoming
        if partial and not provided:
            continue
        raw = incoming.get(key, existing.get(key))

        if _is_empty(raw):
            if d.required and not partial:
                errors[key] = f'« {d.label} » est obligatoire.'
            elif d.required and provided:
                errors[key] = f'« {d.label} » est obligatoire.'
            else:
                result[key] = None
            continue

        try:
            if d.field_type == TYPE_TEXT:
                result[key] = str(raw)
            elif d.field_type == TYPE_NUMBER:
                result[key] = _coerce_number(raw)
            elif d.field_type == TYPE_BOOLEAN:
                result[key] = _coerce_boolean(raw)
            elif d.field_type == TYPE_DATE:
                result[key] = _coerce_date(raw)
            elif d.field_type == TYPE_CHOICE:
                val = str(raw)
                if val not in (d.choices or []):
                    raise ValueError(
                        f'Valeur non autorisée pour « {d.label} ».')
                result[key] = val
            else:
                result[key] = raw
        except ValueError as exc:
            errors[key] = str(exc)

    if errors:
        raise ValueError(errors)
    return result


def read_custom_fields(company, module, stored):
    """Fusionne les valeurs stockées avec les définitions actives pour la
    lecture : garantit qu'une clé existe pour chaque définition active (None si
    absente) et n'expose pas les valeurs orphelines (définitions supprimées)."""
    stored = stored or {}
    out = {}
    for d in active_definitions(company, module):
        out[d.field_key] = stored.get(d.field_key)
    return out
