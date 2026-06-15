"""Normalisation d'un numéro marocain au format international wa.me.

Objectif : produire `2126XXXXXXXX` (sans + ni espaces) à partir de ce que les
commerciaux saisissent réellement (06…, +212…, 00212…, espaces, tirets,
parenthèses). Utilisé pour construire les liens https://wa.me/<number>.
"""
import re


def normalize_ma_phone(raw):
    """Renvoie le numéro marocain en `212XXXXXXXXX`, ou None si vide/invalide."""
    if not raw:
        return None
    digits = re.sub(r'\D', '', str(raw))  # ne garde que les chiffres
    if not digits:
        return None
    if digits.startswith('00'):  # préfixe international 00
        digits = digits[2:]
    if digits.startswith('212'):
        local = digits[3:]
    elif digits.startswith('0'):
        local = digits[1:]
    else:
        local = digits
    local = local.lstrip('0')
    if not local:
        return None
    return '212' + local
