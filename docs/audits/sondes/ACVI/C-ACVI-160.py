# flake8: noqa  (sonde de vérification PA1 lane E, rejouable par scripts/sonde.py)
"""E-1 / E-21 (C-ACVI-160, 180) — rôle « Commercial terrain » (COMMERCIAL_TERRAIN_PERMISSIONS, sans crm_voir),
société démo 1, transaction annulée. E-1 : T1 ne lit pas le lead L (témoin) mais POST /visites/visites/
{lead: L, date_prevue: +9, commercial: T1} → 201 avec client_panel + devis ? la visite brouillon de T2 (+5 j)
est-elle déplacée et réassignée à T1 ? T2 la perd-il (404) ? E-21 : une photo (Attachment du lead) de la
visite de T2 lue par T1 (non assigné) via /records/attachments/<id>/ et /download/ (fetch_attachment simulé,
aucun accès MinIO)."""
SONDE = {"constat": "C-ACVI-160+180", "sha": "352ae5455",
         "attendu": "défaut : lead illisible (403/404) mais visite créée 201 avec client_panel/devis, visite de T2 "
                    "déplacée et réassignée ; photo d'autrui lisible 200",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "visites.VisiteTerrain",
                     "visites.VisiteMedia", "records.Attachment", "roles.Role"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.records.models import Attachment
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_TERRAIN_PERMISSIONS
    from apps.ventes.models import Devis
    from apps.visites.models import VisiteTerrain, VisiteMedia
    U = get_user_model()
    ua = U.objects.get(username='demo_admin')
    c = ua.company
    role = Role.objects.create(company=c, nom='Commercial terrain sonde 160',
                               permissions=list(COMMERCIAL_TERRAIN_PERMISSIONS))
    t1 = U.objects.create_user(username='sonde-acvi-160-t1', password='x', company=c, role=role)
    t2 = U.objects.create_user(username='sonde-acvi-160-t2', password='x', company=c, role=role)
    A1, A2 = APIClient(), APIClient()
    A1.force_authenticate(t1)
    A2.force_authenticate(t2)

    def appel(cl, meth, url, corps=None):
        try:
            with transaction.atomic():
                if meth in ('get', 'delete'):
                    r = getattr(cl, meth)(url, HTTP_HOST='localhost')
                else:
                    r = getattr(cl, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = r.content.decode('utf-8', 'replace') if hasattr(r, 'content') else ''
            try:
                return r.status_code, json.loads(txt)
            except Exception:
                return r.status_code, {'_brut': txt[:120]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    avec_visite = set(VisiteTerrain.objects.filter(company=c).values_list('lead_id', flat=True))
    dv = (Devis.objects.filter(company=c, lead__isnull=False).exclude(lead_id__in=avec_visite)
          .select_related('lead').order_by('id').first())
    L = dv.lead
    today = timezone.localdate()
    V = VisiteTerrain.objects.create(company=c, lead=L, commercial=t2, statut='brouillon',
                                     date_prevue=today + dt.timedelta(days=5), mesures={}, qualification={})
    obs = {'perms_T': list(COMMERCIAL_TERRAIN_PERMISSIONS), 'lead': L.id, 'devis_du_lead': dv.reference}
    s, _ = appel(A1, 'get', f'/api/django/crm/leads/{L.id}/')
    obs['T1_lit_lead'] = s
    s, _ = appel(A2, 'get', f'/api/django/visites/visites/{V.id}/')
    obs['T2_lit_sa_visite_avant'] = s
    s, r = appel(A1, 'post', '/api/django/visites/visites/',
                 {'lead': L.id, 'date_prevue': (today + dt.timedelta(days=9)).isoformat(), 'commercial': t1.id})
    cp = r.get('client_panel') if isinstance(r, dict) else None
    dvr = r.get('devis') if isinstance(r, dict) else None
    obs['T1_post_visite'] = {
        'http': s, 'visite_id': (r.get('visite') or {}).get('id') if isinstance(r.get('visite'), dict) else r.get('id'),
        'cles': sorted(r.keys())[:25] if isinstance(r, dict) else None,
        'client_panel_cles': sorted(cp.keys()) if isinstance(cp, dict) else cp,
        'client_panel_telephone_present': bool(isinstance(cp, dict) and (cp.get('telephone') or cp.get('whatsapp'))),
        'devis_servi': (type(dvr).__name__, (len(dvr) if hasattr(dvr, '__len__') else None),
                        str(dvr)[:160] if dvr else None)}
    V.refresh_from_db()
    L.refresh_from_db()
    obs['visite_T2_apres'] = {'date_prevue': str(V.date_prevue), 'commercial': V.commercial.username if V.commercial else None,
                              'notes': V.notes[-120:], 'nb_visites_lead': VisiteTerrain.objects.filter(lead=L).count()}
    obs['lead_visite_prevue_le'] = str(getattr(L, 'visite_prevue_le', None))
    s, _ = appel(A2, 'get', f'/api/django/visites/visites/{V.id}/')
    obs['T2_lit_sa_visite_apres'] = s
    e1 = (obs['T1_lit_lead'] in (403, 404) and obs['T1_post_visite']['http'] == 201
          and V.commercial_id == t1.id and V.date_prevue == today + dt.timedelta(days=9))

    # ---------- E-21 : photo de la visite d'un autre ----------
    V2 = VisiteTerrain.objects.create(company=c, lead=L, commercial=t2, statut='en_cours',
                                      date_prevue=today, mesures={}, qualification={})
    ct = ContentType.objects.get(app_label='crm', model='lead')
    att = Attachment.objects.create(company=c, content_type=ct, object_id=L.id, file_key='sonde/acvi-180.jpg',
                                    filename='toit.jpg', size=10, mime='image/jpeg', uploaded_by=t2)
    VisiteMedia.objects.create(company=c, visite=V2, attachment=att, slot_code='toiture_vue_generale')
    import apps.records.views as rv
    orig = rv.fetch_attachment
    rv.fetch_attachment = lambda key: (b'\xff\xd8sonde', None)
    try:
        s1, r1 = appel(A1, 'get', f'/api/django/records/attachments/{att.id}/')
        s2, _ = appel(A1, 'get', f'/api/django/records/attachments/{att.id}/download/')
        s3, _ = appel(A1, 'get', f'/api/django/visites/visites/{V2.id}/')
    finally:
        rv.fetch_attachment = orig
    obs['E21'] = {'T1_lit_visite_V2': s3, 'T1_meta_photo': [s1, r1.get('filename') if isinstance(r1, dict) else None],
                  'T1_download_photo': s2}
    e21 = s3 == 404 and s2 == 200
    obs['repro_par_constat'] = {'E1': bool(e1), 'E21': bool(e21)}
    return {'repro': bool(e1 and e21), 'observe': obs}
