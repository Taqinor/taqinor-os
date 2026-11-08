# flake8: noqa  (sonde d'audit PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K25 — la variante RETENUE reste-t-elle la conception après une retouche ? Variantes A (8 modules) et
B (12) ; on retient A (vraie route POST variantes/<A>/retenir/) ; on ajoute 4 modules dans l'atelier
(enregistrer_layout, service du PUT layout) ; comparatif servi (vraie route GET variantes/comparer/ si
elle existe, sinon le sélecteur comparer_variantes). Puis retenir B puis re-retenir A : les 4 ajouts
survivent-ils dans la conception ? Transaction annulée."""
SONDE = {"constat": "C-ACON-025", "sha": "33cba7f5d",
         "attendu": "repro si comparatif reference_modules=8 (A retenue) alors que la conception compte 12, et si re-retenir A rend 8",
         "modeles": ["calepinage.Calepinage", "calepinage.CalepinageVariante", "calepinage.CalepinageVersion"]}


def sonde(ctx):
    import copy
    import json
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.calepinage.models import Calepinage
    from apps.calepinage.selectors import comparer_variantes
    from apps.calepinage.services.layout import enregistrer_layout
    from apps.calepinage.services.mesures import mesures_du_document
    from apps.calepinage.services.variantes import creer_variante
    from apps.calepinage.tests.test_acal_multi_pans import _layout, _zone

    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 025', slug='sonde-acon-025')
    u = get_user_model().objects.create_user(username='k25', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    lead = Lead.objects.create(company=co, nom='Lead K25')
    c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='K25', roof_layout=_layout(_zone(1, 8)),
                                  cree_par=u)
    va = creer_variante(c, nom='A', roof_layout=_layout(_zone(1, 8)), user=u)
    vb = creer_variante(c, nom='B', roof_layout=_layout(_zone(1, 12)), user=u)
    base = f'/api/django/calepinage/calepinages/{c.pk}/variantes/'
    obs = {}

    def modules():
        c.refresh_from_db()
        return mesures_du_document(c.roof_layout).get('modules')

    def comparatif():
        r = api.get(f'/api/django/calepinage/calepinages/{c.pk}/comparer/', **H)
        if r.status_code == 200:
            j = r.json()
            return 'route', j.get('reference_modules'), j.get('retenue_id')
        j = comparer_variantes(c)
        return f'selecteur (route {r.status_code})', j.get('reference_modules'), j.get('retenue_id')

    r = api.post(base + f'{va.pk}/retenir/', {}, format='json', **H)
    obs['retenir_A'] = r.status_code
    obs['conception_apres_retenue_A'] = modules()
    doc = copy.deepcopy(c.roof_layout)
    doc['zones'][0]['geometry']['count'] = 12
    enregistrer_layout(c, doc, user=u, libelle='+4 modules dans l atelier')
    obs['conception_apres_retouche'] = modules()
    src, ref, ret = comparatif()
    obs['comparatif'] = {'source': src, 'reference_modules': ref, 'retenue_est_A': ret == va.pk}
    va.refresh_from_db()
    obs['variante_A_modules'] = mesures_du_document(va.roof_layout).get('modules')
    obs['retenir_B'] = api.post(base + f'{vb.pk}/retenir/', {}, format='json', **H).status_code
    obs['retenir_A_encore'] = api.post(base + f'{va.pk}/retenir/', {}, format='json', **H).status_code
    obs['conception_apres_aller_retour'] = modules()
    obs['repro'] = bool(obs['conception_apres_retouche'] == 12 and ref == 8 and ret == va.pk
                        and obs['conception_apres_aller_retour'] == 8)
    print(json.dumps(obs, default=str, ensure_ascii=False))
    return {'repro': obs['repro']}
