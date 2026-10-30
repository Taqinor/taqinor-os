# flake8: noqa  (sonde de contre-visite vérifie ACHT, rejouable par scripts/sonde.py — AMET93)
"""ACHT41 : sur une intervention terminée, le serveur exige un motif de suppression (409) ; l'écran
(`installationsApi.supprimerPhoto` / `supprimerSerial` / `supprimerMemo` / `supprimerLigneConsommation`)
n'envoie jamais de motif : aucune preuve supprimable depuis l'écran. Corps exact de l'écran. Transaction
annulée, aucun objet MinIO touché (refus avant suppression)."""
SONDE = {"constat": "C-ACHT-VER-008", "sha": "db8ca9670",
         "attendu": "POST supprimer-photo {photo} (corps de l'écran) sur intervention terminée : 409, photo intacte"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import Installation, Intervention
    from apps.records.models import Attachment
    co = Company.objects.create(nom='Sonde ACHT VER-005', slug='sonde-acht-ver-005')
    u = get_user_model().objects.create_user(username='sonde-acht-ver-005', password='x', company=co, role_legacy='admin')
    inst = Installation.objects.create(company=co, reference='CH-SONDE-ACHT-005')
    iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose', created_by=u,
                                     technicien=u, statut=Intervention.Statut.TERMINEE)
    att = Attachment.objects.create(company=co, content_type=ContentType.objects.get_for_model(Intervention),
                                    object_id=iv.id, file_key=f'sonde/acht-005/{iv.id}', filename='slot:facade|p.png',
                                    uploaded_by=u)
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/installations/interventions/{iv.id}/supprimer-photo/', {'photo': att.id},
                 format='json', HTTP_HOST='localhost')
    intacte = Attachment.objects.filter(pk=att.pk).exists()
    print(f'supprimer-photo(corps écran)={r.status_code} detail={getattr(r, "data", None)} photo_intacte={intacte}')
    return {'repro': r.status_code == 409 and intacte, 'statut': r.status_code, 'photo_intacte': intacte}
