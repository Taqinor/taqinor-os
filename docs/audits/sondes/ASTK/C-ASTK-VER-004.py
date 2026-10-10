SONDE = {"constat": "C-ASTK-VER-004", "sha": "5ea32b58b",
         "attendu": "produit 15 en stock dont 10 rappelés (quarantaine) : une sortie scannée de 12 au poste scanner est refusée (400 nommé), stock inchangé"}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Categorie, LotEntrepot, Produit
    from apps.stock.models_wms import BlocageQualite
    co = Company.objects.create(nom='Sonde ASTK VER-004', slug='sonde-astk-ver-004')
    u = get_user_model().objects.create_user(username='sonde_astk_ver_004', password='x', role_legacy='admin', company=co)
    api = APIClient(); api.force_authenticate(u)
    cat = Categorie.objects.create(company=co, nom='Batteries sonde')
    p = Produit.objects.create(company=co, nom='Batterie sonde', sku='SONDE-VER-004', categorie=cat,
                               prix_achat=Decimal('100'), prix_vente=Decimal('200'), quantite_stock=15)
    lot = LotEntrepot.objects.create(company=co, produit=p, numero_lot='LOT-RAPPEL', date_peremption=datetime.date(2027, 1, 1),
                                     quantite_recue=10, quantite_restante=10)
    LotEntrepot.objects.create(company=co, produit=p, numero_lot='LOT-SAIN', date_peremption=datetime.date(2028, 1, 1),
                               quantite_recue=5, quantite_restante=5)
    rap = api.post('/api/django/stock/alertes-rappel/', {'produit': p.id, 'lot': lot.id, 'motif': 'Défaut cellule'}, format='json', HTTP_HOST='localhost')
    bloque = sum(b.quantite for b in BlocageQualite.objects.filter(company=co, produit=p, statut=BlocageQualite.Statut.EN_QUARANTAINE))
    r = api.post('/api/django/stock/scanner/mouvement/', {'produit': p.id, 'type_mouvement': 'sortie', 'quantite': 12}, format='json', HTTP_HOST='localhost')
    p.refresh_from_db()
    print(f"rappel {rap.status_code} quarantaine={bloque} ; scanner sortie 12 -> {r.status_code} {str(getattr(r, 'data', ''))[:160]} ; stock {p.quantite_stock} (attendu 400, stock 15)")
    return {'repro': r.status_code < 400 and p.quantite_stock == 3}
