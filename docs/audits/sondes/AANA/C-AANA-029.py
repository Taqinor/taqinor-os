"""Sonde AANA50 : rejoue C-AANA-029 (audit analyse du 05/10) : lead L et client C de même pk ; le lead importé avec
external_id=A1, puis des clients mode=maj external_id=A1 modifiaient le client C (référence externe non typée)."""
SONDE = {
    'constat': 'C-AANA-029',
    'sha': '5908d43bb',
    'attendu': "défaut absent : l'import clients mode=maj external_id=A1 ne modifie pas le client C de même pk que le lead L",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    co = Company.objects.create(nom='Sonde 029', slug='sonde-aana-029')
    u = get_user_model().objects.create_user(username='sonde-aana-029', password='x', company=co, role_legacy='responsable')
    api = APIClient()
    api.force_authenticate(u)
    pk = 987654
    Lead.objects.create(pk=pk, company=co, nom='Lead L', email='l@x.ma')
    c = Client.objects.create(pk=pk, company=co, nom='Client C', email='c@x.ma', adresse='Rue origine')

    def post(contenu, target, **extra):
        f = SimpleUploadedFile('d.csv', contenu.encode(), content_type='text/csv')
        d = {'file': f, 'target': target}
        d.update(extra)
        return api.post('/api/django/imports/commit/', d, format='multipart', HTTP_HOST='localhost')
    r1 = post('Nom,Email,External_id\nLead L,l@x.ma,A1\n', 'leads', mode='upsert')
    r2 = post('Nom,Adresse,External_id\nZ,PWNED-adresse,A1\n', 'clients', mode='maj', ecraser='true')
    c.refresh_from_db()
    touche = c.adresse != 'Rue origine' or c.nom != 'Client C'
    upd = r2.data.get('updated') if r2.status_code == 200 else None
    print('lead-import=%s client-maj=%s updated=%s client.adresse=%r modifie=%s' % (r1.status_code, r2.status_code, upd, c.adresse, touche))
    return {'repro': not touche, 'updated': upd, 'adresse': c.adresse}
