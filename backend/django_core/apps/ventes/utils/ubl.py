"""N38 — Export structuré local d'une facture au format UBL 2.1 (APERÇU
BROUILLON, travail préparatoire).

Génère un XML de forme UBL 2.1 (Invoice) à partir d'une facture : identité +
identifiants légaux du vendeur (ICE/IF/RC) depuis CompanyProfile, identité +
ICE du client, numéro et dates, le détail TVA par ligne et la ventilation
HT → TVA par taux → TTC.

PÉRIMÈTRE STRICT — groundwork uniquement :
  * AUCUN appel externe, AUCun endpoint DGI, AUCUN identifiant/clé.
  * Le document est explicitement marqué « APERÇU BROUILLON — non transmis ».
  * Le XML est aussi déposé localement (MinIO) en best-effort ; l'échec de
    stockage n'empêche jamais la génération/le téléchargement.

Le constructeur (`build_ubl_xml`) est une fonction pure (str → str) testable
sans Django ni MinIO.
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# Espaces de noms officiels UBL 2.1.
NS = {
    '': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:'
           'CommonAggregateComponents-2',
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:'
           'CommonBasicComponents-2',
}


def _q2(value):
    """Quantize au centime, renvoie une chaîne « 1234.56 »."""
    return str(Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def build_ubl_xml(facture, profile, currency=None):
    """Construit le XML UBL 2.1 d'une facture. Renvoie une chaîne (str).

    FG52 / DC25 — ``currency`` est résolu (dans l'ordre) depuis :
      1. Le paramètre explicite ``currency`` (rétro-compat).
      2. Le champ ``facture.devise`` (défaut « MAD » sur les factures existantes).
      3. La devise par défaut de la société (``CompanyProfile.devise_defaut``).
      4. Le repli ultime « MAD ».
    """
    if currency is None:
        # DC25 — plus de « MAD » codé en dur : devise du document, puis devise
        # par défaut de la société (profile), et seulement en dernier « MAD ».
        currency = (getattr(facture, 'devise', None)
                    or getattr(profile, 'devise_defaut', None)
                    or 'MAD')
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)
    inv_ns = NS['']
    cac = NS['cac']
    cbc = NS['cbc']

    def el(parent, tag, ns=cbc, text=None, **attrs):
        node = ET.SubElement(parent, f'{{{ns}}}{tag}', attrs)
        if text is not None:
            node.text = str(text)
        return node

    root = ET.Element(f'{{{inv_ns}}}Invoice')
    # Marqueur APERÇU BROUILLON, sans ambiguïté (cf. périmètre N38).
    el(root, 'UBLVersionID', text='2.1')
    el(root, 'ProfileID', text='APERCU-BROUILLON-NON-TRANSMIS')
    el(root, 'ID', text=facture.reference or '')
    if facture.date_emission:
        el(root, 'IssueDate', text=facture.date_emission.isoformat())
    if facture.date_livraison:
        el(root, 'TaxPointDate', text=facture.date_livraison.isoformat())
    el(root, 'InvoiceTypeCode', text='380')
    el(root, 'DocumentCurrencyCode', text=currency)
    if facture.conditions_paiement:
        el(root, 'Note', text=facture.conditions_paiement)

    # ── Vendeur (AccountingSupplierParty) ──
    supplier = ET.SubElement(root, f'{{{cac}}}AccountingSupplierParty')
    s_party = ET.SubElement(supplier, f'{{{cac}}}Party')
    s_name = ET.SubElement(s_party, f'{{{cac}}}PartyName')
    el(s_name, 'Name', text=getattr(profile, 'nom', '') or '')
    # ICE / IF / RC du vendeur (identifiants légaux marocains).
    for scheme, value in (
        ('ICE', getattr(profile, 'ice', '')),
        ('IF', getattr(profile, 'identifiant_fiscal', '')),
        ('RC', getattr(profile, 'rc', '')),
    ):
        if (value or '').strip():
            s_tax = ET.SubElement(s_party, f'{{{cac}}}PartyTaxScheme')
            el(s_tax, 'CompanyID', text=value, schemeID=scheme)
            ts = ET.SubElement(s_tax, f'{{{cac}}}TaxScheme')
            el(ts, 'ID', text=scheme)
    if getattr(profile, 'adresse', ''):
        s_addr = ET.SubElement(s_party, f'{{{cac}}}PostalAddress')
        el(s_addr, 'StreetName', text=profile.adresse)

    # ── Client (AccountingCustomerParty) ──
    client = facture.client
    customer = ET.SubElement(root, f'{{{cac}}}AccountingCustomerParty')
    c_party = ET.SubElement(customer, f'{{{cac}}}Party')
    c_name = ET.SubElement(c_party, f'{{{cac}}}PartyName')
    nom_client = ''
    if client is not None:
        nom_client = ' '.join(
            p for p in [getattr(client, 'prenom', ''),
                        getattr(client, 'nom', '')] if p).strip() \
            or (getattr(client, 'nom', '') or '')
    el(c_name, 'Name', text=nom_client)
    client_ice = (getattr(client, 'ice', '') or '').strip() if client else ''
    if client_ice:
        c_tax = ET.SubElement(c_party, f'{{{cac}}}PartyTaxScheme')
        el(c_tax, 'CompanyID', text=client_ice, schemeID='ICE')
        cts = ET.SubElement(c_tax, f'{{{cac}}}TaxScheme')
        el(cts, 'ID', text='ICE')

    # ── Ventilation TVA par taux (réutilise la logique exacte de la facture) ──
    # QX2 — ``facture.total_*`` sont désormais NETS de la remise globale (QX1) :
    # header LegalMonetaryTotal, TVA et PayableAmount reflètent le montant remisé.
    total_ht = Decimal(facture.total_ht)         # HT NET (après remise globale)
    total_tva = Decimal(facture.total_tva)
    total_ttc = Decimal(facture.total_ttc)

    # QX2 — remise globale documentée en AllowanceCharge (cohérence UBL : la
    # somme des lignes est BRUTE, l'AllowanceCharge la ramène au HT net du
    # header). Aucune remise → aucun AllowanceCharge (document inchangé).
    from decimal import Decimal as _D
    lignes_brut = sum(
        (_D(str(li.total_ht)) for li in facture.lignes.all()), _D('0'))
    remise_montant = (lignes_brut - total_ht).quantize(
        _D('0.01'), rounding=ROUND_HALF_UP)
    if remise_montant > 0:
        allowance = ET.SubElement(root, f'{{{cac}}}AllowanceCharge')
        el(allowance, 'ChargeIndicator', text='false')  # false = remise
        el(allowance, 'AllowanceChargeReason', text='Remise globale')
        el(allowance, 'Amount', text=_q2(remise_montant), currencyID=currency)

    tax_total = ET.SubElement(root, f'{{{cac}}}TaxTotal')
    el(tax_total, 'TaxAmount', text=_q2(total_tva), currencyID=currency)
    for bucket in facture.tva_par_taux:
        sub = ET.SubElement(tax_total, f'{{{cac}}}TaxSubtotal')
        el(sub, 'TaxableAmount', text=_q2(bucket['base_ht']),
           currencyID=currency)
        el(sub, 'TaxAmount', text=_q2(bucket['montant']), currencyID=currency)
        cat = ET.SubElement(sub, f'{{{cac}}}TaxCategory')
        el(cat, 'Percent', text=_q2(bucket['taux']))
        scheme = ET.SubElement(cat, f'{{{cac}}}TaxScheme')
        el(scheme, 'ID', text='TVA')

    # ── Totaux (LegalMonetaryTotal) ──
    # QX2 — LineExtensionAmount = somme BRUTE des lignes ; AllowanceTotalAmount =
    # remise globale ; TaxExclusive/Inclusive/Payable = montants NETS remisés.
    # Cohérence UBL : LineExtension − Allowance = TaxExclusive.
    monetary = ET.SubElement(root, f'{{{cac}}}LegalMonetaryTotal')
    el(monetary, 'LineExtensionAmount', text=_q2(lignes_brut),
       currencyID=currency)
    el(monetary, 'TaxExclusiveAmount', text=_q2(total_ht), currencyID=currency)
    el(monetary, 'TaxInclusiveAmount', text=_q2(total_ttc), currencyID=currency)
    if remise_montant > 0:
        el(monetary, 'AllowanceTotalAmount', text=_q2(remise_montant),
           currencyID=currency)
    el(monetary, 'PayableAmount', text=_q2(total_ttc), currencyID=currency)

    # ── Lignes (InvoiceLine) ──
    for idx, ligne in enumerate(facture.lignes.all(), start=1):
        il = ET.SubElement(root, f'{{{cac}}}InvoiceLine')
        el(il, 'ID', text=str(idx))
        el(il, 'InvoicedQuantity', text=str(ligne.quantite))
        el(il, 'LineExtensionAmount', text=_q2(ligne.total_ht),
           currencyID=currency)
        item = ET.SubElement(il, f'{{{cac}}}Item')
        el(item, 'Name', text=ligne.designation or '')
        l_tax = ET.SubElement(item, f'{{{cac}}}ClassifiedTaxCategory')
        el(l_tax, 'Percent', text=_q2(ligne.taux_tva_effectif))
        l_scheme = ET.SubElement(l_tax, f'{{{cac}}}TaxScheme')
        el(l_scheme, 'ID', text='TVA')
        price = ET.SubElement(il, f'{{{cac}}}Price')
        el(price, 'PriceAmount', text=_q2(ligne.prix_unitaire),
           currencyID=currency)

    xml_body = ET.tostring(root, encoding='unicode')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!-- APERCU BROUILLON UBL 2.1 — non transmis a la DGI, '
        'travail preparatoire (N38). -->\n'
        + xml_body
    )


def store_ubl_xml(facture, xml_str):
    """Dépose le XML dans MinIO (best-effort) et renvoie la clé, ou None."""
    try:
        from django.conf import settings
        from .minio_client import get_minio_client
        key = f'ubl/{facture.company_id or 0}/{facture.reference}.xml'
        client = get_minio_client()
        client.put_object(
            Bucket=settings.MINIO_BUCKET_PDF,
            Key=key,
            Body=xml_str.encode('utf-8'),
            ContentType='application/xml',
        )
        return key
    except Exception as exc:  # pragma: no cover - stockage best-effort
        logger.warning('Stockage UBL échoué pour %s: %s',
                       facture.reference, exc)
        return None
