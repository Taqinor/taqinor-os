# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K01 — Relevé : « Nouveau relevé » daté AVANT le relevé courant. La réponse du POST rend le relevé CRÉÉ (que
l'écran garde dans le formulaire) ET `releve_courant_id` = l'AUTRE relevé (le plus récent par date saisie).
L'écran (PanneauReleve.jsx::enregistrer) pose alors releveCourantId = R1 ; le bouton principal devient
« Enregistrer (corriger ce relevé) » = PATCH releve/<R1>/ avec le contenu du formulaire (celui de R2).
On rejoue ce PATCH tel que l'écran le construit, par la vraie route. (T) témoin : un relevé daté APRÈS
devient le courant (aucune discordance)."""
SONDE = {"constat": "C-ACON-001", "sha": "33cba7f5d",
         "attendu": "repro si POST R2 (01/11) rend releve.id=R2 et releve_courant_id=R1 (05/11), puis le PATCH "
                    "que l'écran envoie à releve_courant_id écrase R1 avec le contenu de R2 (date 01/11, notes R2) ; "
                    "témoin : R3 daté 07/11 => courant = R3",
         "modeles": ["calepinage.Calepinage", "calepinage.ReleveTerrain"]}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.calepinage.models import Calepinage, ReleveTerrain
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 001', slug='sonde-acon-001')
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = get_user_model().objects.create_user(username='sonde_acon_001', password='x', company=co, role=role)
    api = APIClient()
    api.force_authenticate(u)
    lead = Lead.objects.create(company=co, nom='Toiture', prenom='K01')
    cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='K01')
    url = f'/api/django/calepinage/calepinages/{cal.pk}/releve/'

    corps_r1 = {'releve_le': '2026-11-05', 'notes': 'R1 visite du 05/11',
                'chaines': [{'nom': 'Facade sud', 'total_mesure': 12.4, 'tolerance_m': 0.05,
                             'cotes': [{'nom': 'a', 'valeur': 5.2}, {'nom': 'b', 'valeur': 7.2}]}],
                'azimut_boussole_deg': 182, 'precision_azimut_deg': 5}
    r1 = api.post(url, corps_r1, format='json', **H)
    id_r1 = r1.data['releve']['id'] if r1.status_code == 201 else None

    corps_r2 = {'releve_le': '2026-11-01', 'notes': 'R2 visite du 01/11',
                'chaines': [{'nom': 'Pignon est', 'total_mesure': 8.0,
                             'cotes': [{'nom': 'c', 'valeur': 4.0}, {'nom': 'd', 'valeur': 4.0}]}]}
    r2 = api.post(url, corps_r2, format='json', **H)
    id_r2 = r2.data.get('releve', {}).get('id') if r2.status_code == 201 else None
    courant_apres_r2 = r2.data.get('releve_courant_id') if r2.status_code == 201 else None

    # L'écran : le formulaire garde R2 (setResultat(donnees)) ; releveCourantId = courant_apres_r2 ;
    # le technicien corrige une cote puis clique « Enregistrer (corriger ce relevé) ».
    corps_ecran = dict(corps_r2, azimut_boussole_deg=None, precision_azimut_deg=None, photo_ids=[])
    corps_ecran['chaines'] = [dict(corps_r2['chaines'][0], cotes=[{'nom': 'c', 'valeur': 4.1},
                                                                   {'nom': 'd', 'valeur': 3.9}])]
    p = api.patch(f'{url}{courant_apres_r2}/', corps_ecran, format='json', **H)
    R1 = ReleveTerrain.objects.get(pk=id_r1)
    R2 = ReleveTerrain.objects.get(pk=id_r2)
    obs = {'post_r1': r1.status_code, 'post_r2': r2.status_code, 'r2_releve_id_rendu': id_r2,
           'r2_releve_courant_id_rendu': courant_apres_r2, 'id_r1': id_r1,
           'patch_vise': courant_apres_r2, 'patch_http': p.status_code,
           'R1_apres': {'releve_le': str(R1.releve_le), 'notes': R1.notes,
                        'chaines': [c.get('nom') for c in R1.chaines],
                        'azimut': R1.azimut_boussole_deg},
           'R2_apres': {'releve_le': str(R2.releve_le), 'notes': R2.notes,
                        'cotes': R2.chaines[0]['cotes']}}
    # Témoin : un relevé daté APRÈS le courant devient le courant.
    r3 = api.post(url, dict(corps_r2, releve_le='2026-11-07', notes='R3'), format='json', **H)
    obs['temoin_r3'] = {'http': r3.status_code, 'releve_id': r3.data.get('releve', {}).get('id'),
                        'courant': r3.data.get('releve_courant_id')}
    temoin_ok = r3.status_code == 201 and obs['temoin_r3']['releve_id'] == obs['temoin_r3']['courant']
    discordance = id_r2 is not None and courant_apres_r2 == id_r1 and id_r2 != id_r1
    ecrase = (p.status_code == 200 and str(R1.releve_le) == '2026-11-01'
              and R1.notes == 'R2 visite du 01/11' and R2.notes == 'R2 visite du 01/11'
              and R2.chaines[0]['cotes'][0]['valeur'] == 4.0)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and discordance and ecrase)
    print(obs)
    return obs
