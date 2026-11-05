# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K60 — retour chantier VALIDÉ encore modifiable : chantier sorti de 10 (F11 validée, stock 0).
R1 : ligne 10 → `valider` (ENTRÉE 10). Puis, selon la variante, (a) PATCH de la ligne validée à 0,
(b) DELETE de la ligne validée, (c) DELETE du retour validé ; puis R2 : ligne 10 → `valider`.
Question : la seconde validation passe-t-elle (stock +20 pour 10 sortis) ? Témoin (T) : sans geste sur R1,
R2 de 10 est refusé (409, retournable 0). Vraies routes `installations/retours-materiel/` et
`installations/retour-materiel-lignes/`, rôle responsable."""
SONDE = {"constat": "C-AAPV-080", "sha": "6ffa876688",
         "attendu": "repro si a/b/c : geste sur R1 validé 2xx puis R2 valider 200, Σ ENTRÉE RETOUR 20 et stock 20 pour 10 sortis ; T : R2 409",
         "modeles": ["stock.Produit", "stock.MouvementStock", "installations.RetourMateriel",
                     "installations.RetourMaterielLigne", "installations.ConsommationLigne"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import (Installation, Intervention, MaterielConsommation, ConsommationLigne)
    from apps.installations.services import quantite_retournable
    from apps.stock.models import Produit, MouvementStock
    H = {'HTTP_HOST': 'localhost'}
    B = '/api/django/installations'
    co = Company.objects.create(nom='Sonde AAPV 080', slug='sonde-aapv-080')
    u = get_user_model().objects.create_user(username='sonde_aapv_080', password='x', role_legacy='responsable',
                                             company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client AAPV80', prenom='T', email='aapv80@example.invalid')

    def chantier(tag):
        inst = Installation.objects.create(company=co, reference=f'CHT-AAPV80-{tag}', client=cl,
                                           statut=Installation.Statut.INSTALLE)
        p = Produit.objects.create(company=co, nom=f'Panneau AAPV80 {tag}', sku=f'AAPV-080-{tag}',
                                   prix_vente=Decimal('1000'), quantite_stock=0)
        itv = Intervention.objects.create(company=co, installation=inst, type_intervention=Intervention.Type.POSE)
        cons = MaterielConsommation.objects.create(company=co, intervention=itv, valide=True)
        ConsommationLigne.objects.create(company=co, consommation=cons, produit=p, designation=p.nom,
                                         quantite_prevue=Decimal('10'), quantite_utilisee=Decimal('10'),
                                         stock_applique=True)
        return inst, p

    def retour(inst, p, q):
        r = api.post(f'{B}/retours-materiel/', {'installation': inst.id}, format='json', **H)
        assert r.status_code == 201, (r.status_code, r.data)
        li = api.post(f'{B}/retour-materiel-lignes/', {'retour': r.data['id'], 'produit': p.id, 'quantite': str(q)},
                      format='json', **H)
        assert li.status_code == 201, (li.status_code, li.data)
        v = api.post(f'{B}/retours-materiel/{r.data["id"]}/valider/', {}, format='json', **H)
        return r.data['id'], li.data['id'], v.status_code, (None if v.status_code < 400 else str(v.data)[:140])

    def bilan(inst, p):
        p.refresh_from_db()
        ent = MouvementStock.objects.filter(company=co, produit=p, reference=f'RETOUR-{inst.reference}').aggregate(
            t=Sum('quantite'))['t'] or 0
        return {'entrees_retour': str(ent), 'stock': str(p.quantite_stock),
                'retournable': str(quantite_retournable(inst, p.id))}

    obs = {}
    for tag in ('a', 'b', 'c', 'T'):
        inst, p = chantier(tag)
        r1, l1, v1, d1 = retour(inst, p, 10)
        geste = None
        if tag == 'a':
            g = api.patch(f'{B}/retour-materiel-lignes/{l1}/', {'quantite': '0'}, format='json', **H)
            geste = ('PATCH ligne 0', g.status_code)
        elif tag == 'b':
            g = api.delete(f'{B}/retour-materiel-lignes/{l1}/', **H)
            geste = ('DELETE ligne', g.status_code)
        elif tag == 'c':
            g = api.delete(f'{B}/retours-materiel/{r1}/', **H)
            geste = ('DELETE retour', g.status_code)
        apres_geste = bilan(inst, p)
        r2, l2, v2, d2 = retour(inst, p, 10)
        obs[tag] = {'R1_valider': v1, 'geste': geste, 'apres_geste': apres_geste,
                    'R2_valider': v2, 'R2_detail': d2, 'final': bilan(inst, p)}
    print(obs)
    temoin_ok = obs['T']['R2_valider'] == 409 and obs['T']['final']['stock'] == '10'
    defauts = {t: obs[t]['geste'][1] < 300 and obs[t]['R2_valider'] == 200
               and Decimal(obs[t]['final']['entrees_retour']) == 20 for t in ('a', 'b', 'c')}
    obs['temoin_ok'] = temoin_ok
    obs['defauts'] = defauts
    obs['repro'] = bool(temoin_ok and any(defauts.values()))
    return obs
