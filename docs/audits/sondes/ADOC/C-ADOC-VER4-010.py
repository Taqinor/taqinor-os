# flake8: noqa  (sonde de contre-visite « vérifie ADOC » du 04/11/2026, rejouable par scripts/sonde.py — AMET93)
"""ADOC29/ADOC189 rejoués sur c38868a62 : `ged/services.py::_cles_binaires_exclusives` ne cherche une clé
partagée que parmi les AUTRES `DocumentVersion` ; or `migrate_attachments_to_ged.import_attachments`
(planifié chaque semaine, WIR73 `ged.migrer_pieces_jointes`) crée la version GED en RÉUTILISANT la clé
MinIO de la `records.Attachment` d'origine (« aucun fichier recopié »). Scénario : une pièce jointe de
client (records.Attachment, clé K) est importée en GED ; le document GED est mis en corbeille puis purgé
définitivement. Seul le client MinIO est simulé (on enregistre les `delete_object`).
Attendu sain : K n'est jamais effacée tant que la pièce jointe la référence.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADOC-VER4-010", "sha": "c38868a62",
         "attendu": "repro=True si la purge GED efface du bucket la clé encore portée par la records.Attachment d'origine (pièce jointe du client sans binaire) ; sain : delete_object jamais appelé avec K",
         "modeles": ["authentication.Company", "records.Attachment", "ged.Document",
                     "ged.DocumentVersion", "ged.Folder", "ged.Cabinet", "ged.DocumentLien"]}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.records.models import Attachment
    from apps.ged import services
    from apps.ged.models import Document, DocumentVersion
    from apps.ged.management.commands.migrate_attachments_to_ged import import_attachments
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER4-010', slug='sonde-adoc-ver4-010')
    a = U.objects.create_user(username='sonde-adoc-ver4-010', password='x', company=co,
                              role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client K', email='k-ver4010@example.invalid')
    K = 'attachments/sonde-ver4-010-contrat-signe.pdf'
    att = Attachment.objects.create(
        company=co, content_type=ContentType.objects.get_for_model(Client), object_id=cl.pk,
        file_key=K, filename='contrat-signe.pdf', size=10, mime='application/pdf', uploaded_by=a)
    res = import_attachments(company=co, dry_run=False)
    v = DocumentVersion.objects.filter(company=co, file_key=K).select_related('document').first()
    if v is None:
        return {'repro': False, 'note': f'import n a cree aucune version (res={res})'}
    doc = v.document
    services.mettre_en_corbeille(doc, a)
    doc.refresh_from_db()
    effaces = []

    class _Client:
        def delete_object(self, **kw):
            effaces.append(kw.get('Key'))

    with mock.patch('apps.records.storage.get_minio_client', return_value=_Client()):
        services.purger_definitivement(doc)
    att_existe = Attachment.objects.filter(pk=att.pk, file_key=K).exists()
    print(f"import={res} ; version GED reutilise la cle K={v.file_key == K} ; "
          f"purge -> delete_object={effaces} ; records.Attachment portant K encore en base={att_existe} ; "
          f"document GED en base={Document.objects.filter(pk=v.document_id).exists()}")
    return {'repro': (K in effaces) and att_existe}
