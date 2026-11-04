# flake8: noqa  (sonde vérifie ASTK 04/11, rejouable par scripts/sonde.py — AMET93)
"""C-ASTK-VER4-060 — vente annulée après facture d'ACOMPTE émise : le panier sorti du stock à l'émission
revient-il ? Chaîne API réelle : stock 20, devis accepté de 10 panneaux + chantier ; POST generer-facture
(1re tranche) puis POST emettre si brouillon (stock → 10) ; POST factures/<id>/annuler/ (sans paiement :
aucune directive requise ; avoir de contre-passation) ; puis PATCH leads/<id>/ stage SIGNED → QUOTE_SENT
+ confirme_recul (la dés-acceptation réelle, décision fondateur 08/10). Attendu sain : stock 20 (ENTREE de 10) ou refus
nommé. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-060", "sha": "c38868a62",
         "attendu": "stock 20 → acompte émis (stock 10) → facture annulée → lead sorti de « Signé » : stock 20 si sain ; 10 sans ENTREE = REPRO",
         "modeles": ["stock.MouvementStock", "stock.Produit", "ventes.Facture", "ventes.Avoir", "ventes.Devis",
                     "installations.Installation", "installations.StockReservation", "crm.Lead"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.installations.models import Installation, StockReservation
    from apps.installations.services import create_installation_from_devis
    from apps.stock.models import MouvementStock, Produit
    from apps.stock.services import mouvement_type_entree, mouvement_type_sortie
    from apps.ventes.models import Devis, LigneDevis
    co = Company.objects.create(nom='Sonde ASTK VER4-060', slug='sonde-astk-ver4-060')
    u = get_user_model().objects.create_user(username='sonde-astk-ver4-060', password='x', company=co,
                                             role_legacy='admin')
    p = Produit.objects.create(company=co, nom='Panneau VER4-060', sku='SONDE-ASTK-VER4-060',
                               prix_vente=Decimal('100'), quantite_stock=20, tva=Decimal('20.00'))
    cl = Client.objects.create(company=co, nom='Site', prenom='Client', email='ver4-060@example.invalid')
    lead = Lead.objects.create(company=co, nom='Site', prenom='Client', stage=stages.SIGNED,
                               type_installation='residentiel', client=cl) if hasattr(Lead, 'client') else \
        Lead.objects.create(company=co, nom='Site', prenom='Client', stage=stages.SIGNED,
                            type_installation='residentiel')
    d = Devis.objects.create(company=co, reference='DEV-SONDE-VER4-060', client=cl, lead=lead,
                             statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
    LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                              prix_unitaire=Decimal('100'), taux_tva=Decimal('20.00'))
    inst, _ = create_installation_from_devis(d, u, co)

    def tot(tm):
        return MouvementStock.objects.filter(produit=p, type_mouvement=tm).aggregate(t=Sum('quantite'))['t'] or 0

    def stock():
        p.refresh_from_db()
        return p.quantite_stock

    def resas():
        return [(r.quantite, r.consomme) for r in StockReservation.objects.filter(installation=inst)] \
            if hasattr(StockReservation, 'installation') else None

    resas_init = resas()
    api = APIClient()
    api.force_authenticate(u)
    r1 = api.post(f'/api/django/ventes/devis/{d.id}/generer-facture/', {}, format='json', HTTP_HOST='localhost')
    fac = d.factures.order_by('id').first()
    r_em = None
    if fac is not None and fac.statut == 'brouillon':
        r_em = api.post(f'/api/django/ventes/factures/{fac.id}/emettre/', {}, format='json', HTTP_HOST='localhost')
        fac.refresh_from_db()
    stock_apres_acompte = stock()
    resas_apres_acompte = resas()
    fac_avant = (fac.reference, fac.statut, str(fac.total_ttc)) if fac else None
    r_an = api.post(f'/api/django/ventes/factures/{fac.id}/annuler/', {}, format='json',
                    HTTP_HOST='localhost') if fac else None
    if fac:
        fac.refresh_from_db()
    stock_apres_annulation = stock()
    from apps.ventes.domain.cycle_vie import raison_blocage_annulation_acceptation
    blocage = raison_blocage_annulation_acceptation(d)
    r_lead = api.patch(f'/api/django/crm/leads/{lead.id}/', {'stage': stages.QUOTE_SENT, 'confirme_recul': True}, format='json',
                       HTTP_HOST='localhost')
    lead.refresh_from_db()
    d.refresh_from_db()
    inst.refresh_from_db()
    stock_final = stock()
    mvts = list(MouvementStock.objects.filter(produit=p).values_list('type_mouvement', 'reference', 'quantite'))
    obs = {'generer_facture': r1.status_code,
           'generer_detail': (r1.data if r1.status_code >= 400 else None),
           'emettre': getattr(r_em, 'status_code', None),
           'facture_avant_annulation': fac_avant,
           'stock_apres_acompte': stock_apres_acompte, 'resas_init': resas_init,
           'resas_apres_acompte': resas_apres_acompte,
           'annuler': getattr(r_an, 'status_code', None),
           'annuler_detail': (r_an.data if r_an is not None and r_an.status_code >= 400 else
                              (r_an.data or {}).get('avoir') if r_an is not None else None),
           'facture_statut_apres': getattr(fac, 'statut', None),
           'stock_apres_annulation': stock_apres_annulation,
           'blocage_desacceptation': blocage, 'patch_lead': r_lead.status_code,
           'patch_lead_detail': (r_lead.data if r_lead.status_code >= 400 else None),
           'lead_stage': lead.stage, 'devis_statut': d.statut,
           'chantier': (inst.annule, inst.motif_annulation), 'resas_final': resas(),
           'entrees': str(tot(mouvement_type_entree())), 'sorties': str(tot(mouvement_type_sortie())),
           'stock_final': stock_final, 'mouvements': [(t, r, str(q)) for t, r, q in mvts]}
    print(obs)
    return {'repro': stock_final != 20 and fac is not None and fac.statut == 'annulee', **obs}
