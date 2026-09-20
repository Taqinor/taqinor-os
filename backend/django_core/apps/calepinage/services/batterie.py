"""CAL152/CAL153 — les stratégies de batterie, en BOUCLES DE DISPATCH horaires.

LE CONSTAT (CAL152)
-------------------
``battery_storage_sizing`` (``apps/ventes/solar_design.py``) n'offre que
``autoconso`` / ``backup`` / ``both``, et il DIMENSIONNE (des kWh utiles à
partir d'un surplus journalier) — il ne fait tourner aucune batterie.
PVsyst documente QUATRE stratégies (autoconsommation, effacement de pointe,
réseau faible/îlotage, décalage de puissance programmé —
https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-systems-with-storage/index.html)
et SAM une répartition TOU automatisée
(https://sam.nrel.gov/battery-storage/battery-publications.html). Ce module
ajoute ``peak_shaving`` et ``decalage``, et les fait tourner HEURE PAR HEURE :
une stratégie qui ne se simule pas ne se compare pas.

LE CONSTAT (CAL153)
-------------------
Le dimensionnement partait de constantes (DoD et rendement aller-retour) alors
que la FICHE porte ``bat_dod_pct``, ``bat_kwh_usable``,
``bat_rendement_ar_pct``, ``cycles_publies`` (``apps/stock/models.py``, lus par
``apps.stock.selectors.specs_for_produit``). Ici chaque grandeur est LUE sur la
fiche, et l'hypothèse de référence n'est appliquée qu'en étant **NOMMÉE**
(``source: 'fiche' | 'hypothese'``, jamais un forfait muet). La limite du port
batterie de l'onduleur (``bat_max_charge_kw`` / ``bat_max_decharge_kw``) BORNE
la puissance publiée.

CE QUI N'EST JAMAIS DEVINÉ
--------------------------
Le seuil d'effacement et les heures de charge/décharge sont **SAISIS** ; aucun
tarif n'entre ici (le module ne connaît aucun prix). Les tranches horaires de
référence du dépôt sont OFFERTES (``tranches_horaires()``) pour que l'écran
propose « charger en creuse » — mais rien ne s'applique tant que
l'utilisateur n'a pas choisi.

Module PUR côté calcul ; la fiche est lue par le SÉLECTEUR du stock, jamais par
ses modèles.
"""
from __future__ import annotations

import math

__all__ = ['GRANDEURS_BATTERIE', 'STRATEGIES', 'StrategieInvalide',
           'simuler_batterie', 'specs_batterie', 'tranches_horaires']

#: Les stratégies simulables. ``autoconso`` et ``backup`` existaient (côté
#: dimensionnement) ; ``peak_shaving`` et ``decalage`` sont l'apport de CAL152.
STRATEGIES = ('autoconso', 'peak_shaving', 'backup', 'decalage')

#: Les grandeurs batterie PUBLIÉES, chacune avec sa source (CAL153).
GRANDEURS_BATTERIE = ('kwh_nominal', 'kwh_usable', 'dod_pct',
                      'rendement_ar_pct', 'cycles_publies',
                      'max_charge_kw', 'max_decharge_kw')


