"""CIQ110 — autoconsommation C&I HEURE PAR HEURE et régime d'injection.

Module PUR (aucune base lue, aucun prix). Pour chaque jour type de charge
(``profil_charge.jours_types`` CIQ108, heures GMT) on croise la production du
même mois (``production.jours_types`` CIQ109, kWh/kWc, heures GMT) × la taille,
par le SEUL moteur de croisement du dépôt
``apps.ventes.solar_design.hourly_self_consumption`` (déjà appelé par le
calepinage) : autoconsommé = Σ min(charge_h, production_h), surplus =
production − autoconsommé, pondérés par le nombre de jours du type.

Aucun taux fixe (ni « part diurne », ni 60 %, ni 80 % — D-CIQ-1).

Régime d'injection (D-CIQ-4, ANRE 04/26, loi 82-21 art. 12) :

* BT (ou tension inconnue) : aucune revente ouverte — tout le surplus est
  ``non_valorise_kwh`` ; une revente demandée lève une alerte nommée ;
* MT/HT avec ``revente_choisie`` : surplus valorisable plafonné à
  ``PLAFOND_INJECTION_PCT`` % de la production ANNUELLE, l'excédent est non
  valorisé ;
* MT/HT sans revente = BT.

Sortie = le bloc ``bilan`` du contrat ``etude_ci_preview.json`` ; la matrice
``horaire`` est celle que lit la valorisation (``apps.ventes.economie_ci``).
"""

from apps.ventes.quote_engine.constants_82_21 import (
    MENTION_BT,
    PLAFOND_INJECTION_PCT,
    PLAFOND_INJECTION_SOURCE,
)
from apps.ventes.solar_design import hourly_self_consumption

HEURES = 24
TENSIONS_REVENTE = frozenset({'mt', 'ht', 'tht'})


def _alerte(code, champ, message, niveau='alerte', interne=False):
    return {'code': code, 'champ': champ, 'message': message,
            'niveau': niveau, 'interne': interne}


def _num(valeur):
    try:
        if valeur is None or isinstance(valeur, bool):
            return 0.0
        return max(0.0, float(valeur))
    except (TypeError, ValueError):
        return 0.0


def _matrice_heure(charge, production):
    """(autoconsommé, surplus) d'une heure pour la matrice ``horaire``.

    La MÊME règle que ``hourly_self_consumption`` (min(charge, production)) ;
    les totaux du bilan viennent, eux, du moteur de croisement unique.
    """
    auto = charge if charge < production else production
    return auto, production - auto


def regime_injection(tension, revente_choisie):
    """``'revente'`` (MT/HT et revente choisie) ou ``'sans_revente'``."""
    if revente_choisie and (tension or '').lower() in TENSIONS_REVENTE:
        return 'revente'
    return 'sans_revente'


def bilan_horaire(charge_jours_types, production_jours_types, kwc, *, tension,
                  revente_choisie=False):
    """Bloc ``bilan`` pour une taille ``kwc`` et ses alertes.

    ``charge_jours_types`` : ``[{mois, type_jour, nb_jours, charge_kwh[24]}]``.
    ``production_jours_types`` : ``[{mois, production_kwh_kwc[24]}]``.
    Rend ``(bilan, alertes)``.
    """
    alertes = []
    puissance = _num(kwc)
    prod_par_mois = {}
    for bloc in production_jours_types or []:
        if isinstance(bloc, dict) and bloc.get('mois') is not None:
            prod_par_mois[bloc['mois']] = [_num(v) * puissance
                                           for v in (bloc.get('production_kwh_kwc') or [])]

    mois_cumul = {}
    horaire = []
    tot_prod = tot_auto = tot_surplus = tot_conso = 0.0
    for jt in charge_jours_types or []:
        mois = jt.get('mois')
        nb = _num(jt.get('nb_jours'))
        charge = [_num(v) for v in (jt.get('charge_kwh') or [])]
        prod = prod_par_mois.get(mois)
        if prod is None or len(prod) != HEURES or len(charge) != HEURES:
            alertes.append(_alerte(
                'production_mois_absente', 'production.jours_types',
                f'Production ou charge horaire incomplète pour le mois {mois} : '
                'ce jour type n’entre pas dans le bilan.', interne=True))
            continue
        # Totaux du jour : le moteur de croisement unique, sur les 24 h.
        jour = hourly_self_consumption(charge, prod)
        auto_h, surplus_h = zip(*(_matrice_heure(c, p) for c, p in zip(charge, prod)))
        horaire.append({
            'mois': mois,
            'type_jour': jt.get('type_jour'),
            'nb_jours': jt.get('nb_jours'),
            'autoconso_kwh': [round(v, 3) for v in auto_h],
            'surplus_kwh': [round(v, 3) for v in surplus_h],
        })
        p_j = jour['total_production_kwh'] * nb
        a_j = jour['self_consumed_kwh'] * nb
        s_j = jour['surplus_kwh'] * nb
        c_j = jour['total_load_kwh'] * nb
        tot_prod += p_j
        tot_auto += a_j
        tot_surplus += s_j
        tot_conso += c_j
        cumul = mois_cumul.setdefault(mois, [0.0, 0.0, 0.0, 0.0])
        cumul[0] += p_j
        cumul[1] += c_j
        cumul[2] += a_j
        cumul[3] += s_j

    regime = regime_injection(tension, revente_choisie)
    if regime == 'revente':
        plafond = tot_prod * PLAFOND_INJECTION_PCT / 100.0
        injecte = min(tot_surplus, plafond)
        if tot_surplus > plafond:
            alertes.append(_alerte(
                'plafond_injection_atteint', 'contraintes.revente_choisie',
                f'Surplus au-delà de {PLAFOND_INJECTION_PCT} % de la production '
                f'annuelle : excédent non valorisé ({PLAFOND_INJECTION_SOURCE}).',
                niveau='info', interne=True))
    else:
        injecte = 0.0
        if revente_choisie:
            alertes.append(_alerte(
                'revente_non_ouverte', 'contraintes.revente_choisie',
                MENTION_BT if (tension or '').lower() == 'bt' else
                'Tension non déclarée MT/HT : revente du surplus non valorisée '
                '(à confirmer à la visite).', interne=True))

    par_mois = [
        {'mois': mois,
         'production_kwh': int(round(v[0])),
         'consommation_kwh': int(round(v[1])),
         'autoconso_kwh': int(round(v[2])),
         'surplus_kwh': int(round(v[3]))}
        for mois, v in sorted(mois_cumul.items())
    ]
    bilan = {
        'production_kwh': int(round(tot_prod)),
        'autoconso_kwh': int(round(tot_auto)),
        'surplus_kwh': int(round(tot_surplus)),
        'injecte_valorise_kwh': int(round(injecte)),
        'non_valorise_kwh': int(round(tot_surplus - injecte)),
        'taux_autoconso': round(tot_auto / tot_prod, 3) if tot_prod > 0 else 0.0,
        'taux_couverture': round(tot_auto / tot_conso, 3) if tot_conso > 0 else 0.0,
        'par_mois': par_mois,
        'horaire': horaire,
    }
    return bilan, alertes
