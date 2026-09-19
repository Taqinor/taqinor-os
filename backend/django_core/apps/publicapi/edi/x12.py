"""NTAPI35 — EDI ANSI X12 : générateur 810 (facture) et parseur 850 (commande).

La variante nord-américaine de la grande distribution, à côté d'EDIFACT
(NTAPI33/34). Deux sens, stdlib seulement :

  * ``generer_810(company, facture_id, …)`` — projette une facture client
    (lue par ``ventes.selectors.get_facture_scoped``, jamais un import de ses
    models) en un message 810 complet : enveloppe d'interchange ISA/IEA,
    groupe fonctionnel GS/GE, transaction ST/SE, en-tête BIG, lignes IT1,
    total TDS, contrôle CTT.
  * ``parser_850(contenu)`` — lit une commande client 850 (BEG + PO1) et rend
    une structure exploitable ; ``importer_850`` en crée un devis BROUILLON.

LA TRADUCTION DES CODES ARTICLES est celle de NTAPI36 (``edi_partners`` —
``traduire_lignes`` à la sortie, ``resoudre_sku`` à l'entrée) : aucune seconde
table de correspondance n'est introduite ici, et un code non mappé n'est jamais
bloquant (SKU brut + avertissement listé).

GATED — ``PUBLICAPI_EDI_ACTIF`` (absent = OFF). Sans le drapeau, les quatre
points d'entrée publics renvoient ``None`` sans rien lire ni écrire : la
fonctionnalité est INERTE, pas en erreur. Aucune transmission n'existe de toute
façon — ce module produit du texte, l'acheminement reste une étape fondateur.

CE QUI N'EST JAMAIS ÉMIS. Un 810 porte les montants CONTRACTUELS facturés au
client (prix de vente, TVA, total) — ce sont les chiffres du document que le
client reçoit déjà. Aucun ``prix_achat`` ni aucune marge n'entre dans un
message, dans les deux sens.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

from ..edi_partners import resoudre_sku, traduire_lignes

logger = logging.getLogger(__name__)

# ── Séparateurs X12 ─────────────────────────────────────────────────────────
SEP_ELEMENT = '*'
SEP_SEGMENT = '~'
SEP_COMPOSANT = '>'

# Versions de l'enveloppe et du groupe fonctionnel (004010 = le palier que
# demandent encore la majorité des VAN de la grande distribution US).
VERSION_ISA = '00401'
VERSION_GS = '004010'

# Indicateur d'usage ISA15 : 'T' (test) tant que la fonctionnalité est gated —
# jamais 'P' par défaut, un partenaire ne doit pas prendre un essai pour une
# facture réelle.
USAGE_TEST = 'T'
USAGE_PRODUCTION = 'P'

# Qualifiants d'identifiant d'interchange (ISA05/ISA07) selon le registre
# NTAPI36 : DUNS ('01') pour l'Amérique du Nord, GLN/EAN ('14') sinon.
QUALIFIANT_PAR_TYPE = {'duns': '01', 'gln': '14'}
QUALIFIANT_DEFAUT = 'ZZ'  # identifiant défini mutuellement

# Qualifiant d'identifiant produit (IT106/PO106) : 'VP' = référence vendeur,
# le code que le partenaire attend de NOUS.
QUALIFIANT_ARTICLE = 'VP'
UNITE_DEFAUT = 'EA'  # « each » — unité X12 par défaut

TYPE_810 = '810'
TYPE_850 = '850'


class X12Error(ValueError):
    """Message X12 illisible (entrée), jamais un 500 pour l'appelant."""


def edi_actif():
    """Drapeau de la famille EDI — absent = OFF (aucun message, aucun fichier)."""
    return bool(getattr(settings, 'PUBLICAPI_EDI_ACTIF', False))


# ── Fabrique de segments ────────────────────────────────────────────────────

def _segment(*elements):
    """Un segment X12 : éléments joints, terminateur final. Les éléments vides
    de QUEUE sont conservés — leur position porte du sens en X12 (un IT1 sans
    IT105 doit garder sa place vide avant IT106)."""
    return SEP_ELEMENT.join(str(e) for e in elements) + SEP_SEGMENT


def _cale(valeur, largeur):
    """ISA est le SEUL segment X12 à largeur FIXE : chaque élément est calé à
    droite par des espaces (un ISA de largeur variable est rejeté par la
    plupart des traducteurs, silencieusement)."""
    texte = str(valeur or '')[:largeur]
    return texte.ljust(largeur)


