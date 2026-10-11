SONDE = {"constat": "C-ADOC-VER-005", "sha": "6f3191ad7",
         "attendu": "une disposition « archiver » approuvée dont un document est en corbeille s'exécute en ignorant ce document (demande exécutée), jamais ValueError/500 avec la demande bloquée « approuvée »"}


def sonde(ctx):
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.ged.models import Cabinet, Folder, Document, DemandeDisposition
    from apps.ged import services
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER-005', slug='sonde-adoc-ver-005')
    a1 = U.objects.create_user(username='sonde-adoc-ver-005-a1', password='x', company=co, is_superuser=True, is_staff=True)
    a2 = U.objects.create_user(username='sonde-adoc-ver-005-a2', password='x', company=co, is_superuser=True, is_staff=True)
    cab = Cabinet.objects.create(company=co, nom='CAB')
    f = Folder.objects.create(company=co, cabinet=cab, nom='F')
    doc = Document.objects.create(company=co, folder=f, nom='ancien-contrat.pdf')
    services.mettre_en_corbeille(doc, a1)
    d = services.creer_demande_disposition(co, libelle='archivage', document_ids=[doc.pk], action='archiver', user=a1)
    services.approuver_demande_disposition(d, user=a2)
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(a2)
    r = api.post(f'/api/django/ged/demandes-disposition/{d.pk}/executer/', {}, format='json', HTTP_HOST='localhost')
    d.refresh_from_db()
    print(f"executer -> {r.status_code} ; demande.statut={d.statut} ; corps={str(getattr(r, 'content', b''))[:160]}")
    return {'repro': r.status_code >= 500 or d.statut != 'executee'}
