# flake8: noqa  (sonde d'audit de parcours PA5, rejouable par scripts/sonde.py — METHODE §C.4)
"""K20 — fiche d'intervention ZFSM1 : un champ « obligatoire » (case à cocher) bloque « Terminée » ;
le seul moyen de le remplir est l'API `renseigner-fiche` (aucun écran) qui stocke `str(valeur)` sans
contrôle de type : « false » sur une case obligatoire compte « renseigné » et débloque la clôture.
Vraies routes : PATCH interventions/<id>/ {statut: terminee}, POST interventions/<id>/renseigner-fiche/."""
SONDE = {"constat": "C-ACSV-020", "sha": "f57951e87",
         "attendu": "repro si PATCH terminee refusé (4xx) nommant le champ, puis renseigner-fiche "
                    "valeur 'false' sur la case obligatoire = 200 et PATCH terminee = 200",
         "modeles": ["installations.Intervention", "installations.FicheInterventionValeur",
                     "installations.FicheInterventionReleve"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import (
        FicheInterventionChamp, FicheInterventionTemplate, Installation, Intervention)

    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde ACSV 020', slug='sonde-acsv-020')
    u = get_user_model().objects.create_user(username='sonde_acsv_020', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client', prenom='A020', email='a020@example.invalid')
    inst = Installation.objects.create(company=co, reference='CHT-A020', client=cl)
    tpl = FicheInterventionTemplate.objects.create(company=co, nom='Pose', type_intervention='pose')
    FicheInterventionChamp.objects.create(company=co, template=tpl, cle='disj', libelle='Disjoncteur testé',
                                          type_champ='case', ordre=1, obligatoire=True)
    iv = Intervention.objects.create(company=co, installation=inst, type_intervention='pose',
                                     created_by=u, statut='sur_site')
    obs = {}
    r1 = api.patch(f'{B}/interventions/{iv.id}/', {'statut': 'terminee'}, format='json', **H)
    obs['patch_terminee_1'] = r1.status_code
    obs['patch_terminee_1_detail'] = str(r1.content[:300], 'utf-8', 'replace')
    iv.refresh_from_db()
    obs['statut_apres_1'] = iv.statut
    rf = api.get(f'{B}/interventions/{iv.id}/fiche/', **H)
    vid = rf.json()['valeurs'][0]['id']
    r2 = api.post(f'{B}/interventions/{iv.id}/renseigner-fiche/', {'valeur_id': vid, 'valeur': 'false'},
                  format='json', **H)
    obs['renseigner_false'] = r2.status_code
    obs['valeur_stockee'] = r2.json()['valeurs'][0].get('valeur') if r2.status_code == 200 else None
    r3 = api.patch(f'{B}/interventions/{iv.id}/', {'statut': 'terminee'}, format='json', **H)
    obs['patch_terminee_2'] = r3.status_code
    iv.refresh_from_db()
    obs['statut_apres_2'] = iv.statut
    print(obs)
    obs['repro'] = bool(r1.status_code in (400, 409) and 'Disjoncteur' in obs['patch_terminee_1_detail']
                        and r2.status_code == 200 and r3.status_code == 200 and iv.statut == 'terminee')
    return obs