def _centimes(montant):
    """Montant X12 « implied decimal » : TDS s'exprime en centièmes SANS point
    décimal. 61 200,00 → ``6120000``."""
    try:
        valeur = Decimal(str(montant or 0))
    except (InvalidOperation, TypeError):
        valeur = Decimal('0')
    return str(int((valeur * 100).to_integral_value()))


def _montant(valeur, decimales=2):
    try:
        return f'{Decimal(str(valeur or 0)):.{decimales}f}'
    except (InvalidOperation, TypeError):
        return f'{Decimal("0"):.{decimales}f}'


def _quantite(valeur):
    """Quantité sans zéros décimaux inutiles (``10`` plutôt que ``10.00``) :
    un IT102 à ``10.00`` est valide mais illisible dans un rapprochement."""
    try:
        decimal = Decimal(str(valeur or 0)).normalize()
    except (InvalidOperation, TypeError):
        return '0'
    texte = format(decimal, 'f')
    return texte


def _qualifiant(partenaire):
    if partenaire is None:
        return QUALIFIANT_DEFAUT
    return QUALIFIANT_PAR_TYPE.get(
        (partenaire.type_identifiant or '').lower(), QUALIFIANT_DEFAUT)


def _enveloppe(*, emetteur_qualifiant, emetteur, destinataire_qualifiant,
               destinataire, maintenant, controle, usage, code_groupe,
               transactions, segments_transaction):
    """ISA/GS … GE/IEA autour d'un corps de transaction déjà construit."""
    numero = str(controle).rjust(9, '0')
    isa = SEP_ELEMENT.join([
        'ISA',
        '00', _cale('', 10),           # ISA01/02 — pas d'info d'autorisation
        '00', _cale('', 10),           # ISA03/04 — pas d'info de sécurité
        _cale(emetteur_qualifiant, 2), _cale(emetteur, 15),
        _cale(destinataire_qualifiant, 2), _cale(destinataire, 15),
        maintenant.strftime('%y%m%d'), maintenant.strftime('%H%M'),
        'U', VERSION_ISA, numero,
        '0',                           # ISA14 — aucun accusé demandé
        usage,
        SEP_COMPOSANT,
    ]) + SEP_SEGMENT
    gs = _segment(
        'GS', code_groupe, emetteur, destinataire,
        maintenant.strftime('%Y%m%d'), maintenant.strftime('%H%M'),
        str(int(controle)), 'X', VERSION_GS)
    ge = _segment('GE', str(transactions), str(int(controle)))
    iea = _segment('IEA', '1', numero)
    return isa + gs + segments_transaction + ge + iea


def _transaction(type_message, numero_controle, segments_interieurs):
    """ST … SE. SE01 compte les segments DE ST À SE INCLUS — un compte faux
    est le rejet le plus fréquent d'un 810, et il est silencieux côté VAN."""
    controle = str(numero_controle).rjust(4, '0')
    st = _segment('ST', type_message, controle)
    corps = ''.join(segments_interieurs)
    total = 2 + len(segments_interieurs)  # ST + intérieurs + SE
    se = _segment('SE', str(total), controle)
    return st + corps + se


# ── 810 — facture sortante ──────────────────────────────────────────────────

def lignes_facture_pour_edi(facture):
    """Lignes d'une facture sous la forme plate que ``edi_partners`` attend.

    ``prix_unitaire`` est le prix de VENTE facturé (la ligne du document que le
    client a déjà entre les mains) — jamais ``Produit.prix_achat``."""
    lignes = []
    for ligne in facture.lignes.select_related('produit').all():
        produit = getattr(ligne, 'produit', None)
        lignes.append({
            'sku': (getattr(produit, 'sku', '') or ''),
            'designation': ligne.designation,
            'quantite': ligne.quantite,
            'prix_unitaire': ligne.prix_unitaire,
        })
    return lignes


