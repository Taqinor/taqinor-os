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


# ── ACAL828 — plages horaires du plafond d'injection ─────────────────────

#: Le nombre de plages admises : une pointe du matin, une du soir, une
#: troisième au besoin — pas un calendrier. Borne de FORME, jamais électrique.
PLAGES_MAXIMUM = 3

CHAMP_PLAGES = 'plages_plafond_injection'


class PlageInvalide(ValueError):
    """Une plage refusée ; ``champ`` nomme la plage fautive
    (``plages_plafond_injection[i]``), ``message`` dit quoi corriger.
    ``etat`` marque une règle qui LIE plusieurs valeurs (fin avant début,
    chevauchement) : le schéma ne la dit pas, l'API la refuse en 409 (ENF11)."""

    def __init__(self, message, champ=CHAMP_PLAGES, *, etat=False):
        super().__init__(message)
        self.champ = champ
        self.etat = etat


def _entier_horaire(valeur):
    """Une heure entière 0-24, ou ``None`` (un booléen n'est pas une heure)."""
    if isinstance(valeur, bool) or valeur is None or valeur == '':
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return int(nombre) if nombre == int(nombre) and 0 <= nombre <= 24 else None


def plages_saisies(brutes):
    """Les plages normalisées ``[{debut_h, fin_h, plafond_kw}]``, ou ``None``.

    Une plage vaut pour les heures locales ``debut_h ≤ h < fin_h`` ; une plage
    à cheval sur minuit se saisit en deux plages. Refus nommés (``PlageInvalide``,
    champ ``plages_plafond_injection[i]``) : plus de trois plages, bornes hors
    0-24 ou ``debut_h ≥ fin_h``, chevauchement, plafond illisible ou négatif.
    """
    if brutes is None or brutes == []:
        return None
    if not isinstance(brutes, (list, tuple)):
        raise PlageInvalide("Les plages se donnent en liste de "
                            "{debut_h, fin_h, plafond_kw}.")
    if len(brutes) > PLAGES_MAXIMUM:
        raise PlageInvalide(
            "Au plus %d plages horaires : %d reçues." % (PLAGES_MAXIMUM,
                                                         len(brutes)),
            champ='%s[%d]' % (CHAMP_PLAGES, PLAGES_MAXIMUM))
    lues = []
    for rang, brute in enumerate(brutes):
        champ = '%s[%d]' % (CHAMP_PLAGES, rang)
        if not isinstance(brute, dict):
            raise PlageInvalide("La plage doit porter debut_h, fin_h et "
                                "plafond_kw.", champ=champ)
        debut, fin = (_entier_horaire(brute.get('debut_h')),
                      _entier_horaire(brute.get('fin_h')))
        if debut is None or fin is None or debut >= fin:
            raise PlageInvalide(
                "Une plage va d'une heure de début à une heure de fin plus "
                "tardive, entre 0 et 24 (heures entières) ; une plage à "
                "cheval sur minuit se saisit en deux plages.", champ=champ,
                etat=None not in (debut, fin))  # deux heures lisibles mal ordonnées
        try:
            plafond = float(brute.get('plafond_kw'))
        except (TypeError, ValueError):
            plafond = float('nan')
        if plafond != plafond or plafond in (float('inf'), float('-inf')):
            raise PlageInvalide("Le plafond de la plage est illisible : il "
                                "se saisit en kW.", champ=champ)
        if plafond < 0:
            raise PlageInvalide("Le plafond d'une plage ne peut pas être "
                                "négatif.", champ=champ)
        for autre in lues:
            if debut < autre['fin_h'] and autre['debut_h'] < fin:
                raise PlageInvalide("Cette plage chevauche une autre plage.",
                                    champ=champ, etat=True)
        lues.append({'debut_h': debut, 'fin_h': fin, 'plafond_kw': plafond})
    return lues


def plafonds_par_pas(plages, heure_de_depart, longueur):
    """Par pas horaire : ``(plafond_kw, rang de la plage)`` ou ``None``.

    L'heure locale du pas ``r`` est ``(heure du premier point + r) mod 24`` —
    la même lecture que ``etapes/batterie.py`` pour ``heures_tarif`` ; la
    série doit être au pas de 60 min (l'appelant l'impose).
    """
    sortie = []
    for rang in range(longueur):
        heure = (heure_de_depart + rang) % 24
        trouve = None
        for numero, plage in enumerate(plages or ()):
            if plage['debut_h'] <= heure < plage['fin_h']:
                trouve = (plage['plafond_kw'], numero)
                break
        sortie.append(trouve)
    return sortie


# ── ACAL829 — plafond de soutirage (kW) ──────────────────────────────────

def soutirage_au_dessus(imports_kwh, plafond_kw, pas_heures=1.0):
    """``{pointe_kw, heures_au_dessus, energie_au_dessus_kwh}`` de l'import
    réseau face à un plafond de soutirage SAISI (kW).

    ``imports_kwh`` est l'import réseau pas à pas, APRÈS batterie (kWh par
    pas) ; la puissance d'un pas est ``import ÷ pas``. Une heure est « au
    dessus » quand sa puissance dépasse STRICTEMENT le plafond ; l'énergie
    est la part de l'import au-delà de ``plafond × pas`` (énergie de la
    fenêtre simulée, ramenée à l'année par l'appelant).
    """
    pas = pas_heures if pas_heures and pas_heures > 0 else 1.0
    plafond_kwh = plafond_kw * pas
    heures = sum(1 for valeur in imports_kwh if valeur / pas > plafond_kw)
    energie = sum(valeur - plafond_kwh for valeur in imports_kwh
                  if valeur / pas > plafond_kw)
    return {
        'pointe_kw': round(max(imports_kwh, default=0.0) / pas, 3),
        'heures_au_dessus': heures,
        'energie_au_dessus_kwh': round(energie, 3),
    }
