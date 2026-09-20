"""NTI18N17 — Factur-X (XML EN16931, profil BASIC) embarqué dans le PDF de
facture du pack FRANCE. **Désactivé par défaut.**

CE QUE CE MODULE EST. Une extension du moteur vendoré, pas un second moteur de
facture : il ne rend AUCUN document. Il prend des octets PDF déjà produits par
le chemin de rendu existant, y attache un fichier XML, et rend de nouveaux
octets PDF. Le rendu, les statuts et le cycle de vie de la facture restent
exactement où ils sont.

CE QU'IL NE FAIT PAS, ET IL FAUT LE SAVOIR AVANT DE VENDRE EN FRANCE :
  * il ne CALCULE rien. Tous les montants viennent de l'appelant ; ce module
    les met en forme (deux décimales) et VÉRIFIE la cohérence exigée par la
    norme (``base + taxe == total``). Un écart lève plutôt que de publier une
    facture électronique qui se contredit ;
  * il ne rend pas le PDF conforme **PDF/A-3**. Attacher un XML ne suffit pas :
    il faut un intention de sortie ICC, l'identification PDF/A dans les
    métadonnées et un flux graphique conforme. Le bon levier existe déjà en
    amont — WeasyPrint 62.3 sait écrire directement en ``pdf/a-3b``
    (``write_pdf(..., pdf_variant='pdf/a-3b')``) — mais il vit dans le chemin
    qui REND la facture (``apps/ventes/utils/pdf.generate_facture_pdf``), hors
    de ce module. Tant que ce levier n'est pas posé là-bas, ce qui sort d'ici
    est un PDF valide portant le XML, pas une facture Factur-X certifiable ;
  * il ne transmet rien, ne signe rien, n'archive rien.

L'INTERRUPTEUR. Deux conditions, toutes deux fausses par défaut :
``pack_pays == 'FR'`` ET une option explicitement cochée. Le champ
``CompanyProfile.pack_pays`` N'EXISTE PAS ENCORE (NTI18N16, GATED-founder) :
il est lu défensivement, donc ce module se comporte correctement avant comme
après son arrivée, sans modification. Sans ce champ, la porte est fermée pour
tout le monde — ce qui est exactement l'état voulu tant que le pack France
n'est pas vendu.

LE CONTRAT D'ENTRÉE est un dictionnaire PLAT (aucun modèle Django importé) que
l'appelant construit depuis sa facture ; voir :data:`CHAMPS_REQUIS` et
``construire_xml``. Aucun prix d'achat, aucune marge n'y a sa place : le
constructeur ne lit que les clés qu'il connaît, et rien d'autre ne peut
traverser.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

#: Pack pays qui ouvre la porte. Tout autre pack (dont le défaut marocain)
#: laisse le PDF rigoureusement inchangé.
PACK_PAYS_FACTURX = 'FR'

#: Profil de la norme produit : EN 16931, profil BASIC de Factur-X 1.0.
PROFIL_BASIC = (
    'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic')

#: Nom de fichier imposé par la norme pour la pièce jointe.
NOM_FICHIER_XML = 'factur-x.xml'

#: Code de type de document UNTDID 1001 — 380 = facture commerciale.
CODE_TYPE_FACTURE = '380'

#: Code d'unité UN/ECE Rec. 20 par défaut d'une ligne : l'unité « pièce ».
UNITE_PAR_DEFAUT = 'C62'

#: Clés que l'appelant DOIT fournir : ce module ne devine aucune d'entre elles.
#: (``lignes`` a sa propre garde, avec le message du profil BASIC.)
CHAMPS_REQUIS = ('numero', 'date_emission', 'devise', 'vendeur', 'acheteur',
                 'total_ht', 'total_tva', 'total_ttc')

_NS = {
    'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
    'ram': ('urn:un:unece:uncefact:data:standard:'
            'ReusableAggregateBusinessInformationEntity:100'),
    'udt': ('urn:un:unece:uncefact:data:standard:'
            'UnqualifiedDataType:100'),
}
for _prefixe, _uri in _NS.items():
    ET.register_namespace(_prefixe, _uri)


class DonneesFacturxInvalides(ValueError):
    """Les données reçues ne permettent pas d'écrire une facture honnête.

    Levée plutôt que de compléter, arrondir ou inventer : une facture
    électronique fausse est plus coûteuse qu'une facture non produite.
    """


# ── Mise en forme (jamais de calcul) ────────────────────────────────────────

def _decimal(valeur, champ):
    """``valeur`` en ``Decimal``, sans rien supposer de son écriture."""
    if valeur is None or valeur == '':
        raise DonneesFacturxInvalides(f'{champ} manquant')
    try:
        return Decimal(str(valeur).replace(' ', '').replace(' ', '')
                       .replace(' ', '').replace(',', '.'))
    except (InvalidOperation, ArithmeticError):
        raise DonneesFacturxInvalides(
            f'{champ} illisible comme nombre : {valeur!r}') from None


def _montant(valeur, champ):
    """Montant à deux décimales — la seule forme admise par la norme."""
    return str(_decimal(valeur, champ).quantize(Decimal('0.01'),
                                                rounding=ROUND_HALF_UP))


def _quantite(valeur, champ):
    """Quantité à quatre décimales, zéros de queue retirés."""
    brut = _decimal(valeur, champ).quantize(Decimal('0.0001'),
                                            rounding=ROUND_HALF_UP)
    texte = format(brut.normalize(), 'f')
    return texte if '.' not in texte else texte.rstrip('0').rstrip('.')


def _taux(valeur, champ):
    """Taux de TVA en pourcentage, deux décimales."""
    return _montant(valeur, champ)


def _date_102(valeur, champ):
    """Date au format UNTDID 2379 « 102 » : AAAAMMJJ."""
    if isinstance(valeur, datetime):
        valeur = valeur.date()
    if isinstance(valeur, date):
        return valeur.strftime('%Y%m%d')
    texte = str(valeur or '').strip()
    for motif in ('%Y-%m-%d', '%d/%m/%Y', '%Y%m%d'):
        try:
            return datetime.strptime(texte, motif).strftime('%Y%m%d')
        except ValueError:
            continue
    raise DonneesFacturxInvalides(f'{champ} n\'est pas une date : {valeur!r}')


def _texte(valeur, champ, *, obligatoire=True):
    texte = str(valeur or '').strip()
    if obligatoire and not texte:
        raise DonneesFacturxInvalides(f'{champ} manquant')
    return texte


def _sous(parent, nom, texte=None, **attributs):
    """Sous-élément ``ram:``/``udt:``/``rsm:`` — le texte est échappé par ET."""
    prefixe, local = nom.split(':', 1)
    element = ET.SubElement(parent, f'{{{_NS[prefixe]}}}{local}', attributs)
    if texte is not None:
        element.text = texte
    return element


# ── Répartition de TVA ──────────────────────────────────────────────────────

def _buckets_tva(facture):
    """Répartition de TVA à écrire, telle que l'appelant la connaît.

    Soit ``tva_par_taux`` est fourni (plusieurs taux sur la facture), soit le
    trio ``taux_tva``/``total_ht``/``total_tva`` décrit à lui seul l'unique
    tranche. Dans les deux cas, AUCUNE base ni aucun montant n'est recalculé
    ici : ce sont ceux de la facture.

    Le code de catégorie n'est jamais deviné à taux zéro : une exonération
    engage juridiquement (motif obligatoire), donc elle doit être DÉCLARÉE.
    """
    explicites = facture.get('tva_par_taux')
    if explicites:
        tranches = list(explicites)
    else:
        tranches = [{
            'taux': facture.get('taux_tva'),
            'base_ht': facture.get('total_ht'),
            'montant': facture.get('total_tva'),
        }]
    sorties = []
    for index, tranche in enumerate(tranches):
        etiquette = f'tva_par_taux[{index}]'
        taux = _decimal(tranche.get('taux'), f'{etiquette}.taux')
        categorie = _texte(tranche.get('categorie'), '', obligatoire=False)
        if not categorie:
            if taux <= 0:
                raise DonneesFacturxInvalides(
                    f'{etiquette} : taux de TVA nul sans code de catégorie '
                    f'déclaré — une exonération se déclare (catégorie + '
                    f'motif), elle ne se devine pas')
            categorie = 'S'
        sorties.append({
            'taux': _taux(taux, f'{etiquette}.taux'),
            'base_ht': _montant(tranche.get('base_ht'),
                                f'{etiquette}.base_ht'),
            'montant': _montant(tranche.get('montant'),
                                f'{etiquette}.montant'),
            'categorie': categorie,
            'motif_exoneration': _texte(tranche.get('motif_exoneration'), '',
                                        obligatoire=False),
        })
    return sorties


def _verifier_coherence(facture, buckets):
    """BR-CO-15 : total TTC == total HT + total TVA, au centime.

    Ce n'est pas un calcul de complaisance : c'est la vérification que les
    trois nombres FOURNIS racontent la même facture. S'ils divergent, le
    document part avec une contradiction que tout outil de contrôle verra.
    """
    ht = _decimal(facture['total_ht'], 'total_ht')
    tva = _decimal(facture['total_tva'], 'total_tva')
    ttc = _decimal(facture['total_ttc'], 'total_ttc')
    centime = Decimal('0.01')
    if abs((ht + tva) - ttc) > centime:
        raise DonneesFacturxInvalides(
            f'total_ttc ({ttc}) ne vaut pas total_ht ({ht}) + total_tva '
            f'({tva}) : la facture se contredirait')
    somme_tva = sum(Decimal(b['montant']) for b in buckets)
    if abs(somme_tva - tva) > centime:
        raise DonneesFacturxInvalides(
            f'la répartition de TVA totalise {somme_tva}, la facture annonce '
            f'{tva}')


# ── Construction du XML ─────────────────────────────────────────────────────

def _partie(parent, nom_element, partie, etiquette):
    """Un ``ram:*TradeParty`` : nom, pays, et n° de TVA s'il est fourni."""
    noeud = _sous(parent, nom_element)
    _sous(noeud, 'ram:Name', _texte(partie.get('nom'), f'{etiquette}.nom'))
    adresse = _sous(noeud, 'ram:PostalTradeAddress')
    code_postal = _texte(partie.get('code_postal'), '', obligatoire=False)
    if code_postal:
        _sous(adresse, 'ram:PostcodeCode', code_postal)
    ligne1 = _texte(partie.get('adresse'), '', obligatoire=False)
    if ligne1:
        _sous(adresse, 'ram:LineOne', ligne1)
    ville = _texte(partie.get('ville'), '', obligatoire=False)
    if ville:
        _sous(adresse, 'ram:CityName', ville)
    _sous(adresse, 'ram:CountryID',
          _texte(partie.get('pays'), f'{etiquette}.pays').upper())
    tva_intracom = _texte(partie.get('tva_intracom'), '', obligatoire=False)
    if tva_intracom:
        enregistrement = _sous(noeud, 'ram:SpecifiedTaxRegistration')
        _sous(enregistrement, 'ram:ID', tva_intracom, schemeID='VA')
    return noeud


