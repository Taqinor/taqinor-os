"""N43 → CIQ613 — régime loi 82-21 suggéré pour un chantier.

CIQ613 : ce module ne porte PLUS de seuil propre. Il DÉLÈGUE au noyau sourcé
``core.reglementaire.regime_8221`` (CIQ612 : déclaration < 11 kW en BT,
accord de raccordement de 11 kW à < 5 MW, autorisation ≥ 5 MW — décret
2.25.100 art. 5, 11, 18 ; loi 82-21 art. 2-6), avec les SURCHARGES société
nullables de Paramètres (CIQ614 : ``seuil_regime_*`` vide = seuil sourcé).

Les trois appelants (création du chantier, ``regime_suggere`` du
sérialiseur, action ``regime-suggestion``) transmettent la puissance DC
(kWc), la puissance AC des onduleurs (kW, nomenclature gelée), le niveau de
tension (CIQ610) et le drapeau hors réseau (AGR602).

Un chantier ``industriel`` (C&I) dont la puissance est inconnue reçoit
``a_qualifier`` (jamais ``non_concerne`` par défaut) ; le gate dossier le
traite comme non approuvé. Résidentiel : suggestion inchangée (hors seuil
d'autorisation), puissance inconnue → ``non_concerne``.
"""
from decimal import Decimal, InvalidOperation

from core.reglementaire import regime_8221 as noyau

CODE_A_QUALIFIER = 'a_qualifier'
CODE_NON_CONCERNE = 'non_concerne'
TYPE_INDUSTRIEL = 'industriel'


def _decimal(valeur):
    if valeur is None or valeur == '':
        return None
    try:
        return Decimal(str(valeur))
    except (InvalidOperation, TypeError, ValueError):
        return None


def suggest_regime_8221(kwc, seuil_declaration=None, seuil_anre=None,
                        hors_reseau=False, kw_ac=None, niveau=None,
                        type_installation=None):
    """Code régime suggéré (valeur de ``Installation.Regime8221``).

    Fonction pure : délègue au noyau sourcé. ``seuil_declaration`` /
    ``seuil_anre`` = surcharges société (None = seuil des textes).
    Puissance inconnue (ou cas non couvert par les textes lus) →
    ``a_qualifier`` pour un chantier ``industriel``, ``non_concerne`` sinon
    (comportement historique du résidentiel)."""
    surcharges = {}
    if seuil_declaration is not None:
        surcharges['seuil_declaration_kw'] = seuil_declaration
    if seuil_anre is not None:
        surcharges['seuil_autorisation_kw'] = seuil_anre
    niv = (niveau or '').strip().upper() or None
    forme = noyau.regime_8221(
        kwc, kw_ac, niveau=niv, hors_reseau=hors_reseau,
        surcharges=surcharges)
    if forme['code']:
        return forme['code']
    if type_installation == TYPE_INDUSTRIEL:
        return CODE_A_QUALIFIER
    return CODE_NON_CONCERNE


def regime_surcharges(company):
    """(seuil_declaration, seuil_autorisation) SURCHARGÉS par la société
    (CIQ614), None quand vides — jamais un défaut local."""
    if company is None:
        return None, None
    try:
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company=company)
    except Exception:
        return None, None
    return (prof.seuil_regime_declaration_kwc, prof.seuil_regime_anre_kwc)


def regime_thresholds(company):
    """(seuil_declaration, seuil_autorisation) EFFECTIFS : surcharge société
    sinon seuils sourcés du noyau (décret 2.25.100 art. 5, 18)."""
    seuil_decl, seuil_auto = regime_surcharges(company)
    if seuil_decl is None:
        seuil_decl = Decimal(noyau.SEUIL_DECLARATION_KW)
    if seuil_auto is None:
        seuil_auto = Decimal(noyau.SEUIL_AUTORISATION_KW)
    return seuil_decl, seuil_auto


def suggest_for_company(kwc, company, hors_reseau=False, kw_ac=None,
                        niveau=None, type_installation=None):
    """Suggestion en appliquant les surcharges société (CIQ614)."""
    seuil_decl, seuil_auto = regime_surcharges(company)
    return suggest_regime_8221(
        kwc, seuil_decl, seuil_auto, hors_reseau=hors_reseau, kw_ac=kw_ac,
        niveau=niveau, type_installation=type_installation)


def kw_ac_onduleurs(bom, company):
    """kW AC TOTAL des onduleurs de la nomenclature gelée (``bom``), lus sur
    leur fiche technique (``ac_kw``) via les sélecteurs stock (frontière
    M3). None si aucun onduleur à puissance AC connue (jamais deviné)."""
    if not bom or company is None:
        return None
    from apps.stock.selectors import get_produit_scoped
    from apps.stock.selectors_fiche_technique import specs_for_produit
    total = None
    for ligne in bom:
        if not isinstance(ligne, dict) or not ligne.get('produit_id'):
            continue
        try:
            produit = get_produit_scoped(company, ligne['produit_id'])
        except Exception:
            continue
        ac_kw = _decimal((specs_for_produit(produit) or {}).get('ac_kw'))
        quantite = _decimal(ligne.get('quantite'))
        if ac_kw is None or ac_kw <= 0 or quantite is None or quantite <= 0:
            continue
        total = (total or Decimal('0')) + ac_kw * quantite
    return total


def suggest_for_installation(installation):
    """Régime suggéré d'un chantier : kWc DC, kW AC des onduleurs de la
    nomenclature gelée, niveau de tension (CIQ610), hors réseau (AGR602)."""
    from .models import Installation
    return suggest_for_company(
        installation.puissance_installee_kwc, installation.company,
        hors_reseau=(installation.raccordement_reseau
                     == Installation.RaccordementReseau.HORS_RESEAU),
        kw_ac=kw_ac_onduleurs(installation.bom, installation.company),
        niveau=installation.niveau_tension,
        type_installation=installation.type_installation)
