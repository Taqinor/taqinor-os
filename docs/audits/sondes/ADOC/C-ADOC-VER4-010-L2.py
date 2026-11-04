# flake8: noqa  (seconde lentille « vérifie ADOC » du 04/11/2026, rejouable par scripts/sonde.py — AMET93)
"""C-ADOC-VER4-010, reproduction INDÉPENDANTE (seconde lentille). Différences avec la sonde 1 :
import par la TÂCHE planifiée réelle (`ged.tasks.migrer_pieces_jointes_task`, beat hebdo WIR73), voie
de destruction = DISPOSITION « détruire » approuvée puis exécutée (`executer_demande_disposition`), au
lieu de la corbeille ; ET sens inverse : une 2e pièce jointe importée puis supprimée par la route réelle
DELETE /api/django/records/attachments/<id>/ — la version GED garde-t-elle un binaire ? Seul le client
MinIO est simulé (on enregistre les `delete_object`). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADOC-VER4-010", "sha": "c38868a62",
         "attendu": "repro=True si la disposition « détruire » du document GED importé efface la clé K1 encore portée par la records.Attachment ; info : sens inverse (DELETE pièce jointe efface K2 encore portée par une DocumentVersion)",
         "modeles": ["authentication.Company", "records.Attachment", "ged.Document", "ged.DocumentVersion",
                     "ged.Folder", "ged.Cabinet", "ged.DocumentLien", "ged.DemandeDisposition",
                     "ged.CertificatDestruction"]}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.records.models import Attachment
    from apps.ged import services
    from apps.ged.models import DemandeDisposition, DocumentVersion, CertificatDestruction
    from apps.ged.tasks import migrer_pieces_jointes_task
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER4-010-L2', slug='sonde-adoc-ver4-010-l2')
    dem = U.objects.create_user(username='sonde-v4010l2-dem', password='x', company=co, role_legacy='admin')
    app = U.objects.create_user(username='sonde-v4010l2-app', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client L2', email='l2-ver4010@example.invalid')
    ct = ContentType.objects.get_for_model(Client)
    K1 = 'attachments/sonde-ver4-010-l2-facture-fournisseur.pdf'
    K2 = 'attachments/sonde-ver4-010-l2-photo-toiture.jpg'
    a1 = Attachment.objects.create(company=co, content_type=ct, object_id=cl.pk, file_key=K1,
                                   filename='facture-fournisseur.pdf', size=10, mime='application/pdf',
                                   uploaded_by=dem)
    a2 = Attachment.objects.create(company=co, content_type=ct, object_id=cl.pk, file_key=K2,
                                   filename='photo-toiture.jpg', size=10, mime='image/jpeg', uploaded_by=dem)
    res = migrer_pieces_jointes_task()
    v1 = DocumentVersion.objects.filter(company=co, file_key=K1).first()
    v2 = DocumentVersion.objects.filter(company=co, file_key=K2).first()
    if v1 is None or v2 is None:
        return {'repro': False, 'note': f'tâche n a pas importé (res={res})'}
    effaces = []

    class _Client:
        def delete_object(self, **kw):
            effaces.append(kw.get('Key'))

    d = DemandeDisposition.objects.create(company=co, libelle='sonde L2', action='detruire',
                                          documents=[v1.document_id], demandeur=dem)
    services.approuver_demande_disposition(d, user=app)
    d.refresh_from_db()
    with mock.patch('apps.records.storage.get_minio_client', return_value=_Client()):
        certs = services.executer_demande_disposition(d, user=app)
    k1_efface = K1 in effaces
    a1_porte_k1 = Attachment.objects.filter(pk=a1.pk, file_key=K1).exists()
    # Sens inverse : suppression de la pièce jointe par la route réelle.
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(dem)
    effaces2 = []

    class _Client2:
        def delete_object(self, **kw):
            effaces2.append(kw.get('Key'))

    with mock.patch('apps.records.storage.get_minio_client', return_value=_Client2()):
        r = api.delete(f'/api/django/records/attachments/{a2.pk}/', HTTP_HOST='localhost')
    v2_reste = DocumentVersion.objects.filter(pk=v2.pk, file_key=K2).exists()
    print(f"tache={res} ; disposition -> certificats={len(certs)} delete_object={effaces} ; "
          f"K1 efface={k1_efface} records.Attachment porte encore K1={a1_porte_k1} ; "
          f"inverse : DELETE pièce jointe -> {r.status_code} delete_object={effaces2} "
          f"DocumentVersion porte encore K2={v2_reste} (version GED sans binaire={K2 in effaces2 and v2_reste})")
    return {'repro': bool(k1_efface and a1_porte_k1)}
