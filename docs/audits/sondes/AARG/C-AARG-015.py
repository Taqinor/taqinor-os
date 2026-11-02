# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K15 : `views/bon_commande.py::BonCommandeViewSet.perform_create` ne contrôle que la SOCIÉTÉ du client et du devis
(ERR13) + l'unicité (AMET5 `creer_bon_commande`) : ni « devis accepté » ni « client du BC = client du devis ».
`creer_facture` recopie le panier du devis (`copier_devis_sur_facture`) sur `bc.client`, et l'émission
(`facturation_ops.emettre_facture` → `vente_facturation.motif_emission_hors_prix`) saute les devis non acceptés.
Chaîne API réelle (responsable). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-015", "sha": "56d5b623a",
         "attendu": "POST bons-commande {client X, devis BROUILLON de Y} → 201 ; confirmer → 200 ; creer-facture → 201 ; emettre → 200 : facture ÉMISE au nom de X avec les lignes du devis de Y ; attendu sain : 400 dès la création du BC",
         "modeles": ["authentication.Company", "ventes.BonCommande", "facturation.Facture", "ventes.Devis"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis, Facture
    co = Company.objects.create(nom='Sonde AARG-015', slug='sonde-aarg-015')
    u = get_user_model().objects.create_user(username='sonde-aarg-015', password='x', role_legacy='responsable', company=co)
    x = Client.objects.create(company=co, nom='Client X', email='x-aarg015@example.invalid')
    y = Client.objects.create(company=co, nom='Client Y', email='y-aarg015@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-AARG-015', prix_vente=Decimal('5000'), quantite_stock=0)
    dy = Devis.objects.create(company=co, reference='DEV-SONDE-AARG15-Y', client=y, statut=Devis.Statut.BROUILLON,
                              taux_tva=Decimal('20'))
    LigneDevis.objects.create(devis=dy, produit=p, designation='Onduleur de Y', quantite=Decimal('2'), prix_unitaire=Decimal('5000'))
    api = APIClient()
    api.force_authenticate(u)
    B = '/api/django/ventes'
    etapes = {}
    r = api.post(B + '/bons-commande/', {'client': x.pk, 'devis': dy.pk}, format='json', HTTP_HOST='localhost')
    etapes['creer_bc'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    bc_id = r.data['id']
    r = api.post(f'{B}/bons-commande/{bc_id}/confirmer/', HTTP_HOST='localhost')
    etapes['confirmer'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    r = api.post(f'{B}/bons-commande/{bc_id}/creer-facture/', HTTP_HOST='localhost')
    etapes['creer_facture'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    if r.status_code != 201:
        return {'repro': False, 'etapes': etapes}
    fid = r.data['id']
    r = api.post(f'{B}/factures/{fid}/emettre/', HTTP_HOST='localhost')
    etapes['emettre'] = (r.status_code, (r.data if r.status_code >= 400 else None))
    f = Facture.objects.get(pk=fid)
    dy.refresh_from_db()
    lignes = list(f.lignes.values_list('designation', 'quantite', 'prix_unitaire'))
    obs = {'facture_ref': f.reference, 'facture_statut': f.statut, 'facture_client': f.client.nom,
           'devis_client': dy.client.nom, 'devis_statut': dy.statut, 'total_ttc': str(f.total_ttc),
           'lignes': [(a, str(b), str(c)) for a, b, c in lignes]}
    print(f'etapes={etapes} obs={obs}')
    repro = f.statut == Facture.Statut.EMISE and f.client_id == x.pk and dy.client_id == y.pk and bool(lignes)
    return {'repro': repro, 'etapes': etapes, **obs}
