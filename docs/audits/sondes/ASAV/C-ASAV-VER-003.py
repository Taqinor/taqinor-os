SONDE = {"constat": "C-ASAV-VER-003", "sha": "641a2266d",
         "attendu": "ancien ticket de même texte sur l'équipement ; signalement QR refusé pour sa photo (HEIC, 400) puis renvoyé sans photo → 201, nouveau ticket (pas 200 avec l'ancienne référence)"}


def sonde(ctx):
    from datetime import timedelta
    from unittest import mock
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.sav.models import Equipement, Ticket
    from apps.stock.models import Produit
    today = timezone.localdate()
    texte = 'Onduleur bip sonde VER-003'
    co = Company.objects.create(nom='Sonde ASAV VER-003', slug='sonde-asav-ver-003')
    cl = Client.objects.create(company=co, nom='Client', prenom='VER003', email='sonde-asav-ver-003@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-ASAV-003', client=cl)
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ASAV-003', prix_achat=0, prix_vente=100)
    eq = Equipement.objects.create(company=co, produit=p, installation=inst)
    token = eq.ensure_public_token()
    ancien = Ticket.objects.create(company=co, reference='SAV-SONDE-003-ANCIEN', client=cl, installation=inst, equipement=eq,
                                   type=Ticket.Type.CORRECTIF, description=texte, date_ouverture=today - timedelta(days=40))
    statut_resolu = getattr(Ticket.Statut, 'RESOLU', None)
    if statut_resolu is not None:
        Ticket.objects.filter(pk=ancien.pk).update(statut=statut_resolu)
    heic = b'\x00\x00\x00\x18ftypheic' + b'\x00' * 32
    url = f'/api/django/public/sav/equipement/{token}/signaler/'
    api = APIClient()
    with mock.patch('apps.records.storage.get_minio_client'), mock.patch('apps.records.storage.ensure_uploads_bucket'):
        r1 = api.post(url, {'description': texte, 'photo': SimpleUploadedFile('photo.heic', heic)}, format='multipart', HTTP_HOST='localhost')
        r2 = api.post(url, {'description': texte}, format='multipart', HTTP_HOST='localhost')
    n = Ticket.objects.filter(equipement=eq).count()
    ref2 = (getattr(r2, 'data', None) or {}).get('reference')
    print(f'1er envoi (HEIC)={r1.status_code} renvoi sans photo={r2.status_code} référence={ref2} '
          f'ancienne={ancien.reference} tickets de l’équipement={n} (attendu 400 puis 201, 2 tickets)')
    return {'repro': r1.status_code == 400 and r2.status_code == 200 and ref2 == ancien.reference and n == 1,
            'envoi': r1.status_code, 'renvoi': r2.status_code, 'reference': ref2, 'tickets': n}
