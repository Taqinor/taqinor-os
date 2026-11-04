# flake8: noqa  (sonde de contre-visite « vérifie ASTK », rejouable par scripts/sonde.py — AMET93)
"""ASTK38 + ASTK39 (comptage cyclique, chemin installations) et ASTK39 (session d'inventaire) sur le code de main.
Cyclique : ajouter-ligne (stock 100, théorique 100) → SORTIE 20 (live 80) → PATCH compté 80 → ENTREE +20 (live 100)
→ terminer. Règle D-ASTK « stock à la saisie » : théorique re-snapshoté à 80, écart 0, l'entrée postérieure gardée
⇒ stock final 100, aucun AJUSTEMENT. Session : POST inventaire-sessions {compté 80} après une sortie 20 (live 80)
puis valider ⇒ stock 80. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-010", "sha": "c38868a62",
         "attendu": "cyclique : théorique relu 80 après saisie, stock final 100, 0 AJUSTEMENT ; session : théorique 80, stock final 80 ; |après−avant| = quantite pour tout mouvement",
         "modeles": ["authentication.Company", "stock.Produit", "stock.MouvementStock", "installations.SessionComptage",
                     "installations.ComptageLigne", "stock.InventaireSession", "stock.LigneInventaire"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.installations.models import SessionComptage, ComptageLigne
    from apps.stock.models import Produit, MouvementStock
    from apps.stock.services import record_stock_movement
    co = Company.objects.create(nom='Sonde ASTK-VER4-010', slug='sonde-astk-ver4-010')
    u = get_user_model().objects.create_user(username='sonde-astk-ver4-010', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)

    def mvt(p, typ, q):
        p.refresh_from_db()
        apres = p.quantite_stock + (q if typ == 'ENTREE' else -q)
        record_stock_movement(company=co, produit=p, type_mouvement=getattr(MouvementStock.TypeMouvement, typ),
                              quantite=q, quantite_avant=p.quantite_stock, quantite_apres=apres,
                              reference='SONDE-' + typ, note='sonde', created_by=u)

    def nouveau(sku):
        p = Produit.objects.create(company=co, nom='Panneau ' + sku, sku=sku, prix_vente=Decimal('100'),
                                   prix_achat=Decimal('50'), quantite_stock=0)
        mvt(p, 'ENTREE', 100)
        return p

    H = dict(HTTP_HOST='localhost', format='json')
    etapes = {}
    # --- chemin cyclique (installations)
    p1 = nouveau('SONDE-VER4-010-A')
    s = SessionComptage.objects.create(company=co, reference='CYC-SONDE-VER4-010',
                                       statut=SessionComptage.Statut.EN_COURS, created_by=u)
    r = api.post(f'/api/django/installations/sessions-comptage/{s.id}/ajouter-ligne/', {'produit': p1.id}, **H)
    etapes['ajouter_ligne'] = (r.status_code, r.data.get('quantite_theorique') if r.status_code < 400 else r.data)
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    lid = r.data['id']
    mvt(p1, 'SORTIE', 20)
    r = api.patch(f'/api/django/installations/comptage-lignes/{lid}/', {'quantite_comptee': 80, 'compte': True}, **H)
    etapes['saisie'] = (r.status_code, r.data.get('quantite_theorique') if r.status_code < 400 else r.data)
    mvt(p1, 'ENTREE', 20)
    r = api.post(f'/api/django/installations/sessions-comptage/{s.id}/terminer/', **H)
    etapes['terminer'] = r.status_code
    p1.refresh_from_db()
    ajust1 = MouvementStock.objects.filter(produit=p1, type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT).count()
    theo1 = ComptageLigne.objects.get(pk=lid).quantite_theorique
    # --- chemin session d'inventaire (stock)
    p2 = nouveau('SONDE-VER4-010-B')
    mvt(p2, 'SORTIE', 20)
    r = api.post('/api/django/stock/inventaire-sessions/',
                 {'motif': 'sonde', 'lignes': [{'produit': p2.id, 'quantite_comptee': 80, 'quantite_theorique': 999}]}, **H)
    etapes['session_creer'] = (r.status_code, [l.get('quantite_theorique') for l in r.data.get('lignes', [])] if r.status_code < 400 else r.data)
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    r2 = api.post(f"/api/django/stock/inventaire-sessions/{r.data['id']}/valider/", **H)
    etapes['session_valider'] = (r2.status_code, r2.data if r2.status_code < 400 else r2.data)
    p2.refresh_from_db()
    incoherents = [m.reference for m in MouvementStock.objects.filter(company=co)
                   if abs(m.quantite_apres - m.quantite_avant) != m.quantite]
    obs = {'cyc_theorique_apres_saisie': theo1, 'cyc_stock_final': p1.quantite_stock, 'cyc_ajustements': ajust1,
           'session_stock_final': p2.quantite_stock, 'mouvements_incoherents': incoherents}
    print(f'etapes={etapes} obs={obs}')
    ok = (theo1 == 80 and p1.quantite_stock == 100 and ajust1 == 0 and p2.quantite_stock == 80 and not incoherents)
    return {'repro': ok, 'etapes': etapes, **obs}
