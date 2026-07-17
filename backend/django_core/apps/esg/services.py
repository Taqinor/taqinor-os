"""Services d'écriture / orchestration de l'app ESG (Groupe NTESG).

``figer_periode`` (NTESG1) est la seule opération qui MUTE une
``PeriodeReportingESG`` : elle calcule ``selectors.agreger_indicateurs_
periode`` une fois et gèle le résultat dans ``SnapshotESG`` — même logique de
verrouillage que ``compta.services.cloturer_periode``. Refuse (lève
``ValidationError``) si la période n'est plus en ``brouillon`` : le figeage
n'est PAS ré-exécutable (contrairement à une simple clôture idempotente) —
une période déjà figée/publiée ne recalcule jamais ses chiffres.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone


@transaction.atomic
def figer_periode(periode, *, user=None):
    """Fige une ``PeriodeReportingESG`` : gèle son ``SnapshotESG`` (NTESG1).

    Refuse (``ValidationError``) si la période est déjà ``figee`` ou
    ``publiee`` — le figeage ne recalcule/n'écrase JAMAIS un snapshot
    existant, pour garantir qu'une période figée renvoie exactement les
    mêmes chiffres indéfiniment, même si les données sources QHSE ont changé
    depuis. Renvoie la période (rafraîchie).
    """
    from .models import PeriodeReportingESG, SnapshotESG
    from .selectors import agreger_indicateurs_periode

    if periode.statut != PeriodeReportingESG.Statut.BROUILLON:
        raise ValidationError(
            'Cette période est déjà figée ou publiée — le figeage est '
            'refusé (les chiffres figés ne sont jamais recalculés).')

    donnees = agreger_indicateurs_periode(
        periode.company, periode.date_debut, periode.date_fin)
    SnapshotESG.objects.create(
        company=periode.company, periode=periode, donnees=donnees)
    periode.statut = PeriodeReportingESG.Statut.FIGEE
    periode.figee_le = timezone.now()
    periode.figee_par = user
    periode.save(update_fields=['statut', 'figee_le', 'figee_par'])
    return periode
