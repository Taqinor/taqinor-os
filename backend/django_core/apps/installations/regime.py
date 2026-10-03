"""N43 — suggestion configurable du régime loi 82-21 d'un chantier.

À partir de la puissance (kWc) et du type de raccordement, propose le régime
réglementaire probable comme DÉFAUT MODIFIABLE. Les seuils sont éditables dans
Paramètres ; leurs défauts reprennent le cadre marocain standard :

  * < 11 kWc, basse tension  → Déclaration (declaration_bt)
  * 11 kWc … 1 MW (1000 kWc) → Accord de raccordement
  * > 1 MW                    → Autorisation ANRE

Le cœur (`suggest_regime_8221`) est une fonction pure, testable sans Django.
"""
from decimal import Decimal, InvalidOperation

# Défauts du cadre loi 82-21 (kWc). 1 MW = 1000 kWc.
DEFAULT_SEUIL_DECLARATION_KWC = Decimal('11')
DEFAULT_SEUIL_ANRE_KWC = Decimal('1000')


def suggest_regime_8221(kwc, seuil_declaration=DEFAULT_SEUIL_DECLARATION_KWC,
                        seuil_anre=DEFAULT_SEUIL_ANRE_KWC, hors_reseau=False):
    """Renvoie le code régime suggéré (valeur de Installation.Regime8221).

    AGR602 — ``hors_reseau`` : loi 82-21, art. 3 — toute installation non
    raccordée au réseau relève d'une déclaration, QUELLE QUE SOIT la
    puissance → 'declaration_hors_reseau'. Aucune logique d'injection.

    kWc inconnu/non positif → 'non_concerne' (rien à proposer)."""
    if hors_reseau:
        return 'declaration_hors_reseau'
    try:
        p = Decimal(str(kwc)) if kwc is not None else None
    except (InvalidOperation, TypeError, ValueError):
        p = None
    if p is None or p <= 0:
        return 'non_concerne'
    if p < Decimal(str(seuil_declaration)):
        return 'declaration_bt'
    if p <= Decimal(str(seuil_anre)):
        return 'accord_raccordement'
    return 'autorisation_anre'


def regime_thresholds(company):
    """(seuil_declaration_kwc, seuil_anre_kwc) depuis Paramètres, défauts sinon."""
    seuil_decl = DEFAULT_SEUIL_DECLARATION_KWC
    seuil_anre = DEFAULT_SEUIL_ANRE_KWC
    if company is not None:
        try:
            from apps.parametres.models import CompanyProfile
            prof = CompanyProfile.get(company=company)
            if prof.seuil_regime_declaration_kwc is not None:
                seuil_decl = prof.seuil_regime_declaration_kwc
            if prof.seuil_regime_anre_kwc is not None:
                seuil_anre = prof.seuil_regime_anre_kwc
        except Exception:
            pass
    return seuil_decl, seuil_anre


def suggest_for_company(kwc, company, hors_reseau=False):
    """Suggestion en appliquant les seuils éditables de la société."""
    seuil_decl, seuil_anre = regime_thresholds(company)
    return suggest_regime_8221(
        kwc, seuil_decl, seuil_anre, hors_reseau=hors_reseau)
