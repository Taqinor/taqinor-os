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


def operation_scoped(company, client_op_id):
    """Une opération par sa clé client, bornée société (ou None)."""
    if not client_op_id:
        return None
    return OfflineOperation.objects.filter(
        company=company, client_op_id=client_op_id).first()


def compte_par_statut(company):
    """``{statut: n}`` pour la société — alimente un écran de diagnostic."""
    from django.db.models import Count

    lignes = (operations_scoped(company)
              .values('statut').annotate(n=Count('id')))
    return {ligne['statut']: ligne['n'] for ligne in lignes}
