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
    'note_debit': 'ND',
}


def _profile(company):
    if company is None:
        return None

    def _load():
        try:
            from apps.parametres.models import CompanyProfile
            return CompanyProfile.get(company=company)
        except Exception:
            return None

    # SCA43 / NTPLT16 — mémo PAR REQUÊTE : le profil société est constant le temps
    # d'une requête ; la liste des devis appelle le moteur une fois par devis, donc
    # sans ce mémo la même config est relue ~1×/devis (N+1). Hors requête (Celery/
    # PDF) le cache est inactif → CompanyProfile.get à chaque appel (inchangé).
    from core import request_cache
    return request_cache.memoize(
        ("parametres.company_profile", getattr(company, "id", None)), _load)


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


_VALID_RESET = {'monthly', 'yearly', 'none'}


def numbering_config(company, key):
    """Config de numérotation pour un type de pièce (D3).

    Renvoie {'prefix', 'padding', 'period'} en fusionnant le préfixe éditable
    (doc_prefixes, inchangé) et la largeur + période de réinitialisation
    (doc_numbering). Les défauts (padding 4, période 'monthly') reproduisent
    EXACTEMENT le comportement historique tant que rien n'est édité.
    """
    prof = _profile(company)
    padding, period = 4, 'monthly'
    cfg = getattr(prof, 'doc_numbering', None) if prof else None
    if isinstance(cfg, dict):
        entry = cfg.get(key)
        if isinstance(entry, dict):
            try:
                padding = max(1, int(entry.get('padding', 4)))
            except (TypeError, ValueError):
                padding = 4
            reset = str(entry.get('reset', 'monthly'))
            if reset in _VALID_RESET:
                period = reset
    return {'prefix': doc_prefix(company, key), 'padding': padding,
            'period': period}


def create_numbered(model, company, key, save_fn):
    """Crée une pièce numérotée selon la config (D3) du type `key`.

    Centralise la résolution préfixe + largeur + période et délègue à
    `references.create_with_reference` (sans collision, race-safe). Tant que
    rien n'est édité, identique au comportement historique.
    """
    from apps.ventes.utils.references import create_with_reference
    cfg = numbering_config(company, key)
    return create_with_reference(
        model, cfg['prefix'], company, save_fn,
        padding=cfg['padding'], period=cfg['period'])


def tva_standard(company):
    """Taux de TVA standard (défaut 20)."""
    prof = _profile(company)
    val = getattr(prof, 'tva_standard', None) if prof else None
    try:
        return Decimal(str(val)) if val is not None else Decimal('20')
    except Exception:
        return Decimal('20')


def tva_panneaux(company):
    """Taux de TVA société pour les lignes PANNEAUX (défaut 10 % — DC4).

    DÉCISION DC4 : `CompanyProfile.tva_panneaux` (jusqu'ici écrit/validé mais lu
    nulle part) devient le DÉFAUT société du taux de TVA des lignes panneaux.
    `Produit.tva` reste la source AUTORITAIRE par ligne (cf. DC7) ; ce taux ne
    s'applique qu'au repli, lorsqu'une ligne panneau n'a ni taux explicite ni
    produit portant un taux. Repli sur 10 % (défaut historique) si le champ est
    absent, donc le comportement reste identique tant que rien n'est édité.
    """
    prof = _profile(company)
    val = getattr(prof, 'tva_panneaux', None) if prof else None
    try:
        return Decimal(str(val)) if val is not None else Decimal('10')
    except Exception:
        return Decimal('10')
