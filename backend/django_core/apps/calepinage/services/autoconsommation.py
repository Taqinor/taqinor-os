"""CAL150/CAL151 — autoconsommation, couverture (COUV-AUTO) et plafond d'export.

LA RÈGLE COUV-AUTO, PAR CONSTRUCTION
------------------------------------
La règle fondateur vient d'être corrigée sur le parcours devis : **la
couverture solaire est la part AUTOCONSOMMÉE de la consommation, JAMAIS
production ÷ consommation**. Un champ qui produit deux fois la consommation
annuelle ne « couvre » pas 200 % des besoins : il en couvre la fraction
réellement consommée au même instant, le reste part au réseau. Le module naît
donc conforme :

* le croisement horaire est celui de ``hourly_self_consumption``
  (``apps/ventes/solar_design.py``) — **un seul moteur**, celui qui porte déjà
  la règle ; on ne réécrit pas une seconde arithmétique qui finirait par
  diverger ;
* **sans courbe horaire, aucun taux n'est publié.** Pas de ratio forfaitaire
  « 60 % sans batterie / 85 % avec » : ces deux-là sont exactement ce que
  CAL150 supprime. Une absence de donnée se dit, elle ne se remplace pas.

LE PLAFOND D'INJECTION (CAL151)
-------------------------------
Rien dans le dépôt ne bornait l'injection : ``net_metering_savings`` valorise
tout l'excédent, et l'écrêtage cité ailleurs est un écrêtage d'ONDULEUR, pas
de point de livraison. PVsyst en fait une limite SYSTÈME, base même du peak
shaving
(https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-systems-with-storage/storage-powers-peak-shaving.html).
Ici :

* le plafond est **SAISI en kW** et porte sa **justification** (contrat,
  autorisation) — un plafond sans justification est REFUSÉ en nommant le
  champ : on ne bride pas la production d'un client sur un chiffre que
  personne ne peut produire devant l'ONEE ;
* il s'applique **heure par heure** au surplus, et l'énergie écrêtée est
  publiée SÉPARÉMENT (kWh/an + nombre d'heures concernées) ;
* **plafond vide ⇒ aucun écrêtage, et RIEN d'affiché** (``plafond: None``) :
  un « 0 kWh écrêté » se lirait comme un plafond vérifié.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

from apps.ventes.solar_design import hourly_self_consumption

__all__ = ['BilanInvalide', 'MOTIF_SANS_COURBE', 'bilan_autoconsommation',
           'plafond_injection']

MOTIF_SANS_COURBE = (
    "Aucune courbe horaire (consommation ou production) n'est disponible : "
    "le taux d'autoconsommation et la couverture ne sont PAS publiés. Ils se "
    'calculent heure par heure — un ratio forfaitaire serait un chiffre '
    'inventé.')


class BilanInvalide(ValueError):
    """Une entrée de bilan refusée, en français et en NOMMANT le champ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def _serie(valeurs, *, champ):
    if valeurs is None:
        return []
    if isinstance(valeurs, (str, bytes, dict)):
        raise BilanInvalide(
            f'La courbe « {champ} » se donne en liste de valeurs horaires '
            f'(reçu : {type(valeurs).__name__}).', champ=champ)
    lues = []
    for rang, valeur in enumerate(valeurs):
        try:
            nombre = float(valeur)
        except (TypeError, ValueError):
            raise BilanInvalide(
                f"L'heure n°{rang + 1} de la courbe « {champ} » est illisible "
                f'(reçu : {valeur!r}).', champ=f'{champ}[{rang}]')
        if nombre != nombre:
            raise BilanInvalide(
                f"L'heure n°{rang + 1} de la courbe « {champ} » est "
                'illisible.', champ=f'{champ}[{rang}]')
        lues.append(max(0.0, nombre))
    return lues


