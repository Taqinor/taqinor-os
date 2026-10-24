"""Validation du corps d'un relevé de compteur (extraite de ``views.py``, C20).

Corrections de fuzz nocturne : corps non objet, valeur hors bornes
(DecimalField(12, 2) -> débordement SQL = 500), date non texte ou hors bornes.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework.exceptions import ParseError
from rest_framework.response import Response

from .models import ReleveCompteurEquipement


def exiger_objet(donnees):
    """Un corps JSON LISTE n'a pas de ``.get`` -> 500 : 400 à la place.
    Rend ``donnees`` (lecture en une expression dans les vues-murs)."""
    if not hasattr(donnees, 'get'):
        raise ParseError('Corps JSON objet attendu.')
    return donnees


def _refus(cle, message, statut=400):
    return Response({cle: message}, status=statut)


def lire_releve(corps):
    """``(type, valeur, date)`` validés, ou la ``Response`` 400 à renvoyer."""
    if not hasattr(corps, 'get'):
        return _refus('detail', 'Corps JSON objet attendu.')
    type_releve = corps.get('type')
    # AGR615 — le compteur d'eau d'une pompe (m³) est accepté.
    if type_releve not in (
            ReleveCompteurEquipement.Type.HEURES,
            ReleveCompteurEquipement.Type.KWH,
            ReleveCompteurEquipement.Type.M3):
        return _refus('detail', 'type invalide (heures|kwh|m3).')
    # Le compteur est cumulatif : fini, >= 0 et < 10**10 (10 entiers + 2 décimales).
    try:
        valeur = Decimal(str(corps.get('valeur')))
    except (InvalidOperation, TypeError, ValueError):
        return _refus('valeur', 'valeur invalide.')
    if not valeur.is_finite() or valeur < 0 or valeur >= Decimal(10) ** 10:
        return _refus('valeur', 'valeur hors bornes (0 à 9999999999,99).')
    valeur = valeur.quantize(Decimal('0.01'))

    date_raw = corps.get('date') or ''
    if not isinstance(date_raw, str):
        return _refus('date', 'date invalide.')
    date_raw = date_raw.strip()
    try:
        date_releve = date.fromisoformat(date_raw) if date_raw else timezone.localdate()
    except ValueError:
        return _refus('date', 'date invalide.')
    # Pas de refus « futur » (contrats et tests datent leurs relevés en
    # 2027) : seule l'année hors de toute saisie plausible est refusée.
    if date_releve.year > timezone.localdate().year + 10:
        # ENF11 : la borne dépend de la date du jour (donc de l'ÉTAT), le
        # schéma ne peut la publier -> 409, jamais un 400 « conforme refusé ».
        return _refus('date', 'date hors bornes (année trop lointaine).', 409)
    return type_releve, valeur, date_releve
