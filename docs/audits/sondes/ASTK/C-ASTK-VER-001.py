SONDE = {"constat": "C-ASTK-VER-001", "sha": "5ea32b58b",
         "attendu": "BC livré partiellement (4) puis facture directe du devis (10) puis « Installé » : Σ SORTIE = 10, stock 30 -> 20"}


def sonde(ctx):
    from decimal import Decimal
    from django.db.models import Sum
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.stock.models import Produit, MouvementStock
    from apps.stock.services import mouvement_type_sortie
    from apps.ventes.models import Devis, LigneDevis, BonCommande
    from apps.installations.models import Installation
    from apps.installations.services import create_installation_from_devis, changer_statut_chantier
    from apps.ventes.domain.facturation_ops import facturer_devis_complet
    co = Company.objects.create(nom='Sonde VER-001', slug='sonde-astk-ver-001')
    u = get_user_model().objects.create_user(username='sonde-astk-ver-001', password='x', company=co, role_legacy='responsable')
    p = Produit.objects.create(company=co, nom='Panneau sonde', sku='SONDE-VER-001', prix_vente=Decimal('100'), quantite_stock=30, tva=Decimal('20.00'))
    cl = Client.objects.create(company=co, nom='S', prenom='C', email='sonde-ver-001@example.invalid')
    lead = Lead.objects.create(company=co, nom='S', prenom='C', stage='SIGNED', type_installation='residentiel')
    d = Devis.objects.create(company=co, reference='DEV-SONDE-VER-001', client=cl, lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
    l = LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'), prix_unitaire=Decimal('100'), taux_tva=Decimal('20.00'))
    inst, _ = create_installation_from_devis(d, u, co)
    bc = BonCommande.objects.create(company=co, reference='BC-SONDE-VER-001', devis=d, client=cl, statut=BonCommande.Statut.CONFIRME)
    api = APIClient(); api.force_authenticate(u)
    r = api.post(f'/api/django/ventes/bons-commande/{bc.id}/livrer-partiel/', {'lignes': [{'ligne_devis': l.id, 'quantite': '4'}]}, format='json', HTTP_HOST='localhost')
    s1 = MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).aggregate(t=Sum('quantite'))['t']
    facturer_devis_complet(devis=d, user=u, company=co, paiements=[])
    s2 = MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).aggregate(t=Sum('quantite'))['t']
    inst.refresh_from_db()
    changer_statut_chantier(inst, Installation.Statut.INSTALLE, u, verifier_gates=False)
    tot = MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).aggregate(t=Sum('quantite'))['t']
    p.refresh_from_db()
    print(f'livrer-partiel={r.status_code} sorties après livraison={s1} après facture={s2} après Installé={tot} stock={p.quantite_stock} (attendu 10 / 20)')
    return {'repro': tot != 10 or p.quantite_stock != 20, 'sorties': tot, 'stock': p.quantite_stock}