def plafond_injection(surplus_horaire, *, plafond_kw=None, justification='',
                      pas_heures=1.0):
    """Applique un plafond d'injection AU POINT DE LIVRAISON, heure par heure.

    Args:
        surplus_horaire: le surplus injecté heure par heure (kWh/h).
        plafond_kw: le plafond SAISI (kW). ``None`` ⇒ aucun écrêtage et RIEN
            de publié.
        justification: contrat, autorisation… OBLIGATOIRE dès qu'un plafond
            est donné.
        pas_heures: la durée d'un pas de la série (h). Un pas horaire (1 h)
            fait coïncider kW et kWh ; un autre pas est converti ici plutôt
            que supposé ailleurs.

    Returns:
        dict — ``applique``, ``plafond_kw``, ``justification``,
        ``surplus_apres_ecretage`` (série), ``energie_ecretee_kwh``,
        ``heures_ecretees``, ``motif``.

    Raises:
        BilanInvalide: plafond illisible, négatif, ou sans justification.
    """
    surplus = _serie(surplus_horaire, champ='surplus')
    if plafond_kw is None or plafond_kw == '':
        return {
            'applique': False, 'plafond_kw': None, 'justification': '',
            'surplus_apres_ecretage': surplus,
            'energie_ecretee_kwh': None, 'heures_ecretees': None,
            'motif': ("Aucun plafond d'injection n'est saisi : rien n'est "
                      "écrêté et aucun écrêtage n'est affiché."),
        }

    try:
        plafond = float(plafond_kw)
    except (TypeError, ValueError):
        raise BilanInvalide(
            "Le plafond d'injection est illisible "
            f'(reçu : {plafond_kw!r}) : il se saisit en kW.',
            champ='plafond_injection_kw')
    if plafond < 0:
        raise BilanInvalide(
            "Le plafond d'injection ne peut pas être négatif "
            f'(reçu : {plafond}).', champ='plafond_injection_kw')
    if not str(justification or '').strip():
        raise BilanInvalide(
            "Un plafond d'injection doit porter sa justification (contrat de "
            "raccordement, autorisation) : sans elle, on bride la production "
            "d'un client sur un chiffre que personne ne peut défendre.",
            champ='plafond_injection_justification')

    try:
        pas = float(pas_heures)
    except (TypeError, ValueError):
        pas = 1.0
    if pas <= 0:
        pas = 1.0
    maximum_kwh = plafond * pas

    apres = []
    ecrete = 0.0
    heures = 0
    for valeur in surplus:
        if valeur > maximum_kwh:
            ecrete += valeur - maximum_kwh
            heures += 1
            apres.append(maximum_kwh)
        else:
            apres.append(valeur)

    return {
        'applique': True,
        'plafond_kw': plafond,
        'justification': str(justification).strip(),
        'surplus_apres_ecretage': apres,
        'energie_ecretee_kwh': round(ecrete, 3),
        'heures_ecretees': heures,
        'motif': (
            f'Plafond d’injection de {plafond} kW appliqué heure par heure au '
            f'point de livraison ({heures} heure(s) écrêtée(s)).'),
    }


def bilan_autoconsommation(charge_horaire, production_horaire, *,
                           plafond_injection_kw=None,
                           justification_plafond='', pas_heures=1.0):
    """Le bilan horaire : autoconsommation, couverture COUV-AUTO, écrêtage.

    Args:
        charge_horaire / production_horaire: les deux courbes, MÊME période et
            MÊME longueur. L'une vide ⇒ aucun taux publié.

    Returns:
        dict — ``publiable``, ``heures``, ``consommation_kwh``,
        ``production_kwh``, ``autoconsomme_kwh``, ``surplus_kwh``,
        ``import_reseau_kwh``, ``taux_autoconsommation``,
        ``taux_couverture``, ``plafond`` (bloc CAL151 ou ``None``),
        ``definition``, ``motif``.

        ``taux_couverture`` = autoconsommé ÷ CONSOMMATION (règle COUV-AUTO) —
        jamais production ÷ consommation.

    Raises:
        BilanInvalide: courbes illisibles, ou de longueurs différentes (elles
            ne décrivent alors pas la même période, et aucun total n'est
            calculable).
    """
    charge = _serie(charge_horaire, champ='consommation')
    production = _serie(production_horaire, champ='production')

    if not charge or not production:
        return {
            'publiable': False, 'heures': 0,
            'consommation_kwh': None, 'production_kwh': None,
            'autoconsomme_kwh': None, 'surplus_kwh': None,
            'import_reseau_kwh': None,
            'taux_autoconsommation': None, 'taux_couverture': None,
            'plafond': None,
            'definition': '',
            'motif': MOTIF_SANS_COURBE,
        }
    if len(charge) != len(production):
        raise BilanInvalide(
            'Les deux courbes ne décrivent pas la même période '
            f'(consommation : {len(charge)} h, production : '
            f'{len(production)} h) : aucun total n’est calculable.',
            champ='production')

    croise = hourly_self_consumption(load_curve=charge,
                                     production_curve=production)
    surplus_horaire = [max(0.0, p - c) for c, p in zip(charge, production)]
    bloc_plafond = plafond_injection(
        surplus_horaire, plafond_kw=plafond_injection_kw,
        justification=justification_plafond, pas_heures=pas_heures)

    return {
        'publiable': True,
        'heures': croise['hours'],
        'consommation_kwh': croise['total_load_kwh'],
        'production_kwh': croise['total_production_kwh'],
        'autoconsomme_kwh': croise['self_consumed_kwh'],
        'surplus_kwh': croise['surplus_kwh'],
        'import_reseau_kwh': croise['grid_import_kwh'],
        'taux_autoconsommation': croise['self_consumption_rate'],
        # COUV-AUTO — la part AUTOCONSOMMÉE de la CONSOMMATION.
        'taux_couverture': croise['coverage_rate'],
        'plafond': bloc_plafond if bloc_plafond['applique'] else None,
        'definition': (
            "Taux d'autoconsommation = énergie autoconsommée ÷ production. "
            'Couverture = énergie autoconsommée ÷ CONSOMMATION (règle '
            'COUV-AUTO) — jamais production ÷ consommation : un champ qui '
            'produit deux fois la consommation ne couvre pas 200 % des '
            'besoins.'),
        'motif': '',
    }
