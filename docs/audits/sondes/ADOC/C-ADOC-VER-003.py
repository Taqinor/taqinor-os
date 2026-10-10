# SONDE = {'constat': 'C-ADOC-VER-003', 'sha': '1a186a82c', 'attendu': "POST /ged/documents/<D>/nouvelle-version/ pendant une demande de signature en_attente → 409, une seule version (aujourd'hui : 201, v2 créée — le signataire signera un autre contenu que celui envoyé)"}
# Écart ADOC68 : l'action nouvelle_version (ajoutée par ADOC18 après ADOC68) n'appelle pas assert_aucune_signature_en_attente.
import secrets
from unittest import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from authentication.models import CustomUser
from apps.ged.models import Cabinet, Folder, Document, DocumentVersion, DemandeSignatureDocument
from apps.ged import services
u = CustomUser.objects.get(username='demo_admin')
co = u.company
PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
try:
    with transaction.atomic():
        cab = Cabinet.objects.create(company=co, nom='SONDE-ADOC68')
        f = Folder.objects.create(company=co, cabinet=cab, nom='Contrats sonde')
        d = Document.objects.create(company=co, folder=f, nom='Contrat a signer.pdf')
        services.add_version(d, file_key='sonde/v1.pdf', company=co, filename='v1.pdf', size=len(PDF), mime='application/pdf', checksum=services.compute_checksum(PDF), uploaded_by=u)
        dem = DemandeSignatureDocument.objects.create(company=co, document=d, signataire_nom='Client', signataire_email='client@sonde.invalid', token=secrets.token_urlsafe(16))
        print('demande', dem.statut, 'versions avant', DocumentVersion.objects.filter(document=d).count())
        c = APIClient(); c.force_authenticate(user=u)
        fake = ({'file_key': 'sonde/v2.pdf', 'filename': 'v2.pdf', 'mime': 'application/pdf'}, None)
        with mock.patch('apps.ged.views.store_attachment', return_value=fake):  # MinIO seul simulé
            r = c.post(f'/api/django/ged/documents/{d.pk}/nouvelle-version/', {'file': SimpleUploadedFile('v2.pdf', PDF + b'%modifie', content_type='application/pdf')}, format='multipart')
        print('nouvelle-version pendant signature en_attente ->', r.status_code, 'versions après', DocumentVersion.objects.filter(document=d).count())
        # comparaison : la route versions (gardée par ADOC68)
        print('mails', len(mail.outbox), 'celery', _CELERY_CALLS)
        raise R()
except R:
    print('ROLLED BACK')
