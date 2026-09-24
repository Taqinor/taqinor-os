"""CAL160 — dimensionnement HORS-RÉSEAU : J jours d'autonomie, et le risque.

LE CONSTAT
----------
``grep -rn "autonomie_jours|jours d'autonomie|SHScalc" backend --include=*.py``
= 0. ``battery_storage_sizing`` (``apps/ventes/solar_design.py``) ne connaît
qu'un secours en HEURES (``backup_hours``) : de quoi passer une coupure, pas
de quoi faire vivre un site isolé une semaine de ciel couvert. PVsyst a un
module autonome dédié (banque + régulateur + charge) et PVGIS expose
``SHScalc`` (lat, lon, peakpower, batterysize, cutoff, consumptionday —
https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/api-non-interactive-service_en).

CE QUE CE MODULE GARANTIT
-------------------------
1. **J est SAISI.** Jamais de « 3 jours par défaut » : un abri de berger et
   un relais télécom n'ont pas la même exigence, et le nombre de jours DÉCIDE
   du prix de la banque. Un J absent est refusé en nommant le champ.
2. **La DoD vient de la FICHE** (CAL153, ``specs_batterie``) : la capacité
   NOMINALE à installer est la capacité utile divisée par la profondeur de
   décharge réellement publiée par le fabricant. Une DoD supposée serait une
   banque sous-dimensionnée vendue comme suffisante.
3. **Le taux de défaillance est CALCULÉ sur la série horaire**, pas estimé :
   on fait tourner le site heure par heure SANS réseau, et l'énergie que la
   batterie n'a pas pu servir est publiée (kWh, heures, taux).
4. **Le mois le plus défavorable est IDENTIFIÉ** : c'est lui qui dimensionne
   un site isolé, jamais la moyenne annuelle.
5. **AUCUN ÉCRAN NEUF** : le résultat est publié pour le panneau pompage/site
   existant (CAL159).

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

__all__ = ['ETATS_PROTECTION', 'HorsReseauInvalide', 'SEUILS_PROTECTION',
           'banque_pour_autonomie', 'dimensionner_hors_reseau',
           'simuler_hors_reseau']

MOIS_LIBELLES = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                 'juillet', 'août', 'septembre', 'octobre', 'novembre',
                 'décembre')


class HorsReseauInvalide(ValueError):
    """Une entrée hors-réseau refusée, en français et en NOMMANT le champ."""

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


def banque_pour_autonomie(*, consommation_journaliere_kwh=None,
                          jours_autonomie=None, dod_pct=None,
                          source_dod=None, rendement_ar_pct=None):
    """La banque à installer pour tenir J jours SANS soleil.

    Args:
        consommation_journaliere_kwh: la consommation du site (kWh/jour).
        jours_autonomie: **J, SAISI** — aucun défaut n'est fabriqué.
        dod_pct: la profondeur de décharge, LUE sur la fiche (CAL153).
        source_dod: ``fiche`` ou ``hypothese`` — republié tel quel pour que
            personne ne confonde une banque calculée et une banque supposée.
        rendement_ar_pct: le rendement aller-retour publié par la fiche.
            Absent ⇒ aucune perte de stockage n'est ajoutée, et c'est DIT.

    Returns:
        dict — ``capacite_utile_kwh``, ``capacite_nominale_kwh``,
        ``jours_autonomie``, ``dod_pct``, ``source_dod``, ``mentions``.

    Raises:
        HorsReseauInvalide: J absent ou ≤ 0, consommation absente, DoD absente.
    """
    conso = _nombre(consommation_journaliere_kwh)
    jours = _nombre(jours_autonomie)
    dod = _nombre(dod_pct)

    if conso is None or conso <= 0:
        raise HorsReseauInvalide(
            'La consommation journalière du site est obligatoire : sans elle, '
            'aucune banque ne peut être dimensionnée.',
            champ='consommation_journaliere_kwh')
    if jours is None or jours <= 0:
        raise HorsReseauInvalide(
            "Le nombre de jours d'autonomie est SAISI, jamais supposé : un "
            'abri isolé et un relais télécom n’ont pas la même exigence, et '
            'ce nombre décide du prix de la banque.',
            champ='jours_autonomie')
    if dod is None or not 0 < dod <= 100:
        raise HorsReseauInvalide(
            'La profondeur de décharge doit être lue sur la fiche du pack '
            '(CAL153) : une DoD supposée donne une banque sous-dimensionnée '
            'vendue comme suffisante.', champ='dod_pct')

    utile = conso * jours
    mentions = []
    rendement = _nombre(rendement_ar_pct)
    if rendement is None:
        mentions.append(
            'Aucun rendement aller-retour publié par la fiche : aucune perte '
            'de stockage n’est ajoutée à la banque (hypothèse annoncée).')
    else:
        if not 0 < rendement <= 100:
            raise HorsReseauInvalide(
                'Le rendement aller-retour se compte en pourcentage entre 0 '
                f'et 100 (reçu : {rendement}).', champ='rendement_ar_pct')
        utile = utile / (rendement / 100.0)
        mentions.append(
            f'Banque majorée du rendement aller-retour publié ({rendement} %).')

    if source_dod == 'hypothese':
        mentions.append(
            'La profondeur de décharge employée est une HYPOTHÈSE (la fiche '
            'ne la publie pas) : la banque obtenue l’est aussi.')

    return {
        'capacite_utile_kwh': round(utile, 3),
        'capacite_nominale_kwh': round(utile / (dod / 100.0), 3),
        'jours_autonomie': jours,
        'dod_pct': dod,
        'source_dod': source_dod,
        'mentions': mentions,
    }


#: CALX272 — les quatre états de la banque sous protection, dans l'ordre.
ETATS_PROTECTION = ('normal', 'veille', 'entretien', 'arret')

#: CALX272 — les trois seuils SAISIS, du plus haut au plus bas.
SEUILS_PROTECTION = ('veille_pct', 'entretien_pct', 'arret_pct')

MOTIF_SANS_SEUILS = (
    'Aucun seuil de protection de la batterie n’est saisi (veille, recharge '
    'd’entretien, arrêt) : la banque se décharge jusqu’à vide, comportement '
    'de référence. Aucun seuil n’est supposé — ni celui d’un fabricant, ni '
    'une règle de dimensionnement d’un autre logiciel.')

MENTION_SEUILS = (
    'Seuils de protection SAISIS — veille {veille} %, recharge d’entretien '
    '{entretien} %, arrêt {arret} % de la capacité utile — lus sur l’état de '
    'charge au DÉBUT de chaque pas (schéma à trois niveaux de PV*SOL). Sous '
    'la veille, l’onduleur ne décharge plus tant que le soleil n’a pas '
    'rechargé la banque au-dessus du seuil ; l’arrêt est un plancher de '
    'décharge que l’état de charge ne franchit jamais.')

MENTION_ENTRETIEN_SANS_SOURCE_AC = (
    'Aucune source de recharge côté alternatif (groupe électrogène) n’est '
    'modélisée : les tentatives de recharge d’entretien (toutes les deux '
    'heures chez PV*SOL) ne rechargent rien ici — seule la production '
    'solaire recharge la banque.')

MENTION_ARRET = (
    'Arrêt complet contre la décharge profonde au pas n°{pas} : PV*SOL '
    'termine la simulation à ce point ; ici la banque reste COUPÉE jusqu’à '
    'la fin de la série, et toute la charge que le soleil ne sert pas '
    'directement devient une défaillance.')


def _seuils_de_protection(seuils):
    """CALX272 — ``{veille_pct, entretien_pct, arret_pct}`` vérifiés, ou None.

    Tous trois SAISIS, entre 0 et 100 % de la capacité utile, et ORDONNÉS
    (veille ≥ entretien ≥ arrêt) : un ordre incohérent est refusé en
    NOMMANT le seuil fautif.
    """
    if seuils is None:
        return None
    if not isinstance(seuils, dict):
        raise HorsReseauInvalide(
            'Les seuils de protection se déclarent {veille_pct, '
            f'entretien_pct, arret_pct}} (reçu : {seuils!r}).',
            champ='seuils')
    lus = {}
    for nom in SEUILS_PROTECTION:
        valeur = _nombre(seuils.get(nom))
        if valeur is None or not 0 <= valeur <= 100:
            raise HorsReseauInvalide(
                f'Le seuil « {nom} » est SAISI, en pourcentage de la capacité '
                f'utile entre 0 et 100 (reçu : {seuils.get(nom)!r}) : aucun '
                'seuil n’est supposé.', champ=f'seuils.{nom}')
        lus[nom] = valeur
    if lus['veille_pct'] < lus['arret_pct']:
        raise HorsReseauInvalide(
            f'Le seuil de veille ({lus["veille_pct"]} %) est sous le seuil '
            f'd’arrêt ({lus["arret_pct"]} %) : la veille protège AVANT '
            'l’arrêt, jamais après.', champ='seuils.veille_pct')
    if not lus['arret_pct'] <= lus['entretien_pct'] <= lus['veille_pct']:
        raise HorsReseauInvalide(
            f'Le seuil de recharge d’entretien ({lus["entretien_pct"]} %) doit '
            f'se situer entre l’arrêt ({lus["arret_pct"]} %) et la veille '
            f'({lus["veille_pct"]} %).', champ='seuils.entretien_pct')
    return lus


def _etat_de_protection(soc_pct, seuils):
    if soc_pct > seuils['veille_pct']:
        return 'normal'
    if soc_pct > seuils['entretien_pct']:
        return 'veille'
    if soc_pct > seuils['arret_pct']:
        return 'entretien'
    return 'arret'


def _plages(etats):
    """``{etat: [[premier_pas, dernier_pas], …]}`` — les pas CONTIGUS."""
    plages = {etat: [] for etat in ETATS_PROTECTION}
    debut = 0
    for rang in range(1, len(etats) + 1):
        if rang == len(etats) or etats[rang] != etats[debut]:
            plages[etats[debut]].append([debut, rang - 1])
            debut = rang
    return plages


def simuler_hors_reseau(charge_horaire, production_horaire, *,
                        capacite_utile_kwh, puissance_charge_kw=None,
                        puissance_decharge_kw=None, rendement_ar_pct=None,
                        mois_par_heure=None, etat_initial_kwh=None,
                        pas_heures=1.0, seuils=None):
    """Fait tourner le site SANS RÉSEAU et publie son taux de défaillance.

    Il n'y a pas de soutirage ici : ce que la production et la batterie ne
    servent pas est une DÉFAILLANCE DE CHARGE (loss of load), et c'est
    exactement le chiffre qu'un site isolé doit connaître avant d'être vendu.

    Args:
        mois_par_heure: le mois (1-12) de chaque pas, pour identifier le mois
            le plus défavorable. Absent ⇒ aucun mois n'est désigné (et on ne
            devine pas un calendrier).
        etat_initial_kwh: l'état de charge au départ. Absent ⇒ banque PLEINE,
            l'hypothèse la plus favorable — elle est ANNONCÉE pour que
            personne ne la prenne pour une mesure.
        seuils: CALX272 — ``{veille_pct, entretien_pct, arret_pct}`` SAISIS,
            en % de la capacité utile : le schéma de protection à trois
            niveaux de PV*SOL
            (https://help.valentin-software.com/pvsol/en/pages/battery-inverter-and-battery/general/),
            lu sur l'état de charge au DÉBUT de chaque pas. Au-dessus de la
            veille : service normal, décharge bornée par le plancher d'arrêt.
            Sous la veille (« transition standby ») ou sous l'entretien :
            l'onduleur ne décharge plus, seul le soleil recharge (aucune
            source AC d'entretien n'est modélisée, et c'est dit). À l'arrêt :
            la banque est COUPÉE jusqu'à la fin de la série (PV*SOL, lui,
            termine la simulation). Absents ⇒ le comportement d'aujourd'hui,
            terme à terme, et ``protection['motif']`` le DIT. Aucune règle
            de dimensionnement étrangère n'est importée : le « 4,8 kWh par
            kWc » que PV*SOL publie pour l'autonomie est REFUSÉ comme défaut.

    Returns:
        dict — ``heures``, ``consommation_kwh``, ``production_kwh``,
        ``servi_kwh``, ``defaillance_kwh``, ``heures_defaillantes``,
        ``taux_defaillance``, ``surplus_perdu_kwh``, ``etat_de_charge_kwh``,
        ``par_mois``, ``mois_le_plus_defavorable``, ``mentions``,
        ``protection`` (CALX272 — ``seuils``, ``heures_par_etat``,
        ``plages_par_etat`` ``{etat: [[premier_pas, dernier_pas]]}``,
        ``arret_au_pas`` et ``motif`` ; tout ``None`` sans seuils, avec le
        motif qui le dit).

    Raises:
        HorsReseauInvalide: courbes absentes, de longueurs différentes,
            capacité inconnue, ou seuils incomplets / hors bornes / dans un
            ordre incohérent (``seuils.<nom>``).
    """
    charge = [max(0.0, _nombre(v) or 0.0) for v in (charge_horaire or [])]
    production = [max(0.0, _nombre(v) or 0.0)
                  for v in (production_horaire or [])]
    if not charge or not production:
        raise HorsReseauInvalide(
            'La simulation hors-réseau exige les DEUX courbes horaires '
            '(consommation et production).', champ='production')
    if len(charge) != len(production):
        raise HorsReseauInvalide(
            'Les deux courbes ne décrivent pas la même période '
            f'(consommation : {len(charge)} h, production : '
            f'{len(production)} h).', champ='production')

    capacite = _nombre(capacite_utile_kwh)
    if capacite is None or capacite <= 0:
        raise HorsReseauInvalide(
            'La capacité utile de la banque est inconnue : elle se dimensionne '
            "d'abord (jours d'autonomie saisis, DoD de la fiche).",
            champ='capacite_utile_kwh')

    pas = _nombre(pas_heures) or 1.0
    if pas <= 0:
        pas = 1.0
    p_charge = _nombre(puissance_charge_kw)
    p_decharge = _nombre(puissance_decharge_kw)
    rendement = _nombre(rendement_ar_pct)
    eta = ((max(0.0, min(1.0, rendement / 100.0)) ** 0.5)
           if rendement is not None else 1.0)

    mentions = []
    etat = _nombre(etat_initial_kwh)
    if etat is None:
        etat = capacite
        mentions.append(
            'Banque supposée PLEINE au premier pas : c’est l’hypothèse la '
            'plus favorable, et elle est annoncée.')
    etat = min(max(0.0, etat), capacite)
    if rendement is None:
        mentions.append(
            'Aucun rendement aller-retour publié : le stockage est simulé '
            'sans perte (hypothèse annoncée).')

    mois = list(mois_par_heure or [])
    if mois and len(mois) != len(charge):
        raise HorsReseauInvalide(
            'La liste des mois ne couvre pas la même période que les courbes '
            f'({len(mois)} contre {len(charge)}).', champ='mois_par_heure')

    protection = _seuils_de_protection(seuils)
    plancher = (capacite * protection['arret_pct'] / 100.0
                if protection is not None else 0.0)
    coupee = False
    arret_au_pas = None
    etats_de_protection = []

    etats = []
    total_charge = 0.0
    total_production = 0.0
    total_servi = 0.0
    total_defaut = 0.0
    total_perdu = 0.0
    heures_defaut = 0
    par_mois = {}

    for rang, (conso, prod) in enumerate(zip(charge, production)):
        total_charge += conso
        total_production += prod
        direct = min(conso, prod)
        besoin = conso - direct
        surplus = prod - direct

        # CALX272 — l'état de protection se lit sur l'état de charge au
        # DÉBUT du pas ; une banque COUPÉE (arrêt) le reste.
        decharge_permise = True
        if protection is not None:
            if coupee:
                etat_du_pas = 'arret'
            else:
                etat_du_pas = _etat_de_protection(etat / capacite * 100.0,
                                                  protection)
                if etat_du_pas == 'arret':
                    coupee = True
                    arret_au_pas = rang
            etats_de_protection.append(etat_du_pas)
            decharge_permise = etat_du_pas == 'normal'

        if surplus > 0:
            place = (capacite - etat) / eta if eta > 0 else 0.0
            entree = min(surplus, place)
            if p_charge is not None:
                entree = min(entree, p_charge * pas)
            if coupee:
                entree = 0.0
            etat += entree * eta
            total_perdu += surplus - entree

        sortie = 0.0
        if besoin > 0 and decharge_permise:
            if protection is None:
                disponible = etat * eta
            else:
                disponible = max(0.0, etat - plancher) * eta
            sortie = min(besoin, disponible)
            if p_decharge is not None:
                sortie = min(sortie, p_decharge * pas)
            etat -= (sortie / eta) if eta > 0 else 0.0

        defaut = max(0.0, besoin - sortie)
        total_servi += direct + sortie
        total_defaut += defaut
        if defaut > 0:
            heures_defaut += 1
        etats.append(round(etat, 4))

        if mois:
            cle = int(mois[rang])
            bilan = par_mois.setdefault(cle, {'mois': cle,
                                              'libelle': MOIS_LIBELLES[
                                                  (cle - 1) % 12],
                                              'consommation_kwh': 0.0,
                                              'defaillance_kwh': 0.0,
                                              'heures_defaillantes': 0})
            bilan['consommation_kwh'] += conso
            bilan['defaillance_kwh'] += defaut
            if defaut > 0:
                bilan['heures_defaillantes'] += 1

    lignes_mois = []
    for cle in sorted(par_mois):
        bilan = par_mois[cle]
        conso_mois = bilan['consommation_kwh']
        bilan['taux_defaillance'] = (round(bilan['defaillance_kwh']
                                           / conso_mois, 4)
                                     if conso_mois > 0 else None)
        bilan['consommation_kwh'] = round(conso_mois, 3)
        bilan['defaillance_kwh'] = round(bilan['defaillance_kwh'], 3)
        lignes_mois.append(bilan)

    pire = None
    candidats = [ligne for ligne in lignes_mois
                 if ligne['taux_defaillance'] is not None]
    if candidats:
        pire = max(candidats, key=lambda ligne: (ligne['taux_defaillance'],
                                                 ligne['mois']))
    elif not mois:
        mentions.append(
            'Aucun mois n’accompagne la série : le mois le plus défavorable '
            'n’est PAS désigné (aucun calendrier n’est deviné).')

    if protection is None:
        bilan_protection = {'seuils': None, 'heures_par_etat': None,
                            'plages_par_etat': None, 'arret_au_pas': None,
                            'motif': MOTIF_SANS_SEUILS}
    else:
        bilan_protection = {
            'seuils': dict(protection),
            'heures_par_etat': {
                etat: sum(1 for lu in etats_de_protection if lu == etat)
                for etat in ETATS_PROTECTION},
            'plages_par_etat': _plages(etats_de_protection),
            'arret_au_pas': arret_au_pas,
            'motif': '',
        }
        mentions.append(MENTION_SEUILS.format(
            veille=f'{protection["veille_pct"]:g}',
            entretien=f'{protection["entretien_pct"]:g}',
            arret=f'{protection["arret_pct"]:g}'))
        mentions.append(MENTION_ENTRETIEN_SANS_SOURCE_AC)
        if arret_au_pas is not None:
            mentions.append(MENTION_ARRET.format(pas=arret_au_pas + 1))

    return {
        'heures': len(charge),
        'consommation_kwh': round(total_charge, 3),
        'production_kwh': round(total_production, 3),
        'servi_kwh': round(total_servi, 3),
        'defaillance_kwh': round(total_defaut, 3),
        'heures_defaillantes': heures_defaut,
        'taux_defaillance': (round(total_defaut / total_charge, 4)
                             if total_charge > 0 else None),
        'surplus_perdu_kwh': round(total_perdu, 3),
        'etat_de_charge_kwh': etats,
        'par_mois': lignes_mois,
        'mois_le_plus_defavorable': pire,
        'mentions': mentions,
        'protection': bilan_protection,
    }


def dimensionner_hors_reseau(charge_horaire, production_horaire, *,
                             jours_autonomie=None,
                             consommation_journaliere_kwh=None,
                             dod_pct=None, source_dod=None,
                             rendement_ar_pct=None, **simulation):
    """La banque POUR J jours, puis le risque RÉELLEMENT couru avec elle.

    Les deux moitiés vont ensemble : dimensionner sans simuler laisse croire
    que « J jours » suffit toujours ; simuler sans dimensionner ne dit pas
    quoi acheter.
    """
    banque = banque_pour_autonomie(
        consommation_journaliere_kwh=consommation_journaliere_kwh,
        jours_autonomie=jours_autonomie, dod_pct=dod_pct,
        source_dod=source_dod, rendement_ar_pct=rendement_ar_pct)
    resultat = simuler_hors_reseau(
        charge_horaire, production_horaire,
        capacite_utile_kwh=banque['capacite_utile_kwh'],
        rendement_ar_pct=rendement_ar_pct, **simulation)
    return {'banque': banque, 'simulation': resultat}
