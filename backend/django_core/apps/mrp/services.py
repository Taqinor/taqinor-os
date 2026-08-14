"""Services (écritures/orchestration) de l'app `mrp` (Groupe NTMFG)."""
from decimal import Decimal


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def temps_operation_min(operation_gamme, quantite):
    """NTMFG2 — temps prévu d'UNE opération pour `quantite` pièces :
    préparation + (temps unitaire × quantité), borné en bas par le temps
    minimum par lot (ex. changement d'outillage) s'il est renseigné."""
    quantite = _dec(quantite)
    prepa = _dec(operation_gamme.temps_prepa_min)
    unitaire = _dec(operation_gamme.temps_unitaire_min) * quantite
    minimum_lot = _dec(operation_gamme.temps_min_par_lot)
    return max(prepa + unitaire, minimum_lot)


def temps_total_gamme(gamme, quantite):
    """NTMFG2 — temps total prévu de toute la gamme pour `quantite` pièces
    (somme des temps d'opération). Renvoie un `Decimal` (minutes)."""
    total = Decimal('0')
    for operation in gamme.operations.all():
        total += temps_operation_min(operation, quantite)
    return total
