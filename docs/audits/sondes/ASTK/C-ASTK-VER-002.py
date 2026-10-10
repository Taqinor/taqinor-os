SONDE = {"constat": "C-ASTK-VER-002", "sha": "5ea32b58b",
         "attendu": "BCF 10 x 100, réception 12 (10 appliqués) : une facture fournisseur de 1 200 HT passe le rapprochement 3 voies en 'exception' (attendu 1 000)"}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur, FactureFournisseur
    from apps.stock.services import confirm_reception_fournisseur, evaluer_rapprochement_3_voies
    co = Company.objects.create(slug='sonde-astk-ver-002', nom='Sonde VER-002')
    u = get_user_model().objects.create_user(username='sonde_astk_ver_002', password='x', company=co, role_legacy='responsable')
    f = Fournisseur.objects.create(company=co, nom='F sonde')
    p = Produit.objects.create(company=co, nom='Panneau sonde', sku='SONDE-VER-002', prix_vente=Decimal('200'), prix_achat=Decimal('100'), quantite_stock=0)
    bc = BonCommandeFournisseur.objects.create(company=co, reference='BCF-SONDE-VER-002', fournisseur=f, statut=BonCommandeFournisseur.Statut.ENVOYE)
    l = bc.lignes.create(produit=p, quantite=10, prix_achat_unitaire=Decimal('100'))
    rec = ReceptionFournisseur.objects.create(company=co, reference='REC-SONDE-VER-002', bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON, created_by=u)
    rec.lignes.create(ligne_commande=l, produit=p, quantite=12)
    confirm_reception_fournisseur(rec, u)
    lr = rec.lignes.get(); p.refresh_from_db()
    ff = FactureFournisseur.objects.create(company=co, reference='FF-SONDE-VER-002', fournisseur=f, bon_commande=bc,
                                           montant_ht=Decimal('1200'), montant_tva=Decimal('0'), montant_ttc=Decimal('1200'))
    st = evaluer_rapprochement_3_voies(ff)
    ff.refresh_from_db()
    statut = getattr(ff, 'statut_controle', st)
    print(f"stock={p.quantite_stock} quantite_appliquee={lr.quantite_appliquee} retour={st!r} statut_controle={statut!r} (facture 1200 HT, 10 x 100 entrés ; attendu exception)")
    return {'repro': 'exception' not in str(statut).lower()}
