# flake8: noqa  (sonde de vérification C5, rejouable par scripts/sonde.py)
"""C-ACVI-104 (F-5) + C-ACVI-105 (F-6) — deux portes de fondation vers le chatter d'un lead.
F-5 : offlinesync/operations/batch/ (IsResponsableOrAdmin, app de APPS_SANS_MODULE) : Admin RH et Commercial
terrain (403 sur /crm/leads/<id>/ et sur crm/leads/<id>/noter/ = témoins) posent une note (`crm.lead.noter`)
et un tag (`crm.lead.tag`) sur un lead : la portée (AANA41) est appliquée, le droit CRM non. Contraste :
un Commercial « soi » sur le lead d'un collègue reçoit « Lead inconnu. ».
F-6 : records/attachments|comments ne bornent la cible `crm.lead` qu'à la SOCIÉTÉ : un Commercial « soi »
(404 sur la fiche du collègue = témoin) liste et télécharge la pièce du lead du collègue ; Admin RH dépose un
commentaire et une pièce sur ce lead. Le stockage objet est remplacé dans la sonde par un double en mémoire
(`fetch_attachment` / `store_attachment` patchés) : la garde testée est celle de la vue, pas MinIO.
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-104+105", "sha": "352ae5455",
         "attendu": "F-5 : op `error` sans crm_modifier, aucune note ni tag ; F-6 : liste vide / 404 pour le "
                    "Commercial soi, 403 au dépôt pour Admin RH (défaut : applied + écriture ; 200 + octets ; 201)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "records.Attachment", "records.Comment",
                     "offlinesync.OfflineOperation", "roles.Role"]}


def sonde(ctx):
    import json
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead, LeadActivity
    from apps.records.models import Attachment, Comment
    from apps.roles.models import Role
    from apps.roles.permissions_registre import (ADMIN_RH_PERMISSIONS, COMMERCIAL_PERMISSIONS,
                                                 COMMERCIAL_TERRAIN_PERMISSIONS, TECHNICIEN_PERMISSIONS)
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 104', slug='sonde-acvi-104')

    def role(nom, perms):
        return Role.objects.create(company=c, nom=nom + ' sonde 104', permissions=list(perms))
    r_com = role('Commercial', COMMERCIAL_PERMISSIONS)
    rh = U.objects.create_user(username='s104-rh', password='x', company=c, role=role('Admin RH', ADMIN_RH_PERMISSIONS))
    ter = U.objects.create_user(username='s104-terrain', password='x', company=c,
                                role=role('Commercial terrain', COMMERCIAL_TERRAIN_PERMISSIONS))
    tech = U.objects.create_user(username='s104-tech', password='x', company=c,
                                 role=role('Technicien', TECHNICIEN_PERMISSIONS))
    c1 = U.objects.create_user(username='s104-c1', password='x', company=c, role=r_com)
    c2 = U.objects.create_user(username='s104-c2', password='x', company=c, role=r_com)
    lead = Lead.objects.create(company=c, nom='Tazi', prenom='Omar', email='omar@x.ma', telephone='0661000041',
                               ville='Agadir', owner=c1)
    ct = ContentType.objects.get(app_label='crm', model='lead')
    piece = Attachment.objects.create(company=c, content_type=ct, object_id=lead.id, file_key='sonde/facture.pdf',
                                      filename='facture-electricite.pdf', size=10, mime='application/pdf',
                                      uploaded_by=c1)

    def api(u):
        a = APIClient()
        a.force_authenticate(u)
        return a

    def appel(cl, meth, url, corps=None, fmt='json'):
        try:
            with transaction.atomic():
                rr = getattr(cl, meth)(url, corps or {}, format=fmt, HTTP_HOST='localhost')
            if rr.get('Content-Type', '').startswith('application/json'):
                try:
                    return rr.status_code, json.loads(rr.content.decode('utf-8', 'replace'))
                except Exception:
                    pass
            return rr.status_code, {'_octets': bytes(getattr(rr, 'content', b''))[:20].decode('latin-1')}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    def act():
        return LeadActivity.objects.filter(lead=lead).count()

    obs = {}
    # ── F-5 (C-ACVI-104) ──
    f5 = {}
    for nom, u in (('rh', rh), ('terrain', ter), ('c2_soi_contraste', c2)):
        r = {'temoin_GET_lead': appel(api(u), 'get', f'/api/django/crm/leads/{lead.id}/')[0],
             'temoin_POST_crm_noter': appel(api(u), 'post', f'/api/django/crm/leads/{lead.id}/noter/',
                                            {'body': 'temoin'})[0]}
        a0 = act()
        s, rep = appel(api(u), 'post', '/api/django/offlinesync/operations/batch/', {'ops': [
            {'client_op_id': f's104-{nom}-n', 'op_type': 'crm.lead.noter', 'payload': {'lead': lead.id,
                                                                                    'body': f'note {nom}'}},
            {'client_op_id': f's104-{nom}-t', 'op_type': 'crm.lead.tag', 'payload': {'lead': lead.id,
                                                                                  'tag': f'tag-{nom}'}}]})
        res = rep.get('results') if isinstance(rep, dict) else None
        lead.refresh_from_db()
        r['batch'] = [s, [(x.get('op_type'), x.get('status'), x.get('error')) for x in (res or [])]
                      or (rep.get('detail') if isinstance(rep, dict) else str(rep)[:120])]
        r['activites_delta'] = act() - a0
        r['tag_pose'] = f'tag-{nom}' in (lead.tags or [])
        f5[nom] = r
    obs['F5'] = f5
    ok5 = all(f5[k]['temoin_GET_lead'] in (403, 404) and f5[k]['activites_delta'] >= 1 for k in ('rh', 'terrain'))
    # ── F-6 (C-ACVI-105) ──
    obs['F6_temoin_c2_GET_lead_c1'] = appel(api(c2), 'get', f'/api/django/crm/leads/{lead.id}/')[0]
    s, rep = appel(api(c2), 'get', f'/api/django/records/attachments/?model=crm.lead&id={lead.id}')
    ids = [x.get('id') for x in (rep if isinstance(rep, list) else (rep.get('results') or [] if isinstance(rep, dict)
                                                                   else [])) if isinstance(x, dict)]
    obs['F6_c2_liste_pieces_lead_c1'] = [s, piece.id in ids]
    s, rep = appel(api(c2), 'get', '/api/django/records/attachments/')
    ids = [x.get('id') for x in (rep if isinstance(rep, list) else (rep.get('results') or [] if isinstance(rep, dict)
                                                                   else [])) if isinstance(x, dict)]
    obs['F6_c2_liste_sans_filtre_contient_piece'] = [s, piece.id in ids]
    with mock.patch('apps.records.views.fetch_attachment', return_value=(b'%PDF-sonde-104', None)):
        obs['F6_c2_download_piece'] = appel(api(c2), 'get', f'/api/django/records/attachments/{piece.id}/download/')
    obs['F6_temoin_rh_GET_lead'] = f5['rh']['temoin_GET_lead']
    n0 = Comment.objects.filter(object_id=lead.id, content_type=ct).count()
    s, rep = appel(api(rh), 'post', '/api/django/records/comments/',
                   {'model': 'crm.lead', 'id': lead.id, 'body': 'commentaire Admin RH sonde'})
    obs['F6_rh_POST_comment'] = [s, Comment.objects.filter(object_id=lead.id, content_type=ct).count() - n0]
    s, rep = appel(api(tech), 'post', '/api/django/records/comments/',
                   {'model': 'crm.lead', 'id': lead.id, 'body': 'commentaire Technicien sonde'})
    obs['F6_tech_POST_comment'] = [s, Comment.objects.filter(object_id=lead.id, content_type=ct).count() - n0]
    meta = {'file_key': 'sonde/rh.pdf', 'filename': 'rh.pdf', 'size': 4, 'mime': 'application/pdf'}
    n0 = Attachment.objects.filter(object_id=lead.id, content_type=ct).count()
    with mock.patch('apps.records.views.store_attachment', return_value=(meta, None)):
        s, rep = appel(api(rh), 'post', '/api/django/records/attachments/',
                       {'model': 'crm.lead', 'id': str(lead.id),
                        'file': SimpleUploadedFile('rh.pdf', b'%PDF', content_type='application/pdf')}, 'multipart')
    obs['F6_rh_POST_attachment'] = [s, Attachment.objects.filter(object_id=lead.id, content_type=ct).count() - n0,
                                    rep.get('detail') if isinstance(rep, dict) else None]
    ok6 = (obs['F6_temoin_c2_GET_lead_c1'] == 404 and obs['F6_c2_liste_pieces_lead_c1'] == [200, True]) or \
        obs['F6_rh_POST_comment'][0] == 201
    obs['verdicts'] = {'C-ACVI-104': bool(ok5), 'C-ACVI-105': bool(ok6)}
    return {'repro': bool(ok5 and ok6), 'observe': obs}
