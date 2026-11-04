# flake8: noqa  (sonde d'audit, contre-visite ADEV du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ADEV81 (D-ACI-8=a) — jumeau oublié : l'APERÇU du générateur `POST /ventes/economie-ci/preview/`
(`economie_ci_view.py::economie_ci_preview`) appelle `economie_ci.assembler_economie_ci` SANS
`controle_lignes` (défaut False) : seul « total ≤ 0 » y est contrôlé. Une composition C&I dont les
articles de taille sont « prix à renseigner » (contrat etude_ci_preview.json : 3 articles) et dont
l'écran ne porte que 1 000 MAD HT sans panneau sort avec un retour, un TRI et un coût du kWh chiffrés
(affichés par `CarteEconomieCi.jsx` / `CarteResultatCi.jsx`), là où `economie_ci_pour_devis` pose
l'omission « investissement non encore chiffré ». Chaîne API réelle. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADEV-VER4-010", "sha": "fcbed3760",
         "attendu": "preview 200 avec indicateurs.retour_ans / tri_pct non nuls et AUCUNE omission investissement_mad "
                    "alors que assembler_economie_ci(..., controle_lignes=True) sur les mêmes entrées pose l'omission ; "
                    "attendu sain : omission + indicateurs nuls dans les deux cas",
         "modeles": ["authentication.Company", "ventes.Devis"]}


def sonde(ctx):
    import copy, json, os
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    import apps.ventes as ventes_pkg
    from apps.ventes import economie_ci as eco
    chemin = os.path.join(os.path.dirname(ventes_pkg.__file__), 'contract_samples', 'etude_ci_preview.json')
    with open(chemin, encoding='utf-8') as f:
        apercu = copy.deepcopy(json.load(f)['exemple'])
    apercu['entrees_resolues']['tension'] = {'valeur': 'mt', 'provenance': None}
    co = Company.objects.create(nom='Sonde ADEV-VER4-010', slug='sonde-adev-ver4-010')
    u = get_user_model().objects.create_user(username='sonde-adev-ver4-010', password='x',
                                             role_legacy='responsable', company=co)
    api = APIClient()
    api.force_authenticate(u)
    lignes = [{'designation': 'Smart Meter', 'quantite': 1, 'optionnelle': False,
               'totaux': {'ht': 1000.0, 'ttc': 1200.0}}]
    r = api.post('/api/django/ventes/economie-ci/preview/',
                 {'sortie_etude_ci': apercu, 'saisies': {}, 'lignes': lignes},
                 format='json', HTTP_HOST='localhost')
    if r.status_code != 200:
        return {'repro': False, 'status': r.status_code, 'data': str(r.data)[:400]}
    bloc = r.json()
    ind = bloc.get('indicateurs') or {}
    omis_preview = [o for o in bloc.get('omissions') or [] if o.get('cle') == 'investissement_mad']
    # Même entrées, contrôle des lignes ACTIVÉ (ce que lit le document, economie_ci_pour_devis).
    ligne_doc = [{'designation': 'Smart Meter', 'ht': 1000.0, 'ttc': 1200.0, 'optionnelle': False,
                  'onduleur': False, 'panneau': False, 'role_ci': None}]
    doc = eco.assembler_economie_ci(copy.deepcopy(apercu), investissement={'ht': 1000.0, 'ttc': 1200.0},
                                    lignes=ligne_doc, mode_installation=bloc.get('mode') or 'industriel',
                                    controle_lignes=True)
    omis_doc = [o for o in doc.get('omissions') or [] if o.get('cle') == 'investissement_mad']
    obs = {'statut_preview': bloc.get('statut'),
           'preview_retour_ans': ind.get('retour_ans'), 'preview_tri_pct': ind.get('tri_pct'),
           'preview_lcoe': ind.get('lcoe_mad_kwh'), 'preview_omission_inv': omis_preview,
           'prix_a_renseigner': (apercu.get('composition') or {}).get('prix_a_renseigner'),
           'doc_retour_ans': (doc.get('indicateurs') or {}).get('retour_ans'),
           'doc_omission_inv': omis_doc}
    print(json.dumps(obs, ensure_ascii=False, default=str))
    repro = (bloc.get('statut') == 'calcule' and not omis_preview
             and (ind.get('retour_ans') is not None or ind.get('tri_pct') is not None)
             and bool(omis_doc))
    return {'repro': repro, **obs}
