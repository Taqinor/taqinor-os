# flake8: noqa  (sonde de contre-visite « vérifie ASTK », rejouable par scripts/sonde.py — AMET93)
"""ASTK32 + ASTK40 + ASTK41 sur le code de main, par les routes réelles (admin).
(1) POST produit {quantite_stock: 7} → stock 7 + ENTREE « stock initial » 7 ; réception +5 (12) ; PATCH
{prix_vente, quantite_stock: 7} puis {quantite_stock: 3} → 200, stock relu 12, dernier quantite_apres = 12.
(2) Produit B reçu 10 @ 1 000 (ligne BCF reçue + mouvement) puis revalorisé et validé à 600 :
GET produits/valorisation/ total B = 6 000 = GET valorisation-a-date/?date=<aujourd'hui> = BI valeur_achat ;
valorisation-a-date/?date=<hier> exclut la revalo d'aujourd'hui (coût 1 000).
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-011", "sha": "c38868a62",
         "attendu": "ASTK32 : stock 12 après les PATCH, Σ registre = stock ; ASTK40/41 : écran B = à date du jour = BI = 6000.00 ; à date d'hier coût 1000.00",
         "modeles": ["authentication.Company", "stock.Produit", "stock.MouvementStock", "stock.Fournisseur",
                     "stock.BonCommandeFournisseur", "stock.LigneBonCommandeFournisseur", "stock.RevalorisationStock"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import (Produit, MouvementStock, Fournisseur, BonCommandeFournisseur,
                                   LigneBonCommandeFournisseur, RevalorisationStock)
    from apps.stock.services import record_stock_movement, creer_revalorisation, valider_revalorisation
    from apps.stock.bi_datasets import PRODUITS_DATASET
    from core import data_explorer
    co = Company.objects.create(nom='Sonde ASTK-VER4-011', slug='sonde-astk-ver4-011')
    u = get_user_model().objects.create_superuser(username='sonde-astk-ver4-011', password='x', email='v4011@example.invalid')
    u.company = co
    u.role_legacy = 'admin'
    u.save()
    api = APIClient()
    api.force_authenticate(u)
    H = dict(HTTP_HOST='localhost', format='json')
    B = '/api/django/stock/produits/'
    etapes = {}
    # (1) ASTK32
    r = api.post(B, {'nom': 'Onduleur sonde VER4-011', 'sku': 'SONDE-VER4-011-A', 'prix_vente': '1000',
                     'prix_achat': '500', 'quantite_stock': 7}, **H)
    etapes['creer'] = (r.status_code, r.data.get('quantite_stock') if r.status_code < 400 else r.data)
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    pa = Produit.objects.get(pk=r.data['id'])
    initial = list(MouvementStock.objects.filter(produit=pa).values_list('type_mouvement', 'quantite', 'reference'))
    record_stock_movement(company=co, produit=pa, type_mouvement=MouvementStock.TypeMouvement.ENTREE, quantite=5,
                          quantite_avant=7, quantite_apres=12, reference='REC-SONDE', note='sonde', created_by=u)
    r1 = api.patch(f'{B}{pa.id}/', {'prix_vente': '99', 'quantite_stock': 7}, **H)
    r2 = api.patch(f'{B}{pa.id}/', {'quantite_stock': 3}, **H)
    etapes['patch'] = (r1.status_code, r2.status_code)
    pa.refresh_from_db()
    dernier = MouvementStock.objects.filter(produit=pa).order_by('-date', '-id').values_list('quantite_apres', flat=True).first()
    # (2) ASTK40 / ASTK41
    f = Fournisseur.objects.create(company=co, nom='Fournisseur sonde VER4-011')
    pb = Produit.objects.create(company=co, nom='Batterie sonde VER4-011', sku='SONDE-VER4-011-B',
                                prix_vente=Decimal('2000'), prix_achat=Decimal('1500'), quantite_stock=0)
    hier = timezone.localdate() - datetime.timedelta(days=1)
    moment = timezone.make_aware(datetime.datetime.combine(hier, datetime.time(10, 0)))
    bc = BonCommandeFournisseur.objects.create(company=co, reference='BCF-SONDE-VER4-011', fournisseur=f,
                                               statut=BonCommandeFournisseur.Statut.RECU)
    BonCommandeFournisseur.objects.filter(pk=bc.pk).update(date_creation=moment)
    LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=pb, quantite=10,
                                               prix_achat_unitaire=Decimal('1000'), quantite_recue=10)
    m = record_stock_movement(company=co, produit=pb, type_mouvement=MouvementStock.TypeMouvement.ENTREE, quantite=10,
                              quantite_avant=0, quantite_apres=10, reference=bc.reference, note='sonde', created_by=u)
    MouvementStock.objects.filter(pk=m.pk).update(date=moment)
    revalo = creer_revalorisation(company=co, produit=pb, nouveau_cout=Decimal('600'), motif='sonde', user=u)
    valider_revalorisation(revalo)
    r = api.get(B + 'valorisation/', HTTP_HOST='localhost')
    ecran = [l for l in r.data.get('lignes', []) if l['produit_id'] == pb.id] if r.status_code == 200 else r.data
    ecran_b = sum(Decimal(str(l['valeur'])) for l in ecran) if isinstance(ecran, list) else None
    auj = timezone.localdate().isoformat()
    r = api.get(B + 'valorisation-a-date/', {'date': auj}, HTTP_HOST='localhost')
    a_date = [l for l in r.data.get('lignes', []) if l['produit_id'] == pb.id] if r.status_code == 200 else r.data
    r = api.get(B + 'valorisation-a-date/', {'date': hier.isoformat()}, HTTP_HOST='localhost')
    a_hier = [l for l in r.data.get('lignes', []) if l['produit_id'] == pb.id] if r.status_code == 200 else r.data
    bi = {x['id']: x['valeur_achat'] for x in data_explorer.run_query(
        PRODUITS_DATASET, co, u, {'select': ['id', 'valeur_achat']})}
    obs = {'astk32_mvt_initial': initial, 'astk32_stock': pa.quantite_stock, 'astk32_prix_vente': str(pa.prix_vente),
           'astk32_dernier_apres': dernier, 'ecran_b': str(ecran_b),
           'a_date_aujourdhui': [(str(l['cout_moyen']), str(l['valeur'])) for l in a_date] if isinstance(a_date, list) else a_date,
           'a_date_hier': [(str(l['cout_moyen']), str(l['valeur'])) for l in a_hier] if isinstance(a_hier, list) else a_hier,
           'bi_valeur_achat_b': str(bi.get(pb.id)), 'revalo_statut': RevalorisationStock.objects.get(pk=revalo.pk).statut}
    print(f'etapes={etapes} obs={obs}')
    ok = (pa.quantite_stock == 12 and dernier == 12 and str(pa.prix_vente) == '99.00'
          and ecran_b == Decimal('6000.00') and isinstance(a_date, list) and len(a_date) == 1
          and Decimal(str(a_date[0]['valeur'])) == Decimal('6000.00')
          and Decimal(str(bi.get(pb.id))) == Decimal('6000.00')
          and isinstance(a_hier, list) and len(a_hier) == 1 and Decimal(str(a_hier[0]['cout_moyen'])) == Decimal('1000.00'))
    return {'repro': ok, 'etapes': etapes, **obs}
