# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K63 — comptage cyclique : une session TERMINÉE peut-elle être rouverte par `demarrer`, et `terminer`
re-poste-t-il alors l'écart ? Panneau stock 30 ; session CYC, `ajouter-ligne`, ligne comptée 28 (théorique
re-snapshoté à 30), `demarrer` → `terminer` (AJUSTEMENT −2, stock 28). Puis `demarrer` + `terminer` encore, deux
fois. Témoin : `terminer` rejoué SANS `demarrer` ne poste rien (idempotence AUD320). Vraies routes
`installations/sessions-comptage/` et `comptage-lignes/`, rôle responsable."""
SONDE = {"constat": "C-AAPV-083", "sha": "6ffa876688",
         "attendu": "repro si demarrer d'une session terminée → 200 et chaque cycle re-poste −2 (3 AJUSTEMENT, stock 24) ; témoin terminer seul : rien",
         "modeles": ["stock.Produit", "stock.MouvementStock", "installations.SessionComptage",
                     "installations.ComptageLigne"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit, MouvementStock
    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde AAPV 083', slug='sonde-aapv-083')
    u = get_user_model().objects.create_user(username='sonde_aapv_083', password='x', role_legacy='responsable',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    p = Produit.objects.create(company=co, nom='Panneau AAPV83', sku='AAPV-083', prix_vente=Decimal('1000'),
                               quantite_stock=30)
    s = api.post(f'{B}/sessions-comptage/', {'intitule': 'Cycle AAPV83'}, format='json', **H)
    assert s.status_code == 201, (s.status_code, s.data)
    sid, ref = s.data['id'], s.data['reference']
    li = api.post(f'{B}/sessions-comptage/{sid}/ajouter-ligne/', {'produit': p.id}, format='json', **H)
    pl = api.patch(f'{B}/comptage-lignes/{li.data["id"]}/', {'quantite_comptee': 28, 'compte': True},
                   format='json', **H)

    def etat():
        p.refresh_from_db()
        aj = list(MouvementStock.objects.filter(company=co, produit=p, reference=ref).order_by('id')
                  .values_list('type_mouvement', 'quantite', 'quantite_avant', 'quantite_apres'))
        return {'stock': str(p.quantite_stock), 'ajustements': len(aj),
                'mvts': [(t, str(q), str(a), str(b)) for t, q, a, b in aj]}

    journal = []
    d0 = api.post(f'{B}/sessions-comptage/{sid}/demarrer/', {}, format='json', **H)
    t0 = api.post(f'{B}/sessions-comptage/{sid}/terminer/', {}, format='json', **H)
    journal.append(('cycle 1', d0.status_code, t0.status_code, t0.data.get('statut'), etat()))
    tt = api.post(f'{B}/sessions-comptage/{sid}/terminer/', {}, format='json', **H)
    journal.append(('témoin terminer seul', None, tt.status_code, tt.data.get('statut'), etat()))
    for n in (2, 3):
        d = api.post(f'{B}/sessions-comptage/{sid}/demarrer/', {}, format='json', **H)
        statut_apres_demarrer = d.data.get('statut') if d.status_code < 400 else str(d.data)[:100]
        t = api.post(f'{B}/sessions-comptage/{sid}/terminer/', {}, format='json', **H)
        journal.append((f'cycle {n}', (d.status_code, statut_apres_demarrer), t.status_code,
                        t.data.get('statut'), etat()))
    obs = {'creation': s.status_code, 'ajouter_ligne': li.status_code,
           'theorique_snapshot': li.data.get('quantite_theorique'), 'patch_ligne': pl.status_code,
           'journal': journal}
    print(obs)
    temoin_ok = journal[0][4]['ajustements'] == 1 and journal[0][4]['stock'] == '28' \
        and journal[1][4]['ajustements'] == 1
    final = journal[-1][4]
    obs['temoin_ok'] = temoin_ok
    obs['repro'] = bool(temoin_ok and final['ajustements'] > 1 and Decimal(final['stock']) < 28)
    return obs
