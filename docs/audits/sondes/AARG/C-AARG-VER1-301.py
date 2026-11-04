# flake8: noqa  (sonde de contre-visite VER1 lot 3 — AARG30, rejouable par scripts/sonde.py)
"""AARG30 (C-AARG-032) : un BC annulé / la facture annulée d'un BC ne bloquent plus la chaîne. Parcours API réel
(Responsable) : BC1 confirmé → annulé → `convertir-bc` ; BC2 → `creer-facture` → émise → annulée → `creer-facture` ;
les vivants bloquent toujours (409). `repro` = vrai quand l'écart EXISTE (un des attendus est faux).
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-032", "sha": "06ced8b1a",
         "attendu": "BC1 annulé → convertir-bc 201 (BC1 détaché, référence gardée, chatter) ; BC vivant → 409 ; BC2 facturé → 409 au 2e essai ; F1 annulée → creer-facture 201 (F1 détachée, référence/chatter gardés) ; facturable.ok vrai après annulation de F1",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.BonCommande", "ventes.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import BonCommande, Devis, Facture, FactureActivity, LigneDevis
    co = Company.objects.create(nom='Sonde VER1-301', slug='sonde-ver1-301')
    u = get_user_model().objects.create_user(username='sonde-ver1-301', password='x', role_legacy='responsable',
                                              company=co)
    cl = Client.objects.create(company=co, nom='Alaoui', prenom='Sara', email='v301@example.invalid',
                               telephone='+212600000301')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-VER1-301', prix_vente=Decimal('1000'),
                               quantite_stock=100)
    dv = Devis.objects.create(company=co, created_by=u, client=cl, reference='DEV-SONDE-V301',
                              statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=dv, produit=p, designation='Kit', quantite=Decimal('1'),
                              prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    H = dict(HTTP_HOST='localhost', format='json')
    obs = {}

    def post(url, corps=None):
        r = api.post(url, corps or {}, **H)
        return r.status_code, (r.data if hasattr(r, 'data') else None)

    bc1 = BonCommande.objects.create(company=co, reference='BC-SONDE-V301-1', devis=dv, client=cl,
                                     statut=BonCommande.Statut.CONFIRME)
    obs['0_bc_vivant_convertir'] = post(f'{B}/devis/{dv.id}/convertir-bc/')[0]          # attendu 409
    obs['1_annuler_bc1'] = post(f'{B}/bons-commande/{bc1.id}/annuler/')[0]               # 200
    st, d = post(f'{B}/devis/{dv.id}/convertir-bc/')
    obs['2_convertir_apres_annulation'] = st                                              # attendu 201
    bc2 = BonCommande.objects.filter(devis=dv).first()
    bc1.refresh_from_db()
    obs['2_bc1_detache'] = bc1.devis_id is None
    obs['2_bc1_reference'] = bc1.reference
    obs['2_bc2_sur_le_devis'] = bool(bc2) and bc2.pk != bc1.pk
    obs['2_chatter_devis'] = dv.activites.filter(body__contains='détaché à la recréation').exists()
    obs['2_bc_company'] = bc2.company_id == co.pk if bc2 else None
    if bc2:
        obs['3_confirmer_bc2'] = post(f'{B}/bons-commande/{bc2.id}/confirmer/')[0]
        st, f1 = post(f'{B}/bons-commande/{bc2.id}/creer-facture/')
        obs['3_creer_facture_1'] = st                                                     # 201
        obs['3_second_essai_vivante'] = post(f'{B}/bons-commande/{bc2.id}/creer-facture/')[0]  # 409
        f1id = f1.get('id') if isinstance(f1, dict) else None
        if f1id:
            obs['4_emettre_f1'] = post(f'{B}/factures/{f1id}/emettre/')[0]
            obs['4_annuler_f1'] = post(f'{B}/factures/{f1id}/annuler/')[0]
            F1 = Facture.objects.get(pk=f1id)
            obs['4_f1_statut'] = F1.statut
            ref_avant = F1.reference
            lst = api.get(f'{B}/bons-commande/', HTTP_HOST='localhost')
            ligne = next((x for x in (lst.data.get('results', lst.data) if hasattr(lst.data, 'get') else lst.data)
                          if x['id'] == bc2.id), {})
            obs['4_liste_bc_facturable'] = ligne.get('facturable')
            obs['4_liste_bc_facture_active'] = ligne.get('facture_active')
            obs['4_liste_bc_has_facture'] = ligne.get('has_facture')
            st, f2 = post(f'{B}/bons-commande/{bc2.id}/creer-facture/')
            obs['5_creer_facture_2'] = st                                                 # 201
            F1.refresh_from_db()
            obs['5_f1_detachee'] = F1.bon_commande_id is None
            obs['5_f1_reference_gardee'] = F1.reference == ref_avant
            obs['5_f1_chatter'] = FactureActivity.objects.filter(facture=F1, body__contains='à la recréation').exists()
            obs['5_f2_sur_bc2'] = Facture.objects.filter(bon_commande=bc2).count()
            obs['5_troisieme_essai_vivante'] = post(f'{B}/bons-commande/{bc2.id}/creer-facture/')[0]  # 409
    print(obs)
    ok = (obs['0_bc_vivant_convertir'] == 409 and obs['2_convertir_apres_annulation'] == 201
          and obs['2_bc1_detache'] and obs['2_bc1_reference'] == 'BC-SONDE-V301-1' and obs['2_bc2_sur_le_devis']
          and obs['2_chatter_devis'] and obs.get('3_creer_facture_1') == 201 and obs.get('3_second_essai_vivante') == 409
          and obs.get('5_creer_facture_2') == 201 and obs.get('5_f1_detachee') and obs.get('5_f1_reference_gardee')
          and obs.get('5_f1_chatter') and obs.get('5_f2_sur_bc2') == 1 and obs.get('5_troisieme_essai_vivante') == 409)
    return {'repro': not ok, **{k: v for k, v in obs.items()}}