class StrategieInvalide(ValueError):
    """Une entrée de stratégie refusée, en français et en NOMMANT le champ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


def tranches_horaires():
    """Les tranches horaires de RÉFÉRENCE du dépôt (creuse/pleine/pointe).

    Relues dans ``apps.ventes.solar_design`` — jamais recopiées. Elles sont
    OFFERTES à l'écran pour proposer des heures ; elles ne s'appliquent pas
    toutes seules : ``decalage`` n'agit que sur des heures SAISIES.
    """
    from apps.ventes.solar_design import DEFAULT_HOUR_TRANCHES

    return list(DEFAULT_HOUR_TRANCHES)


def _hypotheses_de_reference():
    """Les hypothèses de référence du dépôt — relues, jamais recopiées.

    Elles ne s'appliquent QUE si la fiche ne dit rien, et elles sont alors
    publiées avec ``source: 'hypothese'`` et leur provenance nommée.
    """
    from apps.ventes import solar_design

    return {
        'dod_pct': (solar_design._BATTERY_DEFAULT_DOD * 100.0,
                    'Hypothèse de référence du dépôt '
                    '(apps/ventes/solar_design.py) — la fiche ne publie pas '
                    'de profondeur de décharge.'),
        'rendement_ar_pct': (
            solar_design._BATTERY_DEFAULT_ROUND_TRIP * 100.0,
            'Hypothèse de référence du dépôt '
            '(apps/ventes/solar_design.py) — la fiche ne publie pas de '
            'rendement aller-retour.'),
    }


def specs_batterie(produit_batterie, *, produit_onduleur=None, nb_packs=1):
    """Les grandeurs batterie, chacune AVEC SA SOURCE (fiche ou hypothèse).

    Args:
        produit_batterie: le produit BATTERIE retenu (sa fiche est lue par
            ``apps.stock.selectors.specs_for_produit``). ``None`` ⇒ aucune
            grandeur, et le dire.
        produit_onduleur: l'onduleur retenu — son port batterie
            (``bat_max_charge_kw`` / ``bat_max_decharge_kw``) BORNE la
            puissance publiée.
        nb_packs: nombre de packs EN PARALLÈLE (saisi). Les capacités et les
            puissances du parc sont celles d'un pack × ``nb_packs`` ; la
            borne de l'onduleur, elle, ne se multiplie PAS.

    Returns:
        dict — ``grandeurs`` (``{nom: {valeur, source, mention}}``),
        ``nb_packs``, ``capacite_utile_kwh``, ``puissance_charge_kw``,
        ``puissance_decharge_kw``, ``borne_onduleur``, ``avertissements``.
        Une grandeur inconnue vaut ``None`` avec sa raison — jamais un
        forfait muet.
    """
    from apps.stock.selectors import specs_for_produit

    fiche = specs_for_produit(produit_batterie) if produit_batterie else {}
    fiche = fiche if isinstance(fiche, dict) else {}
    hypotheses = _hypotheses_de_reference()

    grandeurs = {}
    avertissements = []
    for nom in GRANDEURS_BATTERIE:
        valeur = _nombre(fiche.get(nom))
        if valeur is not None:
            grandeurs[nom] = {'valeur': valeur, 'source': 'fiche',
                              'mention': 'Lu sur la fiche produit.'}
            continue
        if nom in hypotheses:
            valeur_hypothese, mention = hypotheses[nom]
            grandeurs[nom] = {'valeur': valeur_hypothese,
                              'source': 'hypothese', 'mention': mention}
            avertissements.append(f'« {nom} » : {mention}')
            continue
        grandeurs[nom] = {
            'valeur': None, 'source': None,
            'mention': ('La fiche ne publie pas cette grandeur : rien n’est '
                        'supposé, elle reste vide.')}

    try:
        packs = max(1, int(nb_packs or 1))
    except (TypeError, ValueError):
        packs = 1

    utile = grandeurs['kwh_usable']['valeur']
    source_utile = grandeurs['kwh_usable']['source']
    if utile is None:
        nominal = grandeurs['kwh_nominal']['valeur']
        dod = grandeurs['dod_pct']['valeur']
        if nominal is not None and dod is not None:
            utile = nominal * dod / 100.0
            source_utile = grandeurs['dod_pct']['source']
            avertissements.append(
                'Capacité UTILE déduite de la capacité nominale et de la '
                f'profondeur de décharge ({grandeurs["dod_pct"]["source"]}).')

    borne_charge = None
    borne_decharge = None
    if produit_onduleur is not None:
        fiche_ond = specs_for_produit(produit_onduleur) or {}
        borne_charge = _nombre(fiche_ond.get('bat_max_charge_kw'))
        borne_decharge = _nombre(fiche_ond.get('bat_max_decharge_kw'))

    def _puissance(nom_grandeur, borne):
        valeur = grandeurs[nom_grandeur]['valeur']
        if valeur is None:
            return None, False
        parc = valeur * packs
        if borne is not None and borne < parc:
            return borne, True
        return parc, False

    charge_kw, bornee_charge = _puissance('max_charge_kw', borne_charge)
    decharge_kw, bornee_decharge = _puissance('max_decharge_kw',
                                              borne_decharge)
    if bornee_charge or bornee_decharge:
        avertissements.append(
            'La puissance publiée est BORNÉE par le port batterie de '
            'l’onduleur : ajouter des packs n’augmente plus la puissance.')

    return {
        'grandeurs': grandeurs,
        'nb_packs': packs,
        'capacite_utile_kwh': (round(utile * packs, 3)
                               if utile is not None else None),
        'capacite_utile_source': source_utile,
        'puissance_charge_kw': charge_kw,
        'puissance_decharge_kw': decharge_kw,
        'borne_onduleur': {'charge_kw': borne_charge,
                           'decharge_kw': borne_decharge},
        'avertissements': avertissements,
    }


def _serie(valeurs, *, champ):
    if valeurs is None:
        return []
    lues = []
    for rang, valeur in enumerate(valeurs):
        nombre = _nombre(valeur)
        if nombre is None:
            raise StrategieInvalide(
                f"L'heure n°{rang + 1} de la courbe « {champ} » est illisible "
                f'(reçu : {valeur!r}).', champ=f'{champ}[{rang}]')
        lues.append(max(0.0, nombre))
    return lues


def _heures(valeurs, *, champ):
    if not valeurs:
        raise StrategieInvalide(
            f'Les heures « {champ} » sont obligatoires pour la stratégie de '
            'décalage : aucune heure n’est devinée (aucun tarif n’est connu '
            'de ce module).', champ=champ)
    heures = set()
    for valeur in valeurs:
        nombre = _nombre(valeur)
        if nombre is None or not 0 <= int(nombre) <= 23:
            raise StrategieInvalide(
                f'Heure invalide dans « {champ} » (reçu : {valeur!r}) : les '
                'heures se comptent de 0 à 23.', champ=champ)
        heures.add(int(nombre))
    return heures


def simuler_batterie(charge_horaire, production_horaire, *, strategie,
                     capacite_utile_kwh, puissance_charge_kw,
                     puissance_decharge_kw, rendement_ar_pct=None,
                     seuil_effacement_kw=None, heures_charge=None,
                     heures_decharge=None, reserve_backup_kwh=None,
                     etat_initial_kwh=0.0, pas_heures=1.0,
                     heure_de_depart=0):
    """Fait TOURNER la batterie heure par heure selon la stratégie retenue.

    Args:
        strategie: ``autoconso`` | ``peak_shaving`` | ``backup`` |
            ``decalage``.
        seuil_effacement_kw: SAISI — obligatoire pour ``peak_shaving`` (on
            n'efface pas au-dessus d'un seuil que personne n'a choisi).
        heures_charge / heures_decharge: SAISIES — obligatoires pour
            ``decalage``.
        reserve_backup_kwh: la réserve à ne jamais entamer, SAISIE —
            obligatoire pour ``backup``.

    Returns:
        dict — ``strategie``, ``objectif_dimensionnant``, ``heures``,
        ``charge_batterie_kwh``, ``decharge_batterie_kwh``,
        ``import_reseau_kwh``, ``surplus_injecte_kwh``, ``pertes_stockage_kwh``,
        ``etat_de_charge_kwh`` (série), ``energie_effacee_kwh`` (peak shaving),
        ``parametres``.

    Raises:
        StrategieInvalide: stratégie inconnue, paramètre saisi manquant,
            capacité ou puissance absente (on ne fait pas tourner une batterie
            dont on ignore la taille).
    """
    if strategie not in STRATEGIES:
        raise StrategieInvalide(
            f'Stratégie de batterie inconnue : « {strategie} ». Stratégies '
            f'admises : {", ".join(STRATEGIES)}.', champ='strategie')

    charge = _serie(charge_horaire, champ='consommation')
    production = _serie(production_horaire, champ='production')
    if not charge or not production:
        raise StrategieInvalide(
            'La simulation de batterie exige les DEUX courbes horaires '
            '(consommation et production) : sans elles, aucun dispatch n’est '
            'calculable.', champ='production')
    if len(charge) != len(production):
        raise StrategieInvalide(
            'Les deux courbes ne décrivent pas la même période '
            f'(consommation : {len(charge)} h, production : '
            f'{len(production)} h).', champ='production')

    capacite = _nombre(capacite_utile_kwh)
    p_charge = _nombre(puissance_charge_kw)
    p_decharge = _nombre(puissance_decharge_kw)
    if capacite is None or capacite <= 0:
        raise StrategieInvalide(
            'La capacité UTILE de la batterie est inconnue : elle se lit sur '
            'la fiche (CAL153), elle ne se suppose pas.',
            champ='capacite_utile_kwh')
    if p_charge is None or p_decharge is None:
        raise StrategieInvalide(
            'Les puissances de charge et de décharge sont inconnues : elles '
            'se lisent sur la fiche (et sont bornées par le port batterie de '
            'l’onduleur), elles ne se supposent pas.',
            champ='puissance_charge_kw')

    pas = _nombre(pas_heures) or 1.0
    if pas <= 0:
        pas = 1.0
    rendement = _nombre(rendement_ar_pct)
    # Rendement ALLER-RETOUR : la racine de part et d'autre, pour que le
    # produit des deux sens vaille exactement le rendement publié.
    eta = math.sqrt(max(0.0, min(1.0, (rendement or 100.0) / 100.0)))

    seuil = _nombre(seuil_effacement_kw)
    if strategie == 'peak_shaving' and (seuil is None or seuil < 0):
        raise StrategieInvalide(
            "L'effacement de pointe exige un seuil SAISI (kW) : aucun seuil "
            'n’est deviné, et ce module ne connaît aucun tarif.',
            champ='seuil_effacement_kw')
    if strategie == 'decalage':
        heures_charge = _heures(heures_charge, champ='heures_charge')
        heures_decharge = _heures(heures_decharge, champ='heures_decharge')
        communes = heures_charge & heures_decharge
        if communes:
            raise StrategieInvalide(
                'Les mêmes heures sont déclarées en charge ET en décharge '
                f'({sorted(communes)}) : la batterie ne peut pas faire les '
                'deux à la fois.', champ='heures_decharge')
    reserve = _nombre(reserve_backup_kwh)
    if strategie == 'backup' and (reserve is None or reserve < 0):
        raise StrategieInvalide(
            'La stratégie de secours exige une réserve SAISIE (kWh) : la '
            'part du parc qu’on refuse d’entamer pour tenir une coupure.',
            champ='reserve_backup_kwh')

    etat = min(max(0.0, _nombre(etat_initial_kwh) or 0.0), capacite)
    plancher = min(reserve, capacite) if strategie == 'backup' else 0.0

    etats = []
    total_charge = 0.0
    total_decharge = 0.0
    total_import = 0.0
    total_injecte = 0.0
    total_efface = 0.0

    for rang, (conso, prod) in enumerate(zip(charge, production)):
        heure = (int(heure_de_depart) + rang) % 24
        surplus = max(0.0, prod - conso)
        deficit = max(0.0, conso - prod)

        # ── charge ───────────────────────────────────────────────────────
        autorise_charge = True
        if strategie == 'decalage':
            autorise_charge = heure in heures_charge
        entree = 0.0
        if autorise_charge and surplus > 0:
            place = (capacite - etat) / eta if eta > 0 else 0.0
            entree = min(surplus, p_charge * pas, place)
            etat += entree * eta
            total_charge += entree
            surplus -= entree

        # ── décharge ─────────────────────────────────────────────────────
        besoin = deficit
        if strategie == 'peak_shaving':
            # On n'efface QUE la part du soutirage au-dessus du seuil saisi.
            besoin = max(0.0, deficit - seuil * pas)
        elif strategie == 'decalage':
            besoin = deficit if heure in heures_decharge else 0.0

        sortie = 0.0
        if besoin > 0:
            disponible = max(0.0, etat - plancher) * eta
            sortie = min(besoin, p_decharge * pas, disponible)
            etat -= (sortie / eta) if eta > 0 else 0.0
            total_decharge += sortie
            if strategie == 'peak_shaving':
                total_efface += sortie

        total_import += max(0.0, deficit - sortie)
        total_injecte += surplus
        etats.append(round(etat, 4))

    objectif = {
        'autoconso': 'Maximiser l’énergie autoconsommée (stocker le surplus '
                     'du jour pour le restituer le soir).',
        'peak_shaving': 'Effacer le soutirage au-dessus du seuil SAISI de '
                        f'{seuil} kW.',
        'backup': 'Tenir une coupure : la réserve SAISIE de '
                  f'{reserve} kWh n’est jamais entamée en fonctionnement '
                  'normal.',
        'decalage': 'Décaler la charge et la décharge sur les heures SAISIES '
                    'par l’utilisateur.',
    }[strategie]

    return {
        'strategie': strategie,
        'objectif_dimensionnant': objectif,
        'heures': len(charge),
        'charge_batterie_kwh': round(total_charge, 3),
        'decharge_batterie_kwh': round(total_decharge, 3),
        'import_reseau_kwh': round(total_import, 3),
        'surplus_injecte_kwh': round(total_injecte, 3),
        'pertes_stockage_kwh': round(
            max(0.0, total_charge - total_decharge
                - (etats[-1] - min(max(0.0, _nombre(etat_initial_kwh) or 0.0),
                                   capacite))), 3),
        'etat_de_charge_kwh': etats,
        'energie_effacee_kwh': (round(total_efface, 3)
                                if strategie == 'peak_shaving' else None),
        'parametres': {
            'capacite_utile_kwh': capacite,
            'puissance_charge_kw': p_charge,
            'puissance_decharge_kw': p_decharge,
            'rendement_ar_pct': rendement,
            'seuil_effacement_kw': seuil,
            'heures_charge': sorted(heures_charge) if strategie == 'decalage'
            else None,
            'heures_decharge': (sorted(heures_decharge)
                                if strategie == 'decalage' else None),
            'reserve_backup_kwh': reserve if strategie == 'backup' else None,
        },
    }
