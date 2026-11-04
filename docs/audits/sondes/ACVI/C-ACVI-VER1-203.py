# flake8: noqa  (contre-visite ACVI60 + ACVI18 + ACVI27 + ACVI34 par les portes réelles)
"""ACVI60 : visite brouillon planifiée (planifier_visite) puis DELETE API -> Lead.visite_prevue_le None et plus aucune
touche de visite ouverte ; même chose pour PATCH {date_prevue: null} -> visite annulée. ACVI18 : POST locataire ->
ConsentRecord du propriétaire créé, granted False. ACVI27 : lead sans numéro puis PATCH telephone -> touche contact
ouverte (persistée) ou refus tracé. ACVI34 : merge_leads avec une instance survivante périmée + UPDATE concurrent
de `ville` -> la valeur concurrente survit. Société NEUVE, transaction annulée. `repro` = au moins une clause violée."""
SONDE = {"constat": "ACVI60+18+27+34", "sha": "06ced8b1a",
         "attendu": "annulation compense le lead (DELETE et date vidée) ; registre écrit ; cadence relancée ; PATCH concurrent survit à la fusion",
         "modeles": ["crm.Lead", "crm.RelanceEtape", "visites.VisiteTerrain", "core.ConsentRecord"]}


def sonde(ctx):
    import datetime as dt
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from core.models import ConsentRecord
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.leads_fusion import merge_leads
    from apps.roles.models import Role
    from apps.visites import services as vs
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    from apps.parametres.models import CompanyProfile
    c = Company.objects.create(nom='Sonde VER1 203', slug='sonde-ver1-203')
    CompanyProfile.objects.get_or_create(company=c)
    r = Role.objects.create(company=c, nom='Admin sonde 203', permissions=[
        'crm_voir', 'crm_creer', 'crm_modifier', 'crm_supprimer', 'crm_fusionner', 'client_pii_voir', 'visites_voir', 'visites_creer',
        'visites_modifier', 'visites_valider'])
    u = U.objects.create_user(username='sonde-ver1-203', password='x', company=c, role=r)
    api = APIClient()
    api.force_authenticate(u)
    today = timezone.localdate()
    obs = {}

    def touches_visite(L):
        return list(RelanceEtape.objects.filter(lead=L, statut='a_faire').values_list('libelle', flat=True))

    # --- ACVI60 DELETE ---
    L = Lead.objects.create(company=c, nom='Del', telephone='0661000211', owner=u)
    V, err = vs.planifier_visite(L, u, today + dt.timedelta(days=4), commercial=u)
    L.refresh_from_db()
    avant = {'visite_prevue_le': str(L.visite_prevue_le), 'touches': touches_visite(L)}
    rep = api.delete(f'/api/django/visites/visites/{V.id}/', HTTP_HOST='localhost')
    L.refresh_from_db()
    obs['acvi60_delete'] = {'avant': avant, 'http': rep.status_code, 'existe': VisiteTerrain.objects.filter(pk=V.pk).exists(),
                            'visite_prevue_le': str(L.visite_prevue_le), 'touches': touches_visite(L)}
    ko60d = not (rep.status_code == 204 and L.visite_prevue_le is None and not any('isite' in t for t in touches_visite(L)))
    # --- ACVI60 PATCH null ---
    L2 = Lead.objects.create(company=c, nom='Nul', telephone='0661000212', owner=u)
    V2, err = vs.planifier_visite(L2, u, today + dt.timedelta(days=4), commercial=u)
    rep = api.patch(f'/api/django/visites/visites/{V2.id}/', {'date_prevue': None}, format='json', HTTP_HOST='localhost')
    L2.refresh_from_db()
    V2.refresh_from_db()
    obs['acvi60_patch_null'] = {'http': rep.status_code, 'statut': V2.statut, 'visite_prevue_le': str(L2.visite_prevue_le),
                                'touches': touches_visite(L2)}
    ko60p = not (rep.status_code == 200 and V2.statut == 'annulee' and L2.visite_prevue_le is None
                 and not any('isite' in t for t in touches_visite(L2)))
    # --- ACVI18 ---
    T = Lead.objects.create(company=c, nom='Locataire', telephone='0661000213', owner=u)
    rep = api.post(f'/api/django/crm/leads/{T.id}/locataire/', {'proprietaire': {'nom': 'Prop', 'telephone': '0661000214'}},
                   format='json', HTTP_HOST='localhost')
    regs = list(ConsentRecord.objects.filter(company=c, subject_identifier__in=['0661000214', '212661000214'])
                .values_list('subject_identifier', 'purpose', 'granted', 'source'))
    obs['acvi18'] = {'http': rep.status_code, 'registre': regs}
    ko18 = not (rep.status_code in (200, 201) and regs and not any(g for _s, _p, g, _src in regs))
    # --- ACVI27 ---
    rep = api.post('/api/django/crm/leads/', {'nom': 'SansNumero'}, format='json', HTTP_HOST='localhost')
    lid = rep.data.get('id') if hasattr(rep, 'data') and isinstance(rep.data, dict) else None
    L3 = Lead.objects.get(pk=lid)
    avant27 = RelanceEtape.objects.filter(lead=L3, cadence='contact').count()
    rep = api.patch(f'/api/django/crm/leads/{L3.id}/', {'telephone': '0661000215'}, format='json', HTTP_HOST='localhost')
    apres27 = RelanceEtape.objects.filter(lead=L3, cadence='contact').count()
    L3.refresh_from_db()
    obs['acvi27_tel'] = L3.telephone
    from apps.crm.models import LeadActivity
    obs['acvi27'] = {'notes': [(n.kind, (n.body or '')[:90]) for n in LeadActivity.objects.filter(lead=L3)], 'create': 201, 'patch_http': rep.status_code, 'touches_contact_avant': avant27, 'apres': apres27}
    ko27 = not (avant27 == 0 and apres27 >= 1)
    # --- ACVI34 ---
    B = Lead.objects.create(company=c, nom='Surv', telephone='0661000216', ville='Fès', owner=u)
    A = Lead.objects.create(company=c, nom='Surv', telephone='0661000216', email='a-203@example.invalid', owner=u)
    inst = Lead.objects.get(pk=B.pk)
    Lead.objects.filter(pk=B.pk).update(ville='Meknès')
    merge_leads(inst, [A], u)
    rel = Lead.objects.get(pk=B.pk)
    obs['acvi34'] = {'ville': rel.ville, 'email': rel.email, 'email_normalise': rel.email_normalise}
    ko34 = not (rel.ville == 'Meknès' and rel.email == 'a-203@example.invalid')
    obs['ko'] = {'acvi60_delete': ko60d, 'acvi60_patch': ko60p, 'acvi18': ko18, 'acvi27': ko27, 'acvi34': ko34}
    return {'repro': bool(ko60d or ko60p or ko18 or ko27 or ko34), 'observe': obs}
