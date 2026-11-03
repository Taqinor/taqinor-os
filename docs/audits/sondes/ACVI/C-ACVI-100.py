# flake8: noqa  (sonde de vérification C5, rejouable par scripts/sonde.py)
"""C-ACVI-100 (F-1) — imports/dry-run et imports/commit (IsResponsableOrAdmin sur `dataimport`, app de
APPS_SANS_MODULE) : un Admin RH (aucun droit CRM, 403 sur /crm/leads/ = témoin), un Technicien, et un
Commercial « soi » sur le lead d'un collègue (404 sur la fiche = témoin) lisent par l'aperçu l'identité d'un
lead rapproché par son téléphone (cible_id, cible_libelle, ecrasements[].ancienne) et la RÉÉCRIVENT par le
commit mode=maj ecraser=true. Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-100", "sha": "352ae5455",
         "attendu": "Admin RH / Technicien : 403 sur dry-run et commit ; Commercial soi : ligne « aucune "
                    "correspondance », lead inchangé (défaut : 200, cible_id + ancienne valeur servis, lead réécrit)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "dataimport.ImportJob", "roles.Role"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import (ADMIN_RH_PERMISSIONS, COMMERCIAL_PERMISSIONS,
                                                 TECHNICIEN_PERMISSIONS)
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 100', slug='sonde-acvi-100')

    def role(nom, perms):
        return Role.objects.create(company=c, nom=nom + ' sonde 100', permissions=list(perms))
    r_rh, r_com, r_tech = role('Admin RH', ADMIN_RH_PERMISSIONS), role('Commercial', COMMERCIAL_PERMISSIONS), \
        role('Technicien', TECHNICIEN_PERMISSIONS)
    rh = U.objects.create_user(username='s100-rh', password='x', company=c, role=r_rh)
    tech = U.objects.create_user(username='s100-tech', password='x', company=c, role=r_tech)
    c1 = U.objects.create_user(username='s100-c1', password='x', company=c, role=r_com)
    c2 = U.objects.create_user(username='s100-c2', password='x', company=c, role=r_com)
    lead = Lead.objects.create(company=c, nom='Alaoui', prenom='Karim', email='a@x.ma',
                               telephone='0600000001', ville='Rabat', owner=c1)

    def api(u):
        a = APIClient()
        a.force_authenticate(u)
        return a

    def appel(cl, meth, url, corps=None, fmt='json'):
        try:
            with transaction.atomic():
                rr = getattr(cl, meth)(url, corps or {}, format=fmt, HTTP_HOST='localhost')
            txt = rr.content.decode('utf-8', 'replace')
            try:
                return rr.status_code, json.loads(txt)
            except Exception:
                return rr.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    def corps(csv, **opt):
        d = {'file': SimpleUploadedFile('l.csv', csv.encode('utf-8'), content_type='text/csv'),
             'target': 'leads', 'mode': 'maj'}
        d.update(opt)
        return d

    def resume_dry(rep):
        if not isinstance(rep, dict):
            return rep
        cf = (rep.get('conflits') or [{}])[0] if rep.get('conflits') else {}
        return {'cible_id': cf.get('cible_id'), 'cible_libelle': cf.get('cible_libelle'),
                'ecrasements': cf.get('ecrasements'), 'resume': rep.get('resume'), 'detail': rep.get('detail')}

    obs = {'lead': {'id': lead.id, 'owner': 'c1', 'email': lead.email, 'nom': lead.nom}}
    # Témoins : le rôle est borné sur la porte normale.
    obs['temoin_rh_GET_crm_leads'] = appel(api(rh), 'get', '/api/django/crm/leads/')[0]
    obs['temoin_tech_GET_crm_leads'] = appel(api(tech), 'get', '/api/django/crm/leads/')[0]
    obs['temoin_c2_GET_lead_c1'] = appel(api(c2), 'get', f'/api/django/crm/leads/{lead.id}/')[0]
    obs['temoin_c1_GET_son_lead'] = appel(api(c1), 'get', f'/api/django/crm/leads/{lead.id}/')[0]
    res = {}
    for nom, u, email, nom_lead in (('rh', rh, 'rh@pirate.ma', 'PirateRH'),
                                    ('tech', tech, 'tech@pirate.ma', 'PirateTech'),
                                    ('c2', c2, 'c2@pirate.ma', 'PirateC2')):
        Lead.objects.filter(pk=lead.pk).update(email='a@x.ma', nom='Alaoui')
        csv = 'telephone,email,nom\n0600000001,%s,%s\n' % (email, nom_lead)
        s, rep = appel(api(u), 'post', '/api/django/imports/dry-run/', corps(csv, ecraser='true'), 'multipart')
        d = resume_dry(rep)
        s2, rep2 = appel(api(u), 'post', '/api/django/imports/commit/', corps(csv, ecraser='true'), 'multipart')
        lead.refresh_from_db()
        res[nom] = {'dry_run': s, 'dry_cible_id_eq_lead': d.get('cible_id') == lead.id if isinstance(d, dict) else None,
                    'dry': d,
                    'commit': s2, 'commit_resume': {k: rep2.get(k) for k in ('updated', 'created', 'ecrasements', 'detail')}
                    if isinstance(rep2, dict) else str(rep2)[:150],
                    'lead_apres': {'email': lead.email, 'nom': lead.nom},
                    'reecrit': lead.email == email}
    obs['portes'] = res
    v = {k: (r['dry_run'] == 200 and r['dry_cible_id_eq_lead']) or r['reecrit'] for k, r in res.items()}
    obs['defaut_par_role'] = v
    repro = (obs['temoin_rh_GET_crm_leads'] == 403 and obs['temoin_c2_GET_lead_c1'] == 404
             and v.get('rh') and v.get('c2'))
    return {'repro': bool(repro), 'observe': obs}
