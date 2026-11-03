# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py — AMET93)
"""Écrivains automatiques d'owner/score contre une décision humaine, société démo :
B-8 (`recycler_leads_non_travailles()` avec `lead_sla_deassign_hours=48` : owner posé par PATCH humain retiré) ;
B-9 (`seuil_mql=1`, PATCH {owner:null} : le recalcul du même PATCH réassigne via `maybe_assign_mql`) ;
B-19 (`ajuster_score_lead(+10)` puis PATCH {nom} : ajustement écrasé ; aucun appelant hors la façade).
Beat appelé directement, jamais Celery. Transaction annulée."""
SONDE = {"constat": "C-ACVI-027+028+038", "sha": "352ae5455",
         "attendu": "défaut : owner None après le recyclage ; owner reposé après PATCH owner:null ; score ≠ ancien+10 "
                    "après PATCH",
         "modeles": ["crm.Lead", "crm.LeadActivity", "parametres.CompanyProfile", "roles.Role"]}


def sonde(ctx):
    import datetime as dt
    import json
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.urls import reverse
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.crm.fiche_funnel import ajuster_score_lead
    from apps.crm.management.commands.recycler_leads_non_travailles import recycler_leads_non_travailles
    from apps.parametres.models import CompanyProfile
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    leads_url = reverse('lead-list')
    etapes = []

    def appel(nom, meth, url, corps=None):
        try:
            with transaction.atomic():
                r = getattr(api, meth)(url, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            etapes.append((nom, 599, repr(e)[:300]))
            return 599, {}
        txt = r.content.decode('utf-8', 'replace')
        etapes.append((nom, r.status_code, txt[:200] if r.status_code >= 400 else ''))
        try:
            return r.status_code, json.loads(txt)
        except Exception:
            return r.status_code, {}

    prof = CompanyProfile.objects.filter(company=c).first()
    obs = {'profil': {'lead_sla_hours': prof.lead_sla_hours, 'deassign_avant': prof.lead_sla_deassign_hours,
                      'seuil_mql_avant': prof.seuil_mql}}
    role_com = Role.objects.filter(company=c, nom='Commercial').first()
    if role_com is None:
        role_com = Role.objects.create(company=c, nom='Commercial', permissions=list(COMMERCIAL_PERMISSIONS))
    com = U.objects.create_user(username='sonde-acvi-027-com', password='x', company=c, role=role_com)
    # B-8
    CompanyProfile.objects.filter(pk=prof.pk).update(lead_sla_deassign_hours=48, lead_sla_hours=24)
    l8 = Lead.objects.create(company=c, nom='Recycle', prenom='ACVI027', telephone='+212600027008')
    Lead.objects.filter(pk=l8.pk).update(date_creation=timezone.now() - dt.timedelta(days=5), first_contacted_at=None,
                                         stage='NEW')
    s, _ = appel('PATCH owner humain', 'patch', '%s%d/' % (leads_url, l8.id), {'owner': com.id})
    l8.refresh_from_db()
    owner_apres_patch = getattr(l8.owner, 'username', None)
    marques = list(l8.saisies_humaines or [])
    esc, desass = recycler_leads_non_travailles()
    l8.refresh_from_db()
    obs['B8'] = {'http_patch': s, 'owner_apres_patch': owner_apres_patch, 'saisies_humaines': marques,
                 'recycler_retour': [esc, desass], 'owner_apres_recyclage': getattr(l8.owner, 'username', None),
                 'first_contacted_at': str(l8.first_contacted_at)}
    CompanyProfile.objects.filter(pk=prof.pk).update(lead_sla_deassign_hours=0)
    # B-9
    l9 = Lead.objects.create(company=c, nom='Mql', prenom='ACVI027', telephone='+212600027009', ville='Casablanca',
                             facture_hiver=900, owner=ua)
    CompanyProfile.objects.filter(pk=prof.pk).update(seuil_mql=1)
    l9.refresh_from_db()
    av9 = (getattr(l9.owner, 'username', None), str(l9.mql_assigned_at), l9.score)
    s, _ = appel('PATCH owner null', 'patch', '%s%d/' % (leads_url, l9.id), {'owner': None})
    l9.refresh_from_db()
    obs['B9'] = {'avant': av9, 'http': s, 'owner_apres': getattr(l9.owner, 'username', None),
                 'mql_assigned_at': str(l9.mql_assigned_at), 'score': l9.score,
                 'owner_marque_humain': 'owner' in (l9.saisies_humaines or [])}
    # B-19
    l19 = Lead.objects.create(company=c, nom='Score', prenom='ACVI027', telephone='+212600027019', owner=ua)
    s0, _ = appel('PATCH initial (score calculé)', 'patch', '%s%d/' % (leads_url, l19.id), {'ville': 'Rabat'})
    l19.refresh_from_db()
    base = l19.score or 0
    ajuster_score_lead(l19, ua, 10)
    l19.refresh_from_db()
    apres_ajust = l19.score
    s1, _ = appel('PATCH nom', 'patch', '%s%d/' % (leads_url, l19.id), {'nom': 'Score2'})
    l19.refresh_from_db()
    obs['B19'] = {'score_base': base, 'apres_ajuster': apres_ajust, 'apres_patch': l19.score,
                  'score_ajustement_colonne': l19.score_ajustement}
    obs['etapes'] = etapes
    obs['defauts'] = {
        'B8_owner_humain_retire': owner_apres_patch == 'sonde-acvi-027-com' and obs['B8']['owner_apres_recyclage'] is None,
        'B9_owner_vide_reassigne': obs['B9']['owner_apres'] is not None,
        'B19_ajustement_ecrase': apres_ajust == base + 10 and l19.score != apres_ajust,
    }
    return {'repro': any(obs['defauts'].values()), 'observe': obs}
