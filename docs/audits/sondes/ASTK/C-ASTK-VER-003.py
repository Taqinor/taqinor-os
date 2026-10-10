SONDE = {"constat": "C-ASTK-VER-003", "sha": "5ea32b58b",
         "attendu": "un rôle Commercial (sans prix_achat_voir) ne reçoit aucune clé montant sur /stock/acomptes-fournisseur/ et /ouverts/"}


def sonde(ctx):
    from decimal import Decimal
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import Fournisseur, BonCommandeFournisseur, AcompteFournisseur
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-VER-003', slug='sonde-astk-ver-003')
    role = Role.objects.create(company=co, nom='Commercial', permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Commercial']), est_systeme=True)
    u = U.objects.create_user(username='sonde-astk-ver-003', password='x', company=co, role=role)
    f = Fournisseur.objects.create(company=co, nom='F')
    bc = BonCommandeFournisseur.objects.create(company=co, reference='BCF-SONDE-VER-003', fournisseur=f)
    AcompteFournisseur.objects.create(company=co, bon_commande=bc, montant=Decimal('820'))
    api = APIClient(); api.force_authenticate(u)
    fuite = False
    for url in ('/api/django/stock/acomptes-fournisseur/', '/api/django/stock/acomptes-fournisseur/ouverts/'):
        r = api.get(url, HTTP_HOST='localhost')
        d = r.json()
        rows = d.get('results', d) if isinstance(d, dict) else d
        montants = [x.get('montant') for x in rows] if isinstance(rows, list) else rows
        fuite = fuite or (r.status_code == 200 and any(m is not None for m in (montants or [])))
        print(url, f"status {r.status_code} can_view_buy_prices={u.can_view_buy_prices} montant={montants}")
    return {'repro': fuite}
