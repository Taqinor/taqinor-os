# flake8: noqa  (sonde d'audit PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K24 — l'accord survit-il à un changement ÉLECTRIQUE ? Société qui EXIGE l'approbation (PUT presets,
vraie route). Témoin : avant accord, la porte d'exécution refuse (409). E approuve (vraie route) une
conception avec onduleur A ; D change l'onduleur (B) et force la longueur de chaîne par la vraie route
POST entree-electrique/ ; on relit l'accord (est_approuve / perimee), la porte d'exécution
(porte_execution 'plan_cablage') et GET plan-cablage.pdf. Transaction annulée."""
SONDE = {"constat": "C-ACON-024", "sha": "33cba7f5d",
         "attendu": "repro si temoin 409 avant accord, puis apres changement d'onduleur : accord non perime, porte d'execution ouverte",
         "modeles": ["calepinage.Calepinage", "calepinage.ParametresCalepinage", "stock.Produit"]}


def sonde(ctx):
    import copy
    import json
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.stock.models import Produit
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.layout import enregistrer_layout
    from apps.calepinage.services.approbation import est_approuve, etat_approbation
    from apps.calepinage.views.sorties import porte_execution
    from apps.calepinage.tests.acal_livrables_helpers import LAYOUT_PLANCHE_SIMULABLE

    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ACON 024', slug='sonde-acon-024')
    D = U.objects.create_user(username='k24_concepteur', password='x', role_legacy='admin', company=co)
    E = U.objects.create_user(username='k24_relecteur', password='x', role_legacy='admin', company=co)
    api_d, api_e = APIClient(), APIClient()
    api_d.force_authenticate(D)
    api_e.force_authenticate(E)
    obs = {}
    r = api_e.put('/api/django/calepinage/parametres/', {'presets': {'approbation_exigee': True}}, format='json', **H)
    obs['put_presets'] = [r.status_code, str(r.content[:120]) if r.status_code != 200 else '']
    ondA = Produit.objects.create(company=co, nom='Onduleur A 5 kW', sku='k24-a', prix_vente=Decimal('9000'), quantite_stock=5)
    ondB = Produit.objects.create(company=co, nom='Onduleur B 8 kW', sku='k24-b', prix_vente=Decimal('14000'), quantite_stock=5)
    lead = Lead.objects.create(company=co, nom='Lead K24')
    c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre='K24', roof_layout={}, cree_par=D, responsable=D)
    enregistrer_layout(c, copy.deepcopy(LAYOUT_PLANCHE_SIMULABLE), user=D, libelle='conception')
    c.refresh_from_db()
    url = f'/api/django/calepinage/calepinages/{c.pk}/'
    r = api_d.post(url + 'entree-electrique/', {'onduleur_produit': ondA.pk}, format='json', **H)
    obs['entree_A'] = [r.status_code, str(r.content[:160]) if r.status_code != 200 else '']
    c.refresh_from_db()
    try:
        porte_execution(c, 'plan_cablage')
        obs['temoin_porte_avant_accord'] = 'ouverte'
    except Exception as exc:
        obs['temoin_porte_avant_accord'] = f'{type(exc).__name__} {getattr(exc, "status_code", "")}'
    r = api_e.post(url + 'approbation/', {'decision': 'approuve'}, format='json', **H)
    obs['approbation_E'] = [r.status_code, str(r.content[:160]) if r.status_code != 200 else '']
    c.refresh_from_db()
    hash_avant = c.layout_hash
    entree_avant = copy.deepcopy((c.resultat or {}).get('entree_electrique'))
    # D change l'onduleur et force la chaîne (onglet Électrique) APRÈS l'accord
    r = api_d.post(url + 'entree-electrique/', {'onduleur_produit': ondB.pk, 'longueur_chaine_forcee': 6},
                   format='json', **H)
    obs['entree_B'] = [r.status_code, str(r.content[:200]) if r.status_code != 200 else '']
    c.refresh_from_db()
    entree_apres = (c.resultat or {}).get('entree_electrique')
    obs['entree_avant'] = {k: (entree_avant or {}).get(k) for k in ('onduleur_produit', 'longueur_chaine_forcee')}
    obs['entree_apres'] = {k: (entree_apres or {}).get(k) for k in ('onduleur_produit', 'longueur_chaine_forcee')}
    obs['layout_hash_inchange'] = hash_avant == c.layout_hash
    obs['est_approuve_apres'] = est_approuve(c)
    obs['perimee_apres'] = etat_approbation(c).get('perimee')
    try:
        porte_execution(c, 'plan_cablage')
        obs['porte_execution_apres'] = 'ouverte'
    except Exception as exc:
        obs['porte_execution_apres'] = f'{type(exc).__name__} {getattr(exc, "detail", "")}'[:160]
    g = api_d.get(url + 'plan-cablage.pdf/', **H)
    obs['get_plan_cablage_pdf'] = [g.status_code, g.get('Content-Type'),
                                   '' if g.status_code == 200 else str(g.content[:160])]
    obs['repro'] = bool(obs['temoin_porte_avant_accord'] != 'ouverte'
                        and obs['entree_apres'].get('onduleur_produit') == ondB.pk
                        and obs['est_approuve_apres'] and obs['porte_execution_apres'] == 'ouverte')
    print(json.dumps(obs, default=str, ensure_ascii=False))
    return {'repro': obs['repro']}
