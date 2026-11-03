# flake8: noqa  (constat C-ACVI-109 : copie rejouable de la sonde groupée C-ACVI-106, sa clé dans `observe`)
"""C-ACVI-106 (F-7) + C-ACVI-108 (F-9) + C-ACVI-109 (F-10) — trois portes S3 de la fiche lead.
F-7 : POST /crm/leads/ accepte `owner` = un collègue pour un Commercial sans `crm_reassign` (le PATCH du même
champ = 403, témoin).
F-9 : PATCH /crm/leads/<id>/ {stage: COLD} range au Froid sans raison ni parc_* (le lot set_stage COLD exige
la raison = 400, témoin de la règle).
F-10 : GET /crm/rapports/attribution/ sert à un Commercial « soi » (404 sur le lead du collègue = témoin) les
chiffres de chaque commercial de la société. Clés d'étape lues de STAGES.py via apps.crm.stages.
Société neuve, transaction annulée."""
SONDE = {"constat": "C-ACVI-106+108+109", "sha": "352ae5455",
         "attendu": "F-7 : 403 au POST avec owner=collègue ; F-9 : PATCH COLD refusé sans raison ou parc_* posés ; "
                    "F-10 : par_commercial borné à la portée (défaut : 201 owner=collègue ; 200 parc vide ; collègue listé)",
         "modeles": ["crm.Lead", "crm.LeadActivity", "roles.Role"]}


def sonde(ctx):
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ACVI 106', slug='sonde-acvi-106')
    r_com = Role.objects.create(company=c, nom='Commercial sonde 106', permissions=list(COMMERCIAL_PERMISSIONS))
    com = U.objects.create_user(username='s106-com', password='x', company=c, role=r_com)
    col = U.objects.create_user(username='s106-collegue', password='x', company=c, role=r_com)
    l_com = Lead.objects.create(company=c, nom='Idrissi', prenom='Nadia', telephone='0661000061', ville='Rabat',
                                owner=com, stage=stages.CONTACTED)
    l_com2 = Lead.objects.create(company=c, nom='Idrissi2', prenom='Nadia', telephone='0661000062', ville='Rabat',
                                 owner=com, stage=stages.CONTACTED)
    l_col = Lead.objects.create(company=c, nom='Chraibi', prenom='Youssef', telephone='0661000063',
                                ville='Rabat', owner=col, stage=stages.SIGNED)

    api = APIClient()
    api.force_authenticate(com)

    def appel(meth, url, corps=None):
        try:
            with transaction.atomic():
                rr = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
            txt = rr.content.decode('utf-8', 'replace')
            try:
                return rr.status_code, json.loads(txt)
            except Exception:
                return rr.status_code, {'_brut': txt[:200]}
        except Exception as e:
            return 599, {'_exc': repr(e)[:300]}

    obs = {'perm_crm_reassign': 'crm_reassign' in COMMERCIAL_PERMISSIONS}
    # ── F-7 (C-ACVI-106) ──
    s, rep = appel('patch', f'/api/django/crm/leads/{l_com.id}/', {'owner': col.id})
    l_com.refresh_from_db()
    obs['F7_temoin_PATCH_owner_collegue'] = [s, (rep.get('detail') or rep.get('code')) if isinstance(rep, dict)
                                             else None, l_com.owner_id == col.id]
    s, rep = appel('post', '/api/django/crm/leads/', {'nom': 'Nouveau', 'prenom': 'Lead', 'telephone': '0611111111',
                                                     'ville': 'Rabat', 'owner': col.id})
    cree = Lead.objects.filter(company=c, pk=rep.get('id')).first() if isinstance(rep, dict) else None
    obs['F7_ids'] = {'com': com.id, 'collegue': col.id}
    obs['F7_POST_owner_collegue'] = [s, rep.get('owner') if isinstance(rep, dict) else None,
                                     getattr(cree, 'owner_id', None) == col.id,
                                     {k: rep.get(k) for k in ('owner', 'detail')} if isinstance(rep, dict) and s >= 400
                                     else None]
    f7 = obs['F7_temoin_PATCH_owner_collegue'][0] == 403 and obs['F7_POST_owner_collegue'][2]
    # ── F-9 (C-ACVI-108) ──
    s, rep = appel('post', '/api/django/crm/leads/bulk/', {'action': 'set_stage', 'stage': stages.COLD,
                                                          'ids': [l_com2.id]})
    obs['F9_temoin_bulk_COLD_sans_raison'] = [s, (rep.get('detail') or rep.get('error')) if isinstance(rep, dict)
                                              else None]
    s, rep = appel('patch', f'/api/django/crm/leads/{l_com.id}/', {'stage': stages.COLD})
    l_com.refresh_from_db()
    obs['F9_PATCH_stage_COLD'] = [s, {'stage': l_com.stage, 'parc_etat': l_com.parc_etat,
                                      'parc_raison': l_com.parc_raison},
                                  None if s < 400 else str(rep)[:200]]
    f9 = (s == 200 and l_com.stage == stages.COLD and not l_com.parc_etat and not l_com.parc_raison
          and obs['F9_temoin_bulk_COLD_sans_raison'][0] == 400)
    # ── F-10 (C-ACVI-109) ──
    obs['F10_temoin_GET_lead_collegue'] = appel('get', f'/api/django/crm/leads/{l_col.id}/')[0]
    s, rep = appel('get', '/api/django/crm/rapports/attribution/')
    lignes = rep.get('par_commercial') if isinstance(rep, dict) else None
    du_col = [x for x in (lignes or []) if isinstance(x, dict) and x.get('commercial') == col.username]
    obs['F10_GET_attribution'] = [s, [{k: x.get(k) for k in ('commercial', 'nb_leads', 'nb_signes', 'ca_signe',
                                                              'taux_conversion_pct')} for x in (lignes or [])][:4]]
    f10 = obs['F10_temoin_GET_lead_collegue'] == 404 and s == 200 and bool(du_col)
    obs['verdicts'] = {'C-ACVI-106': bool(f7), 'C-ACVI-108': bool(f9), 'C-ACVI-109': bool(f10)}
    return {'repro': bool(f7 and f9 and f10), 'observe': obs}
