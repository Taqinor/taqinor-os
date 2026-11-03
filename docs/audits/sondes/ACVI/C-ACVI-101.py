# flake8: noqa  (sonde de vérification C5, rejouable par scripts/sonde.py)
"""C-ACVI-101 (F-2) + C-ACVI-107 (F-8) — portée des leads dans l'app Visites.
F-2 : POST /visites/visites/ ne borne le `lead` du corps qu'à la SOCIÉTÉ. Un Commercial terrain (403 sur
/crm/leads/ et sur /visites/leads-recherche/ = témoins) et un Commercial « soi » sur le lead d'un collègue
(404 sur la fiche = témoin ; porte jumelle crm/leads/<id>/visites/planifier/ rejouée en contraste) créent une
visite : 201, `client_panel` (téléphone, adresse) servi, une note au chatter du lead.
F-8 : un Commercial responsable (portée sous-arbre, `visites_valider`) lit la visite et le client_panel d'un
lead HORS de son sous-arbre (404 sur la fiche CRM = témoin). Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-101+107", "sha": "352ae5455",
         "attendu": "F-2 : 400/404 sur `lead` hors portée, aucune visite, aucune activité ; F-8 : 404 sur la visite "
                    "d'un lead hors sous-arbre (défaut : 201 + client_panel ; 200 + client_panel)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "visites.VisiteTerrain", "roles.Role"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead, LeadActivity
    from apps.roles.models import Role
    from apps.roles.permissions_registre import (COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
                                                 COMMERCIAL_TERRAIN_PERMISSIONS)
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 101', slug='sonde-acvi-101')

    def role(nom, perms):
        return Role.objects.create(company=c, nom=nom + ' sonde 101', permissions=list(perms))
    r_ter = role('Commercial terrain', COMMERCIAL_TERRAIN_PERMISSIONS)
    r_com = role('Commercial', COMMERCIAL_PERMISSIONS)
    r_resp = role('Commercial responsable', COMMERCIAL_RESP_PERMISSIONS)
    ter = U.objects.create_user(username='s101-terrain', password='x', company=c, role=r_ter)
    c1 = U.objects.create_user(username='s101-c1', password='x', company=c, role=r_com)
    c2 = U.objects.create_user(username='s101-c2', password='x', company=c, role=r_com)
    cr = U.objects.create_user(username='s101-cr', password='x', company=c, role=r_resp)
    c3 = U.objects.create_user(username='s101-c3', password='x', company=c, role=r_com)  # hors sous-arbre de cr

    def mk(nom, tel, owner):
        return Lead.objects.create(company=c, nom=nom, prenom='P', email=nom.lower() + '@x.ma', telephone=tel,
                                   ville='Rabat', adresse='12 rue ' + nom, owner=owner)
    l1, l1b, l3 = mk('Lun', '0600000011', c1), mk('Lunbis', '0600000012', c1), mk('Ltrois', '0600000013', c3)

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

    def act(lead):
        return LeadActivity.objects.filter(lead=lead).count()

    def panel(rep):
        if not isinstance(rep, dict):
            return None
        cp = rep.get('client_panel') or {}
        if cp:
            return {k: cp.get(k) for k in ('telephone', 'whatsapp', 'adresse', 'lead_nom')}
        return {'_cles': sorted(rep)[:15], 'detail': rep.get('detail'), 'lead': rep.get('lead')}

    obs = {}
    # ── F-2 (C-ACVI-101) ──
    obs['F2_temoin_terrain_GET_crm_leads'] = appel(api(ter), 'get', '/api/django/crm/leads/')[0]
    obs['F2_temoin_terrain_GET_leads_recherche'] = appel(
        api(ter), 'get', '/api/django/visites/leads-recherche/?q=Lun')[0]
    a0, v0 = act(l1), VisiteTerrain.objects.filter(lead=l1).count()
    s, rep = appel(api(ter), 'post', '/api/django/visites/visites/', {'lead': l1.id})
    obs['F2_terrain_POST_visite_L1'] = {
        'code': s, 'client_panel': panel(rep),
        'visites_creees': VisiteTerrain.objects.filter(lead=l1).count() - v0,
        'activites_lead_delta': act(l1) - a0,
        'devis_cle': ('devis' in rep) if isinstance(rep, dict) else None}
    obs['F2_temoin_c2_GET_lead_c1'] = appel(api(c2), 'get', f'/api/django/crm/leads/{l1b.id}/')[0]
    demain = (timezone.now() + dt.timedelta(days=2)).replace(microsecond=0).isoformat()
    s_j, rep_j = appel(api(c2), 'post', f'/api/django/crm/leads/{l1b.id}/visites/planifier/',
                       {'date_prevue': demain})
    obs['F2_c2_porte_jumelle_crm_planifier'] = [s_j, (rep_j.get('detail') if isinstance(rep_j, dict) else '')]
    a0, v0 = act(l1b), VisiteTerrain.objects.filter(lead=l1b).count()
    s, rep = appel(api(c2), 'post', '/api/django/visites/visites/', {'lead': l1b.id})
    obs['F2_c2_POST_visite_L1b'] = {
        'code': s, 'client_panel': panel(rep),
        'visites_creees': VisiteTerrain.objects.filter(lead=l1b).count() - v0,
        'activites_lead_delta': act(l1b) - a0}
    f2 = (obs['F2_temoin_terrain_GET_crm_leads'] == 403 and obs['F2_temoin_c2_GET_lead_c1'] == 404
          and obs['F2_terrain_POST_visite_L1']['code'] == 201 and obs['F2_c2_POST_visite_L1b']['code'] == 201)
    # ── F-8 (C-ACVI-107) ──
    v3, err = vs.planifier_visite(l3, c3, None, commercial=c3, notes='', replanifier=True,
                                  date_requise=False, assigne_par_defaut=c3)
    obs['F8_visite_V3'] = getattr(v3, 'id', None) or str(err)[:120]
    obs['F8_temoin_cr_GET_lead_L3'] = appel(api(cr), 'get', f'/api/django/crm/leads/{l3.id}/')[0]
    f8 = False
    if v3 is not None:
        obs['F8_temoin_c2_GET_visite_V3'] = appel(api(c2), 'get', f'/api/django/visites/visites/{v3.id}/')[0]
        s, rep = appel(api(cr), 'get', f'/api/django/visites/visites/{v3.id}/')
        obs['F8_cr_GET_visite_V3'] = {'code': s, 'client_panel': panel(rep)}
        s, rep = appel(api(cr), 'get', '/api/django/visites/visites/')
        obs['F8_cr_liste_contient_V3'] = [s, bool(isinstance(rep, list) and any(
            isinstance(x, dict) and x.get('id') == v3.id for x in rep))]
        f8 = obs['F8_temoin_cr_GET_lead_L3'] == 404 and obs['F8_cr_GET_visite_V3']['code'] == 200
    obs['verdicts'] = {'C-ACVI-101': bool(f2), 'C-ACVI-107': bool(f8)}
    return {'repro': bool(f2 and f8), 'observe': obs}