def _ligne(parent, numero_ligne, ligne, etiquette):
    item = _sous(parent, 'ram:IncludedSupplyChainTradeLineItem')
    document = _sous(item, 'ram:AssociatedDocumentLineDocument')
    _sous(document, 'ram:LineID', str(numero_ligne))

    produit = _sous(item, 'ram:SpecifiedTradeProduct')
    _sous(produit, 'ram:Name',
          _texte(ligne.get('designation'), f'{etiquette}.designation'))

    accord = _sous(item, 'ram:SpecifiedLineTradeAgreement')
    prix = _sous(accord, 'ram:NetPriceProductTradePrice')
    _sous(prix, 'ram:ChargeAmount',
          _montant(ligne.get('prix_unitaire_ht'),
                   f'{etiquette}.prix_unitaire_ht'))

    livraison = _sous(item, 'ram:SpecifiedLineTradeDelivery')
    _sous(livraison, 'ram:BilledQuantity',
          _quantite(ligne.get('quantite'), f'{etiquette}.quantite'),
          unitCode=(_texte(ligne.get('unite_code'), '', obligatoire=False)
                    or UNITE_PAR_DEFAUT))

    reglement = _sous(item, 'ram:SpecifiedLineTradeSettlement')
    taxe = _sous(reglement, 'ram:ApplicableTradeTax')
    _sous(taxe, 'ram:TypeCode', 'VAT')
    _sous(taxe, 'ram:CategoryCode',
          _texte(ligne.get('categorie_tva'), '', obligatoire=False) or 'S')
    _sous(taxe, 'ram:RateApplicablePercent',
          _taux(ligne.get('taux_tva'), f'{etiquette}.taux_tva'))
    resume = _sous(reglement,
                   'ram:SpecifiedTradeSettlementLineMonetarySummation')
    _sous(resume, 'ram:LineTotalAmount',
          _montant(ligne.get('montant_ht'), f'{etiquette}.montant_ht'))


