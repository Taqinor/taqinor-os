# flake8: noqa  (sonde de contre-visite vérifie ASTK 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASTK244 (« une vente = une sortie, quels que soient l'ordre ») : composition FACTURE PUIS LIVRAISON DIRECTE
CHANTIER, absente des 6 cas du test. `reserver_stock_devis_facture` sort le panier à l'émission ; la réception du
BCF `chantier_livraison` (`stock/services.py` XPUR23) entre puis ressort la quantité reçue sans lire
`quantites_deja_sorties_pour_vente`. Invariant de la tâche : stock = 30 + Σ ENTRÉE − 10.
Chaîne API réelle (responsable). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-041", "sha": "c38868a62",
         "attendu": "devis accepté 10 panneaux (stock 30) + chantier ; facture émise puis BCF livré direct chantier 10 : Σ SORTIE = 20, stock 20 (attendu sain : Σ SORTIE 10, stock 30 + 10 − 10 = 30)",
         "modeles": ["authentication.Company", "stock.MouvementStock", "stock.Produit", "stock.BonCommandeFournisseur",
                     "facturation.Facture", "installations.Installation", "installations.StockReservation"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations.services import create_installation_from_devis
    from apps.stock.models import BonCommandeFournisseur, Fournisseur, MouvementStock, Produit
    from apps.stock.services import mouvement_type_entree, mouvement_type_sortie
    from apps.ventes.domain.facturation_ops import facturer_devis_complet
    from apps.ventes.models import Devis, LigneDevis
    co = Company.objects.create(nom='Sonde ASTK VER4-041', slug='sonde-astk-ver4-041')
    u = get_user_model().objects.create_user(username='sonde-astk-ver4-041', password='x', company=co,
                                             role_legacy='responsable')
    p = Produit.objects.create(company=co, nom='Panneau VER4-041', sku='SONDE-ASTK-VER4-041',
                               prix_vente=Decimal('100'), prix_achat=Decimal('60'), quantite_stock=30,
                               tva=Decimal('20.00'))
    cl = Client.objects.create(company=co, nom='Site', prenom='Client', email='ver4-041@example.invalid')
    lead = Lead.objects.create(company=co, nom='Site', prenom='Client', stage='SIGNED',
                               type_installation='residentiel')
    d = Devis.objects.create(company=co, reference='DEV-SONDE-VER4-041', client=cl, lead=lead,
                             statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
    LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                              prix_unitaire=Decimal('100'), taux_tva=Decimal('20.00'))
    inst, _ = create_installation_from_devis(d, u, co)

    def somme(t):
        return MouvementStock.objects.filter(produit=p, type_mouvement=t).aggregate(s=Sum('quantite'))['s'] or 0

    facturer_devis_complet(devis=d, user=u, company=co, paiements=[])
    fac = d.factures.order_by('-id').first()
    apres_facture = somme(mouvement_type_sortie())
    f = Fournisseur.objects.create(company=co, nom='Fournisseur VER4-041')
    bcf = BonCommandeFournisseur.objects.create(company=co, reference='BCF-SONDE-VER4-041', fournisseur=f,
                                                chantier_livraison=inst,
                                                statut=BonCommandeFournisseur.Statut.ENVOYE)
    lg = bcf.lignes.create(produit=p, quantite=10, prix_achat_unitaire=Decimal('60'))
    api = APIClient()
    api.force_authenticate(u)
    r = api.post(f'/api/django/stock/bons-commande-fournisseur/{bcf.id}/recevoir/',
                 {'receptions': [{'ligne': lg.id, 'quantite': 10}]}, format='json', HTTP_HOST='localhost')
    p.refresh_from_db()
    sorties, entrees = somme(mouvement_type_sortie()), somme(mouvement_type_entree())
    obs = {'facture': (getattr(fac, 'reference', None), getattr(fac, 'statut', None)),
           'sorties_apres_facture': str(apres_facture), 'recevoir': r.status_code,
           'sorties': str(sorties), 'entrees': str(entrees), 'stock': str(p.quantite_stock),
           'attendu_stock': str(30 + entrees - 10),
           'mouvements': [(a, b, str(c)) for a, b, c in MouvementStock.objects.filter(produit=p)
                          .values_list('type_mouvement', 'reference', 'quantite')]}
    print(obs)
    return {'repro': r.status_code == 200 and Decimal(str(sorties)) > Decimal('10'), **obs}
