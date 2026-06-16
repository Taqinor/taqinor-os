"""Résolution des paramètres métier éditables (CompanyProfile) avec REPLI sur
les valeurs codées en dur historiques. Source unique pour : échéancier par mode,
préfixes de numérotation, taux de TVA, validité du devis, heures de pompage.

Tant que le founder n'a rien édité (champs NULL/défauts), ces fonctions
renvoient EXACTEMENT les valeurs d'avant — comportement identique, tests de
régression inchangés.
"""
from decimal import Decimal

DEFAULT_PREFIXES = {
    'devis': 'DEV', 'facture': 'FAC', 'avoir': 'AVO', 'bon_commande': 'BC',
}


def _profile(company):
    if company is None:
        return None
    try:
        from apps.parametres.models import CompanyProfile
        return CompanyProfile.get(company=company)
    except Exception:
        return None


def payment_terms_for(company, mode):
    """{'acompte','materiel','solde'} en % pour le mode, réglage ou défaut."""
    mode = mode or 'residentiel'
    from apps.ventes.quote_engine.builder import PAYMENT_TERMS_BY_MODE
    default = PAYMENT_TERMS_BY_MODE.get(mode, PAYMENT_TERMS_BY_MODE['residentiel'])
    prof = _profile(company)
    pt = getattr(prof, 'payment_terms', None) if prof else None
    if isinstance(pt, dict):
        t = pt.get(mode)
        if isinstance(t, dict) and all(
                k in t for k in ('acompte', 'materiel', 'solde')):
            try:
                return {k: int(t[k]) for k in ('acompte', 'materiel', 'solde')}
            except (TypeError, ValueError):
                pass
    return default


def doc_prefix(company, key):
    """Préfixe de numérotation pour 'devis'/'facture'/'avoir'/'bon_commande'."""
    prof = _profile(company)
    px = getattr(prof, 'doc_prefixes', None) if prof else None
    if isinstance(px, dict) and px.get(key):
        return str(px[key]).strip() or DEFAULT_PREFIXES.get(key, key.upper())
    return DEFAULT_PREFIXES.get(key, key.upper())


def tva_standard(company):
    """Taux de TVA standard (défaut 20)."""
    prof = _profile(company)
    val = getattr(prof, 'tva_standard', None) if prof else None
    try:
        return Decimal(str(val)) if val is not None else Decimal('20')
    except Exception:
        return Decimal('20')


def quote_validity_days(company):
    """Durée de validité du devis en jours (réglage ou défaut historique 30)."""
    prof = _profile(company)
    val = getattr(prof, 'quote_validity_days', None) if prof else None
    try:
        n = int(val) if val is not None else 30
        return n if n > 0 else 30
    except (TypeError, ValueError):
        return 30


def seuil_remise_approbation(company):
    """Seuil de remise (%) au-delà duquel l'envoi d'un devis exige une
    approbation admin/responsable. NULL/0 = garde DÉSACTIVÉE (défaut) →
    comportement historique strictement inchangé."""
    prof = _profile(company)
    val = getattr(prof, 'seuil_remise_approbation', None) if prof else None
    try:
        return Decimal(str(val)) if val is not None else None
    except Exception:
        return None