def construire_xml(facture) -> bytes:
    """XML Factur-X (CII, profil BASIC) pour ``facture``, en octets UTF-8.

    ``facture`` est le dictionnaire plat décrit en tête de module. Toute clé
    requise absente, illisible ou incohérente lève
    :class:`DonneesFacturxInvalides` — jamais une valeur de complaisance.
    """
    if not isinstance(facture, dict):
        raise DonneesFacturxInvalides('facture: dictionnaire attendu')
    manquants = [c for c in CHAMPS_REQUIS if not facture.get(c)]
    if manquants:
        raise DonneesFacturxInvalides(
            'champs requis absents : ' + ', '.join(manquants))
    lignes = list(facture.get('lignes') or ())
    if not lignes:
        raise DonneesFacturxInvalides(
            'le profil BASIC exige au moins une ligne de facture')

    buckets = _buckets_tva(facture)
    _verifier_coherence(facture, buckets)
    devise = _texte(facture['devise'], 'devise').upper()

    racine = ET.Element(f'{{{_NS["rsm"]}}}CrossIndustryInvoice')

    contexte = _sous(racine, 'rsm:ExchangedDocumentContext')
    guide = _sous(contexte,
                  'ram:GuidelineSpecifiedDocumentContextParameter')
    _sous(guide, 'ram:ID', PROFIL_BASIC)

    document = _sous(racine, 'rsm:ExchangedDocument')
    _sous(document, 'ram:ID', _texte(facture['numero'], 'numero'))
    _sous(document, 'ram:TypeCode', CODE_TYPE_FACTURE)
    emission = _sous(document, 'ram:IssueDateTime')
    _sous(emission, 'udt:DateTimeString',
          _date_102(facture['date_emission'], 'date_emission'), format='102')

    transaction = _sous(racine, 'rsm:SupplyChainTradeTransaction')
    for numero_ligne, ligne in enumerate(lignes, start=1):
        _ligne(transaction, numero_ligne, ligne, f'lignes[{numero_ligne - 1}]')

    accord = _sous(transaction, 'ram:ApplicableHeaderTradeAgreement')
    _partie(accord, 'ram:SellerTradeParty', facture['vendeur'], 'vendeur')
    _partie(accord, 'ram:BuyerTradeParty', facture['acheteur'], 'acheteur')

    _sous(transaction, 'ram:ApplicableHeaderTradeDelivery')

    reglement = _sous(transaction, 'ram:ApplicableHeaderTradeSettlement')
    _sous(reglement, 'ram:InvoiceCurrencyCode', devise)
    for bucket in buckets:
        taxe = _sous(reglement, 'ram:ApplicableTradeTax')
        _sous(taxe, 'ram:CalculatedAmount', bucket['montant'])
        _sous(taxe, 'ram:TypeCode', 'VAT')
        if bucket['motif_exoneration']:
            _sous(taxe, 'ram:ExemptionReason', bucket['motif_exoneration'])
        _sous(taxe, 'ram:BasisAmount', bucket['base_ht'])
        _sous(taxe, 'ram:CategoryCode', bucket['categorie'])
        _sous(taxe, 'ram:RateApplicablePercent', bucket['taux'])
    if facture.get('date_echeance'):
        conditions = _sous(reglement, 'ram:SpecifiedTradePaymentTerms')
        echeance = _sous(conditions, 'ram:DueDateDateTime')
        _sous(echeance, 'udt:DateTimeString',
              _date_102(facture['date_echeance'], 'date_echeance'),
              format='102')
    resume = _sous(reglement,
                   'ram:SpecifiedTradeSettlementHeaderMonetarySummation')
    total_ht = _montant(facture['total_ht'], 'total_ht')
    total_ttc = _montant(facture['total_ttc'], 'total_ttc')
    _sous(resume, 'ram:LineTotalAmount', total_ht)
    _sous(resume, 'ram:TaxBasisTotalAmount', total_ht)
    _sous(resume, 'ram:TaxTotalAmount',
          _montant(facture['total_tva'], 'total_tva'), currencyID=devise)
    _sous(resume, 'ram:GrandTotalAmount', total_ttc)
    _sous(resume, 'ram:DuePayableAmount',
          _montant(facture.get('net_a_payer') or facture['total_ttc'],
                   'net_a_payer'))

    return ET.tostring(racine, encoding='UTF-8', xml_declaration=True)


