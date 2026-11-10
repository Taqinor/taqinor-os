"""ASOC67 — DSR (loi 09-08) du portail, export seul : documents du client OU du lead."""


def export_portail(company, subject_identifier):
    from django.db.models import Q
    from apps.crm.selectors import client_ids_par_identifiant, lead_ids_par_identifiant
    from .models import DocumentClientPortail
    qs = DocumentClientPortail.objects.filter(company=company).filter(
        Q(client_id__in=list(client_ids_par_identifiant(company, subject_identifier)))
        | Q(lead_id__in=list(lead_ids_par_identifiant(company, subject_identifier))))
    return {'documents': [
        {'id': d.pk, 'type': d.type_document, 'libelle': d.libelle,
         'fichier': d.fichier_filename or '', 'date_depot': d.date_depot.isoformat() if d.date_depot else None}
        for d in qs.order_by('pk')]}


def register():
    from core import dsr
    dsr.register_dsr_provider('portail', export=export_portail)
