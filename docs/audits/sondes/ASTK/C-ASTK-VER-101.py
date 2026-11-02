SONDE = {"constat": "C-ASTK-VER-101", "sha": "56d5b623a",
         "modeles": ["achats.FactureFournisseur", "stock.Produit"], "attendu": "un rôle Commercial (sans prix_achat_voir) ne lit aucun montant d'achat dans /factures-fournisseur/ (liste, détail, /stock et /achats) — motif_ecart compris"}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.roles.models import Role
    from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
    from apps.stock.models import (
        Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
        FactureFournisseur, Produit,
    )
    from apps.stock.services import evaluer_rapprochement_3_voies
    U = get_user_model()
    perms = dict(CANONICAL_SYSTEM_ROLES)
    co = Company.objects.create(nom='SONDE-VER-101', slug='sonde-astk-ver-101')
    role = Role.objects.create(company=co, nom='Commercial', permissions=list(perms['Commercial']), est_systeme=True)
    u = U.objects.create_user(username='sonde-astk-ver-101', password='x', company=co, role=role)
    f = Fournisseur.objects.create(company=co, nom='F-101')
    p = Produit.objects.create(company=co, nom='P-101', sku='P-101', prix_achat=Decimal('100'), prix_vente=Decimal('150'))
    bc = BonCommandeFournisseur.objects.create(company=co, reference='BCF-SONDE-101', fournisseur=f,
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                               prix_achat_unitaire=Decimal('100'))
    ff = FactureFournisseur.objects.create(company=co, reference='FF-SONDE-101', fournisseur=f, bon_commande=bc,
                                           date_facture=datetime.date(2026, 10, 1),
                                           montant_ht=Decimal('1234.56'), montant_tva=Decimal('246.91'),
                                           montant_ttc=Decimal('1481.47'))
    statut = evaluer_rapprochement_3_voies(ff)
    ff.refresh_from_db()
    print(f"evaluer_rapprochement_3_voies -> {statut} ; motif_ecart en base = {ff.motif_ecart!r}")
    api = APIClient(); api.force_authenticate(u)
    fuite = False
    for base in ('/api/django/stock/factures-fournisseur/', '/api/django/achats/factures-fournisseur/'):
        for url in (base, f'{base}{ff.id}/'):
            r = api.get(url, HTTP_HOST='localhost')
            d = r.json()
            rows = d.get('results', d) if isinstance(d, dict) and 'results' in d else ([d] if isinstance(d, dict) else d)
            row = next((x for x in rows if isinstance(x, dict) and x.get('id') == ff.id), {})
            motif = row.get('motif_ecart')
            cles_montant = sorted(k for k in row if k.startswith('montant') or k in ('solde_du', 'total_paye', 'paiements'))
            leak = r.status_code == 200 and bool(motif) and '1' in (motif or '') and 'HT' in (motif or '')
            fuite = fuite or leak
            print(f"{url} status {r.status_code} can_view_buy_prices={u.can_view_buy_prices} "
                  f"cles_montant={cles_montant} motif_ecart={motif!r}")
    return {'repro': fuite}
