# flake8: noqa  (sonde de contre-visite vérifie ASTK 04/11, rejouable par scripts/sonde.py — AMET93)
"""ASTK244 (« une vente = une sortie, quels que soient l'ordre ») : la composition FACTURE PUIS F11 n'est pas
dans les 6 cas du test. `facturation_ops.reserver_stock_devis_facture` sort le panier à l'émission de la
facture ; `installations/field_capture.py::validate_consommation` sort ENSUITE la quantité utilisée (amorcée
depuis la nomenclature par `ensure_consommation`) sans lire `quantites_deja_sorties_pour_vente`.
Attendu sain : Σ SORTIE = 10, stock 20. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-040", "sha": "c38868a62",
         "attendu": "devis accepté 10 panneaux (stock 30) + chantier ; facturer_devis_complet (émise) puis F11 validée : Σ SORTIE = 20 et stock 10 (attendu sain 10 / 20)",
         "modeles": ["authentication.Company", "stock.MouvementStock", "stock.Produit", "facturation.Facture",
                     "installations.Installation", "installations.StockReservation"]}


def sonde(ctx):
    from apps.crm import stages
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations import field_capture
    from apps.installations.models import Intervention
    from apps.installations.services import create_installation_from_devis
    from apps.stock.models import MouvementStock, Produit
    from apps.stock.services import mouvement_type_sortie
    from apps.ventes.domain.facturation_ops import facturer_devis_complet
    from apps.ventes.models import Devis, LigneDevis
    co = Company.objects.create(nom='Sonde ASTK VER4-040', slug='sonde-astk-ver4-040')
    u = get_user_model().objects.create_user(username='sonde-astk-ver4-040', password='x', company=co,
                                             role_legacy='responsable')
    p = Produit.objects.create(company=co, nom='Panneau VER4-040', sku='SONDE-ASTK-VER4-040',
                               prix_vente=Decimal('100'), quantite_stock=30, tva=Decimal('20.00'))
    cl = Client.objects.create(company=co, nom='Site', prenom='Client', email='ver4-040@example.invalid')
    lead = Lead.objects.create(company=co, nom='Site', prenom='Client', stage=stages.SIGNED,
                               type_installation='residentiel')
    d = Devis.objects.create(company=co, reference='DEV-SONDE-VER4-040', client=cl, lead=lead,
                             statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
    LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                              prix_unitaire=Decimal('100'), taux_tva=Decimal('20.00'))
    inst, _ = create_installation_from_devis(d, u, co)

    def sorties():
        return MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).aggregate(
            t=Sum('quantite'))['t'] or 0

    facturer_devis_complet(devis=d, user=u, company=co, paiements=[])
    fac = d.factures.order_by('-id').first()
    apres_facture = sorties()
    itv = Intervention.objects.create(company=co, installation=inst)
    cons = field_capture.ensure_consommation(itv)
    lignes_f11 = [(li.produit_id == p.pk, str(li.quantite_utilisee)) for li in cons.lignes.all()]
    field_capture.validate_consommation(cons, u)
    apres_f11 = sorties()
    p.refresh_from_db()
    refs = list(MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie())
                .values_list('reference', 'quantite'))
    obs = {'facture': (getattr(fac, 'reference', None), getattr(fac, 'statut', None)),
           'sorties_apres_facture': str(apres_facture), 'lignes_f11': lignes_f11,
           'sorties_apres_f11': str(apres_f11), 'stock': str(p.quantite_stock),
           'mouvements': [(r, str(q)) for r, q in refs]}
    print(obs)
    return {'repro': Decimal(str(apres_f11)) > Decimal('10'), **obs}
