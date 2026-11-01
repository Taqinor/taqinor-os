# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K16 : le constructeur UBL TRANSMIS à la DGI (`apps/ventes/dgi/dgi_export.py::build_ubl_xml`, appelé par
`dgi/transmission.py::transmettre_facture` et `views/facture_documents.py::dgi_export`) ignore la remise globale :
en-tête LineExtensionAmount = HT NET, lignes BRUTES, aucun AllowanceCharge. Le jumeau aperçu
(`apps/ventes/utils/ubl.py::build_ubl_xml`, QX2) porte le correctif. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-016", "sha": "56d5b623a",
         "attendu": "facture 1 ligne 1 000 HT, remise_globale 10 %, TVA 20 : XML DGI en-tête LineExtension 900, ligne 1000, 0 AllowanceCharge (Σ lignes ≠ en-tête) ; jumeau aperçu : 1000 / Allowance 100",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.LigneFacture"]}


def sonde(ctx):
    import xml.etree.ElementTree as ET
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    from apps.ventes.dgi.dgi_export import build_ubl_xml as ubl_dgi
    from apps.ventes.utils.ubl import build_ubl_xml as ubl_apercu
    from apps.parametres.models import CompanyProfile
    co = Company.objects.create(nom='Sonde AARG-016', slug='sonde-aarg-016')
    cl = Client.objects.create(company=co, nom='Client K16')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-016', prix_vente=Decimal('1000'), quantite_stock=0)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG16', client=cl, statut=Facture.Statut.EMISE,
                               remise_globale=Decimal('10'))
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
    f = Facture.objects.get(pk=f.pk)
    NS = {'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
          'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'}

    def lire(xml):
        xml = xml.split('-->', 1)[-1] if '<!--' in xml else xml
        xml = xml.replace('<?xml version="1.0" encoding="UTF-8"?>', '').strip()
        root = ET.fromstring(xml)
        lmt = root.find('cac:LegalMonetaryTotal', NS)
        return {
            'entete_line_ext': lmt.findtext('cbc:LineExtensionAmount', namespaces=NS),
            'tax_exclusive': lmt.findtext('cbc:TaxExclusiveAmount', namespaces=NS),
            'payable': lmt.findtext('cbc:PayableAmount', namespaces=NS),
            'lignes': [il.findtext('cbc:LineExtensionAmount', namespaces=NS) for il in root.findall('cac:InvoiceLine', NS)],
            'allowance': [a.findtext('cbc:Amount', namespaces=NS) for a in root.findall('cac:AllowanceCharge', NS)],
        }
    dgi = lire(ubl_dgi(f))
    apercu = lire(ubl_apercu(f, CompanyProfile.get(company=co)))
    print(f'total_ht={f.total_ht} total_ttc={f.total_ttc} DGI={dgi} APERCU={apercu}')
    somme_lignes = sum(Decimal(x) for x in dgi['lignes'])
    incoherent = (somme_lignes - sum((Decimal(a) for a in dgi['allowance']), Decimal('0'))) != Decimal(dgi['tax_exclusive'])
    return {'repro': incoherent and not dgi['allowance'] and Decimal(dgi['entete_line_ext']) != somme_lignes,
            'total_ht': str(f.total_ht), 'dgi': dgi, 'apercu': apercu}
