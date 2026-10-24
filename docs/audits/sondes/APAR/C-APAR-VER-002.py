SONDE = {"constat": "C-APAR-VER-002", "sha": "b3c7e4065",
         "attendu": "250 produits : la lecture du sélecteur de composants des kits (GET /stock/produits/?page_size=1000, appel de KitsStock.jsx) rend les 250 produits"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.stock.models import Produit
    co = Company.objects.create(nom='Sonde APAR VER-002', slug='sonde-apar-ver-002')
    u = get_user_model().objects.create_user(username='sonde-apar-ver-002', password='x', company=co, role_legacy='admin')
    Produit.objects.bulk_create([
        Produit(company=co, nom=f'Produit sonde {i:03d}', sku=f'SONDE-APAR-002-{i:03d}',
                prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        for i in range(250)])
    api = APIClient()
    api.force_authenticate(u)
    r = api.get('/api/django/stock/produits/', {'page_size': 1000}, HTTP_HOST='localhost')
    data = r.data if isinstance(r.data, dict) else {'results': r.data}
    lus = len(data.get('results') or [])
    print(f'GET produits page_size=1000 → {r.status_code} ; lignes rendues={lus} sur 250 ; count={data.get("count")} ; '
          f'next={"oui" if data.get("next") else "non"} (KitsStock.jsx lit results sans suivre next : attendu 250 lues)')
    return {'repro': r.status_code == 200 and lus < 250, 'lues': lus, 'count': data.get('count'), 'next': bool(data.get('next'))}
