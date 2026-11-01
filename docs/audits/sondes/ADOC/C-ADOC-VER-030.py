SONDE = {"constat": "C-ADOC-VER-030", "sha": "56d5b623a",
         "attendu": "un fichier « CIN.pdf » téléversé (nom = nom du fichier) dans un dossier dont la seule demande en attente est « CIN » solde cette demande et la checklist passe CIN à 'present' (preuve en direct d'ADOC177)"}


def sonde(ctx):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.ged.models import Cabinet, Folder, Document, ExigenceDossier
    from apps.ged import services
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER-030', slug='sonde-adoc-ver-030')
    a = U.objects.create_user(username='sonde-adoc-ver-030-a', password='x', company=co,
                              is_superuser=True, is_staff=True)
    cab = Cabinet.objects.create(company=co, nom='CAB')
    f = Folder.objects.create(company=co, cabinet=cab, nom='Dossier RH')
    ex = ExigenceDossier.objects.create(company=co, cabinet=cab, folder=f, libelle='CIN')
    dem = services.creer_demande_document(folder=f, company=co, libelle='CIN', created_by=a, exigence=ex)
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(a)
    pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
    r = api.post('/api/django/ged/documents/televerser/',
                 {'folder': f.pk, 'file': SimpleUploadedFile('CIN.pdf', pdf, content_type='application/pdf')},
                 format='multipart', HTTP_HOST='localhost')
    dem.refresh_from_db()
    noms = list(Document.objects.filter(folder=f).values_list('nom', flat=True))
    statut_http = dem.statut
    # Contrôle service (même chemin que le test ADOC177) : noms naturels avec extension.
    res = {}
    for nom in ('CIN.pdf', 'cin.PDF', 'Attestation CNSS.pdf'):
        d2 = services.creer_demande_document(folder=f, company=co, libelle='CIN', created_by=a, exigence=ex) \
            if 'CIN' in nom.upper() else services.creer_demande_document(folder=f, company=co, libelle='Attestation CNSS', created_by=a)
        doc = Document.objects.create(company=co, folder=f, nom=nom)
        s = services.matcher_depot_demandes(doc)
        res[nom] = bool(s)
    check = [(row.get('libelle'), row.get('statut')) for row in services.checklist_dossier(f)]
    print(f"televerser CIN.pdf -> {r.status_code} ; noms={noms} ; demande CIN statut={statut_http} ; "
          f"service soldee par nom={res} ; checklist={check}")
    return {'repro': statut_http != 'soldee'}
