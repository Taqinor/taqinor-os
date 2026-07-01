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


# ── DC1 — identité société pour le moteur de devis premium ──────────────────
# Le moteur premium imprimait l'identité Taqinor EN DUR (RC/ICE/RIB/banque/
# adresse/tél/nom). C'est multi-tenant FAUX et expose le RIB Taqinor à toute
# société. `entreprise_for` renvoie ces champs depuis CompanyProfile en
# REPLI sur les littéraux historiques : tant qu'une société n'a rien renseigné
# (champs vides), chaque clé garde EXACTEMENT la valeur d'avant → le PDF reste
# byte-identique pour Taqinor et les tests de régression ne bougent pas. Une
# AUTRE société qui renseigne son profil voit SES coordonnées, jamais le RIB
# Taqinor. (La voie facture lit déjà CompanyProfile ; on aligne le devis.)
ENTREPRISE_DEFAULTS = {
    'nom': 'TAQINOR',
    'raison_sociale': 'Taqinor Solutions SARLAU',
    'capital': '100 000 MAD',
    'rc': '691213',
    'ice': '003799642000067',
    'identifiant_fiscal': '',
    'patente': '',
    'cnss': '',
    'gerant': 'M. Reda Kasri',
    'adresse': '5 Rue Ennoussour RDC, Casablanca',
    'tribunal': 'Tribunal de Commerce de Casablanca',
    'email': 'contact@taqinor.com',
    'telephone': '+212 6 61 85 04 10',
    'site_web': 'www.taqinor.ma',
    'rib': '022 780 0002720029379418 74',
    'banque': 'Saham Bank',
    'bic': 'SGMBMAMCXXX',
    'couleur_principale': '',
}

# Champs portés 1:1 par CompanyProfile (le reste garde le littéral historique
# tant qu'aucun slot dédié n'existe sur le profil).
_PROFILE_FIELD_MAP = {
    'nom': 'nom',
    'raison_sociale': 'nom',
    'rc': 'rc',
    'ice': 'ice',
    'identifiant_fiscal': 'identifiant_fiscal',
    'patente': 'patente',
    'cnss': 'cnss',
    'adresse': 'adresse',
    'email': 'email',
    'telephone': 'telephone',
    'rib': 'rib',
    'banque': 'banque',
    'couleur_principale': 'couleur_principale',
}


def entreprise_for(company):
    """Identité société (DC1) pour le moteur de devis premium.

    Renvoie un dict JSON-sérialisable : pour chaque champ, la valeur renseignée
    sur CompanyProfile, sinon le littéral historique (REPLI). Aucune valeur
    n'est jamais None → les renderers peuvent l'utiliser directement. Sans
    company ou sans profil, renvoie strictement les défauts historiques."""
    out = dict(ENTREPRISE_DEFAULTS)
    prof = _profile(company)
    if prof is None:
        return out
    for out_key, field in _PROFILE_FIELD_MAP.items():
        val = getattr(prof, field, None)
        if val is None:
            continue
        val = str(val).strip()
        if val:
            out[out_key] = val
    return out
