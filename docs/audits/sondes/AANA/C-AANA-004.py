"""Sonde AANA50 : rejoue C-AANA-004 (audit analyse du 05/10, F1) : un mapping d'import `{'Cid':'company_id'}`
enregistré par un responsable de A faisait naître le lead dans la société B (`lead_in_B=True`).
Transaction annulée par scripts/sonde.py ; deux sociétés créées dans la sonde."""
SONDE = {
    'constat': 'C-AANA-004',
    'sha': '5908d43bb',
    'attendu': "défaut absent : l'enregistrement du mapping company_id répond 400, et même un mapping déjà en base ne place pas le lead dans B",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.dataimport.models import ImportMapping
    a = Company.objects.create(nom='Sonde 004 A', slug='sonde-aana-004-a')
    b = Company.objects.create(nom='Sonde 004 B', slug='sonde-aana-004-b')
    u = get_user_model().objects.create_user(username='sonde-aana-004', password='x', company=a, role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    r1 = api.post('/api/django/imports/mapping/', {'target': 'leads', 'nom': 'Piege', 'mapping': {'Cid': 'company_id', 'Nom': 'nom'}}, format='json', HTTP_HOST='localhost')
    ImportMapping.objects.get_or_create(company=a, entity='leads', nom='Piege', defaults={'mapping': {'Cid': 'company_id', 'Nom': 'nom'}})
    f = SimpleUploadedFile('d.csv', ('Nom,Cid\nZed,%s\n' % b.pk).encode(), content_type='text/csv')
    r2 = api.post('/api/django/imports/commit/', {'file': f, 'target': 'leads', 'mapping': 'Piege'}, format='multipart', HTTP_HOST='localhost')
    lead = Lead.all_objects.filter(nom='Zed').first()
    in_b = bool(lead and lead.company_id == b.pk)
    print('mapping=%s commit=%s lead_in_B=%s lead_company_is_A=%s' % (r1.status_code, r2.status_code, in_b, bool(lead and lead.company_id == a.pk)))
    return {'repro': r1.status_code == 400 and not in_b, 'mapping': r1.status_code, 'commit': r2.status_code, 'lead_in_B': in_b}