def construire_810(*, facture, partenaire=None, maintenant=None,
                   controle=1, usage=USAGE_TEST):
    """Message 810 complet (str) + avertissements de traduction de codes.

    Fonction PURE : elle ne lit aucun drapeau et n'écrit rien. C'est
    ``generer_810`` qui porte la porte et la lecture scopée société."""
    maintenant = maintenant or timezone.localtime(timezone.now())
    lignes, avertissements = traduire_lignes(
        partenaire, lignes_facture_pour_edi(facture))

    interieurs = [
        # BIG01 date de facture, BIG02 numéro de facture.
        _segment('BIG', facture.date_emission.strftime('%Y%m%d'),
                 facture.reference),
    ]
    nom_client = getattr(getattr(facture, 'client', None), 'nom', '') or ''
    if nom_client:
        # N1*ST — « ship to » : le tiers destinataire, sans adresse (le
        # partenaire connaît déjà ses propres sites ; on n'invente rien).
        interieurs.append(_segment('N1', 'ST', nom_client[:60]))
    for index, ligne in enumerate(lignes, 1):
        interieurs.append(_segment(
            'IT1', str(index), _quantite(ligne['quantite']), UNITE_DEFAUT,
            _montant(ligne['prix_unitaire']), '',
            QUALIFIANT_ARTICLE, ligne['code_article']))
    interieurs.append(_segment('TDS', _centimes(facture.montant_ttc)))
    interieurs.append(_segment('CTT', str(len(lignes))))

    corps = _transaction(TYPE_810, controle, interieurs)
    identifiant_partenaire = getattr(partenaire, 'identifiant', '') or ''
    message = _enveloppe(
        emetteur_qualifiant=QUALIFIANT_DEFAUT,
        emetteur=(getattr(facture.company, 'slug', '') or 'TAQINOR')[:15],
        destinataire_qualifiant=_qualifiant(partenaire),
        destinataire=identifiant_partenaire[:15],
        maintenant=maintenant, controle=controle, usage=usage,
        code_groupe='IN', transactions=1, segments_transaction=corps)
    return message, avertissements


def generer_810(company, facture_id, *, identifiant_partenaire='',
                maintenant=None, controle=1):
    """Point d'entrée GATED : ``None`` si ``PUBLICAPI_EDI_ACTIF`` est absent.

    Renvoie ``(message, avertissements)``. La facture est lue par
    ``ventes.selectors`` et scopée société : un id d'une autre société rend
    ``None`` (jamais de fuite cross-tenant)."""
    if not edi_actif():
        logger.info('NTAPI35 — 810 demandé mais PUBLICAPI_EDI_ACTIF est OFF')
        return None
    from apps.ventes.selectors import get_facture_scoped

    facture = get_facture_scoped(company, facture_id)
    if facture is None:
        return None
    partenaire = None
    if identifiant_partenaire:
        from ..edi_partners import partenaire_pour
        partenaire = partenaire_pour(company, identifiant_partenaire)
    return construire_810(facture=facture, partenaire=partenaire,
                          maintenant=maintenant, controle=controle)


# ── 850 — commande entrante ─────────────────────────────────────────────────

def segments(contenu):
    """Segments d'un interchange, éléments déjà découpés. Tolère les sauts de
    ligne décoratifs que beaucoup de partenaires insèrent après le ``~``."""
    if not contenu or not str(contenu).strip():
        raise X12Error('Message X12 vide.')
    brut = str(contenu).replace('\r', '').replace('\n', '')
    resultat = []
    for segment in brut.split(SEP_SEGMENT):
        if not segment.strip():
            continue
        resultat.append(segment.split(SEP_ELEMENT))
    if not resultat:
        raise X12Error('Aucun segment X12 exploitable.')
    return resultat


def _element(elements, index):
    return elements[index].strip() if len(elements) > index else ''


def parser_850(contenu):
    """Lit un 850 et rend ``{'numero', 'date', 'lignes', 'avertissements'}``.

    ``lignes`` : ``[{'code_partenaire', 'sku', 'quantite', 'prix_unitaire'}]``.
    Aucun montant n'est INVENTÉ : un PO1 sans prix laisse ``prix_unitaire`` à
    ``None`` plutôt que d'inscrire un zéro qui se lirait « gratuit »."""
    trouve_st = False
    numero, date = '', ''
    lignes, avertissements = [], []
    for elements in segments(contenu):
        tag = _element(elements, 0).upper()
        if tag == 'ST':
            if _element(elements, 1) != TYPE_850:
                raise X12Error(
                    f'Transaction {_element(elements, 1)!r} reçue, 850 attendue.')
            trouve_st = True
        elif tag == 'BEG':
            # BEG03 numéro de commande, BEG05 date de commande.
            numero = _element(elements, 3)
            date = _element(elements, 5)
        elif tag == 'PO1':
            code = _element(elements, 7)
            lignes.append({
                'code_partenaire': code,
                'sku': code,
                'quantite': _element(elements, 2),
                'prix_unitaire': _element(elements, 4) or None,
                'unite': _element(elements, 3) or UNITE_DEFAUT,
            })
    if not trouve_st:
        raise X12Error("Aucune transaction ST trouvée (850 attendue).")
    if not numero:
        avertissements.append(
            "Commande sans numéro (BEG03 absent) : la référence partenaire ne "
            "pourra pas être rapprochée.")
    return {'numero': numero, 'date': date, 'lignes': lignes,
            'avertissements': avertissements}