# ── Métadonnées XMP + embarquement dans le PDF ──────────────────────────────

def _xmp_facturx() -> str:
    """Bloc XMP déclarant la pièce jointe Factur-X aux outils de contrôle."""
    return (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" '
        'xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#">'
        f'<fx:DocumentFileName>{NOM_FICHIER_XML}</fx:DocumentFileName>'
        '<fx:DocumentType>INVOICE</fx:DocumentType>'
        '<fx:Version>1.0</fx:Version>'
        '<fx:ConformanceLevel>BASIC</fx:ConformanceLevel>'
        '</rdf:Description>'
        '</rdf:RDF></x:xmpmeta>'
        '<?xpacket end="w"?>')


def _declarer_fichier_associe(document, nom_fichier):
    """Déclare la pièce jointe comme FICHIER ASSOCIÉ (``/AF``) du document.

    C'est ce qui distingue, pour un outil de contrôle, une facture Factur-X
    d'un PDF qui trimballe une pièce jointe quelconque. L'API haut niveau de
    PyMuPDF ne l'expose pas : il faut écrire deux entrées de bas niveau. Toute
    la manœuvre est donc gardée, et son SUCCÈS est RAPPORTÉ plutôt que supposé
    — un PDF lisible portant le XML vaut mieux qu'une exception, et l'appelant
    (ou un test) sait ce qu'il a réellement obtenu.
    """
    try:
        xref_fichier = None
        for xref in range(1, document.xref_length()):
            if document.xref_get_key(xref, 'Type')[1] != '/Filespec':
                continue
            if nom_fichier in str(document.xref_get_key(xref, 'F')[1]):
                xref_fichier = xref
                break
        if xref_fichier is None:
            return False
        document.xref_set_key(xref_fichier, 'AFRelationship', '/Data')
        document.xref_set_key(document.pdf_catalog(), 'AF',
                              f'[ {xref_fichier} 0 R ]')
        return True
    except Exception:  # noqa: BLE001 — jamais au prix du PDF lui-même
        return False


