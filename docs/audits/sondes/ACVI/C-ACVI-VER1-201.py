# flake8: noqa  (contre-visite ACVI64 — une seule « visite de référence » pour le feu vert ET le calepinage)
"""ACVI64 : lead L, V1 validée, puis deux brouillons sans date ajoutés par l'API réelle
(POST /visites/visites/ {lead}) -> feu vert et releve_pour_calepinage restent sur V1 ; V1 renvoyée
(a_refaire) -> les deux None. Société NEUVE, transaction annulée. Jumeau : texture_toit_pour_lead,
releve_ci_pour_lead, visite_point_eau_validee_du_lead rendent aussi V1 / None."""
SONDE = {"constat": "C-ACVI-174 (ACVI64)", "sha": "06ced8b1a",
         "attendu": "deux brouillons après une visite validée : feu vert ET relevé calepinage sur V1 ; renvoi : les deux None",
         "modeles": ["crm.Lead", "visites.VisiteTerrain"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.visites import selectors as vsel
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    c = Company.objects.create(nom='Sonde VER1 201', slug='sonde-ver1-201')
    r = Role.objects.create(company=c, nom='Admin sonde 201', permissions=[
        'crm_voir', 'crm_creer', 'crm_modifier', 'visites_voir', 'visites_creer', 'visites_modifier', 'visites_valider'])
    u = U.objects.create_user(username='sonde-ver1-201', password='x', company=c, role=r)
    L = Lead.objects.create(company=c, nom='Ref', telephone='0661000201', owner=u)
    V1 = VisiteTerrain.objects.create(company=c, lead=L, statut=VisiteTerrain.Statut.VALIDEE)
    api = APIClient()
    api.force_authenticate(u)
    obs = {}
    posts = []
    for _ in range(2):
        rep = api.post('/api/django/visites/visites/', {'lead': L.id}, format='json', HTTP_HOST='localhost')
        posts.append(rep.status_code)
    obs['posts_sans_date'] = posts
    obs['statuts'] = list(VisiteTerrain.objects.filter(lead=L).order_by('id').values_list('statut', flat=True))
    fv = vsel.visite_feu_vert(c.id, L.id)
    rel = vsel.releve_pour_calepinage(L)
    obs['apres_brouillons'] = {'feu_vert': (fv or {}).get('visite_id'), 'releve': rel.get('visite_id'), 'V1': V1.id}
    ok1 = obs['apres_brouillons']['feu_vert'] == V1.id and obs['apres_brouillons']['releve'] == V1.id
    VisiteTerrain.objects.filter(pk=V1.pk).update(statut=VisiteTerrain.Statut.A_REFAIRE)
    fv2 = vsel.visite_feu_vert(c.id, L.id)
    rel2 = vsel.releve_pour_calepinage(L)
    obs['apres_renvoi'] = {'feu_vert': fv2, 'releve': rel2.get('visite_id')}
    ok2 = fv2 is None and rel2.get('visite_id') is None
    # annulée seule ajoutée après une validée
    VisiteTerrain.objects.filter(pk=V1.pk).update(statut=VisiteTerrain.Statut.VALIDEE)
    VisiteTerrain.objects.create(company=c, lead=L, statut=VisiteTerrain.Statut.ANNULEE)
    obs['apres_annulee'] = (vsel.visite_feu_vert(c.id, L.id) or {}).get('visite_id')
    ok3 = obs['apres_annulee'] == V1.id
    return {'repro': not (ok1 and ok2 and ok3), 'observe': obs}
