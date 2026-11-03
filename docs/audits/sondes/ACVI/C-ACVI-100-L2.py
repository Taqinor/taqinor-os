# flake8: noqa  (seconde lentille L2 de C-ACVI-100, rejouable par scripts/sonde.py)
"""C-ACVI-100 L2 — autre chemin que la sonde 100 : rapprochement par E-MAIL (pas le téléphone), commit
mode=maj SANS écrasement (ecraser=false, défaut « sûr »), acteur = Commercial à portée ÉQUIPE
(records_scope_equipe à la place de records_scope_soi) d'une autre équipe (superviseurs distincts). Le lead
du collègue a `whatsapp` et `ville` vides : l'import peut-il les REMPLIR (numéro WhatsApp de l'attaquant
posé sur la fiche d'autrui) ? Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-100-L2", "sha": "352ae5455",
         "attendu": "défaut si 200 + cible_id servi + whatsapp/ville du lead hors portée remplis ; correct : "
                    "« aucune correspondance » (ou création) et lead inchangé",
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
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS, SCOPE_SELF, SCOPE_TEAM
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 100 L2', slug='sonde-acvi-100-l2')
    perms = [p for p in COMMERCIAL_PERMISSIONS if p != SCOPE_SELF] + [SCOPE_TEAM]
    r = Role.objects.create(company=c, nom='Commercial equipe sonde 100L2', permissions=perms)
    s1 = U.objects.create_user(username='s100l2-s1', password='x', company=c, role=r)
    s2 = U.objects.create_user(username='s100l2-s2', password='x', company=c, role=r)
    c1 = U.objects.create_user(username='s100l2-c1', password='x', company=c, role=r, supervisor=s1)
    c2 = U.objects.create_user(username='s100l2-c2', password='x', company=c, role=r, supervisor=s2)
    lead = Lead.objects.create(company=c, nom='Bennani', prenom='Sara', email='sara@x.ma',
                               telephone='0600000101', ville='', whatsapp='', owner=c1)

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

    csv = 'email,whatsapp,ville\nSARA@X.MA,0699999999,Pirateville\n'

    def corps(**opt):
        d = {'file': SimpleUploadedFile('l.csv', csv.encode('utf-8'), content_type='text/csv'),
             'target': 'leads', 'mode': 'maj'}
        d.update(opt)
        return d

    obs = {'perms_portee': [p for p in perms if p.startswith('records_scope')]}
    obs['temoin_c2_GET_lead_c1'] = appel(api(c2), 'get', f'/api/django/crm/leads/{lead.id}/')[0]
    obs['temoin_c2_liste_contient_lead'] = None
    s, lst = appel(api(c2), 'get', '/api/django/crm/leads/?search=Bennani')
    rows = lst.get('results', lst) if isinstance(lst, dict) else lst
    obs['temoin_c2_liste_contient_lead'] = [s, any(isinstance(x, dict) and x.get('id') == lead.id for x in (rows or []))
                                            if isinstance(rows, list) else str(rows)[:80]]
    s, rep = appel(api(c2), 'post', '/api/django/imports/dry-run/', corps(ecraser='false'), 'multipart')
    cf = ((rep.get('conflits') or [{}])[0] if isinstance(rep, dict) and rep.get('conflits') else {})
    obs['dry_run'] = {'http': s, 'cible_id': cf.get('cible_id'), 'cible_libelle': cf.get('cible_libelle'),
                      'resume': rep.get('resume') if isinstance(rep, dict) else None,
                      'cles': sorted(rep.keys())[:12] if isinstance(rep, dict) else None}
    s2, rep2 = appel(api(c2), 'post', '/api/django/imports/commit/', corps(ecraser='false'), 'multipart')
    lead.refresh_from_db()
    obs['commit'] = {'http': s2, 'resume': {k: rep2.get(k) for k in ('updated', 'created', 'ecrasements', 'skipped', 'detail')}
                     if isinstance(rep2, dict) else str(rep2)[:150]}
    obs['lead_apres'] = {'whatsapp': lead.whatsapp, 'ville': lead.ville, 'email': lead.email, 'owner': lead.owner.username}
    obs['leads_crees'] = Lead.objects.filter(company=c).count() - 1
    remplit = lead.whatsapp == '0699999999' or lead.ville == 'Pirateville'
    fuite = obs['dry_run']['cible_id'] == lead.id
    obs['defauts'] = {'lecture_identite_hors_portee': fuite, 'ecriture_champs_vides_hors_portee': remplit}
    return {'repro': bool(obs['temoin_c2_GET_lead_c1'] == 404 and (remplit or fuite)), 'observe': obs}
