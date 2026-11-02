SONDE = {"constat": "C-ADOC-VER-031", "sha": "56d5b623a",
         "attendu": "ADOC29 : un échec de l'appel MinIO (delete_object) pendant la purge définitive laisse le document en place (rien de détruit à moitié) — jamais un document effacé dont le binaire reste dans le bucket"}


def sonde(ctx):
    from unittest import mock
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.ged.models import Cabinet, Folder, Document, DocumentVersion
    from apps.ged import services
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER-031', slug='sonde-adoc-ver-031')
    a = U.objects.create_user(username='sonde-adoc-ver-031-a', password='x', company=co,
                              is_superuser=True, is_staff=True)
    cab = Cabinet.objects.create(company=co, nom='CAB')
    f = Folder.objects.create(company=co, cabinet=cab, nom='F')
    doc = Document.objects.create(company=co, folder=f, nom='contrat.pdf')
    DocumentVersion.objects.create(company=co, document=doc, version=1,
                                   file_key='attachments/sonde-ver-031.pdf')
    doc_id = doc.pk
    services.mettre_en_corbeille(doc, a)

    class _ClientEnPanne:
        def delete_object(self, **kw):
            raise ConnectionError('minio indisponible (simulé)')

    exc = None
    # Seul l'appel MinIO est simulé ; records.storage.delete_attachment tourne réellement.
    with mock.patch('apps.records.storage.get_minio_client', return_value=_ClientEnPanne()):
        try:
            services.purger_definitivement(doc)
        except Exception as e:  # noqa: BLE001
            exc = repr(e)
    existe = Document.objects.filter(pk=doc_id).exists()
    print(f"purge avec MinIO en panne -> exception={exc} ; document encore en base={existe}")
    return {'repro': not existe}
