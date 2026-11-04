# flake8: noqa  (sonde seconde lentille vérifie ASTK 04/11, rejouable par scripts/sonde.py — AMET93)
"""Seconde lentille de C-ASTK-VER4-040, montage DIFFÉRENT : chaîne API réelle de bout en bout, facture
d'ACOMPTE (1re tranche de l'échéancier via POST generer-facture puis POST emettre si brouillon), puis F11 par
la route terrain réelle (POST interventions/<id>/valider-consommation/, qui amorce elle-même la nomenclature
par ensure_consommation). Question : la 1re tranche (acompte) sort-elle déjà tout le panier, et F11 le
ressort-elle ? Attendu sain : Σ SORTIE = 10, stock 20. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ASTK-VER4-040-L2", "sha": "c38868a62",
         "attendu": "devis accepté 10 panneaux (stock 30) + chantier ; acompte émis par l'API puis F11 validée par l'API : Σ SORTIE = 20 et stock 10 si REPRO (attendu sain 10 / 20)",
         "modeles": ["stock.MouvementStock", "stock.Produit", "ventes.Facture", "installations.Intervention",
                     "installations.MaterielConsommation"]}


def sonde(ctx):
    from apps.crm import stages
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db.models import Sum
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.installations.models import Intervention
    from apps.installations.services import create_installation_from_devis
    from apps.stock.models import MouvementStock, Produit
    from apps.stock.services import mouvement_type_sortie
    from apps.ventes.models import Devis, LigneDevis
    co = Company.objects.create(nom='Sonde ASTK VER4-040-L2', slug='sonde-astk-ver4-040-l2')
    u = get_user_model().objects.create_user(username='sonde-astk-ver4-040-l2', password='x', company=co,
                                             role_legacy='admin')
    p = Produit.objects.create(company=co, nom='Panneau VER4-040-L2', sku='SONDE-ASTK-VER4-040-L2',
                               prix_vente=Decimal('100'), quantite_stock=30, tva=Decimal('20.00'))
    cl = Client.objects.create(company=co, nom='Site', prenom='Client', email='ver4-040-l2@example.invalid')
    lead = Lead.objects.create(company=co, nom='Site', prenom='Client', stage=stages.SIGNED,
                               type_installation='residentiel')
    d = Devis.objects.create(company=co, reference='DEV-SONDE-VER4-040-L2', client=cl, lead=lead,
                             statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'), mode_installation='residentiel')
    LigneDevis.objects.create(devis=d, produit=p, designation='Panneau', quantite=Decimal('10'),
                              prix_unitaire=Decimal('100'), taux_tva=Decimal('20.00'))
    inst, _ = create_installation_from_devis(d, u, co)

    def sorties():
        return MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie()).aggregate(
            t=Sum('quantite'))['t'] or 0

    api = APIClient()
    api.force_authenticate(u)
    r1 = api.post(f'/api/django/ventes/devis/{d.id}/generer-facture/', {}, format='json', HTTP_HOST='localhost')
    fac_id = (r1.data or {}).get('id') if hasattr(r1, 'data') and isinstance(r1.data, dict) else None
    r_em = None
    fac = d.factures.order_by('id').first()
    if fac is not None and fac.statut == 'brouillon':
        r_em = api.post(f'/api/django/ventes/factures/{fac.id}/emettre/', {}, format='json', HTTP_HOST='localhost')
        fac.refresh_from_db()
    apres_acompte = sorties()
    itv = Intervention.objects.create(company=co, installation=inst)
    r_get = api.get(f'/api/django/installations/interventions/{itv.id}/consommation/', HTTP_HOST='localhost')
    r2 = api.post(f'/api/django/installations/interventions/{itv.id}/valider-consommation/', {}, format='json',
                  HTTP_HOST='localhost')
    apres_f11 = sorties()
    p.refresh_from_db()
    refs = list(MouvementStock.objects.filter(produit=p, type_mouvement=mouvement_type_sortie())
                .values_list('reference', 'quantite'))
    obs = {'generer_facture': r1.status_code, 'facture_id': fac_id,
           'facture': (getattr(fac, 'type_facture', None), getattr(fac, 'statut', None),
                       str(getattr(fac, 'montant_ttc', getattr(fac, 'total_ttc', None)))),
           'emettre': getattr(r_em, 'status_code', None),
           'emettre_detail': (r_em.data if r_em is not None and r_em.status_code >= 400 else None),
           'generer_detail': (r1.data if r1.status_code >= 400 else None),
           'sorties_apres_acompte': str(apres_acompte), 'get_consommation': r_get.status_code,
           'valider_consommation': r2.status_code,
           'valider_detail': (r2.data if r2.status_code >= 400 else None),
           'sorties_apres_f11': str(apres_f11), 'stock': str(p.quantite_stock),
           'mouvements': [(r, str(q)) for r, q in refs]}
    print(obs)
    return {'repro': Decimal(str(apres_f11)) > Decimal('10'), **obs}
