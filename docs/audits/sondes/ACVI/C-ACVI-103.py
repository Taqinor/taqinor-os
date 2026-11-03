# flake8: noqa  (constat C-ACVI-103 : copie rejouable de la sonde groupée C-ACVI-102, sa clé dans `observe`)
"""C-ACVI-102 (F-3) + C-ACVI-103 (F-4) — lectures des relances / rendez-vous / points de contact en
`IsAnyRole`, et numéro servi en clair par le message d'une touche et la file WhatsApp en lot.
F-3 : Commercial terrain et Admin RH (403 sur /crm/leads/ = témoin, portée `all` faute de marqueur) lisent
la file des relances d'un lead, les rendez-vous et les points de contact de la société.
F-4 : Admin RH (sans `client_pii_voir`) reçoit `phone`/`wa_url` en clair par relance-etapes/<id>/message/
alors que la liste de la même touche masque `lead_telephone` ; un rôle personnalisé crm_voir+crm_modifier
sans `client_pii_voir` (fiche masquée = témoin) reçoit `queue[].phone` en clair par le lot
`prepare_whatsapp` et le numéro dans `wa_url` de appointments/<id>/confirmer-whatsapp/.
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-102+103", "sha": "352ae5455",
         "attendu": "F-3 : 403 sur relance-etapes / appointments / points-contact pour terrain et Admin RH ; "
                    "F-4 : phone/wa_url nuls ou 403 sans client_pii_voir (défaut : 200 et numéro en clair)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.Appointment", "crm.PointContact",
                     "roles.Role"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Appointment, Lead, LeadActivity, PointContact
    from apps.crm.models_cadence import RelanceEtape
    from apps.roles.models import Role
    from apps.roles.permissions_registre import (ADMIN_RH_PERMISSIONS, COMMERCIAL_PERMISSIONS,
                                                 COMMERCIAL_TERRAIN_PERMISSIONS)
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 102', slug='sonde-acvi-102')

    def role(nom, perms):
        return Role.objects.create(company=c, nom=nom + ' sonde 102', permissions=list(perms))
    ter = U.objects.create_user(username='s102-terrain', password='x', company=c,
                                role=role('Commercial terrain', COMMERCIAL_TERRAIN_PERMISSIONS))
    rh = U.objects.create_user(username='s102-rh', password='x', company=c,
                               role=role('Admin RH', ADMIN_RH_PERMISSIONS))
    com = U.objects.create_user(username='s102-com', password='x', company=c,
                                role=role('Commercial', COMMERCIAL_PERMISSIONS))
    perso = U.objects.create_user(username='s102-perso', password='x', company=c,
                                  role=role('CRM sans PII', ['crm_voir', 'crm_modifier']))
    lead = Lead.objects.create(company=c, nom='Bennani', prenom='Sara', email='sara@x.ma',
                               telephone='0661000021', whatsapp='0661000021', ville='Fès', owner=com)
    maintenant = timezone.now()
    touche = RelanceEtape.objects.create(company=c, lead=lead, cadence='contact', ordre=1,
                                         due_date=timezone.localdate(), due_at=maintenant, canal='whatsapp',
                                         libelle='Premier message', note='note interne sonde')
    rdv = Appointment.objects.create(company=c, lead=lead, scheduled_at=maintenant + dt.timedelta(days=1))
    pc = PointContact.objects.create(company=c, lead=lead, canal='meta_ads', source='campagne sonde',
                                     date_contact=maintenant)

    def api(u):
        a = APIClient()
        a.force_authenticate(u)
        return a

    def appel(cl, meth, url, corps=None):
        try:
            with transaction.atomic():
                rr = getattr(cl, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = rr.content.decode('utf-8', 'replace')
            try:
                return rr.status_code, json.loads(txt)
            except Exception:
                return rr.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    def lignes(rep):
        if isinstance(rep, dict):
            return rep.get('results') if isinstance(rep.get('results'), list) else []
        return rep if isinstance(rep, list) else []

    obs = {}
    # ── F-3 (C-ACVI-102) ──
    f3 = {}
    for nom, u in (('terrain', ter), ('rh', rh)):
        r = {'temoin_GET_crm_leads': appel(api(u), 'get', '/api/django/crm/leads/')[0]}
        s, rep = appel(api(u), 'get', f'/api/django/crm/relance-etapes/?lead={lead.id}')
        l0 = (lignes(rep) or [{}])[0]
        r['relances_lead'] = [s, {k: l0.get(k) for k in ('lead_nom', 'note', 'lead_telephone', 'owner_nom')
                                  if k in l0}]
        s, rep = appel(api(u), 'get', '/api/django/crm/relance-etapes/?scope=all')
        r['relances_file_all'] = [s, len(lignes(rep))]
        s, rep = appel(api(u), 'get', '/api/django/crm/appointments/')
        r['appointments'] = [s, [x.get('lead_nom') for x in lignes(rep) if isinstance(x, dict)][:3]]
        s, rep = appel(api(u), 'get', '/api/django/crm/points-contact/')
        r['points_contact'] = [s, [{k: x.get(k) for k in ('lead', 'canal', 'source', 'cout')}
                                   for x in lignes(rep) if isinstance(x, dict)][:3]]
        f3[nom] = r
    obs['F3'] = f3
    ok3 = all(r['temoin_GET_crm_leads'] == 403 and r['relances_lead'][0] == 200 and r['relances_lead'][1]
              and r['appointments'][0] == 200 for r in f3.values())
    # ── F-4 (C-ACVI-103) ──
    s, rep = appel(api(rh), 'get', f'/api/django/crm/relance-etapes/{touche.id}/message/')
    obs['F4_rh_message'] = [s, {k: rep.get(k) for k in ('phone', 'wa_url', 'mailto_url')}
                            if isinstance(rep, dict) else str(rep)[:150]]
    obs['F4_rh_liste_lead_telephone_contraste'] = f3['rh']['relances_lead'][1].get('lead_telephone', '<absent>')
    s, rep = appel(api(perso), 'get', f'/api/django/crm/leads/{lead.id}/')
    obs['F4_perso_temoin_fiche'] = [s, {k: rep.get(k) for k in ('telephone', 'whatsapp')}
                                    if isinstance(rep, dict) else None]
    a0 = LeadActivity.objects.filter(lead=lead).count()
    s, rep = appel(api(perso), 'post', '/api/django/crm/leads/bulk/',
                   {'action': 'prepare_whatsapp', 'ids': [lead.id], 'body': 'Bonjour'})
    q0 = ((rep.get('queue') or [{}])[0]) if isinstance(rep, dict) else {}
    obs['F4_perso_bulk_prepare_whatsapp'] = [s, {k: q0.get(k) for k in ('phone', 'wa_url')},
                                             'activites_delta', LeadActivity.objects.filter(lead=lead).count() - a0,
                                             (rep.get('detail') if isinstance(rep, dict) else None)]
    s, rep = appel(api(perso), 'post', f'/api/django/crm/appointments/{rdv.id}/confirmer-whatsapp/')
    obs['F4_perso_confirmer_whatsapp'] = [s, (rep.get('wa_url') or '')[:60] if isinstance(rep, dict) else '',
                                          rep.get('detail') if isinstance(rep, dict) else None]
    num = '0661000021'
    num_i = '212661000021'
    clair_msg = bool(isinstance(obs['F4_rh_message'][1], dict) and (
        obs['F4_rh_message'][1].get('phone') == num or num_i in (obs['F4_rh_message'][1].get('wa_url') or '')))
    clair_bulk = bool(obs['F4_perso_bulk_prepare_whatsapp'][1].get('phone') == num)
    obs['F4_numero_en_clair'] = {'message_rh': clair_msg, 'bulk_perso': clair_bulk,
                                 'confirmer_perso': num_i in (obs['F4_perso_confirmer_whatsapp'][1] or '')}
    obs['verdicts'] = {'C-ACVI-102': bool(ok3), 'C-ACVI-103': bool(clair_msg or clair_bulk)}
    return {'repro': bool(ok3 and (clair_msg or clair_bulk)), 'observe': obs}
