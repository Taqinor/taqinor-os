"""Lectures du journal de l'assistant exposées aux autres apps (AIC35).

Les autres apps passent par ici — jamais par ``agent.models``.
"""
import datetime

from .models import AssistantEvent


def manques_signales_entre(company, user, debut, fin):
    """Nombre de « fonction manquante » (intention ``manque``) signalées par
    ``user`` dans [``debut``, ``fin``[ (datetimes aware), société ``company``."""
    return AssistantEvent.objects.filter(
        company=company, user=user, intention=AssistantEvent.Intention.MANQUE,
        created_at__gte=debut, created_at__lt=fin).count()


def manques_signales_hier(company, user, aujourdhui):
    """Manques signalés par ``user`` la veille de ``aujourdhui`` (date locale
    Casablanca) — compte seulement."""
    from core.dates import TZ_METIER
    minuit = datetime.datetime.combine(
        aujourdhui, datetime.time.min, tzinfo=TZ_METIER)
    return manques_signales_entre(
        company, user, minuit - datetime.timedelta(days=1), minuit)
