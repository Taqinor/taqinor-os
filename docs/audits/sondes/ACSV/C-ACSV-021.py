# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K21 — HSE : réglage « sécurité signée avant démarrage » VRAI. (R) signer les consignes avec 0 point
coché = 200, puis passage « Sur site » accepté ; puis un point décoché (vraie route ET op hors-ligne)
sur un sign-off signé : appliqué, `signe` reste vrai, aucune trace. (T) témoin : sans signature, le
passage « Sur site » est refusé (la garde existe). Vraies routes : POST signer-safety / cocher-safety,
PATCH interventions/<id>/ ; synchro : POST installations/sync/."""
SONDE = {"constat": "C-ACSV-021", "sha": "f57951e87",
         "attendu": "repro si T refusé (409) et R : signer 200 avec 0/N cochés puis PATCH sur_site 200 ; "
                    "décocher après signature 200, signe reste vrai",
         "modeles": ["installations.Intervention", "installations.SafetySignoff",
                     "installations.SafetyCheckItem", "installations.FieldOp"]}


def sonde(ctx):
    import uuid
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation, Intervention
    from apps.installations import field_capture
    from apps.parametres.models import CompanyProfile

    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde ACSV 021', slug='sonde-acsv-021')
    u = get_user_model().objects.create_user(username='sonde_acsv_021', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    prof = CompanyProfile.get(co)
    prof.securite_obligatoire_avant_demarrage = True
    prof.save()
    cl = Client.objects.create(company=co, nom='Client', prenom='A021', email='a021@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-A021', client=cl)

    def mk():
        return Intervention.objects.create(company=co, installation=inst, type_intervention='pose',
                                           created_by=u, statut='en_route')
    obs = {}
    # T — témoin : pas de signature → refus
    ivT = mk()
    rT = api.patch(f'{B}/interventions/{ivT.id}/', {'statut': 'sur_site'}, format='json', **H)
    obs['T_patch_sur_site'] = rT.status_code
    # R — signature à vide
    ivR = mk()
    so = field_capture.ensure_safety_signoff(ivR)
    items = list(so.items.all())
    obs['R_points'] = len(items)
    obs['R_coches_avant'] = sum(1 for i in items if i.coche)
    rs = api.post(f'{B}/interventions/{ivR.id}/signer-safety/', {}, format='json', **H)
    obs['R_signer'] = rs.status_code
    rp = api.patch(f'{B}/interventions/{ivR.id}/', {'statut': 'sur_site'}, format='json', **H)
    obs['R_patch_sur_site'] = rp.status_code
    ivR.refresh_from_db()
    obs['R_statut'] = ivR.statut
    # Décochage après signature : cocher d'abord un point (en ligne), puis décocher en ligne + hors-ligne
    cle1, cle2 = items[0].cle, items[1].cle if len(items) > 1 else items[0].cle
    api.post(f'{B}/interventions/{ivR.id}/cocher-safety/', {'cle': cle1, 'coche': True}, format='json', **H)
    rd = api.post(f'{B}/interventions/{ivR.id}/cocher-safety/', {'cle': cle1, 'coche': False}, format='json', **H)
    obs['R_decocher_en_ligne'] = rd.status_code
    rsync = api.post(f'{B}/sync/', {'ops': [
        {'client_op_id': 'a021-' + uuid.uuid4().hex, 'op_type': 'intervention.cocher_safety',
         'payload': {'intervention': ivR.id, 'cle': cle2, 'coche': False}}]}, format='json', **H)
    obs['R_sync'] = rsync.status_code
    obs['R_sync_status'] = rsync.json().get('results', [{}])[0].get('status') if rsync.status_code == 200 else None
    so.refresh_from_db()
    obs['R_signe_apres_decochage'] = so.signe
    obs['R_coches_final'] = so.items.filter(coche=True).count()
    print(obs)
    obs['repro'] = bool(rT.status_code in (400, 409) and obs['R_points'] >= 1 and obs['R_coches_avant'] == 0
                        and rs.status_code == 200 and rp.status_code == 200 and ivR.statut == 'sur_site'
                        and rd.status_code == 200 and so.signe)
    return obs
