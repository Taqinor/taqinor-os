# flake8: noqa  (sonde de contre-visite vérifie ATOT 04/11, rejouable par scripts/sonde.py — AMET93)
"""ATOT50 : `apps/facturation/tests/test_atot_machine_facturation.py::MachineFacturation._verifier_borne` borne le
facturé net par `TTC + max(0, prévu − prix convenu)` lu sur `vente_facturation.plan_facturation`. Or `prévu` =
émis net + brouillons ⊇ le facturé net du test : le plafond vaut max(TTC, prévu) ≥ facturé net — l'invariant
« Σ factures ≤ devis » ne peut plus échouer, même sur une vraie double facturation. Rejoue la FORMULE EXACTE de
l'invariant (même lecture `_net` : Σ TTC émis − avoirs non annulés, part 1) sur un devis accepté de 1 200 TTC
facturé DEUX fois en complète (état d'un bug de porte, posé par l'ORM). `repro` = invariant vert alors que
net > TTC. Aucune révision, aucun avoir à confirmer en jeu. Transaction annulée."""
SONDE = {"constat": "C-ATOT-VER4-021", "sha": "64c9c7317",
         "attendu": "net 2400.00 > TTC 1200.00 et pourtant net <= plafond (2400.00) : l'invariant passe ; repro=True",
         "modeles": ["authentication.Company", "ventes.Devis", "facturation.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, Facture, LigneDevis
    from apps.ventes.utils.options import option_totaux
    from apps.ventes.vente_facturation import plan_facturation
    Z = Decimal('0')
    co = Company.objects.create(nom='Sonde ATOT VER4-021', slug='sonde-atot-ver4-021')
    u = get_user_model().objects.create_user(username='sonde-atot-ver4-021', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='V4021', email='sonde-atot-ver4-021@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-ATOT-4021', prix_vente=Decimal('1000'), quantite_stock=10)
    d = Devis.objects.create(company=co, reference='DEV-SONDE-ATOT-4021', client=cl, statut=Devis.Statut.ACCEPTE,
                             taux_tva=Decimal('20'), mode_installation='residentiel', created_by=u)
    LigneDevis.objects.create(devis=d, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                              remise=Decimal('0'), taux_tva=Decimal('20'))
    for i in (1, 2):
        Facture.objects.create(company=co, reference=f'FAC-SONDE-ATOT-4021-{i}', devis=d, client=cl,
                               statut=Facture.Statut.EMISE, type_facture=Facture.TypeFacture.COMPLETE,
                               montant_ht=Decimal('1000.00'), montant_tva=Decimal('200.00'),
                               montant_ttc=Decimal('1200.00'), taux_tva=Decimal('20'), created_by=u)
    d = Devis.objects.get(pk=d.pk)
    # Lecture `_net` du test (part 1 : aucune consolidée).
    actives = [f for f in Facture.objects.filter(devis=d).exclude(statut='annulee')
               if f.statut in ('emise', 'payee', 'en_retard')]
    net = sum(((Decimal(str(f.total_ttc)) - sum((Decimal(str(a.total_ttc)) for a in f.avoirs.all()
                                                 if a.statut != 'annulee'), Z)) for f in actives), Z)
    # Formule de `_verifier_borne` (ATOT50), à l'identique.
    plan = plan_facturation(d)
    a_confirmer = max(Z, plan['prevu'] - plan['prix_convenu_ttc'])
    ttc = Decimal(str(option_totaux(d)['ttc']))
    plafond = ttc + a_confirmer
    tolerance = Decimal('0.01') * (len(actives) + 1)
    invariant_vert = net <= plafond + tolerance
    out = {'ttc_devis': str(ttc), 'net': str(net), 'prevu': str(plan['prevu']),
           'prix_convenu_ttc': str(plan['prix_convenu_ttc']), 'a_confirmer': str(a_confirmer),
           'plafond': str(plafond), 'invariant_vert': invariant_vert, 'nb_factures_emises': len(actives)}
    print(out)
    return {'repro': bool(invariant_vert and net > ttc), **out}
