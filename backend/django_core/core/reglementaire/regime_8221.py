"""CIQ612 — UN seul calcul du régime loi 82-21, sourcé (noyau pur).

Module PUR : aucun import d'app, aucun accès base. Il remplace la
classification par les seuls kWc (11 / 1 000, « autorisation ANRE > 1 MW »)
et les règles hors réseau dupliquées dans deux apps (AGR602, AGR603) : chantier,
dossier, devis et constantes du moteur (``quote_engine/constants_82_21.py``,
CIQ201) LISENT ce module, jamais une seconde table.

Textes primaires (lus par la lane de recherche W2 de l'audit du 03/10/2026) :

* loi 82-21 relative à l'autoproduction d'énergie électrique (BO 7400),
  art. 2-6 ; art. 3 : installation non raccordée au réseau → déclaration,
  quelle que soit la puissance ; art. 11 : la puissance d'un site composé de
  plusieurs installations est la SOMME de leurs puissances nominales ;
* décret 2.25.100 (BO 7489 du 09/03/2026, en vigueur le 09/06/2026),
  art. 5, 11, 18 : déclaration < 11 kW (BT) ; accord de raccordement de 11 kW
  à < 5 MW (BT ou MT, chez le distributeur) ; autorisation ≥ 5 MW (MT/HT/THT,
  services déconcentrés de l'énergie après avis technique).

L'unité (kW AC ou kWc DC) n'est pas précisée par les textes : la puissance
retenue est max(DC, AC) et la base reste « à confirmer avec le distributeur ».
Le guichet reste « à confirmer » tant que l'arrêté fixant plateforme et
formulaires (décret art. 25) n'est pas publié. JAMAIS l'ANRE comme guichet.

**Obligation de l'appelant** : transmettre la puissance TOTALE du site
(loi 82-21 art. 11), jamais celle d'une seule installation d'un site composé.

La valeur STOCKÉE ``autorisation_anre`` (choix historique des modèles) est
conservée comme code ; seul son libellé change (« Autorisation », sans ANRE).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

# ── Seuils sourcés (kW) ──────────────────────────────────────────────────────
#: Déclaration en dessous de ce seuil (BT). Décret 2.25.100 art. 5
#: (BO 7489 du 09/03/2026, en vigueur le 09/06/2026) ; loi 82-21 art. 2-6.
SEUIL_DECLARATION_KW = 11
SEUIL_DECLARATION_SOURCE = (
    "décret 2.25.100 art. 5 (BO 7489 du 09/03/2026, en vigueur le "
    "09/06/2026) ; loi 82-21 art. 2-6 (BO 7400)")

#: Autorisation à partir de ce seuil (5 MW). Décret 2.25.100 art. 5, 18
#: (BO 7489 du 09/03/2026, en vigueur le 09/06/2026) ; loi 82-21 art. 2-6.
SEUIL_AUTORISATION_KW = 5000
SEUIL_AUTORISATION_SOURCE = (
    "décret 2.25.100 art. 5, 18 (BO 7489 du 09/03/2026, en vigueur le "
    "09/06/2026) ; loi 82-21 art. 2-6 (BO 7400)")

# ── Codes (valeurs stockées historiques, jamais renommées) ──────────────────
CODE_DECLARATION = 'declaration_bt'
CODE_ACCORD = 'accord_raccordement'
CODE_AUTORISATION = 'autorisation_anre'  # valeur stockée conservée
CODE_HORS_RESEAU = 'declaration_hors_reseau'

GUICHET_DISTRIBUTEUR = 'distributeur'
GUICHET_SERVICES_ENERGIE = 'services_deconcentres_energie'
GUICHET_STATUT = 'a_confirmer'  # arrêté (décret art. 25) non publié
BASE_PUISSANCE = 'a_confirmer_avec_le_distributeur'

NIVEAUX = ('BT', 'MT', 'HT', 'THT')

# Libellés SANS seuil (le seuil vit dans la base, jamais dans le libellé).
_REGIMES = {
    CODE_DECLARATION: {
        'libelle': 'Déclaration',
        'base': 'loi 82-21 art. 2-6 ; décret 2.25.100 art. 5',
        'guichet': GUICHET_DISTRIBUTEUR,
    },
    CODE_ACCORD: {
        'libelle': 'Accord de raccordement',
        'base': 'loi 82-21 art. 4 ; décret 2.25.100 art. 5, 11',
        'guichet': GUICHET_DISTRIBUTEUR,
    },
    CODE_AUTORISATION: {
        'libelle': 'Autorisation',
        'base': 'loi 82-21 art. 2-6 ; décret 2.25.100 art. 5, 18',
        'guichet': GUICHET_SERVICES_ENERGIE,
    },
    CODE_HORS_RESEAU: {
        'libelle': 'Déclaration hors réseau',
        'base': 'loi 82-21 art. 3',
        # Guichet de la déclaration hors réseau non précisé par les textes lus.
        'guichet': None,
    },
}

_A_QUALIFIER = {
    'libelle': 'À qualifier',
    'base': ('loi 82-21 art. 11 : puissance totale du site requise ; '
             'décret 2.25.100 art. 5'),
    'guichet': None,
}


def _kw(valeur):
    """Puissance positive en Decimal, ou None (inconnue / invalide / ≤ 0)."""
    if valeur is None or valeur == '':
        return None
    try:
        p = Decimal(str(valeur))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not p.is_finite() or p <= 0:
        return None
    return p


def _nombre(p):
    """Decimal → int si entier, sinon float (sortie JSON lisible)."""
    if p is None:
        return None
    return int(p) if p == p.to_integral_value() else float(p)


def _forme(code, info, puissance, a_qualifier):
    return {
        'code': code,
        'libelle': info['libelle'],
        'base': info['base'],
        'guichet': info['guichet'],
        'guichet_statut': GUICHET_STATUT,
        'puissance_retenue_kw': _nombre(puissance),
        'base_puissance': BASE_PUISSANCE,
        'a_qualifier': a_qualifier,
    }


def regime_8221(puissance_dc_kwc=None, puissance_ac_kw=None, niveau=None,
                hors_reseau=False, surcharges=None):
    """Régime loi 82-21 d'un SITE — forme ``regime`` du contrat CIQ12.

    ``puissance_dc_kwc`` / ``puissance_ac_kw`` : puissances TOTALES du site
    (loi 82-21 art. 11 — l'appelant somme les installations). La puissance
    retenue est max(DC, AC) (unité non précisée par les textes, base
    « à confirmer avec le distributeur »).

    ``niveau`` : 'BT' | 'MT' | 'HT' | 'THT' | None. La déclaration ne vise que
    la BT : un site non-BT sous le seuil de déclaration n'est couvert par
    aucun des cas lus → ``a_qualifier`` vrai (jamais un régime deviné).

    ``hors_reseau`` : loi 82-21 art. 3 → déclaration hors réseau, QUELLE QUE
    SOIT la puissance (reprend AGR602/AGR603 sans dupliquer).

    ``surcharges`` : dict facultatif {'seuil_declaration_kw',
    'seuil_autorisation_kw'} (réglage société explicite) ; absent = seuils
    sourcés ci-dessus.

    Puissance inconnue → ``a_qualifier`` vrai, ``code`` None : jamais
    ``non_concerne`` par défaut.
    """
    surcharges = surcharges or {}
    dc = _kw(puissance_dc_kwc)
    ac = _kw(puissance_ac_kw)
    connues = [p for p in (dc, ac) if p is not None]
    puissance = max(connues) if connues else None

    if hors_reseau:
        return _forme(CODE_HORS_RESEAU, _REGIMES[CODE_HORS_RESEAU],
                      puissance, False)

    if puissance is None:
        return _forme(None, _A_QUALIFIER, None, True)

    seuil_decl = _kw(surcharges.get('seuil_declaration_kw')) or Decimal(
        SEUIL_DECLARATION_KW)
    seuil_auto = _kw(surcharges.get('seuil_autorisation_kw')) or Decimal(
        SEUIL_AUTORISATION_KW)
    niv = (niveau or '').strip().upper() or None

    if puissance < seuil_decl:
        if niv is not None and niv != 'BT':
            # Déclaration = BT seulement ; un site MT/HT sous 11 kW n'est
            # couvert par aucun cas lu → à qualifier, jamais deviné.
            return _forme(None, _A_QUALIFIER, puissance, True)
        code = CODE_DECLARATION
    elif puissance < seuil_auto:
        code = CODE_ACCORD
    else:
        code = CODE_AUTORISATION
    return _forme(code, _REGIMES[code], puissance, False)


def regime_8221_suggere(puissance_kw, hors_reseau=False):
    """Alias de lecture simple (moteur C&I CIQ118, ``constants_82_21`` CIQ201).

    Renvoie le seul CODE (ou None si la puissance est inconnue). La puissance
    transmise doit être celle du SITE entier (loi 82-21 art. 11).
    """
    return regime_8221(puissance_kw, None, hors_reseau=hors_reseau)['code']


def libelle_regime(code):
    """Libellé sans seuil d'un code (repli : le code brut, ou « À qualifier »)."""
    if not code:
        return _A_QUALIFIER['libelle']
    info = _REGIMES.get(code)
    return info['libelle'] if info else code