def apparier_lignes_850(company, commande, partenaire=None):
    """Traduit chaque code partenaire en SKU interne, puis cherche le produit.

    Renvoie ``(appariees, non_appariees, avertissements)``. Une ligne non
    appariée est LISTÉE, jamais devinée : c'est ce que NTAPI34/35 exigent
    (« lignes non matchées listées »)."""
    # Le MÊME queryset public que la ressource `produits/` (jamais une seconde
    # définition qui pourrait diverger) : company-scoped, archivés exclus,
    # aucun champ de coût.
    from ..public_views import PublicProduitViewSet

    appariees, non_appariees = [], []
    avertissements = list(commande.get('avertissements') or [])
    for ligne in commande.get('lignes') or []:
        sku, avertissement = resoudre_sku(partenaire, ligne['code_partenaire'])
        if avertissement:
            avertissements.append(avertissement)
        produit = (PublicProduitViewSet.queryset
                   .filter(company_id=company.id, sku=sku).first())
        enrichie = {**ligne, 'sku': sku,
                    'produit_id': getattr(produit, 'id', None)}
        if produit is None:
            non_appariees.append(enrichie)
            avertissements.append(
                f"SKU « {sku} » introuvable au catalogue : ligne non appariée.")
        else:
            appariees.append(enrichie)
    return appariees, non_appariees, avertissements


def importer_850(company, contenu, *, lead, identifiant_partenaire=''):
    """Point d'entrée GATED : ``None`` si ``PUBLICAPI_EDI_ACTIF`` est absent.

    Crée un devis BROUILLON depuis un 850 et renvoie
    ``{'devis', 'commande', 'lignes_appariees', 'lignes_non_appariees',
    'avertissements'}``.

    ``lead`` est OBLIGATOIRE : le devis part toujours d'un lead, dont le client
    est résolu côté serveur sans doublon (règle de création de ``ventes``). Un
    850 arrive d'un partenaire DÉJÀ connu — l'import n'invente jamais un client
    à partir d'un identifiant d'interchange.

    AUCUNE ``LigneDevis`` n'est créée ici : l'écrivain unique de lignes vit
    dans ``apps.ventes`` (une ligne exige un produit du catalogue et un prix
    de vente que la commande d'un client ne fixe pas). Les lignes lues sont
    RAPPORTÉES — appariées et non appariées — et résumées dans la note du
    brouillon, où un commercial les reprend. Le devis reste ``brouillon`` :
    l'API ne change jamais un statut aval.
    """
    if not edi_actif():
        logger.info('NTAPI35 — 850 reçu mais PUBLICAPI_EDI_ACTIF est OFF')
        return None
    if lead is None:
        raise X12Error(
            "Un lead est requis pour rattacher le devis brouillon issu du 850.")
    from apps.ventes.services import create_draft_devis_from_ocr

    partenaire = None
    if identifiant_partenaire:
        from ..edi_partners import partenaire_pour
        partenaire = partenaire_pour(company, identifiant_partenaire)

    commande = parser_850(contenu)
    appariees, non_appariees, avertissements = apparier_lignes_850(
        company, commande, partenaire)

    origine = (
        f"Devis brouillon créé depuis une commande EDI X12 850 "
        f"(réf. partenaire {commande['numero'] or 'inconnue'}) : "
        f"{len(appariees)} ligne(s) appariée(s), "
        f"{len(non_appariees)} non appariée(s).")
    devis = create_draft_devis_from_ocr(
        company=company, user=None, lead=lead,
        # Aucun montant n'est repris de la commande : un prix d'achat client
        # n'est pas notre prix de vente, et rien n'est inventé.
        fields={'numero': commande['numero']},
        origine=origine)
    return {
        'devis': devis,
        'commande': commande,
        'lignes_appariees': appariees,
        'lignes_non_appariees': non_appariees,
        'avertissements': avertissements,
    }
