SONDE = {"constat": "C-ADOC-VER-021", "sha": "56d5b623a",
         "attendu": "ADOC26 : tout alias accepte par le dialogue du dossier (motif publie : lettres, chiffres, point, tiret, souligne) classe l'e-mail adresse a ged+<alias>@ dans ce dossier"}


def sonde(ctx):
    from email.message import EmailMessage
    from unittest import mock
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.ged.models import Cabinet, Folder
    from apps.ged import services
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER-021', slug='sonde-adoc-ver-021')
    a = U.objects.create_user(username='sonde-adoc-ver-021-a', password='x', company=co, is_superuser=True, is_staff=True)
    cab = Cabinet.objects.create(company=co, nom='CAB')
    f = Folder.objects.create(company=co, cabinet=cab, nom='Compta')
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(a)
    r = api.patch(f'/api/django/ged/dossiers/{f.pk}/', {'alias_email': 'compta.2026'}, format='json', HTTP_HOST='localhost')
    f.refresh_from_db()
    msg = EmailMessage()
    msg['From'] = 'fournisseur@example.com'
    msg['To'] = 'ged+compta.2026@taqinor.ma'
    msg['Subject'] = 'Facture'
    msg['Message-ID'] = '<sonde-adoc-ver-021@x.com>'
    msg.set_content('Voir piece jointe.')
    msg.add_attachment(b'%PDF-1.4\n%test\n%%EOF', maintype='application', subtype='pdf', filename='facture.pdf')
    with mock.patch('apps.records.storage.store_attachment',
                    return_value=({'file_key': f'attachments/{co.pk}/f.pdf', 'filename': 'facture.pdf', 'size': 20, 'mime': 'application/pdf'}, None)):
        crees = services.importer_message_email(msg.as_bytes(), company=co)
    print(f"PATCH alias 'compta.2026' -> {r.status_code} ; alias_en_base={f.alias_email!r} ; extraire_alias={services.extraire_alias_email(to_addr='ged+compta.2026@taqinor.ma')!r} ; documents_crees={len(crees)}")
    return {'repro': r.status_code == 200 and f.alias_email == 'compta.2026' and len(crees) == 0}
