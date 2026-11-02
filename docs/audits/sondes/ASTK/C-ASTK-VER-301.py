SONDE = {"constat": "C-ASTK-VER-301", "sha": "56d5b623a",
         "attendu": "après émission de la facture de consignation, la déclaration (document_reference, facture_reference) "
                    "et le relevé portent le numéro légal de la facture émise, jamais la référence provisoire BROUILLON-<id>",
         "modeles": ["stock.DeclarationConsommation", "ventes.Facture"]}


def sonde(ctx):
    import datetime
    from decimal import Decimal
    from rest_framework.test import APIClient
    from django.contrib.auth import get_user_model
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.stock.services_consignation import creer_depot_consignation
    from apps.ventes.models import Facture
    from apps.ventes.services import emettre_facture
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-VER-301', slug='sonde-astk-ver-301')
    u = U.objects.create_user(username='sonde-astk-ver-301', password='x', company=co, role_legacy='responsable')
    cli = Client.objects.create(company=co, nom='Consigne', prenom='Sonde', email='ver301@example.invalid')
    p = Produit.objects.create(company=co, nom='Panneau VER301', sku='SKU-VER301', prix_vente=Decimal('1500.00'),
                               prix_achat=Decimal('900.00'), tva=Decimal('20.00'), quantite_stock=10)
    depot = creer_depot_consignation(company=co, user=u, client_id=cli.id, produit_id=p.id, quantite=4,
                                     date_depot=datetime.date(2026, 10, 1), adresse_site='Site')
    api = APIClient(); api.force_authenticate(u)
    r = api.post(f'/api/django/stock/consignations/{depot.id}/declarer-consommation/',
                 {'quantite': 2, 'date_declaration': '2026-10-10'}, format='json', HTTP_HOST='localhost')
    d = r.json()
    ref_decl = d.get('document_reference')
    fac = Facture.objects.get(pk=d.get('facture_id'))
    emettre_facture(fac, user=u, source='sonde')
    fac.refresh_from_db()
    releve = api.get(f'/api/django/stock/consignations/{depot.id}/releve/', HTTP_HOST='localhost').json()
    ref_releve = releve['declarations'][0]['document_reference']
    liste = api.get('/api/django/stock/consignations/', HTTP_HOST='localhost').json()
    rows = liste.get('results', liste) if isinstance(liste, dict) else liste
    decl_liste = [x for x in rows if x['id'] == depot.id][0].get('declarations', [{}])[0]
    print(f"declarer={r.status_code} document_reference(declaration)={ref_decl!r} ; facture emise statut={fac.statut} "
          f"reference={fac.reference!r} ; releve.document_reference={ref_releve!r} ; "
          f"liste.facture_reference={decl_liste.get('facture_reference')!r} liste.facture_id={decl_liste.get('facture_id')!r}")
    return {'repro': ref_releve != fac.reference}
