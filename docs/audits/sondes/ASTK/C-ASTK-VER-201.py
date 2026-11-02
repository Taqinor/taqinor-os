SONDE = {"constat": "C-ASTK-VER-201", "sha": "56d5b623a",
         "attendu": "BCF 10 @ 60, reception API de 12 : 201 puis 2e brouillon de 1 refuse 409 ; confirmation -> stock 10, quantite_appliquee 10, provision GR/IR 600.00, facture 600.00 HT ; annulation retire 10 (ASTK59/ASTK60)",
         "modeles": ["authentication.Company", "stock.Produit", "stock.MouvementStock",
                     "stock.ReceptionFournisseur", "stock.FactureFournisseur",
                     "installations.ReceptionNonFacturee"]}


def sonde(ctx):
    from decimal import Decimal
    from rest_framework.test import APIClient
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.stock.models import (
        Fournisseur, BonCommandeFournisseur, LigneBonCommandeFournisseur,
        Produit, ReceptionFournisseur, FactureFournisseur)
    from apps.stock.services import (
        confirm_reception_fournisseur, facturer_reception,
        annuler_reception_confirmee)
    from apps.installations.models_gr_ir import ReceptionNonFacturee
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-VER-201', slug='sonde-astk-ver-201')
    u = U.objects.create_user(username='sonde-astk-ver-201', password='x',
                              company=co, role_legacy='admin')
    p = Produit.objects.create(company=co, nom='Onduleur sonde 201',
                               sku='SONDE-201', prix_vente=Decimal('100'),
                               quantite_stock=0)
    f = Fournisseur.objects.create(company=co, nom='F201')
    bc = BonCommandeFournisseur.objects.create(
        company=co, fournisseur=f, reference='BCF-SONDE-201',
        statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc = LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, produit=p, quantite=10,
        prix_achat_unitaire=Decimal('60'))
    api = APIClient()
    api.force_authenticate(u)
    url = '/api/django/stock/receptions-fournisseur/'
    corps = {'bon_commande': bc.id,
             'lignes': [{'ligne_commande': lc.id, 'quantite': 12}]}
    r1 = api.post(url, corps, format='json', HTTP_HOST='localhost')
    corps2 = {'bon_commande': bc.id,
              'lignes': [{'ligne_commande': lc.id, 'quantite': 1}]}
    r2 = api.post(url, corps2, format='json', HTTP_HOST='localhost')
    print(f"creation 12 -> {r1.status_code} ; 2e brouillon 1 -> {r2.status_code} {str(getattr(r2, 'data', ''))[:120]}")
    rec = ReceptionFournisseur.objects.get(pk=r1.data['id'])
    confirm_reception_fournisseur(rec, u)
    p.refresh_from_db()
    lr = rec.lignes.get()
    prov = ReceptionNonFacturee.objects.filter(company=co, reception=rec).first()
    montant_prov = getattr(prov, 'montant_provision', None)
    rec.refresh_from_db()
    fac = facturer_reception(co, u, rec)
    stock_apres_conf = p.quantite_stock
    print(f"confirm: stock={stock_apres_conf} quantite={lr.quantite} quantite_appliquee={lr.quantite_appliquee} provision={montant_prov} facture_ht={fac.montant_ht}")
    # annulation : facture liee -> garde ERR-ASTK54 ; on teste sur une 2e chaine sans facture
    p2 = Produit.objects.create(company=co, nom='Panneau sonde 201', sku='SONDE-201-B',
                                prix_vente=Decimal('100'), quantite_stock=5)
    bc2 = BonCommandeFournisseur.objects.create(
        company=co, fournisseur=f, reference='BCF-SONDE-201-B',
        statut=BonCommandeFournisseur.Statut.ENVOYE)
    lc2 = LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc2, produit=p2, quantite=10, prix_achat_unitaire=Decimal('60'))
    rb = api.post(url, {'bon_commande': bc2.id,
                        'lignes': [{'ligne_commande': lc2.id, 'quantite': 12}]},
                  format='json', HTTP_HOST='localhost')
    rec2 = ReceptionFournisseur.objects.get(pk=rb.data['id'])
    confirm_reception_fournisseur(rec2, u)
    annuler_reception_confirmee(ReceptionFournisseur.objects.get(pk=rec2.pk), u)
    p2.refresh_from_db()
    lc2.refresh_from_db()
    print(f"annulation: stock {p2.quantite_stock} (attendu 5) quantite_recue {lc2.quantite_recue} (attendu 0)")
    ok = (r1.status_code == 201 and r2.status_code == 409
          and stock_apres_conf == 10 and lr.quantite_appliquee == 10
          and montant_prov == Decimal('600.00')
          and fac.montant_ht == Decimal('600.00')
          and p2.quantite_stock == 5 and lc2.quantite_recue == 0)
    print(f"observé : {'aucun ecart' if ok else 'ECART'}")
    return {'repro': not ok}
