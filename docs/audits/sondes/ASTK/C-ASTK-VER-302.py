SONDE = {"constat": "C-ASTK-VER-302", "sha": "70db6e071",
         "modeles": ["achats.FactureFournisseur", "stock.Produit"], "attendu": "jumeau d'ASTK255 : un rôle Commercial (sans prix_achat_voir) ne lit aucun montant d'achat dans /stock/achats-parametres/checklist-cloture/ (montant_ttc, motif_ecart d'une facture en exception du mois)"}


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
    co = Company.objects.create(nom='SONDE-VER-302', slug='sonde-astk-ver-302')
    role = Role.objects.create(company=co, nom='Commercial', permissions=list(perms['Commercial']), est_systeme=True)
    u = U.objects.create_user(username='sonde-astk-ver-302', password='x', company=co, role=role)
    f = Fournisseur.objects.create(company=co, nom='F-302')
    p = Produit.objects.create(company=co, nom='P-302', sku='P-302', prix_achat=Decimal('100'), prix_vente=Decimal('150'))
    bc = BonCommandeFournisseur.objects.create(company=co, reference='BCF-SONDE-302', fournisseur=f,
                                               statut=BonCommandeFournisseur.Statut.ENVOYE)
    LigneBonCommandeFournisseur.objects.create(bon_commande=bc, produit=p, quantite=10,
                                               prix_achat_unitaire=Decimal('100'))
    ff = FactureFournisseur.objects.create(company=co, reference='FF-SONDE-302', fournisseur=f, bon_commande=bc,
                                           date_facture=datetime.date(2026, 10, 1),
                                           montant_ht=Decimal('1234.56'), montant_tva=Decimal('246.91'),
                                           montant_ttc=Decimal('1481.47'))
    statut = evaluer_rapprochement_3_voies(ff)
    ff.refresh_from_db()
    print(f"evaluer_rapprochement_3_voies -> {statut} ; motif_ecart en base = {ff.motif_ecart!r}")
    api = APIClient(); api.force_authenticate(u)
    r = api.get('/api/django/stock/achats-parametres/checklist-cloture/?periode=2026-10-15', HTTP_HOST='localhost')
    d = r.json() if r.status_code == 200 else {}
    rows = d.get('factures_en_exception', []) if isinstance(d, dict) else []
    row = next((x for x in rows if isinstance(x, dict) and (x.get('id') == ff.id or x.get('reference') == ff.reference)), {})
    fuite = r.status_code == 200 and (row.get('montant_ttc') not in (None, '') or '1 234,56' in str(row.get('motif_ecart') or ''))
    print(f"checklist-cloture status {r.status_code} can_view_buy_prices={u.can_view_buy_prices} ligne={row!r}")
    return {'repro': fuite}
