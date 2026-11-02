# flake8: noqa  (sonde de vérification C-L1-1, rejouable par scripts/sonde.py)
"""C-L1-1 — un prix TTC tapé (1 000 TTC, envoyé HT 833,33 comme l'écran : htFromTtc) × quantité 3 : le TTC
canonique tombe à 2 999,99 puis le palier ARRONDI-100 le ramène à 2 900. Rejeu par POST devis/atomic/ (API réelle),
société neuve, transaction annulée. Variantes : quantité 1 et 7."""
SONDE = {"constat": "C-ADVS-001", "sha": "1dfa7986c",
         "attendu": "3 × 1000 TTC tapés → total_ttc 3000.00 (défaut : 2900.00)",
         "modeles": ["ventes.Devis", "ventes.LigneDevis"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ADVS 001', slug='sonde-advs-001')
    u = U.objects.create_user(username='sonde-advs-001', password='x', role_legacy='admin', company=c)
    cl = Client.objects.create(company=c, nom='Arrondi', prenom='TTC', email='sonde-advs-001@example.invalid')
    pan = Produit.objects.create(company=c, nom='Panneau Canadien Solar 710W', sku='ADVS001-P',
                                 prix_vente=Decimal('900'), tva=Decimal('20'), quantite_stock=100)
    api = APIClient()
    api.force_authenticate(u)
    res = {}
    for qte in ('1', '3', '7'):
        try:
            with transaction.atomic():
                r = api.post('/api/django/ventes/devis/atomic/', {
                    'client': cl.id, 'taux_tva': '20.00',
                    'lignes': [{'produit': pan.id, 'designation': 'Panneau Canadien Solar 710W', 'quantite': qte,
                                'prix_unitaire': '833.33', 'taux_tva': '20', 'prix_manuel': True}]},
                    format='json', HTTP_HOST='localhost')
            corps = json.loads(r.content.decode('utf-8', 'replace') or '{}')
            dv = Devis.objects.filter(company=c).order_by('-id').first()
            res[qte] = {'http': r.status_code, 'total_ht': str(dv.total_ht) if dv else None,
                        'total_ttc': str(dv.total_ttc) if dv else None,
                        'attendu_tape': str(Decimal(qte) * 1000),
                        'detail': '' if r.status_code < 400 else str(corps)[:200]}
        except Exception as e:
            res[qte] = {'erreur': repr(e)[:300]}
    repro = res.get('3', {}).get('total_ttc') == '2900.00'
    return {'repro': repro, 'observe': res}
