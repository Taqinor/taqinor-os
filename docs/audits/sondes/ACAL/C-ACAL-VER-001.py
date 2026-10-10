SONDE = {"constat": "C-ACAL-VER-001", "sha": "5ea32b58b",
         "attendu": "resynchro (sync-layout) d'un document dont une surface de pose pavée n'a pas de moduleWc : refus 422 nommant la surface, panneaux et TTC inchangés"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.ventes.domain.catalogue import _is_panel
    from apps.ventes.domain.lignes import _classe_ligne
    from authentication.models import Company
    User = get_user_model()
    co = Company.objects.create(nom='SONDE ACAL VER-001', slug='sonde-acal-ver-001')
    u = User.objects.create_user(username='sonde_acal_ver_001', password='x', role_legacy='responsable', company=co)
    api = APIClient(); api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client sonde')
    for nom, sku, prix in (('Panneau mono 550W', 'SAV1-550', '2290'), ('Onduleur réseau Growatt 50kW', 'SAV1-OND', '30000')):
        Produit.objects.create(company=co, nom=nom, sku=sku, prix_vente=Decimal(prix), prix_achat=Decimal('1'), quantite_stock=500)
    TOIT = {'scenario': 'reseau', 'panelWatt': 550, 'zones': [{'id': 'z', 'label': 'Toit', 'geometry': {'count': 12, 'kwc': 6.6, 'azimuthDeg': 180, 'tiltDeg': 30}}]}
    r = api.post('/api/django/ventes/devis/from-layout/', {'layout': TOIT, 'client': cl.pk}, format='json', HTTP_HOST='localhost')
    if r.status_code != 201:
        print('création', r.status_code, str(r.data)[:300]); return {'repro': False}
    did = r.data['id']
    pan = lambda: sum(int(li.quantite) for li in Devis.objects.get(pk=did).lignes.all() if _classe_ligne(li, _is_panel))
    avant, ttc_avant = pan(), Devis.objects.get(pk=did).total_ttc
    MIXTE = dict(TOIT, poseSurfaces=[{'id': 's1', 'kind': 'sol', 'label': 'Champ au sol', 'rowAzimuthDeg': 90, 'tiltDeg': 25, 'engine': {'modules': 40}}])
    s = api.post(f'/api/django/ventes/devis/{did}/sync-layout/', MIXTE, format='json', HTTP_HOST='localhost')
    apres, ttc_apres = pan(), Devis.objects.get(pk=did).total_ttc
    print(f"sync {s.status_code} panneaux {avant}->{apres} ttc {ttc_avant}->{ttc_apres} data={str(s.data)[:200]}")
    return {'repro': s.status_code < 400 and apres != avant}
