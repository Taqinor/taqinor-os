# flake8: noqa  (sonde de contre-visite AARG du 05/11, lot 3 — rejouable par scripts/sonde.py)
"""AARG18 (jumeau) : la porte unique `facturation_ops.py::creer_bon_commande` refuse désormais une V1 remplacée
(409 `version_remplacee`) à la création (convertir-bc, POST bons-commande). Le jumeau `views/bon_commande.py::
BonCommandeViewSet.perform_update` ne passe pas par cette porte : il contrôle « BC existant » sur le nouveau devis et
`_exiger_devis_du_bc` (accepté + même client), jamais `is_active`. Après révision (BC1 rattaché à V2), V1 n'a plus de BC :
un BC « en attente » sans devis re-pointé par PATCH sur V1 passe, puis sa livraison ressort le panier de V1
(`quantites_deja_sorties_pour_vente(V1)` ne voit pas BC1 parti sur V2). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-VER5-020", "sha": "2781a2049",
         "attendu": "conforme si PATCH devis=V1 remplacée → 409 ; écart si 200 puis livrer → stock 7 → 4 (6 sorties pour une vente de 3)",
         "modeles": ["authentication.Company", "ventes.BonCommande", "ventes.Devis", "stock.MouvementStock"]}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit, MouvementStock
    from apps.ventes.models import Devis, LigneDevis, BonCommande
    from apps.ventes.domain.revision import reviser_devis, rattacher_aval_financier_revision
    co = Company.objects.create(nom='Sonde AARG-VER5-020', slug='sonde-aarg-ver5-020')
    u = get_user_model().objects.create_user(username='sonde-aarg-ver5-020', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client V5-020', email='v5020-aarg@example.invalid')
    p = Produit.objects.create(company=co, nom='Panneau V5-020', sku='SONDE-AARG-V5-020', prix_vente=Decimal('1000'), quantite_stock=10)
    v1 = Devis.objects.create(company=co, reference='DEV-SONDE-AARGV5020-V1', client=cl, statut=Devis.Statut.ACCEPTE,
                              date_acceptation=date.today(), taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=v1, produit=p, designation='Panneau', quantite=Decimal('3'), prix_unitaire=Decimal('1000'))
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    et = {}

    def stock():
        return Produit.objects.get(pk=p.pk).quantite_stock

    def livrer(bc_id, cle):
        r = api.post(f'{B}/bons-commande/{bc_id}/confirmer/', HTTP_HOST='localhost')
        et[cle + '_confirmer'] = r.status_code
        r = api.post(f'{B}/bons-commande/{bc_id}/marquer-livre/', {}, format='json', HTTP_HOST='localhost')
        et[cle + '_livrer'] = (r.status_code, r.data.get('detail') if r.status_code >= 400 else None)

    r = api.post(f'{B}/devis/{v1.pk}/convertir-bc/', HTTP_HOST='localhost')
    et['bc1'] = (r.status_code, r.data.get('detail') if r.status_code >= 400 else None)
    if r.status_code != 201:
        return {'repro': False, 'etapes': et, 'note': 'préparation impossible'}
    bc1 = r.data['id']
    livrer(bc1, 'bc1')
    stock_apres_bc1 = stock()
    v2 = reviser_devis(Devis.objects.get(pk=v1.pk), user=u)
    chemin = 'accept_devis'
    try:
        from apps.ventes.domain.cycle_vie import accept_devis
        accept_devis(devis=Devis.objects.get(pk=v2.pk), user=u, nom='Client V5-020', idempotent_reaccept=False)
    except Exception as exc:
        chemin = f'repli rattacher_aval_financier_revision ({type(exc).__name__}: {str(exc)[:120]})'
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE, date_acceptation=date.today())
        rattacher_aval_financier_revision(Devis.objects.get(pk=v2.pk), user=u)
    v1.refresh_from_db()
    bc1_devis = BonCommande.objects.get(pk=bc1).devis_id
    # Témoin de la porte : convertir-bc V1 → 409 version_remplacee (AARG18).
    r = api.post(f'{B}/devis/{v1.pk}/convertir-bc/', HTTP_HOST='localhost')
    et['temoin_convertir_v1'] = (r.status_code, (r.data or {}).get('code'))
    # Jumeau : BC « en attente » sans devis, même client, re-pointé sur V1 par PATCH.
    attente = BonCommande.objects.create(company=co, reference='BC-SONDE-AARGV5020-ATT', client=cl,
                                         statut=BonCommande.Statut.EN_ATTENTE)
    r = api.patch(f'{B}/bons-commande/{attente.pk}/', {'devis': v1.pk}, format='json', HTTP_HOST='localhost')
    et['patch_devis_v1'] = (r.status_code, (r.data or {}).get('code') if r.status_code >= 400 else None,
                            str((r.data or {}).get('detail'))[:120] if r.status_code >= 400 else None)
    if r.status_code == 200:
        livrer(attente.pk, 'bc_patch')
    sorties = sum(MouvementStock.objects.filter(produit=p, type_mouvement=MouvementStock.TypeMouvement.SORTIE)
                  .values_list('quantite', flat=True))
    obs = {'chemin_acceptation_v2': chemin, 'v1_statut': v1.statut, 'v1_is_active': v1.is_active,
           'bc1_rattache_a_v2': bc1_devis == v2.pk, 'stock_initial': 10, 'stock_apres_bc1': stock_apres_bc1,
           'stock_final': stock(), 'sorties_total': sorties, 'qte_vendue': 3,
           'bc_patch_devis': BonCommande.objects.get(pk=attente.pk).devis_id}
    print(f'etapes={et} obs={obs}')
    return {'repro': et['patch_devis_v1'][0] == 200 and sorties >= 6, 'etapes': et, **obs}
