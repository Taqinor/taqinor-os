"""Sélecteurs (lecture) du module ``apps.douane``.

NTLOG13/NTLOG21 (calculs de valeur en douane / droits & taxes estimés) sont
BLOCKED — ils dépendent de ``DossierImport`` (NTLOG10, BLOCKED, voir
``apps/douane/apps.py``)."""
from decimal import Decimal


def delai_moyen_dedouanement(company, *, mois=None):
    """NTLOG51 — KPI « Délai moyen de dédouanement » (jours) : moyenne de
    ``date_leve - date_dum_deposee`` sur les ``DossierExport`` CLÔTURÉS du
    mois donné (défaut : mois courant).

    Lu depuis la trace d'audit GÉNÉRIQUE (``apps.audit.AuditLog``, écrite par
    ``apps.douane.services.tracer_transition_statut_dossier_export`` à
    CHAQUE transition de statut via l'entonnoir ``apps.audit.recorder.
    record_field_change``) plutôt qu'un nouveau champ dédié sur
    ``DossierExport`` — AUCUNE migration requise, la donnée existe déjà dès
    qu'un dossier a transité par ``PATCH statut=`` ou l'action
    ``cloturer``. Consommé par ``apps.reporting.kpi_alertes`` (nouveau
    membre ``KpiAlerte.Kpi.DELAI_MOYEN_DEDOUANEMENT``) — jamais un import
    direct de ``apps.reporting`` ici (lecture pure, ``reporting`` appelle CE
    module).

    Renvoie ``None`` si aucun dossier clôturé du mois n'a atteint les DEUX
    jalons (jamais une moyenne sur un dénominateur nul)."""
    from django.contrib.contenttypes.models import ContentType
    from django.utils import timezone

    from apps.audit.models import AuditLog

    from .models import DossierExport

    if mois is None:
        mois = timezone.now().date().replace(day=1)

    ct = ContentType.objects.get_for_model(DossierExport)
    dossier_ids = list(
        DossierExport.objects.filter(
            company=company, statut=DossierExport.Statut.CLOTURE,
            updated_at__year=mois.year, updated_at__month=mois.month,
        ).values_list('id', flat=True))
    if not dossier_ids:
        return None

    label_dum = DossierExport.Statut.DUM_DEPOSEE.label
    label_leve = DossierExport.Statut.LEVE.label

    entries = AuditLog.objects.filter(
        company=company, content_type=ct,
        object_id__in=[str(pk) for pk in dossier_ids],
        action=AuditLog.Action.STATUS,
    ).order_by('timestamp')

    # Première atteinte de chaque jalon, par dossier (object_id) — un dossier
    # qui repasse par le même statut ne doit pas décaler la mesure.
    premiere_dum = {}
    premiere_leve = {}
    for entry in entries:
        for chg in (entry.changes or []):
            if chg.get('field') != 'statut':
                continue
            if chg.get('new') == label_dum and entry.object_id not in premiere_dum:
                premiere_dum[entry.object_id] = entry.timestamp
            if chg.get('new') == label_leve and entry.object_id not in premiere_leve:
                premiere_leve[entry.object_id] = entry.timestamp

    delais = []
    for pk in dossier_ids:
        oid = str(pk)
        t_dum = premiere_dum.get(oid)
        t_leve = premiere_leve.get(oid)
        if t_dum and t_leve and t_leve >= t_dum:
            delais.append((t_leve - t_dum).days)

    if not delais:
        return None
    return Decimal(sum(delais)) / Decimal(len(delais))
