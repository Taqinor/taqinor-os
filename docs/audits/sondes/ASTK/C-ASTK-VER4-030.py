SONDE = {"constat": "C-ASTK-VER4-030", "sha": "c38868a62",
         "modeles": ["stock.Produit", "stock.MouvementStock", "installations.StockReservation",
                     "installations.Installation", "installations.InstallationActivity",
                     "ventes.Devis", "ventes.Facture", "ventes.BonCommande"],
         "attendu": "ASTK120/135/98 : (a) facture directe puis Installé, (b) BC marquer-livre toggle OFF puis Installé : "
                    "Σ SORTIE = 10, stock 30 -> 20, réservation consommée ; (c) livraison directe chantier reçue en "
                    "DEUX réceptions 5+5 (stock libre 5) puis Installé : Σ SORTIE = 10, stock final 5"}


def sonde(ctx):
    from decimal import Decimal
    from django.db.models import Sum
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.crm import stages
    from apps.stock.models import Produit, MouvementStock, BonCommandeFournisseur, Fournisseur
    from apps.stock.services import mouvement_type_sortie
    from apps.ventes.models import Devis, LigneDevis, BonCommande
    from apps.installations.models import Installation, StockReservation
    from apps.installations.services import create_installation_from_devis, changer_statut_chantier
    from apps.ventes.domain.facturation_ops import facturer_devis_complet
    from apps.parametres.models import CompanyProfile

    def vente(tag, stock):
        co = Company.objects.create(nom=f'Sonde VER4-030 {tag}', slug=f'sonde-astk-ver4-030-{tag}')
        u = get_user_model().objects.create_user(username=f'sonde-ver4-030-{tag}', password='x', company=co,
                                                 role_legacy='responsable')
        p = Produit.objects.create(company=co, nom='Panneau sonde', sku=f'SONDE-VER4-030-{tag}',
                                   prix_vente=Decimal('100'), quantite_stock=stock, tva=Decimal('20.00'))
        cl = Client.objects.create(company=co, nom='S', prenom='C', email=f'sonde-ver4-030-{tag}@example.invalid')
        lead = Lead.objects.create(company=co, nom='S', prenom='C', stage=stages.SIGNED,
                                   type_installation='residentiel')
        d = Devis.objects.create(company=co, reference=f'DEV-SONDE-VER4-030-{tag}', client=cl, lead=lead,
                                 statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
                                 mode_installation='residentiel', created_by=u)
        LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                                  prix_unitaire=Decimal('100'), taux_tva=Decimal('20.00'))
        inst, _ = create_installation_from_devis(d, u, co)
        api = APIClient()
        api.force_authenticate(u)
        return co, u, p, cl, d, inst, api

    def sorties(p):
        return MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).aggregate(
            t=Sum('quantite'))['t'] or 0

    def installer(inst, u):
        inst.refresh_from_db()
        changer_statut_chantier(inst, Installation.Statut.INSTALLE, u, verifier_gates=False)

    out = {}
    # (a) facture directe
    co, u, p, cl, d, inst, api = vente('a', 30)
    facturer_devis_complet(devis=d, user=u, company=co, paiements=[])
    apres_vente = sorties(p)
    installer(inst, u)
    p.refresh_from_db()
    resa = StockReservation.objects.filter(installation=inst, produit=p).first()
    out['a'] = (apres_vente, sorties(p), p.quantite_stock, getattr(resa, 'consomme', None))

    # (b) BC marquer-livre toggle OFF
    co, u, p, cl, d, inst, api = vente('b', 30)
    prof = CompanyProfile.get(company=co)
    prof.reserver_stock_bc = False
    prof.save()
    bc = BonCommande.objects.create(company=co, reference='BC-SONDE-VER4-030-b', devis=d, client=cl,
                                    statut=BonCommande.Statut.CONFIRME)
    r = api.post(f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/', HTTP_HOST='localhost')
    apres_vente = sorties(p)
    installer(inst, u)
    p.refresh_from_db()
    resa = StockReservation.objects.filter(installation=inst, produit=p).first()
    out['b'] = (r.status_code, apres_vente, sorties(p), p.quantite_stock, getattr(resa, 'consomme', None))

    # (c) livraison directe chantier en deux réceptions 5 + 5, stock libre 5
    co, u, p, cl, d, inst, api = vente('c', 5)
    resa0 = StockReservation.objects.filter(installation=inst, produit=p).first()
    f = Fournisseur.objects.create(company=co, nom='Fournisseur sonde')
    bcf = BonCommandeFournisseur.objects.create(company=co, reference='BCF-SONDE-VER4-030-c', fournisseur=f,
                                                chantier_livraison=inst,
                                                statut=BonCommandeFournisseur.Statut.ENVOYE)
    lg = bcf.lignes.create(produit=p, quantite=10, prix_achat_unitaire=Decimal('60'))
    codes = []
    for q in (5, 5):
        rr = api.post(f'/api/django/stock/bons-commande-fournisseur/{bcf.id}/recevoir/',
                      {'receptions': [{'ligne': lg.id, 'quantite': q}]}, format='json', HTTP_HOST='localhost')
        codes.append(rr.status_code)
    apres_vente = sorties(p)
    resa_mid = StockReservation.objects.filter(installation=inst, produit=p).first()
    installer(inst, u)
    p.refresh_from_db()
    out['c'] = (codes, getattr(resa0, 'quantite', None), getattr(resa_mid, 'quantite', None), apres_vente,
                sorties(p), p.quantite_stock)

    print(f"(a) facture directe : sorties après vente={out['a'][0]} après Installé={out['a'][1]} "
          f"stock={out['a'][2]} resa.consomme={out['a'][3]}")
    print(f"(b) marquer-livre={out['b'][0]} sorties après vente={out['b'][1]} après Installé={out['b'][2]} "
          f"stock={out['b'][3]} resa.consomme={out['b'][4]}")
    print(f"(c) recevoir={out['c'][0]} resa initiale={out['c'][1]} resa après réceptions={out['c'][2]} "
          f"sorties après réceptions={out['c'][3]} après Installé={out['c'][4]} stock={out['c'][5]} (attendu 10 / 5)")
    ecart = (out['a'][1] != 10 or out['a'][2] != 20 or out['b'][2] != 10 or out['b'][3] != 20
             or out['c'][4] != 10 or out['c'][5] != 5)
    return {'repro': ecart, 'a': out['a'], 'b': out['b'], 'c': out['c']}