def embarquer_xml(pdf_octets: bytes, xml_octets: bytes):
    """Attache ``xml_octets`` au PDF et rend ``(octets, rapport)``.

    ``rapport`` dit ce qui a RÉELLEMENT été posé : ``fichier_associe`` vaut
    faux quand la déclaration ``/AF`` n'a pas pu être écrite (le XML est alors
    embarqué et extractible, mais le document n'annonce pas sa nature).
    """
    if not pdf_octets or not pdf_octets[:5].startswith(b'%PDF'):
        raise DonneesFacturxInvalides(
            'pdf_octets: des octets PDF sont attendus')
    import fitz  # PyMuPDF, déjà en production — jamais une seconde plomberie

    document = fitz.open(stream=pdf_octets, filetype='pdf')
    try:
        document.embfile_add(
            NOM_FICHIER_XML, xml_octets,
            filename=NOM_FICHIER_XML, ufilename=NOM_FICHIER_XML,
            desc='Factur-X/ZUGFeRD invoice data (EN16931 BASIC)')
        fichier_associe = _declarer_fichier_associe(document, NOM_FICHIER_XML)
        document.set_xml_metadata(_xmp_facturx())
        # `deflate` seul : pas de ramasse-miettes agressif juste après avoir
        # ajouté des objets, le gain ne vaut pas le risque sur une pièce
        # jointe que le document vient tout juste de référencer.
        octets = document.tobytes(deflate=True)
    finally:
        document.close()
    return octets, {
        'embarque': True,
        'fichier_associe': fichier_associe,
        'nom_fichier': NOM_FICHIER_XML,
        'profil': PROFIL_BASIC,
        'pdf_a3': False,  # cf. l'avertissement en tête de module
    }


