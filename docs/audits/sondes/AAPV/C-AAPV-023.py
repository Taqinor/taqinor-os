# flake8: noqa  (sonde d'audit de parcours PA6 « Approvisionnement », rejouable par scripts/sonde.py — METHODE §C.4)
"""K25 — les sorties naturelles de la quarantaine (retour fournisseur, rebut motivé) ne consomment pas le
`BlocageQualite` : quarantaine fantôme qui bloque le stock sain.
Chaque cas : produit d'une catégorie soumise à un plan d'échantillonnage, stock sain 5 ; réception 10
(vraie route `receptions-fournisseur/`), verdict NON CONFORME (`controle-qualite/`), `confirmer/` → blocage 10,
stock 15, disponible hors quarantaine 5.
(RF) retour des 10 au fournisseur (`retours-fournisseur/` + `valider/`) ; (RB) rebut motivé des 10
(`mouvements-rebut/`, NTWMS24) ; puis sortie manuelle des 5 sains (`mouvements/` SORTIE 5).
(T) témoin : même état sans évacuation, sortie des 5 sains → acceptée."""
SONDE = {"constat": "C-AAPV-023", "sha": "b432084786",
         "attendu": "repro si RF/RB : stock 5, blocage 10 toujours en quarantaine, disponible 0, sortie de 5 refusée 409 ; T : sortie 5 acceptée",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.BlocageQualite", "stock.ReceptionFournisseur"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
                                   Produit, Categorie, PlanEchantillonnage, BlocageQualite)
    from apps.stock.services import quantite_disponible_hors_quarantaine
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AAPV 023', slug='sonde-aapv-023')
    u = get_user_model().objects.create_user(username='sonde_aapv_023', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cat = Categorie.objects.create(company=co, nom='Batteries AAPV23')
    PlanEchantillonnage.objects.create(company=co, categorie=cat, taux_echantillon_pct=20)
    f = Fournisseur.objects.create(company=co, nom='F-AAPV23')
    url = '/api/django/stock/receptions-fournisseur/'

    def mise_en_place(n):
        p = Produit.objects.create(company=co, nom=f'Batterie AAPV23-{n}', sku=f'AAPV-023-{n}', categorie=cat,
                                   prix_vente=Decimal('3000'), prix_achat=Decimal('2000'), quantite_stock=5)
        bc = BonCommandeFournisseur.objects.create(company=co, fournisseur=f, reference=f'BCF-AAPV-023-{n}',
                                                   statut=BonCommandeFournisseur.Statut.ENVOYE)
        lc = LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                                        prix_achat_unitaire=Decimal('2000'))
        r = api.post(url, {'bon_commande': bc.id, 'lignes': [{'ligne_commande': lc.id, 'quantite': 10}]},
                     format='json', **H)
        rid = r.data['id']
        rq = api.post(f'{url}{rid}/controle-qualite/', {'resultat': 'non_conforme', 'unites_controlees': 2,
                                                         'observation': 'cellules gonflées'}, format='json', **H)
        rc = api.post(f'{url}{rid}/confirmer/', {}, format='json', **H)
        p.refresh_from_db()
        return p, bc, {'creation': r.status_code, 'controle': rq.status_code, 'confirmer': rc.status_code,
                       'stock': p.quantite_stock, 'dispo': quantite_disponible_hors_quarantaine(co, p),
                       'blocages': blocages(p)}

    def blocages(p):
        return list(BlocageQualite.objects.filter(company=co, produit=p).values_list('quantite', 'statut'))

    def sortie_saine(p):
        r = api.post('/api/django/stock/mouvements/', {'produit': p.id, 'type_mouvement': 'sortie', 'quantite': 5,
                                                       'note': 'sortie chantier des 5 sains'}, format='json', **H)
        return r.status_code, (None if r.status_code < 400 else str(r.data)[:180])

    def apres(p):
        p.refresh_from_db()
        return {'stock': p.quantite_stock, 'dispo': quantite_disponible_hors_quarantaine(co, p),
                'blocages': blocages(p)}

    obs = {}
    # RF — retour fournisseur des 10 non conformes
    p, bc, init = mise_en_place('RF')
    rr = api.post('/api/django/stock/retours-fournisseur/', {
        'fournisseur': f.id, 'bon_commande': bc.id,
        'lignes': [{'produit': p.id, 'quantite': 10, 'motif': 'non conforme'}]}, format='json', **H)
    rv = api.post(f'/api/django/stock/retours-fournisseur/{rr.data["id"]}/valider/', {}, format='json', **H)
    etat = apres(p)
    s = sortie_saine(p)
    obs['RF'] = {'init': init, 'retour_valider': rv.status_code, 'apres_retour': etat, 'sortie_5_sains': s}
    # RB — rebut motivé des 10 non conformes
    p, bc, init = mise_en_place('RB')
    rb = api.post('/api/django/stock/mouvements-rebut/', {'produit': p.id, 'quantite': 10, 'motif': 'casse',
                                                          'note': 'lot non conforme détruit'}, format='json', **H)
    etat = apres(p)
    s = sortie_saine(p)
    obs['RB'] = {'init': init, 'rebut': rb.status_code, 'rebut_detail': None if rb.status_code < 400 else str(rb.data)[:160],
                 'apres_rebut': etat, 'sortie_5_sains': s}
    # T — témoin : aucune évacuation, les 5 sains sortent
    p, bc, init = mise_en_place('T')
    obs['T'] = {'init': init, 'sortie_5_sains': sortie_saine(p), 'apres': apres(p)}
    print(obs)
    t = obs['T']
    temoin_ok = (t['init']['confirmer'] == 200 and t['init']['stock'] == 15 and t['init']['dispo'] == 5
                 and t['sortie_5_sains'][0] == 201)

    def defaut(x, cle):
        e = x[cle]
        return (e['stock'] == 5 and e['dispo'] == 0
                and any(st == 'en_quarantaine' and q == 10 for q, st in e['blocages'])
                and x['sortie_5_sains'][0] == 409)
    obs['temoin_ok'] = temoin_ok
    obs['repro_retour'] = obs['RF']['retour_valider'] == 200 and defaut(obs['RF'], 'apres_retour')
    obs['repro_rebut'] = obs['RB']['rebut'] == 201 and defaut(obs['RB'], 'apres_rebut')
    obs['repro'] = bool(temoin_ok and (obs['repro_retour'] or obs['repro_rebut']))
    return obs
