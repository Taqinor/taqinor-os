"""ACAL827 — le plafond d'injection saisi en AMPÈRES, converti en kW.

L'utilisateur lit souvent sa limite en ampères par phase (contrat du
distributeur) : il ne convertit plus à la main. La conversion est PURE et
n'emploie que ce que la saisie porte : nombre de phases, tension nominale et
cos φ IMPOSÉ — jamais 230 V, 400 V ni cos φ 1 par défaut (le cos φ de repli
de la société n'est pas lu : l'écrêtage ne lit que le cos φ imposé).

* triphasé : ``√3 × U × I × cos φ`` ;
* monophasé : ``U × I × cos φ``.
"""
from __future__ import annotations

import math

#: Nombre de décimales publiées du kW converti (11,085 kW pour 16 A, 400 V).
DECIMALES_KW = 3


def _texte(valeur, decimales=None):
    """Un nombre à la française (virgule), sans zéros inutiles."""
    if decimales is not None:
        return f'{valeur:.{decimales}f}'.replace('.', ',')
    return f'{valeur:.10g}'.replace('.', ',')


def convertir_plafond_a(saisie):
    """``(kw, texte)`` : le plafond converti et sa formule, ou ``(None, motif)``.

    ``(None, None)`` quand aucun plafond en ampères n'est saisi. Un champ
    manquant (phases, tension, cos φ imposé) donne ``kw = None`` et un motif
    qui le NOMME.
    """
    ampere = saisie.get('plafond_injection_a')
    if ampere is None:
        return None, None
    manquants = [nom for cle, nom in (
        ('phases', 'le nombre de phases'),
        ('tension_nominale_v', 'la tension nominale (V)'),
        ('cos_phi_impose', 'le cos φ imposé')) if saisie.get(cle) is None]
    if manquants:
        return None, ("Conversion impossible : renseignez "
                      + ', '.join(manquants) + '.')
    tension, cos_phi = saisie['tension_nominale_v'], saisie['cos_phi_impose']
    triphase = saisie['phases'] == 3
    watts = (math.sqrt(3) if triphase else 1.0) * tension * ampere * cos_phi
    kw = round(watts / 1000.0, DECIMALES_KW)
    produit = (f"{_texte(tension)} V × {_texte(ampere)} A × cos φ "
               f"{_texte(cos_phi)} = {_texte(kw, DECIMALES_KW)} kW")
    return kw, (('3 phases : √3 × ' if triphase else 'Monophasé : ') + produit)


def saisie_pour_simulation(saisie):
    """La saisie telle que la simulation la lit : le plafond en ampères,
    quand il est saisi, devient son kW converti dans ``plafond_injection_kw``
    (ni ``plafond_injection_a`` ni sa conversion ne sortent d'ici)."""
    saisie = dict(saisie)
    ampere = saisie.pop('plafond_injection_a', None)
    if ampere is not None:
        saisie['plafond_injection_kw'] = convertir_plafond_a(
            dict(saisie, plafond_injection_a=ampere))[0]
    return saisie


def ecart_pmax_societe(electrique_societe):
    """ACAL657 — le seuil société ``fiche_ecart_pmax_pct`` (écart toléré entre
    Pmax et Vmp × Imp d'une fiche module importée) : un ``Decimal`` entre 0 et
    100, ou ``None`` quand il n'est pas saisi AVEC sa source (le contrôle est
    alors omis et le dit). Lecteur de la clé, appelé par la vue d'import de
    fiche (``apps/stock``) — le lecteur PVsyst lui-même n'importe pas Django."""
    from decimal import Decimal, InvalidOperation

    saisie = (electrique_societe or {}).get('fiche_ecart_pmax_pct')
    if not isinstance(saisie, dict) or not saisie.get('source'):
        return None
    try:
        seuil = Decimal(str(saisie.get('valeur')))
    except (InvalidOperation, ValueError):
        return None
    return seuil if seuil.is_finite() and 0 <= seuil <= 100 else None