# ── L'interrupteur ──────────────────────────────────────────────────────────

def pack_pays_de(company) -> str:
    """Pack pays de ``company``, ou ``''`` tant que le champ n'existe pas.

    NTI18N16 (GATED-founder) posera ``CompanyProfile.pack_pays``. Lecture
    défensive : import tardif, ``getattr``, aucune exception ne remonte — cette
    fonction est correcte avant ET après l'arrivée du champ, sans modification.
    """
    if company is None:
        return ''
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company)
        return str(getattr(profil, 'pack_pays', '') or '').upper()
    except Exception:  # noqa: BLE001 — jamais bloquant pour une facture
        return ''


def facturx_actif(*, company=None, option_activee=False,
                  pack_pays=None) -> bool:
    """Faut-il embarquer le XML sur CETTE facture ? Faux par défaut.

    Les deux conditions sont nécessaires : le pack pays FRANCE **et** une
    option cochée explicitement pour ce document. Une seule des deux ne suffit
    jamais, et aucune ne s'active toute seule.
    """
    if not option_activee:
        return False
    pack = (pack_pays if pack_pays is not None
            else pack_pays_de(company))
    return str(pack or '').upper() == PACK_PAYS_FACTURX


def appliquer(pdf_octets: bytes, facture, *, company=None,
              option_activee=False, pack_pays=None):
    """Point d'entrée unique du chemin facture : rend ``(octets, rapport)``.

    Porte fermée (le cas de tout le monde aujourd'hui) : les octets d'entrée
    sont rendus TELS QUELS, et ``rapport['embarque']`` vaut faux. Aucun autre
    effet, aucun statut touché — le moteur ne fait que rendre.
    """
    if not facturx_actif(company=company, option_activee=option_activee,
                         pack_pays=pack_pays):
        return pdf_octets, {'embarque': False, 'raison': 'option inactive'}
    return embarquer_xml(pdf_octets, construire_xml(facture))
