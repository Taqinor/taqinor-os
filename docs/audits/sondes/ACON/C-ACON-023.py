# flake8: noqa  (sonde d'audit PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K23 — approbation « à l'aveugle » : le relecteur E ouvre l'onglet Approbation (GET, conception H1),
pendant sa relecture le concepteur D enregistre H2 (pan ajouté), puis E clique « Approuver » (POST
{decision} — exactement le corps de Approbation.jsx, sans empreinte). L'accord porte-t-il sur H2, que E
n'a jamais vu ? Vraies routes GET/POST calepinages/<id>/approbation/ ; H2 écrit par enregistrer_layout
(service du PUT layout). Témoin : un jeton d'empreinte envoyé dans le corps est ignoré. Transaction annulée."""
SONDE = {"constat": "C-ACON-023", "sha": "33cba7f5d",
         "attendu": "repro si POST approuve = 200 et empreinte_approuvee == H2 (!= H1 lu au GET) sans aucun parametre designant H1",
         "modeles": ["calepinage.Calepinage", "calepinage.CalepinageVersion"]}


def sonde(ctx):
    import copy
    import json
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.layout import enregistrer_layout
    from apps.calepinage.services.approbation import est_approuve
    from apps.calepinage.tests.acal_livrables_helpers import LAYOUT_PLANCHE_SIMULABLE

    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ACON 023', slug='sonde-acon-023')
    D = U.objects.create_user(username='k23_concepteur', password='x', role_legacy='admin', company=co)
    E = U.objects.create_user(username='k23_relecteur', password='x', role_legacy='admin', company=co)
    api_e = APIClient()
    api_e.force_authenticate(E)
    lead = Lead.objects.create(company=co, nom='Lead K23')
    c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='K23', roof_layout={},
                                  cree_par=D, responsable=D)
    h1 = copy.deepcopy(LAYOUT_PLANCHE_SIMULABLE)
    enregistrer_layout(c, h1, user=D, libelle='H1')
    c.refresh_from_db()
    obs = {}
    g = api_e.get(f'/api/django/calepinage/calepinages/{c.pk}/approbation/', **H)
    obs['get_http'] = g.status_code
    obs['get_expose_empreinte_courante'] = any(k in (g.json() or {}) for k in ('layout_hash', 'empreinte', 'empreinte_courante', 'version'))
    obs['get_cles'] = sorted((g.json() or {}).keys())
    h1_hash = c.layout_hash
    # pendant la relecture : D ajoute un pan / change la conception
    h2 = copy.deepcopy(c.roof_layout)
    z2 = copy.deepcopy(h2['zones'][0])
    z2['id'] = 'k23-z2'
    z2['label'] = 'Pan ajouté'
    h2['zones'].append(z2)
    enregistrer_layout(c, h2, user=D, libelle='H2 pendant la relecture')
    c.refresh_from_db()
    h2_hash = c.layout_hash
    obs['h1_ne_h2'] = bool(h1_hash and h2_hash and h1_hash != h2_hash)
    obs['zones_h1_h2'] = [len(h1['zones']), len(c.roof_layout['zones'])]
    # E clique « Approuver » (corps de l'écran) en envoyant même l'empreinte qu'il a relue
    p = api_e.post(f'/api/django/calepinage/calepinages/{c.pk}/approbation/',
                   {'decision': 'approuve', 'empreinte': h1_hash, 'layout_hash': h1_hash},
                   format='json', **H)
    c.refresh_from_db()
    obs['post_http'] = p.status_code
    obs['empreinte_approuvee_eq_H2'] = (c.approbation or {}).get('empreinte_approuvee') == h2_hash
    obs['empreinte_approuvee_eq_H1_relue'] = (c.approbation or {}).get('empreinte_approuvee') == h1_hash
    obs['est_approuve_H2'] = est_approuve(c)
    obs['repro'] = bool(obs['h1_ne_h2'] and p.status_code == 200 and obs['empreinte_approuvee_eq_H2']
                        and not obs['empreinte_approuvee_eq_H1_relue'])
    print(json.dumps(obs, default=str, ensure_ascii=False))
    return {'repro': obs['repro']}
