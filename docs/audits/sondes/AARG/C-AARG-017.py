# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K17 : `views/facture_documents.py::dgi_transmettre` → `dgi/transmission.py::transmettre_facture` ne garde ni le
statut (brouillon / annulée) ni la conformité (`validate_dgi_conformity` jamais appelé) : avec l'interrupteur
`dgi_transmission_actif` + fournisseur `mock`, un BROUILLON (référence provisoire « BROUILLON-<id> ») et une facture
ANNULÉE sont « acceptés » par la DGI. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-017", "sha": "56d5b623a",
         "attendu": "POST dgi-transmettre sur une facture BROUILLON puis ANNULÉE → 200 dgi_statut acceptee ; XML <ID>BROUILLON-<id></ID> ; attendu sain : refus (400/409)",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.LigneFacture"]}


def sonde(ctx):
    import re
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    from apps.parametres.models import CompanyProfile
    from apps.ventes.dgi.dgi_export import build_ubl_xml
    from apps.ventes.dgi import validate_dgi_conformity
    co = Company.objects.create(nom='Sonde AARG-017', slug='sonde-aarg-017')
    prof = CompanyProfile.get(company=co)
    prof.dgi_transmission_actif = True
    prof.dgi_transmission_provider = 'mock'
    prof.save()
    u = get_user_model().objects.create_user(username='sonde-aarg-017', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Client K17')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-017', prix_vente=Decimal('1000'), quantite_stock=0)
    brouillon = Facture.objects.create(company=co, client=cl, statut=Facture.Statut.BROUILLON)
    LigneFacture.objects.create(facture=brouillon, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    annulee = Facture.objects.create(company=co, reference='FAC-SONDE-K17-ANN', client=cl, statut=Facture.Statut.ANNULEE)
    LigneFacture.objects.create(facture=annulee, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    brouillon.refresh_from_db()
    xml = build_ubl_xml(brouillon)
    xml_id = re.search(r'<cbc:ID>([^<]*)</cbc:ID>', xml)
    conf_brouillon = validate_dgi_conformity(brouillon)
    api = APIClient()
    api.force_authenticate(u)
    out = {}
    for nom, f in (('brouillon', brouillon), ('annulee', annulee)):
        r = api.post(f'/api/django/ventes/factures/{f.pk}/dgi-transmettre/', HTTP_HOST='localhost')
        f.refresh_from_db()
        out[nom] = {'http': r.status_code, 'corps': getattr(r, 'data', None), 'statut': f.statut,
                    'dgi_statut': f.dgi_statut, 'reference': f.reference}
    print(f'xml_id={xml_id.group(1) if xml_id else None} conformite_brouillon={conf_brouillon} out={out}')
    acceptees = [k for k, v in out.items() if v['http'] == 200 and v['dgi_statut'] == Facture.DgiStatut.ACCEPTEE]
    return {'repro': bool(acceptees), 'acceptees': acceptees, 'xml_id': xml_id.group(1) if xml_id else None,
            'conformite_brouillon': conf_brouillon, 'out': out}
