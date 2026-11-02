SONDE = {"constat": "C-ASTK-VER-102", "sha": "56d5b623a",
         "modeles": ["stock.Produit", "stock.MouvementStock", "stock.InventaireSession"], "attendu": "non-régression ASTK1-8/22/32 sur main : garde de classe vide, produit de B = id absent, quantite_stock et statut BCF non inscriptibles, stock initial par mouvement"}


def sonde(ctx):
    from decimal import Decimal
    from rest_framework.test import APIClient, APIRequestFactory
    from rest_framework.request import Request
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import (
        Categorie, EmplacementStock, Fournisseur, Produit, MouvementStock,
        BonCommandeFournisseur,
    )
    from apps.stock import test_astk_garde_fk_societe as garde
    U = get_user_model()
    perms = dict(CANONICAL_SYSTEM_ROLES)
    a = Company.objects.create(nom='SONDE-VER-102-A', slug='sonde-astk-ver-102-a')
    b = Company.objects.create(nom='SONDE-VER-102-B', slug='sonde-astk-ver-102-b')
    role = Role.objects.create(company=a, nom='Administrateur', permissions=list(perms['Administrateur']), est_systeme=True)
    ua = U.objects.create_user(username='sonde-astk-ver-102-a', password='x', company=a, role=role)
    U.objects.create_user(username='sonde-astk-ver-102-b', password='x', company=b, role_legacy='responsable')
    Fournisseur.objects.create(company=b, nom='F-B-102')
    pb = Produit.objects.create(company=b, nom='PB-SECRET-102', sku='PB-102', prix_achat=Decimal('50'),
                                prix_vente=Decimal('80'), quantite_stock=100)
    Categorie.objects.create(company=b, nom='Cat B 102')
    EmplacementStock.objects.create(company=b, nom='Depot B 102', is_principal=True)
    fb = Fournisseur.objects.create(company=a, nom='F-A-102')

    # 1. Garde de classe ASTK8 rejouée sur le code de main, avec nos sociétés.
    req = Request(APIRequestFactory().get('/'))
    req.user = ua
    classes = garde.decouvrir_serializers()
    manquants = []
    for c in classes:
        manquants.extend(garde.champs_non_bornes(c, req, a, b))
    print(f"garde ASTK8 : {len(classes)} serializers balayés, non bornés = {manquants}")

    api = APIClient(); api.force_authenticate(ua)
    H = {'HTTP_HOST': 'localhost'}
    # 2. ASTK1 — ligne d'inventaire sur produit de B vs id absent.
    rb = api.post('/api/django/stock/inventaire-sessions/', {'motif': 'x', 'lignes': [{'produit': pb.id, 'quantite_comptee': 0}]}, format='json', **H)
    rx = api.post('/api/django/stock/inventaire-sessions/', {'motif': 'x', 'lignes': [{'produit': 99999999, 'quantite_comptee': 0}]}, format='json', **H)
    import re as _re
    _rid = lambda t: _re.sub(r'"request_id":\s*"[0-9a-f]+"', '"request_id":"X"', t)
    corps_b = _rid(rb.content.decode().replace(str(pb.id), 'ID'))
    corps_x = _rid(rx.content.decode().replace('99999999', 'ID'))
    astk1_ok = rb.status_code == rx.status_code and rb.status_code in (400, 404) and corps_b == corps_x and 'SECRET' not in corps_b
    print(f"ASTK1 inventaire produit B : {rb.status_code} vs absent {rx.status_code} identiques={corps_b == corps_x} corps_b={corps_b[:200]} corps_x={corps_x[:200]}")

    # 3. ASTK32 — création avec stock initial puis PATCH quantite_stock ignoré.
    role_dir = Role.objects.create(company=a, nom='Directeur', permissions=list(perms['Directeur']), est_systeme=True)
    udir = U.objects.create_user(username='sonde-astk-ver-102-dir', password='x', company=a, role=role_dir)
    api_dir = APIClient(); api_dir.force_authenticate(udir)
    rc = api_dir.post('/api/django/stock/produits/', {'nom': 'PA-102', 'sku': 'PA-102', 'prix_vente': '10', 'prix_achat': '5', 'quantite_stock': 7}, format='json', **H)
    pid = rc.json().get('id') if rc.status_code == 201 else None
    mv = list(MouvementStock.objects.filter(produit_id=pid).values_list('type_mouvement', 'quantite', 'reference')) if pid else []
    rp = api_dir.patch(f'/api/django/stock/produits/{pid}/', {'prix_vente': '11', 'quantite_stock': 3}, format='json', **H) if pid else None
    pa = Produit.objects.get(pk=pid) if pid else None
    astk32_ok = bool(pid) and pa.quantite_stock == 7 and len(mv) == 1 and mv[0][1] == 7 and str(pa.prix_vente) in ('11', '11.00')
    print(f"ASTK32 creation {rc.status_code} mouvements={mv} ; PATCH {getattr(rp, 'status_code', None)} stock relu={getattr(pa, 'quantite_stock', None)} prix_vente={getattr(pa, 'prix_vente', None)} corps_creation={rc.content.decode()[:200] if rc.status_code != 201 else ''}")

    # 4. ASTK22 — PATCH statut d'un BCF brouillon ignoré.
    bc = BonCommandeFournisseur.objects.create(company=a, reference='BCF-SONDE-102', fournisseur=fb)
    rs = api.patch(f'/api/django/stock/bons-commande-fournisseur/{bc.id}/', {'statut': 'recu'}, format='json', **H)
    bc.refresh_from_db()
    astk22_ok = bc.statut == BonCommandeFournisseur.Statut.BROUILLON
    print(f"ASTK22 PATCH statut=recu : {rs.status_code} statut relu={bc.statut}")
    return {'repro': bool(manquants) or not (astk1_ok and astk32_ok and astk22_ok)}
