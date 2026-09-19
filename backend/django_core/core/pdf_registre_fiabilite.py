"""NTOBS18 — « Registre de fiabilité » : PDF interne consolidé par société et
période (audit fournisseur / due diligence client), HORS Rule#4 (document
interne, distinct du rapport SLA mensuel simple de NTOBS3/``sla_export_pdf``
qui n'exporte qu'UN mois).

Consolide, pour une société et une plage de mois choisie :

  * les ``SlaSnapshot`` de la plage (NTOBS3) ;
  * l'historique ``IncidentPublic`` ayant touché la société — système
    (``company=None``) OU propre à elle — sur la plage ;
  * le dernier dump base (YOPSB1) et le dernier drill de restauration
    (YOPSB2) — ces deux ``BackupRun`` sont SYSTÈME-WIDE (``company=None``),
    l'infrastructure de sauvegarde étant partagée par tous les tenants ;
  * les crédits SLA (NTOBS4) le cas échéant.

``core`` reste une couche de FONDATION : ``apps.statuspage.IncidentPublic``
est résolu via ``django.apps.apps.get_model`` (jamais un import statique).
"""
from __future__ import annotations

from html import escape

from django.apps import apps as django_apps
from django.db.models import Q
from django.utils import timezone


def _snapshots(company, debut, fin):
    from .sla import SlaSnapshot

    return list(
        SlaSnapshot.objects.filter(
            company=company, periode__gte=debut, periode__lte=fin,
        ).order_by('periode'))


def _incidents(company, debut, fin):
    try:
        incident_model = django_apps.get_model('statuspage', 'IncidentPublic')
    except LookupError:
        return []
    return list(
        incident_model.objects.filter(
            Q(company__isnull=True) | Q(company=company),
        ).filter(debute_le__date__gte=debut, debute_le__date__lte=fin)
        .order_by('debute_le'))


def _dernier_backup_et_drill():
    """(dernier dump, dernier drill) — tous deux SYSTÈME-WIDE (YOPSB1/2)."""
    from .models import BackupRun

    dump = (
        BackupRun.objects
        .filter(company__isnull=True, kind=BackupRun.KIND_DB_DUMP)
        .order_by('-created_at').first())
    drill = (
        BackupRun.objects
        .filter(company__isnull=True, kind=BackupRun.KIND_RESTORE_DRILL)
        .order_by('-created_at').first())
    return dump, drill


def _statut_run(run):
    if run is None:
        return 'Aucune donnée disponible'
    return f'{run.get_statut_display()} ({run.created_at:%d/%m/%Y %H:%M})'


def _registre_html(company, debut, fin, snapshots, incidents, dump, drill):
    lignes_sla = ''.join(
        f'<tr><td>{s.periode:%B %Y}</td><td>{s.uptime_pct}%</td>'
        f'<td>{s.latence_p95_ms if s.latence_p95_ms is not None else "—"}</td>'
        f'<td>{s.get_credit_statut_display()}</td></tr>'
        for s in snapshots
    ) or '<tr><td colspan="4">Aucun rapport SLA sur la période.</td></tr>'

    lignes_incidents = ''.join(
        f'<tr><td>{i.debute_le:%d/%m/%Y}</td><td>{escape(i.titre)}</td>'
        f'<td>{i.get_severite_display()}</td><td>{i.get_statut_display()}</td></tr>'
        for i in incidents
    ) or '<tr><td colspan="4">Aucun incident sur la période.</td></tr>'

    return f"""<html><head><meta charset="utf-8"></head><body>
<h1>Registre de fiabilité — {escape(str(company))}</h1>
<p>Période : {debut:%B %Y} — {fin:%B %Y}</p>
<h2>Disponibilité mensuelle (SLA)</h2>
<table border="1">
<tr><th>Mois</th><th>Disponibilité</th><th>Latence P95</th><th>Crédit</th></tr>
{lignes_sla}
</table>
<h2>Incidents</h2>
<table border="1">
<tr><th>Date</th><th>Titre</th><th>Sévérité</th><th>Statut</th></tr>
{lignes_incidents}
</table>
<h2>Sauvegarde &amp; restauration (infrastructure)</h2>
<p>Dernier dump base : {_statut_run(dump)}</p>
<p>Dernier drill de restauration : {_statut_run(drill)}</p>
<p>Généré le {timezone.now():%d/%m/%Y %H:%M}</p>
</body></html>"""


def generer_pdf_registre_fiabilite(company, debut, fin):
    """``debut``/``fin`` : ``date`` (premier jour du mois, bornes incluses)."""
    from .pdf import render_pdf

    snapshots = _snapshots(company, debut, fin)
    incidents = _incidents(company, debut, fin)
    dump, drill = _dernier_backup_et_drill()
    html = _registre_html(company, debut, fin, snapshots, incidents, dump, drill)
    return render_pdf(html=html)
