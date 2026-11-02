# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K12 : `apps/ventes/domain/encaissements.py::consolider_factures` (1) ne retire pas les brouillons de la vente
(aucun appel à `annulation_facture.retirer_brouillons_de_la_vente`, contrairement à `facturation_vente._facturer_complete`
et `bon_commande.creer_facture`) : le brouillon d'acompte automatique VNT62 de A reste vivant après la consolidée ;
(2) ne prend aucun verrou (`facturation_vente.verrouiller_vente` absent ; garde `exiger_devis_facturable` lue AVANT
l'atomic, `emettre_facture` sans select_for_update) — la course est un fait de code, non rejouable en 1 transaction.
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-012", "sha": "56d5b623a",
         "attendu": "devis A et B acceptés, brouillon d'acompte auto sur A ; consolider [A,B] → consolidée émise ; le brouillon d'acompte de A reste BROUILLON (non annulé) ; consolider_factures sans verrouiller_vente / select_for_update",
         "modeles": ["authentication.Company", "facturation.Facture", "ventes.Devis"]}


def sonde(ctx):
    import inspect
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, Facture
    from apps.ventes.domain import encaissements
    from apps.ventes.domain.encaissements import consolider_factures
    from apps.ventes.domain.facturation_vente import acompte_a_l_acceptation
    from apps.ventes.domain.facturation_ops import emettre_facture
    co = Company.objects.create(nom='Sonde AARG-012', slug='sonde-aarg-012')
    u = get_user_model().objects.create_user(username='sonde-aarg-012', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client K12', email='k12-aarg@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit K12', sku='SONDE-AARG-012', prix_vente=Decimal('1000'), quantite_stock=100)
    devis = []
    for suffixe in ('A', 'B'):
        d = Devis.objects.create(company=co, reference=f'DEV-SONDE-AARG12-{suffixe}', client=cl, statut=Devis.Statut.ACCEPTE,
                                 date_acceptation=date.today(), taux_tva=Decimal('20'))
        LigneDevis.objects.create(devis=d, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('10000'))
        devis.append(d)
    a, b = devis
    brouillon = acompte_a_l_acceptation(Devis.objects.get(pk=a.pk), u)
    if brouillon is None:  # échéancier société sans acompte : brouillon d'acompte posé comme VNT62 le ferait
        brouillon = Facture.objects.create(company=co, client=cl, devis=a, statut=Facture.Statut.BROUILLON,
                                           type_facture='acompte', libelle='Acompte 30 %')
        origine = 'repli (aucune tranche acompte dans l\'échéancier par défaut)'
    else:
        origine = 'acompte_a_l_acceptation (VNT62)'
    conso = consolider_factures(company=co, devis_ids=[a.pk, b.pk], user=u, created_by=u)
    conso.refresh_from_db()
    brouillon.refresh_from_db()
    apres_conso = (brouillon.reference, brouillon.statut, str(brouillon.total_ttc))
    emission_brouillon = None
    from django.db import transaction
    try:
        with transaction.atomic():
            emettre_facture(brouillon, user=u, source='sonde')
        emission_brouillon = 'émis'
    except Exception as exc:
        emission_brouillon = f'refusé : {type(exc).__name__}: {str(exc)[:160]}'
    brouillon.refresh_from_db()
    src = inspect.getsource(encaissements.consolider_factures)
    code = {'verrouiller_vente': 'verrouiller_vente' in src, 'select_for_update': 'select_for_update' in src,
            'retirer_brouillons': 'retirer_brouillons' in src}
    obs = {'origine_brouillon': origine, 'consolidee': (conso.reference, conso.statut, str(conso.total_ttc)),
           'brouillon_A_apres_consolidation': apres_conso, 'brouillon_A_final': brouillon.statut,
           'emission_ulterieure_du_brouillon': emission_brouillon, 'code_consolider': code}
    print(obs)
    reste_vivant = apres_conso[1] == Facture.Statut.BROUILLON
    return {'repro': conso.statut == Facture.Statut.EMISE and reste_vivant and not any(code.values()), **obs}
