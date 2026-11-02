# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K14 : une V1 REMPLACÉE (révision) reste `statut=accepte` (règle #4 : `revision.py::reviser_devis` ne touche que
is_active/superseded_by) ; à l'acceptation de V2, `revision.py::rattacher_aval_financier_revision` déplace BC1 sur V2.
`views/devis_facturation.py::convertir_en_bc` ne contrôle que `statut == accepte` et `facturation_ops.creer_bon_commande`
que « un BC par devis » : V1 (sans BC désormais) donne BC2. À la livraison, `bon_commande.py::_sortir_reliquat_bc` →
`facturation_ops.quantites_deja_sorties_pour_vente(V1)` ne lit que les références de V1 et de SES BC (BC1 parti sur V2) :
le panier est sorti une deuxième fois. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-014", "sha": "56d5b623a",
         "attendu": "V1 acceptée qté 3 → BC1 livré (stock 10→7) ; révision V2 acceptée (BC1 rattaché à V2) ; convertir-bc V1 → 201 BC2 ; livrer BC2 → stock 4 : Σ sorties 6 pour une vente de 3",
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
    co = Company.objects.create(nom='Sonde AARG-014', slug='sonde-aarg-014')
    u = get_user_model().objects.create_user(username='sonde-aarg-014', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client K14', email='k14-aarg@example.invalid')
    p = Produit.objects.create(company=co, nom='Panneau K14', sku='SONDE-AARG-014', prix_vente=Decimal('1000'), quantite_stock=10)
    v1 = Devis.objects.create(company=co, reference='DEV-SONDE-AARG14-V1', client=cl, statut=Devis.Statut.ACCEPTE,
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
        return {'repro': False, 'etapes': et}
    bc1 = r.data['id']
    livrer(bc1, 'bc1')
    stock_apres_bc1 = stock()
    v2 = reviser_devis(Devis.objects.get(pk=v1.pk), user=u)
    # Acceptation de V2 : on prend LE chemin unique ; repli sur le rattachement seul s'il refuse (noté).
    chemin = 'accept_devis'
    try:
        from apps.ventes.domain.cycle_vie import accept_devis
        accept_devis(devis=Devis.objects.get(pk=v2.pk), user=u, nom='Client K14', idempotent_reaccept=False)
    except Exception as exc:
        chemin = f'repli rattacher_aval_financier_revision ({type(exc).__name__}: {str(exc)[:120]})'
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE, date_acceptation=date.today())
        rattacher_aval_financier_revision(Devis.objects.get(pk=v2.pk), user=u)
    v1.refresh_from_db()
    bc1_devis = BonCommande.objects.get(pk=bc1).devis_id
    r = api.post(f'{B}/devis/{v1.pk}/convertir-bc/', HTTP_HOST='localhost')
    et['bc2'] = (r.status_code, r.data.get('detail') if r.status_code >= 400 else None)
    if r.status_code == 201:
        livrer(r.data['id'], 'bc2')
    sorties = sum(MouvementStock.objects.filter(produit=p, type_mouvement=MouvementStock.TypeMouvement.SORTIE)
                  .values_list('quantite', flat=True))
    obs = {'chemin_acceptation_v2': chemin, 'v1_statut': v1.statut, 'v1_is_active': v1.is_active,
           'bc1_rattache_a_v2': bc1_devis == v2.pk, 'stock_initial': 10, 'stock_apres_bc1': stock_apres_bc1,
           'stock_final': stock(), 'sorties_total': sorties, 'qte_vendue': 3}
    print(f'etapes={et} obs={obs}')
    return {'repro': et.get('bc2', (0,))[0] == 201 and sorties >= 6, 'etapes': et, **obs}
