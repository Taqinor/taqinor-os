# flake8: noqa  (contre-visite ACVI64 — effet de bord sur texture_toit_pour_lead)
"""Jumeau d'ACVI64 : avant, texture_toit_pour_lead prenait la dernière visite validée AYANT une photo de toit
(`.exclude(photo_toit_key='')`). Après, elle prend la visite de référence puis exige la photo. Cas : V1 validée
(photo de toit), V2 validée sans photo de toit (autre gabarit, p. ex. relevé point d'eau). `repro` = la texture de V1
disparaît (régression d'effet de bord). Société NEUVE, transaction annulée."""
SONDE = {"constat": "ACVI64 effet de bord texture", "sha": "06ced8b1a",
         "attendu": "texture de V1 conservée quand une V2 validée sans photo la suit",
         "modeles": ["crm.Lead", "visites.VisiteTerrain"]}


def sonde(ctx):
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.visites import selectors as vsel
    from apps.visites.models import VisiteTerrain
    c = Company.objects.create(nom='Sonde VER1 202', slug='sonde-ver1-202')
    L = Lead.objects.create(company=c, nom='Texture', telephone='0661000202')
    V1 = VisiteTerrain.objects.create(company=c, lead=L, statut=VisiteTerrain.Statut.VALIDEE, photo_toit_key='sonde/toit-v1.jpg')
    seule = vsel.texture_toit_pour_lead(L)
    V2 = VisiteTerrain.objects.create(company=c, lead=L, statut=VisiteTerrain.Statut.VALIDEE)
    apres = vsel.texture_toit_pour_lead(L)
    obs = {'V1': V1.id, 'V2': V2.id, 'texture_V1_seule': seule.get('visite_id'), 'texture_apres_V2_validee_sans_photo': apres.get('visite_id'),
           'gabarits': list(VisiteTerrain.objects.filter(lead=L).order_by('id').values_list('gabarit', flat=True))}
    return {'repro': seule.get('visite_id') == V1.id and apres.get('visite_id') is None, 'observe': obs}
