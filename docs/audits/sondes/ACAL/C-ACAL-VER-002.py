SONDE = {"constat": "C-ACAL-VER-002", "sha": "5ea32b58b",
         "attendu": "resynchro vers une fiche module désignée NON tarifée : refus « tarifez la fiche … », lignes et TTC inchangés"}


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
    co = Company.objects.create(nom='SONDE ACAL VER-002', slug='sonde-acal-ver-002')
    u = User.objects.create_user(username='sonde_acal_ver_002', password='x', role_legacy='responsable', company=co)
    api = APIClient(); api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client sonde')
    P = lambda nom, sku, prix: Produit.objects.create(company=co, nom=nom, sku=sku, prix_vente=Decimal(prix), prix_achat=Decimal('1'), quantite_stock=100)
    p550 = P('Panneau mono 550W', 'SAV2-550', '2290'); prem = P('Panneau mono 550W premium', 'SAV2-550P', '0'); P('Onduleur réseau Growatt 10kW', 'SAV2-OND', '14000')
    pan = lambda n, m: {'id': 'A', 'label': 'A', 'geometry': {'moduleId': m, 'azimuthDeg': 180, 'tiltDeg': 20, 'panels': [{'cx': i, 'cy': 0} for i in range(n)]}}
    mod = lambda i, p: {'id': i, 'libelle': p.nom, 'source': 'fiche', 'produitId': p.pk, 'pmaxWc': 550}
    L1 = {'scenario': 'reseau', 'panelWatt': 550, 'modules': [mod('m1', p550)], 'zones': [pan(12, 'm1')]}
    r = api.post('/api/django/ventes/devis/from-layout/', {'layout': L1, 'client': cl.pk}, format='json', HTTP_HOST='localhost')
    if r.status_code != 201:
        print('création', r.status_code, str(r.data)[:300]); return {'repro': False}
    did = r.data['id']
    lignes = lambda: {li.produit_id: int(li.quantite) for li in Devis.objects.get(pk=did).lignes.all() if _classe_ligne(li, _is_panel)}
    avant, ttc_avant = lignes(), Devis.objects.get(pk=did).total_ttc
    L2 = {'scenario': 'reseau', 'panelWatt': 550, 'modules': [mod('m2', prem)], 'zones': [pan(12, 'm2')]}
    s = api.post(f'/api/django/ventes/devis/{did}/sync-layout/', L2, format='json', HTTP_HOST='localhost')
    apres, ttc_apres = lignes(), Devis.objects.get(pk=did).total_ttc
    print(f"sync {s.status_code} panneaux {avant}->{apres} ttc {ttc_avant}->{ttc_apres} avert={str((s.data or {}).get('avertissements') if isinstance(s.data, dict) else s.data)[:200]}")
    return {'repro': s.status_code < 400 and ttc_apres != ttc_avant}
