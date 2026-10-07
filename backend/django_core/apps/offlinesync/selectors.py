"""NTMOB1 — lectures du journal des opérations hors-ligne (bornées société).

Point d'entrée pour toute autre app qui veut savoir ce qui attend/a échoué,
sans importer nos modèles (règle de frontière cross-app).
"""
from .models import OfflineOperation


def operations_scoped(company, *, statut=None, module=None):
    """Journal de la société, filtrable par statut/module. Lecture seule."""
    qs = OfflineOperation.objects.filter(company=company)
    if statut:
        qs = qs.filter(statut=statut)
    if module:
        qs = qs.filter(module=module)
    return qs


def conflits_ouverts(company):
    """NTMOB2 — opérations EN CONFLIT non encore arbitrées, bornées société.

    Un arbitrage fait QUITTER le statut ``conflit`` (appliquée ou rejetée) :
    « conflit ouvert » et ``statut='conflit'`` sont donc la même chose — pas de
    second critère à tenir synchronisé."""
    return operations_scoped(
        company, statut=OfflineOperation.Statut.CONFLIT)
