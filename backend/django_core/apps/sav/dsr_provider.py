"""ASOC67 — DSR (loi 09-08) du SAV, export seul : tickets des clients du sujet."""


def export_sav(company, subject_identifier):
    from apps.crm.selectors import client_ids_par_identifiant
    from .models import Ticket
    clients = list(client_ids_par_identifiant(company, subject_identifier))
    return {'tickets': [
        {'id': t.pk, 'reference': t.reference, 'type': t.type, 'statut': t.statut, 'description': t.description or '',
         'date_ouverture': t.date_ouverture.isoformat() if t.date_ouverture else None}
        for t in Ticket.objects.filter(company=company, client_id__in=clients).order_by('pk')]}


def register():
    from core import dsr
    dsr.register_dsr_provider('sav', export=export_sav)
