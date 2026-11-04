# flake8: noqa  (sonde de contre-visite VER1 lot 3 — AARG31 + AARG32, rejouable par scripts/sonde.py)
"""AARG31 (C-AARG-033) : `convertir-bc` crée le BC dans la société du DEVIS (superutilisateur sans société, puis
Responsable de la société) ; devis sans société → 409. AARG32 (C-AARG-034) : client sous avertissement de vente
bloquant → `creer-facture` (BC) et `factures/consolider/` répondent 403 `sale_warning`, rien n'est créé ; la
dérogation d'un Responsable passe (201) et est journalisée au chatter du devis ; un Commercial reste refusé.
`repro` = vrai quand un attendu est faux. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-033/034", "sha": "06ced8b1a",
         "attendu": "BC.company = société du devis (superuser sans société et Responsable) ; devis sans société 409 ; avertissement bloquant : creer-facture BC et consolider 403 sale_warning, 0 facture ; override Responsable 201 + chatter ; Commercial 403",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.BonCommande", "ventes.Facture", "crm.Client"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import BonCommande, Devis, DevisActivity, Facture, LigneDevis
    U = get_user_model()
    a = Company.objects.create(nom='Sonde VER1-302 A', slug='sonde-ver1-302a')
    b = Company.objects.create(nom='Sonde VER1-302 B', slug='sonde-ver1-302b')
    resp = U.objects.create_user(username='sonde-v302-resp', password='x', role_legacy='responsable', company=a)
    com = U.objects.create_user(username='sonde-v302-com', password='x', role_legacy='commercial', company=a)
    root = U.objects.create_superuser(username='sonde-v302-root', password='x', email='')
    root.company = None
    root.role_legacy = 'admin'
    root.save()
    cl = Client.objects.create(company=a, nom='Tazi', prenom='Omar', email='v302@example.invalid',
                               telephone='+212600000302')
    p = Produit.objects.create(company=a, nom='Kit', sku='SONDE-VER1-302', prix_vente=Decimal('1000'),
                               quantite_stock=100)

    def devis(ref, company=a, statut=Devis.Statut.ACCEPTE, createur=resp):
        d = Devis.objects.create(company=company, created_by=createur, client=cl, reference=ref,
                                 statut=statut, taux_tva=Decimal('20'))
        LigneDevis.objects.create(devis=d, produit=p, designation='Kit', quantite=Decimal('1'),
                                  prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        return d

    def client_api(u):
        api = APIClient()
        api.force_authenticate(u)
        return api

    B = '/api/django/ventes'
    H = dict(HTTP_HOST='localhost', format='json')
    obs = {}
    # ── AARG31 ──
    d1, d2 = devis('DEV-SONDE-V302-1'), devis('DEV-SONDE-V302-2')
    r = client_api(root).post(f'{B}/devis/{d1.id}/convertir-bc/', **H)
    bc = BonCommande.objects.filter(devis=d1).first()
    obs['31_root_http'] = r.status_code
    obs['31_root_bc_company_ok'] = bool(bc) and bc.company_id == a.pk
    r = client_api(resp).post(f'{B}/devis/{d2.id}/convertir-bc/', **H)
    bc2 = BonCommande.objects.filter(devis=d2).first()
    obs['31_resp_http'] = r.status_code
    obs['31_resp_bc_company_ok'] = bool(bc2) and bc2.company_id == a.pk
    d0 = Devis.objects.create(company=None, client=cl, reference='DEV-SONDE-V302-0', statut=Devis.Statut.ACCEPTE,
                              taux_tva=Decimal('20'))
    r = client_api(root).post(f'{B}/devis/{d0.id}/convertir-bc/', **H)
    obs['31_sans_societe_http'] = (r.status_code, (r.data or {}).get('detail'))
    obs['31_sans_societe_bc'] = BonCommande.objects.filter(devis=d0).exists()
    # ── AARG32 ──
    d3, d4, d5 = devis('DEV-SONDE-V302-3'), devis('DEV-SONDE-V302-4'), devis('DEV-SONDE-V302-5')
    bc5 = BonCommande.objects.create(company=a, reference='BC-SONDE-V302-5', devis=d5, client=cl,
                                     statut=BonCommande.Statut.CONFIRME)
    Client.objects.filter(pk=cl.pk).update(avertissement_bloquant=True, avertissement_vente='Litige en cours')
    avant = Facture.objects.filter(company=a).count()
    url_bc = f'{B}/bons-commande/{bc5.id}/creer-facture/'
    url_c = f'{B}/factures/consolider/'
    r_bc = client_api(resp).post(url_bc, {}, **H)
    r_c = client_api(resp).post(url_c, {'devis_ids': [d3.id, d4.id]}, **H)
    obs['32_bc_refus'] = (r_bc.status_code, (r_bc.data or {}).get('code'))
    obs['32_consolider_refus'] = (r_c.status_code, (r_c.data or {}).get('code'))
    obs['32_factures_creees_apres_refus'] = Facture.objects.filter(company=a).count() - avant
    obs['32_commercial_bc'] = client_api(com).post(url_bc, {'override_avertissement': True}, **H).status_code
    obs['32_commercial_consolider'] = client_api(com).post(
        url_c, {'devis_ids': [d3.id, d4.id], 'override_avertissement': True}, **H).status_code
    obs['32_drapeau_faux_bc'] = client_api(resp).post(url_bc, {'override_avertissement': False}, **H).status_code
    r_bc = client_api(resp).post(url_bc, {'override_avertissement': True}, **H)
    obs['32_override_bc'] = r_bc.status_code
    r_c = client_api(resp).post(url_c, {'devis_ids': [d3.id, d4.id], 'override_avertissement': True}, **H)
    obs['32_override_consolider'] = r_c.status_code
    obs['32_chatter_d5'] = DevisActivity.objects.filter(devis=d5, field='avertissement_vente').count()
    obs['32_chatter_d3_d4'] = DevisActivity.objects.filter(devis__in=[d3, d4], field='avertissement_vente').count()
    print(obs)
    ok = (obs['31_root_http'] == 201 and obs['31_root_bc_company_ok'] and obs['31_resp_http'] == 201
          and obs['31_resp_bc_company_ok'] and obs['31_sans_societe_http'][0] == 409 and not obs['31_sans_societe_bc']
          and obs['32_bc_refus'] == (403, 'sale_warning') and obs['32_consolider_refus'] == (403, 'sale_warning')
          and obs['32_factures_creees_apres_refus'] == 0 and obs['32_commercial_bc'] == 403
          and obs['32_commercial_consolider'] == 403 and obs['32_drapeau_faux_bc'] == 403
          and obs['32_override_bc'] == 201 and obs['32_override_consolider'] == 201
          and obs['32_chatter_d5'] >= 1 and obs['32_chatter_d3_d4'] >= 2)
    return {'repro': not ok, **obs}
