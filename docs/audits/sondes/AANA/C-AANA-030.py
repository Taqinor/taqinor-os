"""Sonde AANA50 : rejoue C-AANA-030 (audit analyse du 05/10) : le même CSV devis d'une ligne importé deux fois créait deux devis."""
SONDE = {
    'constat': 'C-AANA-030',
    'sha': '5908d43bb',
    'attendu': "défaut absent : second import du même devis (et de la même facture) = created 0, skipped doublon, 1 seul document",
}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Devis
    from apps.facturation.models import Facture
    co = Company.objects.create(nom='Sonde 030', slug='sonde-aana-030')
    u = get_user_model().objects.create_user(username='sonde-aana-030', password='x', company=co, role_legacy='responsable')
    Client.objects.create(company=co, nom='Client Migre', email='cm@x.ma')
    api = APIClient()
    api.force_authenticate(u)

    def imp(target, contenu):
        f = SimpleUploadedFile('d.csv', contenu.encode(), content_type='text/csv')
        return api.post('/api/django/imports/commit/', {'file': f, 'target': target}, format='multipart', HTTP_HOST='localhost')
    cd = 'reference,client_nom,external_id\nSRC-1,Client Migre,EXT-D1\n'
    cf = 'reference,client_nom,external_id\nF-SRC-1,Client Migre,EXT-F1\n'
    d1, d2 = imp('devis', cd), imp('devis', cd)
    f1, f2 = imp('factures', cf), imp('factures', cf)
    nd = Devis.objects.filter(company=co).count()
    nf = Facture.objects.filter(company=co).count()
    sk = d2.data.get('skipped') if d2.status_code == 200 else d2.status_code
    skf = f2.data.get('skipped') if f2.status_code == 200 else f2.status_code
    print('devis HTTP %s/%s skipped=%s nb_devis=%s | factures HTTP %s/%s nb=%s skipped=%s' % (d1.status_code, d2.status_code, sk, nd, f1.status_code, f2.status_code, nf, skf))
    return {'repro': nd == 1 and sk == [{'ligne': 1, 'raison': 'doublon'}] and nf == 1, 'devis': nd, 'factures': nf, 'skipped': sk}
