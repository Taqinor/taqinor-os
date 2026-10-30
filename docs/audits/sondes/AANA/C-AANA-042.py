"""Sonde AANA50 : rejoue C-AANA-042 (audit analyse du 05/10, D-AANA-3) : lead existant (a@x.ma, 0612345678) ; import mode creer
de `B,b@x.ma,+212 612345678` créait un doublon (created=1)."""
SONDE = {
    'constat': 'C-AANA-042',
    'sha': '5908d43bb',
    'attendu': "défaut absent : la ligne au même téléphone normalisé est ignorée (doublon), aucun lead créé",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    co = Company.objects.create(nom='Sonde 042', slug='sonde-aana-042')
    u = get_user_model().objects.create_user(username='sonde-aana-042', password='x', company=co, role_legacy='responsable')
    Lead.objects.create(company=co, nom='A', email='a@x.ma', telephone='0612345678')
    api = APIClient()
    api.force_authenticate(u)
    f = SimpleUploadedFile('d.csv', 'Nom,Email,Telephone\nB,b@x.ma,+212 612345678\n'.encode(), content_type='text/csv')
    r = api.post('/api/django/imports/commit/', {'file': f, 'target': 'leads'}, format='multipart', HTTP_HOST='localhost')
    n = Lead.objects.filter(company=co).count()
    ok = r.status_code == 200
    sk = r.data.get('skipped') if ok else r.status_code
    cr = r.data.get('created') if ok else None
    print('commit=%s created=%s skipped=%s leads=%s' % (r.status_code, cr, sk, n))
    return {'repro': ok and cr == 0 and n == 1 and len(sk) == 1, 'leads': n, 'skipped': sk}
