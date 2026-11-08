# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K02 — « Appliquer la cote au pan » (onglet Relevé de l'atelier) écrit la conception SANS jeton : la route
`releve/<id>/appliquer-cote/` répond 200 sans If-Match et sa réponse ne rend PAS l'empreinte_document. L'atelier,
qui tient le jeton E0 lu avant, enregistre ensuite sa scène avec If-Match E0 => 409 `document_modifie` sur sa
propre action. Témoins : POST `layout/` SANS If-Match = 428 (la porte de l'atelier exige le jeton) ; avec le jeton
frais E1 => 200."""
SONDE = {"constat": "C-ACON-002", "sha": "33cba7f5d",
         "attendu": "repro si appliquer-cote sans If-Match = 200 (version créée, pas d'empreinte_document rendue) "
                    "puis POST layout/ avec If-Match E0 (jeton d'avant) = 409 ; témoins : layout/ sans If-Match = 428, "
                    "avec E1 = 200",
         "modeles": ["calepinage.Calepinage", "calepinage.CalepinageVersion", "calepinage.ReleveTerrain"]}


def sonde(ctx):
    import copy
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.calepinage.models import Calepinage, CalepinageVersion
    from apps.crm.models import Lead
    from apps.roles.models import Role
    from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
    from core.calepinage.geo import deprojeteur_local
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 002', slug='sonde-acon-002')
    role = Role.objects.create(company=co, nom='Directeur', permissions=list(DIRECTEUR_PERMISSIONS))
    u = get_user_model().objects.create_user(username='sonde_acon_002', password='x', company=co, role=role)
    api = APIClient()
    api.force_authenticate(u)
    lead = Lead.objects.create(company=co, nom='Toiture', prenom='K02')
    pin = {'lat': 33.5731, 'lng': -7.5898}
    dep = deprojeteur_local((pin['lng'], pin['lat']))
    rect = [(-5.0, -4.0), (6.9, -4.0), (6.9, 4.0), (-5.0, 4.0)]  # côté 0 = 11,90 m
    layout = {'version': 2, 'pin': dict(pin),
              'zones': [{'id': 'z1', 'vertices': [list(dep(p)) for p in rect],
                         'facingAzimuthDeg': 180, 'pitchDeg': 20}]}
    cal = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='K02', roof_layout=layout)
    base = f'/api/django/calepinage/calepinages/{cal.pk}/'
    rv = api.post(f'{base}releve/', {'releve_le': '2026-11-05', 'chaines': [
        {'nom': 'Egout sud', 'total_mesure': 12.4, 'tolerance_m': 0.05,
         'cotes': [{'nom': 'a', 'valeur': 5.2}, {'nom': 'b', 'valeur': 7.2}]}]}, format='json', **H)
    releve_id = rv.data['releve']['id']

    # L'atelier ouvre : jeton E0 + document E0 (la scène qu'il garde en mémoire).
    g0 = api.get(f'{base}layout/', **H)
    e0 = g0.data.get('empreinte_document')
    doc_e0 = copy.deepcopy(g0.data.get('roof_layout'))
    v_avant = CalepinageVersion.objects.filter(calepinage=cal).count()
    # Onglet Relevé : « Appliquer » (AppliquerCoteAuPan ne reçoit pas documentVivant : aucun en-tête).
    a = api.post(f'{base}releve/{releve_id}/appliquer-cote/',
                 {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 12.4}, format='json', **H)
    v_apres = CalepinageVersion.objects.filter(calepinage=cal).count()
    # Témoin de la porte : l'atelier sans jeton => 428.
    sans = api.post(f'{base}layout/', {'roof_layout': doc_e0}, format='json', **H)
    # L'atelier enregistre sa scène (ici : le document E0 + un obstacle ajouté) avec SON jeton E0.
    doc_atelier = copy.deepcopy(doc_e0)
    doc_atelier['zones'][0]['obstacles'] = [{'id': 'o1', 'type': 'cheminee', 'contour': [
        list(dep(p)) for p in [(0, 0), (0.6, 0), (0.6, 0.6), (0, 0.6)]]}]
    s = api.post(f'{base}layout/', {'roof_layout': doc_atelier}, format='json',
                 HTTP_IF_MATCH=f'"{e0}"', **H)
    # Témoin : avec le jeton frais E1, la même écriture passe.
    e1 = api.get(f'{base}layout/', **H).data.get('empreinte_document')
    t = api.post(f'{base}layout/', {'roof_layout': doc_atelier}, format='json',
                 HTTP_IF_MATCH=f'"{e1}"', **H)
    obs = {'releve_http': rv.status_code, 'e0': e0, 'appliquer_cote_http': a.status_code,
           'appliquer_cote_cles_reponse': sorted(a.data.keys()) if hasattr(a.data, 'keys') else str(a.data)[:200],
           'versions_avant_apres': [v_avant, v_apres],
           'layout_sans_if_match_http': sans.status_code,
           'layout_if_match_E0_http': s.status_code,
           'layout_if_match_E0_corps': str(s.data)[:220],
           'e1_different_de_e0': e1 != e0, 'layout_if_match_E1_http': t.status_code}
    temoin_ok = sans.status_code == 428 and t.status_code == 200
    defaut = (a.status_code == 200 and v_apres == v_avant + 1
              and 'empreinte_document' not in (a.data or {}) and s.status_code == 409)
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and defaut)
    print(obs)
    return obs
