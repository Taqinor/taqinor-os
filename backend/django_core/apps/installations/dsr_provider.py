"""ASOC67 — DSR (loi 09-08) des chantiers, export seul : client OU lead du sujet."""


def export_installations(company, subject_identifier):
    from django.db.models import Q
    from apps.crm.selectors import client_ids_par_identifiant, lead_ids_par_identifiant
    from .models import Installation
    qs = Installation.objects.filter(company=company).filter(
        Q(client_id__in=list(client_ids_par_identifiant(company, subject_identifier)))
        | Q(lead_id__in=list(lead_ids_par_identifiant(company, subject_identifier))))
    return {'chantiers': [
        {'id': c.pk, 'reference': c.reference, 'statut': c.statut, 'site_adresse': c.site_adresse or '',
         'site_ville': c.site_ville or '', 'contact_site_nom': c.contact_site_nom or ''} for c in qs.order_by('pk')]}


def register():
    from core import dsr
    dsr.register_dsr_provider('installations', export=export_installations)
