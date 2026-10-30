SONDE = {"constat": "C-ASEC-008", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : PATCH/POST devis avec roof_image 'roofs/<id B>/x.png' -> ignoré (valeur en "
                    "base inchangée, champ toujours lisible) ; GED POST versions avec file_key/checksum de B et sans "
                    "fichier -> 400, aucune version ; aperçu d'une version portant une clé de B -> 404 sans octet ; "
                    "moteur : clé de toit de B -> download_roof_image NON appelé, rendu '' ; clé de A -> appelé"}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Devis
    from apps.ventes.quote_engine import artefacts_rendu
    from apps.ged import services
    from apps.ged.models import Cabinet, Document, DocumentVersion, Folder
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    P = 'sonde-asec008-'
    a = Company.objects.create(nom='Sonde ASEC008 A', slug=P + 'a')
    b = Company.objects.create(nom='Sonde ASEC008 B', slug=P + 'b')
    resp = User.objects.create_user(username=P + 'resp', password='x', role_legacy='responsable', company=a)
    admin = User.objects.create_user(username=P + 'admin', password='x', role_legacy='admin', company=a)
    api_r, api_ad = APIClient(), APIClient()
    api_r.force_authenticate(resp)
    api_ad.force_authenticate(admin)
    obs, tous = {}, []

    def note(site, geste, ok, **kw):
        obs.setdefault(site, []).append({'geste': geste, 'ok': bool(ok), **kw})
        tous.append(bool(ok))

    # ---------- ASEC22 : roof_image en lecture seule ----------
    S = 'ASEC22'
    cl = Client.objects.create(company=a, nom='Client', prenom='A', email='asec008@sonde.invalid',
                               telephone='+212600000008', adresse='Casa')
    cle_a = f'roofs/{a.id}/DEV-SONDE-ASEC008-1.png'
    cle_b = f'roofs/{b.id}/x.png'
    devis = Devis.objects.create(company=a, reference='DEV-SONDE-ASEC008-1', client=cl,
                                 statut=Devis.Statut.BROUILLON, roof_image=cle_a)
    r = api_r.patch(f'/api/django/ventes/devis/{devis.id}/', {'roof_image': cle_b}, format='json', **H)
    devis.refresh_from_db()
    note(S, "PATCH devis roof_image='roofs/<B>/x.png'", r.status_code == 200 and devis.roof_image == cle_a,
         http=r.status_code, roof_image_relu=devis.roof_image)
    r = api_r.post('/api/django/ventes/devis/', {'client': cl.id, 'taux_tva': '20', 'roof_image': cle_b},
                   format='json', **H)
    nouveau = Devis.objects.filter(pk=r.data.get('id')).first() if isinstance(getattr(r, 'data', None), dict) else None
    note(S, "POST devis roof_image de B", r.status_code == 201 and nouveau is not None
         and nouveau.roof_image in (None, ''), http=r.status_code,
         roof_image_relu=getattr(nouveau, 'roof_image', 'devis absent'))
    r = api_r.get(f'/api/django/ventes/devis/{devis.id}/', **H)
    note(S, 'contre-épreuve GET devis : roof_image reste lisible', r.status_code == 200 and 'roof_image' in r.data,
         http=r.status_code)

    # ---------- ASEC37 : GED, clé de stockage du client ----------
    S = 'ASEC37'
    cab = Cabinet.objects.create(company=a, nom='Cab A')
    folder = Folder.objects.create(company=a, cabinet=cab, nom='Racine A')
    doc = Document.objects.create(company=a, folder=folder, nom='Contrat A')
    cle_ged_b = f'attachments/{b.pk}/secret-b.pdf'
    n0 = DocumentVersion.objects.count()
    r = api_ad.post('/api/django/ged/versions/', {'document': doc.pk, 'file_key': cle_ged_b, 'checksum': 'x'},
                    format='json', **H)
    note(S, 'POST versions file_key/checksum de B, sans fichier (JSON)',
         r.status_code == 400 and doc.versions.count() == 0 and DocumentVersion.objects.count() == n0
         and not DocumentVersion.objects.filter(file_key=cle_ged_b).exists(),
         http=r.status_code, versions_relues=doc.versions.count())
    version = services.add_version(doc, file_key=cle_ged_b, company=a, filename='b.pdf', mime='application/pdf',
                                   uploaded_by=admin)
    r = api_ad.get(f'/api/django/ged/versions/{version.pk}/apercu/', **H)
    corps = r.content if hasattr(r, 'content') and not getattr(r, 'streaming', False) else b''
    note(S, 'aperçu d\'une version portant une clé de B (posée en base)',
         r.status_code == 404 and b'%PDF' not in corps, http=r.status_code)
    resultats_non_rejoues = ('multipart avec fichier (écrit sur MinIO, HTTP sortant bloqué par le lanceur) ; '
                             'classer-apres-vente et scan-lot non rejoués')

    # ---------- ASEC24 : le moteur refuse une clé de toit étrangère ----------
    S = 'ASEC24'
    PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
    Devis.objects.filter(pk=devis.pk).update(roof_image=cle_b)
    devis.refresh_from_db()
    with mock.patch('apps.ventes.utils.pdf.download_roof_image', return_value=PNG) as dl:
        uri = artefacts_rendu._roof_render_data_uri(devis)
    note(S, "_roof_render_data_uri : clé 'roofs/<B>/x.png' sur un devis de A",
         uri == '' and dl.call_count == 0, rendu=repr(uri), appels_download=dl.call_count)
    Devis.objects.filter(pk=devis.pk).update(roof_image=cle_a)
    devis.refresh_from_db()
    with mock.patch('apps.ventes.utils.pdf.download_roof_image', return_value=PNG) as dl:
        uri = artefacts_rendu._roof_render_data_uri(devis)
    note(S, "contre-épreuve : clé de A -> téléchargée et rendue",
         dl.call_count == 1 and uri.startswith('data:image/png;base64,'), appels_download=dl.call_count)

    return {'sites': obs, 'gestes_total': len(tous), 'gestes_ko': tous.count(False),
            'non_rejoue': resultats_non_rejoues,
            'couverture': 'ASEC22 (roof_image), ASEC37 (file_key du corps + aperçu clé étrangère), '
                          'ASEC24 (lecteur du moteur, fonction _roof_render_data_uri, pas la planche calepinage)',
            'repro': bool(tous) and all(tous)}
