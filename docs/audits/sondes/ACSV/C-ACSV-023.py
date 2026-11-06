# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K23 — photo de preuve d'une étape de checklist « photo obligatoire » supprimée depuis la galerie du
chantier (DELETE records/attachments/<id>/) : aucun motif, aucune note au chatter du chantier ; l'étape
reste cochée avec 0 photo et la garde photos du chantier passe. Témoin : la garde au cochage refuse
bien une étape sans photo. Vraies routes : POST chantiers/<id>/checklist-photo/, POST
chantiers/<id>/cocher-checklist/, DELETE records/attachments/<id>/. Stockage objet MOQUÉ (aucun objet
MinIO touché)."""
SONDE = {"constat": "C-ACSV-023", "sha": "f57951e87",
         "attendu": "repro si DELETE = 204 sans motif, item.fait reste vrai, 0 photo liée, "
                    "_gate_check_photos None et 0 InstallationActivity ajoutée par la suppression",
         "modeles": ["records.Attachment", "installations.PhotoChecklistMeta",
                     "installations.ChantierChecklistItem", "installations.InstallationActivity"]}


def sonde(ctx):
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, ChantierChecklistItem, InstallationActivity
    from apps.installations.services import _gate_check_photos
    from apps.records.models import Attachment
    import apps.records.views as rviews

    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde ACSV 023', slug='sonde-acsv-023')
    u = get_user_model().objects.create_user(username='sonde_acsv_023', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='A023', email='a023@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-A023', client=cl, statut='en_cours')
    item = ChantierChecklistItem.objects.create(company=co, installation=inst, cle='cablage',
                                                libelle='Câblage', ordre=1, photo_obligatoire=True)
    ct = ContentType.objects.get_for_model(Installation)
    obs = {}
    # Témoin : cocher sans photo → refus
    r0 = api.post(f'{B}/chantiers/{inst.id}/cocher-checklist/', {'cle': 'cablage', 'fait': True},
                  format='json', **H)
    obs['T_cocher_sans_photo'] = r0.status_code
    att = Attachment.objects.create(company=co, content_type=ct, object_id=inst.id, uploaded_by=u,
                                    file_key='attachments/sonde-a023.jpg', filename='cablage.jpg',
                                    size=10, mime='image/jpeg')
    rm = api.post(f'{B}/chantiers/{inst.id}/checklist-photo/', {'attachment': att.id, 'cle': 'cablage'},
                  format='json', **H)
    obs['meta'] = rm.status_code
    r1 = api.post(f'{B}/chantiers/{inst.id}/cocher-checklist/', {'cle': 'cablage', 'fait': True},
                  format='json', **H)
    obs['cocher_avec_photo'] = r1.status_code
    item.refresh_from_db()
    obs['fait_avant'] = item.fait
    obs['gate_avant'] = _gate_check_photos(inst)
    nb_act = InstallationActivity.objects.filter(installation=inst).count()
    with mock.patch.object(rviews, 'delete_attachment', lambda *a, **k: None):
        rd = api.delete(f'/api/django/records/attachments/{att.id}/', **H)
    obs['delete'] = rd.status_code
    item.refresh_from_db()
    obs['fait_apres'] = item.fait
    obs['photos_liees_apres'] = item.photos.count()
    obs['gate_apres'] = _gate_check_photos(inst)
    obs['activites_ajoutees'] = InstallationActivity.objects.filter(installation=inst).count() - nb_act
    print(obs)
    obs['repro'] = bool(r0.status_code in (400, 409) and r1.status_code == 200 and rd.status_code == 204
                        and item.fait and obs['photos_liees_apres'] == 0 and obs['gate_apres'] is None
                        and obs['activites_ajoutees'] == 0)
    return obs
