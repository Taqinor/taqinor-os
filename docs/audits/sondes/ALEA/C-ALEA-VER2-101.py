SONDE = {"constat": "C-ALEA-VER2-101", "sha": "ce3356e48",
         "attendu": "jumeau d'ALEA13 : DELETE /api/django/visites/visites/<id>/ (visite brouillon portant une photo) "
                    "répond 204, VisiteMedia supprimé en cascade, mais l'Attachment de la photo reste sur le lead "
                    "(photo fantôme dans le panneau pièces jointes)",
         "modeles": ["authentication.Company", "crm.Lead", "visites.VisiteTerrain", "visites.VisiteMedia",
                     "records.Attachment"]}


def sonde(ctx):
    from django.contrib.contenttypes.models import ContentType
    from apps.crm.models import Lead
    from apps.records.models import Attachment
    from apps.visites.models import VisiteMedia, VisiteTerrain
    from apps.visites.tests.test_visite_terrain import TERRAIN, auth, make_user
    from authentication.models import Company

    co = Company.objects.create(nom='Sonde ALEA VER2 101', slug='sonde-alea-ver2-101')
    user = make_user(co, 'sonde-alea-ver2-101', TERRAIN)
    lead = Lead.objects.create(company=co, nom='Lead sonde 101')
    api = auth(user)
    resp = api.post('/api/django/visites/visites/', {'lead': lead.id}, format='json')
    print('creation visite', resp.status_code)
    visite_id = resp.data['id']
    ct = ContentType.objects.get(app_label='crm', model='lead')
    att = Attachment.objects.create(company=co, content_type=ct, object_id=lead.id,
                                    file_key='sonde/alea-ver2-101.png', filename='p.png', size=1, mime='image/png')
    media = VisiteMedia.objects.create(company=co, visite_id=visite_id, attachment=att,
                                       slot_code='general_facade')
    resp = api.delete(f'/api/django/visites/visites/{visite_id}/')
    visite_existe = VisiteTerrain.objects.filter(pk=visite_id).exists()
    media_existe = VisiteMedia.objects.filter(pk=media.id).exists()
    att_existe = Attachment.objects.filter(pk=att.id).exists()
    print(f'DELETE visite -> {resp.status_code} ; visite existe={visite_existe} ; media existe={media_existe} ; '
          f'attachment du lead existe={att_existe}')
    return {'repro': resp.status_code in (200, 204) and not media_existe and att_existe,
            'status': resp.status_code, 'attachment_restant': att_existe}
