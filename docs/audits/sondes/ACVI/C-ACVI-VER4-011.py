# flake8: noqa  (seconde lentille ACVI du 04/11 : jumeau d'ACVI6 sur commentaires et activités)
"""C-ACVI-VER4-011 — ACVI6 a posé `_sans_leads_hors_portee` sur la liste SANS cible des pièces jointes
(`AttachmentViewSet`) mais pas sur `CommentViewSet.get_queryset` ni `ActivityViewSet.get_queryset`
(`apps/records/views.py`), qui ne filtrent que par société quand `model`/`id` manquent. Deux Commerciaux
« soi » (permissions COMMERCIAL_PERMISSIONS), lead de c1 avec un commentaire et une note de chatter ; c2 liste
`/records/comments/` et `/records/activities/` sans cible et lit le détail. Témoin : `/records/attachments/`
sans cible n'expose pas la pièce (ACVI6). Société NEUVE, transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ACVI-VER4-011", "sha": "64c9c7317",
         "attendu": "c2 (« soi ») voit le commentaire / l'activité du lead de c1 en liste sans cible ou en détail ; sain : ni l'un ni l'autre (comme les pièces jointes)",
         "modeles": ["authentication.Company", "roles.Role", "crm.Lead", "records.Comment", "records.Activity",
                     "records.Attachment"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.records.models import Activity, Attachment, Comment
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI VER4-011', slug='sonde-acvi-ver4-011')
    role = Role.objects.create(company=c, nom='Commercial soi', permissions=list(COMMERCIAL_PERMISSIONS))
    c1 = U.objects.create_user(username='sonde-ver4-011-c1', password='x', company=c, role=role)
    c2 = U.objects.create_user(username='sonde-ver4-011-c2', password='x', company=c, role=role)
    L = Lead.objects.create(company=c, nom='Lead de c1', telephone='0661004011', owner=c1)
    ct = ContentType.objects.get_for_model(Lead)
    com = Comment.objects.create(company=c, content_type=ct, object_id=L.pk, body='marge secrète c1', author=c1)
    act = Activity.objects.create(company=c, content_type=ct, object_id=L.pk, kind='note',
                                  body='note privée c1', created_by=c1)
    pj = Attachment.objects.create(company=c, uploaded_by=c1, content_type=ct, object_id=L.pk,
                                   filename='p.pdf', file_key='k/p.pdf', size=1, mime='application/pdf')
    api = APIClient()
    api.force_authenticate(c2)

    def ids(url):
        r = api.get(url, HTTP_HOST='localhost')
        d = r.data
        rows = d.get('results', d) if isinstance(d, dict) else d
        try:
            return r.status_code, [x.get('id') for x in rows]
        except Exception:
            return r.status_code, repr(d)[:120]

    obs = {
        'c2_voit_lead_c1_en_cible': ids(f'/api/django/records/comments/?model=crm.lead&id={L.pk}'),
        'comments_sans_cible': ids('/api/django/records/comments/'),
        'activities_sans_cible': ids('/api/django/records/activities/'),
        'attachments_sans_cible_temoin': ids('/api/django/records/attachments/'),
        'comment_detail': api.get(f'/api/django/records/comments/{com.pk}/', HTTP_HOST='localhost').status_code,
        'activity_detail': api.get(f'/api/django/records/activities/{act.pk}/', HTTP_HOST='localhost').status_code,
        'ids': {'comment': com.pk, 'activity': act.pk, 'attachment': pj.pk},
    }
    fuite_com = isinstance(obs['comments_sans_cible'][1], list) and com.pk in obs['comments_sans_cible'][1]
    fuite_act = isinstance(obs['activities_sans_cible'][1], list) and act.pk in obs['activities_sans_cible'][1]
    fuite_det = obs['comment_detail'] == 200 or obs['activity_detail'] == 200
    obs['fuites'] = {'liste_comment': fuite_com, 'liste_activity': fuite_act, 'detail': fuite_det}
    print(obs)
    return {'repro': bool(fuite_com or fuite_act or fuite_det), 'observe': obs}
