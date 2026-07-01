"""N105 — Export UBL 2.1 conforme DGI d'une facture (à la demande / par
programme).

Construit un XML de forme UBL 2.1 (Invoice) portant tout ce que la DGI exige :
identité + identifiants légaux du vendeur (ICE/IF/RC depuis CompanyProfile),
identité + ICE du client (obligatoire en B2B), numéro et dates, les lignes
avec leur TVA PAR LIGNE, et la ventilation HT → TVA par taux → TTC.

PÉRIMÈTRE STRICT — groundwork local uniquement :
  * AUCUN appel externe, AUCun endpoint Simpl-TVA, AUCUNE signature certifiée.
  * AUCUN prix d'achat / marge ne figure jamais dans le XML (le modèle ne les
    rend pas côté ligne ; on n'écrit que désignation, quantité, prix de vente
    unitaire, total HT et taux de TVA).

``build_ubl_xml`` est une fonction pure (objets → str), testable sans MinIO.
Distincte de l'« aperçu brouillon » N38 (``apps.ventes.utils.ubl``) : ici la
sortie est marquée comme export DGI local conforme, sans bandeau brouillon,
et est gardée derrière l'interrupteur maître N105.
"""
from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

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


def _resolve_profile(facture, profile):
    """Profil vendeur explicite, sinon résolu depuis la société de la facture."""
    if profile is not None:
        return profile
    from apps.parametres.models import CompanyProfile
    return CompanyProfile.get(company=facture.company)


def _client_nom(client):
    if client is None:
        return ''
    plein = ' '.join(
        p for p in [getattr(client, 'prenom', '') or '',
                    getattr(client, 'nom', '') or ''] if p).strip()
    return plein or (getattr(client, 'nom', '') or '')


def build_ubl_xml(facture, profile=None, currency=None):
    """Construit le XML UBL 2.1 conforme DGI d'une facture. Renvoie une str.

    ``profile`` (CompanyProfile vendeur) est optionnel : s'il est absent, il
    est résolu depuis la société de la facture. La portée société est garantie
    par l'appelant (commande/endpoint) ; cette fonction ne fait que rendre.

    FG52 / DC25 — ``currency`` est résolu (dans l'ordre) depuis :
      1. Le paramètre explicite ``currency`` (rétro-compat appels existants).
      2. Le champ ``facture.devise`` (défaut « MAD » sur les factures existantes).
      3. La devise par défaut de la société (``CompanyProfile.devise_defaut``).
      4. Le repli ultime « MAD ».
    """
    profile = _resolve_profile(facture, profile)
    if currency is None:
        # DC25 — plus de « MAD » codé en dur : on prend la devise du document,
        # puis celle par défaut de la société, et seulement en dernier « MAD ».
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
    el(root, 'UBLVersionID', text='2.1')
    el(root, 'CustomizationID', text='DGI-MA-UBL-2.1')
    el(root, 'ID', text=facture.reference or '')
    if facture.date_emission:
        el(root, 'IssueDate', text=facture.date_emission.isoformat())
    if getattr(facture, 'date_livraison', None):
        el(root, 'TaxPointDate', text=facture.date_livraison.isoformat())
    el(root, 'InvoiceTypeCode', text='380')
    el(root, 'DocumentCurrencyCode', text=currency)
    if getattr(facture, 'conditions_paiement', ''):
        el(root, 'Note', text=facture.conditions_paiement)

    # ── Vendeur (AccountingSupplierParty) ──
    supplier = ET.SubElement(root, f'{{{cac}}}AccountingSupplierParty')
    s_party = ET.SubElement(supplier, f'{{{cac}}}Party')
    s_name = ET.SubElement(s_party, f'{{{cac}}}PartyName')
    el(s_name, 'Name', text=getattr(profile, 'nom', '') or '')
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

    # ── Client (AccountingCustomerParty) — ICE obligatoire en B2B ──
    client = facture.client
    customer = ET.SubElement(root, f'{{{cac}}}AccountingCustomerParty')
    c_party = ET.SubElement(customer, f'{{{cac}}}Party')
    c_name = ET.SubElement(c_party, f'{{{cac}}}PartyName')
    el(c_name, 'Name', text=_client_nom(client))
    client_ice = (getattr(client, 'ice', '') or '').strip() if client else ''
    if client_ice:
        c_tax = ET.SubElement(c_party, f'{{{cac}}}PartyTaxScheme')
        el(c_tax, 'CompanyID', text=client_ice, schemeID='ICE')
        cts = ET.SubElement(c_tax, f'{{{cac}}}TaxScheme')
        el(cts, 'ID', text='ICE')

    # ── Ventilation TVA par taux (réutilise la logique exacte de la facture) ──
    total_ht = Decimal(facture.total_ht)
    total_tva = Decimal(facture.total_tva)
    total_ttc = Decimal(facture.total_ttc)
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
    monetary = ET.SubElement(root, f'{{{cac}}}LegalMonetaryTotal')
    el(monetary, 'LineExtensionAmount', text=_q2(total_ht),
       currencyID=currency)
    el(monetary, 'TaxExclusiveAmount', text=_q2(total_ht), currencyID=currency)
    el(monetary, 'TaxInclusiveAmount', text=_q2(total_ttc), currencyID=currency)
    el(monetary, 'PayableAmount', text=_q2(total_ttc), currencyID=currency)

    # ── Lignes (InvoiceLine) — TVA par ligne, jamais de prix d'achat/marge ──
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
        '<!-- Export DGI local UBL 2.1 (N105) — genere a la demande, '
        'non transmis (Simpl-TVA et signature certifiee hors perimetre). -->\n'
        + xml_body
    )
