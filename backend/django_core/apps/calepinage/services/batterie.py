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

PLUSIEURS GROUPES (CALX267)
---------------------------
``simuler_groupes`` fait tourner plusieurs groupes de batteries, chacun avec
son COUPLAGE déclaré (``ac`` | ``dc``, un groupe ``dc`` nomme l'onduleur
hybride qui le porte), dans l'ordre saisi et sur le résidu du précédent, et
publie chaque groupe puis l'agrégat. Contrat partagé :
``contract_samples/calepinage_batterie.json``.

CE QUE LE DISPATCH SAIT EN PLUS (CALX63)
----------------------------------------
Parité : OpenSolar (surdimensionnement DC, dégradation par débit, schémas
TOU — https://support.opensolar.com/hc/en-us/articles/12382460685455-How-OpenSolar-Models-Battery-Energy-Storage),
PVsyst (« Peak shaving: store energy when production exceeds grid injection
limits » —
https://www.pvsyst.com/help/project-design/grid-connected-system-definition/grid-systems-with-storage/index.html)
et HelioScope (dégradation par cycles —
https://help-center.helioscope.com/hc/en-us/articles/8198547156371-Energy-Storage).

* ``couplage='dc'`` : l'énergie que l'onduleur ÉCRÊTE (``ecretage_kw`` de
  CALX172, pas par pas) est offerte à la charge AVANT le surplus alternatif,
  dans la limite de la puissance de charge de fiche, et publiée
  ``ecretage_recupere_kwh``. Une batterie couplée en alternatif vit derrière
  l'onduleur : l'écrêtage ne lui est jamais offert.
* stratégie ``plafond_injection`` : seul le surplus AU-DESSUS du plafond
  d'injection SAISI au raccordement (CALX190, justification obligatoire) est
  stocké, avant d'être écrêté ; le reste est plafonné par la MÊME fonction
  que CALX190 (``autoconsommation.plafond_injection``).
* stratégie ``heures_tarif`` : la charge RÉSEAU se fait sur les heures
  étiquetées ``creuse``, la décharge est réservée aux heures ``pointe`` —
  libellés LUS dans la grille SAISIE par la société
  (``apps.parametres.selectors.tou_pour``, CALX274/275). Aucun prix n'entre
  (D5) ; sans grille, la stratégie est REFUSÉE en nommant le réglage
  (``parametres.tou_heures``) — jamais la grille de référence du dépôt.
* :func:`vieillissement_batterie` : la capacité année par année tirée des
  cycles ANNUELS du dispatch, des cycles et de la rétention de fin de vie
  PUBLIÉS par la fiche — l'un des deux absent ⇒ omis en nommant le champ,
  jamais un 80 % supposé.
"""
from __future__ import annotations

import copy
import math

__all__ = ['CHAMP_CYCLES_FICHE', 'CHAMP_EOL_FICHE', 'CHAMP_TOU_HEURES',
           'COUPLAGES', 'FENETRES_MAX', 'GRANDEURS_BATTERIE', 'MOTIVATIONS',
           'SOURCES_RENDEMENT', 'STRATEGIES',
           'StrategieInvalide', 'candidates_omises', 'capacites_candidates',
           'capacite_batterie_par_annee', 'heures_tarif_societe',
           'reserve_depuis_appareils',
           'simuler_batterie', 'simuler_groupes', 'specs_batterie',
           'tranches_horaires', 'vieillissement_batterie']

#: Les stratégies simulables. ``autoconso`` et ``backup`` existaient (côté
#: dimensionnement) ; ``peak_shaving`` et ``decalage`` sont l'apport de
#: CAL152 ; ``plafond_injection`` et ``heures_tarif`` celui de CALX63.
STRATEGIES = ('autoconso', 'peak_shaving', 'backup', 'decalage',
              'plafond_injection', 'heures_tarif')

#: Les grandeurs batterie PUBLIÉES, chacune avec sa source (CAL153).
#: ``eol_pct`` (CALX63) : la rétention de capacité publiée en fin de vie
#: garantie (``bat_retention_fin_de_vie_pct``, publiée ``eol_pct`` par le
#: sélecteur du stock, CALX60) — lue par :func:`vieillissement_batterie`,
#: jamais supposée.
GRANDEURS_BATTERIE = ('kwh_nominal', 'kwh_usable', 'dod_pct',
                      'rendement_ar_pct', 'cycles_publies',
                      'max_charge_kw', 'max_decharge_kw', 'eol_pct')


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


#: CALX268 — au plus trois fenêtres de chaque sorte (PV*SOL « Timed
#: control », fenêtres C1–C3 et D1–D3).
FENETRES_MAX = 3


def _fenetres_saisies(liste, *, sorte):
    """Les fenêtres d'une sorte (``charge`` | ``decharge``), vérifiées.

    Chaque fenêtre est ``{heures: [0..23], soc_cible_pct}`` ; une fenêtre
    qui recouvre une fenêtre PRÉCÉDENTE de la même sorte est refusée en
    nommant la seconde.
    """
    champ = f'fenetres.{sorte}'
    if not isinstance(liste, (list, tuple)) or not liste:
        raise StrategieInvalide(
            f'Les fenêtres de {sorte} sont obligatoires pour la stratégie de '
            'décalage : aucune heure n’est devinée (aucun tarif n’est connu '
            'de ce module).', champ=champ)
    if len(liste) > FENETRES_MAX:
        raise StrategieInvalide(
            f'Au plus {FENETRES_MAX} fenêtres de {sorte} sont admises '
            f'(reçu : {len(liste)}).', champ=f'{champ}[{FENETRES_MAX}]')
    lues = []
    deja = set()
    for rang, fenetre in enumerate(liste):
        nom = f'{champ}[{rang}]'
        if not isinstance(fenetre, dict):
            raise StrategieInvalide(
                f'La fenêtre « {nom} » n’est pas lisible (reçu : '
                f'{fenetre!r}).', champ=nom)
        heures = _heures(fenetre.get('heures'), champ=f'{nom}.heures')
        brute = fenetre.get('soc_cible_pct')
        soc = _nombre(brute)
        if brute not in (None, '') and (soc is None or not 0 <= soc <= 100):
            raise StrategieInvalide(
                f'L’état de charge visé de « {nom} » se compte en pourcentage '
                f'de la capacité utile, entre 0 et 100 (reçu : {brute!r}).',
                champ=f'{nom}.soc_cible_pct')
        communes = heures & deja
        if communes:
            raise StrategieInvalide(
                f'La fenêtre « {nom} » recouvre une fenêtre de {sorte} '
                f'précédente (heures {sorted(communes)}) : une heure ne suit '
                'qu’une seule consigne.', champ=nom)
        deja |= heures
        lues.append({'heures': heures, 'soc_cible_pct': soc})
    return lues


def _fenetres(fenetres, heures_charge, heures_decharge):
    """CALX268 — ``(charge, decharge)`` : les fenêtres de la commande horaire.

    Les listes d'heures d'aujourd'hui (``heures_charge`` /
    ``heures_decharge``) restent acceptées et valent UNE fenêtre sans état de
    charge visé — leurs refus sont inchangés.
    """
    if fenetres is None:
        charge = _heures(heures_charge, champ='heures_charge')
        decharge = _heures(heures_decharge, champ='heures_decharge')
        communes = charge & decharge
        if communes:
            raise StrategieInvalide(
                'Les mêmes heures sont déclarées en charge ET en décharge '
                f'({sorted(communes)}) : la batterie ne peut pas faire les '
                'deux à la fois.', champ='heures_decharge')
        return ([{'heures': charge, 'soc_cible_pct': None}],
                [{'heures': decharge, 'soc_cible_pct': None}])
    if heures_charge or heures_decharge:
        raise StrategieInvalide(
            'Des fenêtres ET des listes d’heures sont déclarées : la commande '
            'horaire se saisit d’une seule façon, jamais les deux.',
            champ='fenetres')
    if not isinstance(fenetres, dict):
        raise StrategieInvalide(
            'Les fenêtres se déclarent {charge: [...], decharge: [...]} '
            f'(reçu : {fenetres!r}).', champ='fenetres')
    charge = _fenetres_saisies(fenetres.get('charge'), sorte='charge')
    decharge = _fenetres_saisies(fenetres.get('decharge'), sorte='decharge')
    heures_de_charge = set().union(*(f['heures'] for f in charge))
    for rang, fenetre in enumerate(decharge):
        communes = fenetre['heures'] & heures_de_charge
        if communes:
            raise StrategieInvalide(
                f'La fenêtre « fenetres.decharge[{rang}] » recouvre une '
                f'fenêtre de charge (heures {sorted(communes)}) : la batterie '
                'ne peut pas faire les deux à la fois.',
                champ=f'fenetres.decharge[{rang}]')
    return charge, decharge


def _fenetre_de(fenetres, heure):
    for fenetre in fenetres:
        if heure in fenetre['heures']:
            return fenetre
    return None


def _publier_fenetres(fenetres):
    return [{'heures': sorted(fenetre['heures']),
             'soc_cible_pct': fenetre['soc_cible_pct']}
            for fenetre in fenetres]


#: CALX404 — les provenances publiables d'un rendement aller-retour.
SOURCES_RENDEMENT = ('fiche', 'hypothese', 'saisie')


def _rendement(rendement_ar_pct):
    """CALX404 — ``(rendement_pct, source)``, ou un REFUS nommant le champ.

    Accepte un nombre SAISI (``source: 'saisie'``) ou la grandeur telle que
    :func:`specs_batterie` la publie (``{valeur, source}``, source ``fiche``
    ou ``hypothese`` nommée). Absent ou non numérique ⇒ refus : une batterie
    dont on ignore le rendement n'est JAMAIS simulée sans perte.
    """
    source = 'saisie'
    valeur = rendement_ar_pct
    if isinstance(rendement_ar_pct, dict):
        valeur = rendement_ar_pct.get('valeur')
        source = rendement_ar_pct.get('source') or None
    rendement = _nombre(valeur)
    if rendement is None:
        raise StrategieInvalide(
            'Le rendement aller-retour de la batterie est inconnu : complétez '
            'la fiche produit de la batterie (« rendement aller-retour », '
            'bat_rendement_ar_pct) ou saisissez-le. Aucun rendement de 100 % '
            'n’est supposé — une batterie sans pertes n’existe pas.',
            champ='rendement_ar_pct')
    if not 0 < rendement <= 100:
        raise StrategieInvalide(
            'Le rendement aller-retour se compte en pourcentage, strictement '
            f'positif et au plus 100 (reçu : {valeur!r}).',
            champ='rendement_ar_pct')
    if source not in SOURCES_RENDEMENT:
        raise StrategieInvalide(
            'La provenance du rendement aller-retour doit être nommée '
            f'({", ".join(SOURCES_RENDEMENT)}) — reçu : {source!r}.',
            champ='rendement_ar_pct')
    return rendement, source


def reserve_depuis_appareils(appareils, *, duree_h):
    """CALX270 — la réserve de secours DÉDUITE des appareils réellement secourus.

    Parité OpenSolar, « Enter by Appliance » : chaque appareil secouru est
    SAISI avec sa puissance continue, sa puissance de pointe et sa quantité,
    et l'outil en tire la puissance continue et la puissance de pointe
    totales
    (https://support.opensolar.com/hc/en-us/articles/10632948081551-Battery-Design-Assistant-on-OpenSolar-UK-AU-US).

    AUCUN facteur de pointe par défaut : celui du dimensionnement des ventes
    (``_BATTERY_BACKUP_PEAK_FACTOR``) n'est PAS relu ici — une puissance de
    pointe absente est refusée en NOMMANT l'appareil.

    Args:
        appareils: ``[{nom, puissance_continue_kw, puissance_pointe_kw,
            quantite}]``, tout SAISI.
        duree_h: la durée de coupure à tenir, SAISIE (heures).

    Returns:
        dict — ``energie_kwh`` (Σ continue × quantité × durée),
        ``puissance_continue_kw`` (Σ continue × quantité),
        ``puissance_pointe_kw`` (Σ pointe × quantité : les démarrages
        simultanés, le cas qui fait tomber un onduleur), ``duree_h``,
        ``detail`` (une ligne par appareil).

    Raises:
        StrategieInvalide: liste vide (``appareils``), durée absente
            (``duree_h``), ou grandeur d'un appareil absente/incohérente
            (``appareils[i].<grandeur>``).
    """
    duree = _nombre(duree_h)
    if duree is None or duree <= 0:
        raise StrategieInvalide(
            'La durée de coupure à tenir est SAISIE (heures) : sans elle, '
            'aucune réserve ne se déduit des appareils.', champ='duree_h')
    if not isinstance(appareils, (list, tuple)) or not appareils:
        raise StrategieInvalide(
            'Aucun appareil secouru n’est déclaré : la réserve se déduit des '
            'appareils que la batterie doit réellement tenir.',
            champ='appareils')

    detail = []
    continue_totale = 0.0
    pointe_totale = 0.0
    for rang, appareil in enumerate(appareils):
        champ = f'appareils[{rang}]'
        if not isinstance(appareil, dict):
            raise StrategieInvalide(
                f'L’appareil n°{rang + 1} n’est pas lisible (reçu : '
                f'{appareil!r}).', champ=champ)
        nom = _texte(appareil.get('nom')) or f'Appareil {rang + 1}'
        continu = _nombre(appareil.get('puissance_continue_kw'))
        pointe = _nombre(appareil.get('puissance_pointe_kw'))
        quantite = _nombre(appareil.get('quantite'))
        if continu is None or continu <= 0:
            raise StrategieInvalide(
                f'« {nom} » : la puissance CONTINUE (kW) est à saisir — elle '
                'se lit sur la plaque de l’appareil.',
                champ=f'{champ}.puissance_continue_kw')
        if pointe is None:
            raise StrategieInvalide(
                f'« {nom} » : la puissance de POINTE (kW, au démarrage) est à '
                'saisir — aucun facteur de pointe n’est supposé.',
                champ=f'{champ}.puissance_pointe_kw')
        if pointe < continu:
            raise StrategieInvalide(
                f'« {nom} » : la puissance de pointe ({pointe} kW) ne peut '
                f'pas être inférieure à la puissance continue ({continu} kW).',
                champ=f'{champ}.puissance_pointe_kw')
        if quantite is None or quantite <= 0:
            raise StrategieInvalide(
                f'« {nom} » : la quantité secourue est à saisir.',
                champ=f'{champ}.quantite')
        continue_totale += continu * quantite
        pointe_totale += pointe * quantite
        detail.append({
            'nom': nom,
            'quantite': quantite,
            'puissance_continue_kw': continu,
            'puissance_pointe_kw': pointe,
            'energie_kwh': round(continu * quantite * duree, 3),
        })

    return {
        'energie_kwh': round(continue_totale * duree, 3),
        'puissance_continue_kw': round(continue_totale, 3),
        'puissance_pointe_kw': round(pointe_totale, 3),
        'duree_h': duree,
        'detail': detail,
    }


def _part_effacable(part_effacable_pct, plafond_effacable_kw):
    """CALX270 — ``(part, plafond)`` SAISIS, ou ``None`` (aucune borne)."""
    part = None
    if part_effacable_pct not in (None, ''):
        part = _nombre(part_effacable_pct)
        if part is None or not 0 < part <= 100:
            raise StrategieInvalide(
                'La part effaçable de la charge se compte en pourcentage, '
                f'strictement positif et au plus 100 (reçu : '
                f'{part_effacable_pct!r}).', champ='part_effacable_pct')
    plafond = None
    if plafond_effacable_kw not in (None, ''):
        plafond = _nombre(plafond_effacable_kw)
        if plafond is None or plafond <= 0:
            raise StrategieInvalide(
                'Le plafond effaçable est une puissance strictement positive '
                f'(kW) (reçu : {plafond_effacable_kw!r}).',
                champ='plafond_effacable_kw')
    return part, plafond


#: Tolérance d'arithmétique flottante — jamais un seuil métier.
_EPSILON = 1e-9

#: CALX269 — les quatre grandeurs de pointe, publiées ``None`` hors
#: effacement de pointe (aucun seuil n'a été saisi : aucune pointe « évitée »
#: ne se chiffre sans lui).
_POINTE_ABSENTE = {'pointe_avant_kw': None, 'pointe_apres_kw': None,
                   'heures_au_dessus_du_seuil': None,
                   'depassements_residuels': None}


def _pointe(deficits, imports, *, seuil, pas, heure_de_depart):
    """CALX269 — la pointe de soutirage AVANT et APRÈS effacement.

    ``deficits`` est le soutirage de chaque pas SANS batterie (kWh),
    ``imports`` celui qui reste APRÈS le dispatch ; la puissance d'un pas est
    son énergie divisée par la durée du pas. ``heures_au_dessus_du_seuil``
    compte les pas où le soutirage SANS batterie dépassait le seuil SAISI ;
    ``depassements_residuels`` liste ceux où la batterie n'a PAS suffi.
    Aucun montant n'entre ici : c'est la grandeur physique qui décide de la
    prime de puissance, jamais son prix.
    """
    avant = [deficit / pas for deficit in deficits]
    apres = [valeur / pas for valeur in imports]
    if seuil is None:
        heures = None
        depassements = None
    else:
        heures = sum(1 for puissance in avant if puissance > seuil + _EPSILON)
        depassements = []
        for rang, puissance in enumerate(apres):
            if puissance > seuil + _EPSILON:
                depassements.append({
                    'rang': rang,
                    'heure': (int(heure_de_depart) + rang) % 24,
                    'soutirage_kw': round(puissance, 3),
                    'depassement_kw': round(puissance - seuil, 3),
                })
    return {
        'pointe_avant_kw': round(max(avant), 3) if avant else None,
        'pointe_apres_kw': round(max(apres), 3) if apres else None,
        'heures_au_dessus_du_seuil': heures,
        'depassements_residuels': depassements,
    }


# ── CALX63 — couplage DC, plafond d'injection, heures du tarif ─────────────

#: Le réglage société qui porte la grille horaire — nommé comme l'écran
#: Paramètres → Tarification & ROI le saisit (CALX274/275).
CHAMP_TOU_HEURES = 'parametres.tou_heures'

#: Les deux champs du plafond d'injection — ceux de CALX190, saisis au
#: raccordement du site.
CHAMP_PLAFOND = 'plafond_injection_kw'
CHAMP_JUSTIFICATION_PLAFOND = 'plafond_injection_justification'

#: Les SEULS libellés de tranche que la stratégie ``heures_tarif`` lit :
#: charge réseau en creuse, décharge en pointe. Aucun montant n'entre.
TRANCHE_CHARGE = 'creuse'
TRANCHE_DECHARGE = 'pointe'

MOTIF_TOU_ABSENTE = (
    'La stratégie « heures du tarif » lit la grille horaire SAISIE par la '
    'société (Paramètres → Tarification & ROI, tranches horaires '
    '« tou_heures ») : aucune grille n’est saisie, la stratégie est donc '
    'REFUSÉE. Aucune grille n’est supposée — ni celle de référence du dépôt, '
    'ni une autre.')


def _libelle_tranche(valeur):
    texte = str(valeur).strip().lower() if valeur is not None else ''
    return texte or None


def _grille_tou(tou_heures):
    """CALX63 — la grille horaire SAISIE, vérifiée, ou un REFUS nommant le réglage.

    Forme de ``apps.parametres.selectors.tou_pour(company)['heures']`` : une
    liste de 24 libellés (toute l'année) ou ``{saison: [24 libellés]}``
    (CALX275). Seuls les LIBELLÉS entrent ici ; les tarifs de la grille ne
    sont jamais lus (D5).
    """
    vide = tou_heures in (None, '') or (
        isinstance(tou_heures, (list, tuple, dict)) and not tou_heures)
    if vide:
        raise StrategieInvalide(MOTIF_TOU_ABSENTE, champ=CHAMP_TOU_HEURES)
    if isinstance(tou_heures, dict):
        grille = {}
        for saison, liste in tou_heures.items():
            if not isinstance(liste, (list, tuple)) or len(liste) != 24:
                raise StrategieInvalide(
                    f'La grille horaire de la saison « {saison} » doit porter '
                    '24 libellés, un par heure (reçu : '
                    f'{liste!r}).', champ=f'{CHAMP_TOU_HEURES}.{saison}')
            grille[str(saison)] = [_libelle_tranche(valeur)
                                   for valeur in liste]
        libelles = {libelle for liste in grille.values() for libelle in liste}
    elif isinstance(tou_heures, (list, tuple)):
        if len(tou_heures) != 24:
            raise StrategieInvalide(
                'La grille horaire doit porter 24 libellés, un par heure '
                f'(reçu : {len(tou_heures)}).', champ=CHAMP_TOU_HEURES)
        grille = [_libelle_tranche(valeur) for valeur in tou_heures]
        libelles = set(grille)
    else:
        raise StrategieInvalide(
            'La grille horaire se lit en 24 libellés ou en {saison: [24 '
            f'libellés]}} (reçu : {tou_heures!r}).', champ=CHAMP_TOU_HEURES)
    if TRANCHE_DECHARGE not in libelles:
        raise StrategieInvalide(
            'La grille horaire saisie ne porte AUCUNE heure de pointe : la '
            'stratégie « heures du tarif » décharge sur les heures de pointe, '
            'elle n’a donc rien à faire.', champ=CHAMP_TOU_HEURES)
    return grille


def _mois_des_heures(valeurs, longueur):
    """Le mois (1-12) de chaque pas, ou ``None`` (mois inconnu)."""
    if valeurs is None:
        return None
    if not isinstance(valeurs, (list, tuple)) or len(valeurs) != longueur:
        raise StrategieInvalide(
            'Les mois des pas ne décrivent pas la même période que les courbes '
            f'({len(valeurs) if isinstance(valeurs, (list, tuple)) else 0} '
            f'mois pour {longueur} pas).', champ='mois_des_heures')
    mois = []
    for valeur in valeurs:
        nombre = _nombre(valeur)
        mois.append(int(nombre) if nombre is not None
                    and 1 <= int(nombre) <= 12 else None)
    return mois


def _tranches_par_pas(grille, longueur, heure_de_depart, mois):
    """``(tranches, motifs)`` — la tranche SAISIE de chaque pas, ou ``None``.

    La tranche d'une heure se résout par ``tranches_du_mois`` (CALX275 :
    saison saisie, sinon ``annuel``, sinon ``None`` avec son motif — jamais
    « pleine » supposée). Import LOCAL de ``apps.ventes.solar_design`` :
    aucun sélecteur de ``ventes`` n'expose cette résolution, et ce module
    relit déjà ce fichier de la même façon (:func:`tranches_horaires`).
    """
    from apps.ventes.solar_design import tranches_du_mois

    parmois = {}
    tranches = []
    motifs = []
    for rang in range(longueur):
        cle = mois[rang] if mois is not None else None
        if cle not in parmois:
            parmois[cle] = tranches_du_mois(grille, cle)
        ligne = parmois[cle][(int(heure_de_depart) + rang) % 24]
        tranches.append(ligne['tranche'])
        if ligne['tranche'] is None and ligne['motif'] \
                and ligne['motif'] not in motifs:
            motifs.append(ligne['motif'])
    return tranches, motifs


def _plafond_valide(plafond_kw, justification, pas):
    """CALX63 — le plafond d'injection SAISI et sa justification, vérifiés.

    La vérification est celle de CALX190 (``autoconsommation.
    plafond_injection``) — un plafond illisible, négatif ou sans
    justification y est refusé en nommant le champ ; ce refus est rendu tel
    quel. Plafond absent ⇒ refus : la stratégie n'a rien à stocker.
    """
    from apps.calepinage.services.autoconsommation import (BilanInvalide,
                                                           plafond_injection)

    if plafond_kw in (None, ''):
        raise StrategieInvalide(
            'La stratégie « plafond d’injection » stocke le surplus AU-DESSUS '
            'du plafond d’injection SAISI au raccordement (avec sa '
            'justification) : aucun plafond n’est saisi.', champ=CHAMP_PLAFOND)
    try:
        bloc = plafond_injection([], plafond_kw=plafond_kw,
                                 justification=justification, pas_heures=pas)
    except BilanInvalide as refus:
        raise StrategieInvalide(refus.motif, champ=refus.champ) from refus
    return bloc['plafond_kw'], bloc['justification']


def _ecretage_injection(surplus_restant, surplus_brut, *, plafond,
                        justification, pas):
    """CALX63 — l'injection plafonnée APRÈS stockage, et ce qu'elle écrête.

    Les DEUX écrêtages passent par la même fonction que CALX190 : celui qui
    reste après la batterie, et celui de CALX190 seul (le surplus brut, sans
    batterie) — c'est leur écart qui dit ce que la stratégie a récupéré.
    """
    from apps.calepinage.services.autoconsommation import plafond_injection

    apres = plafond_injection(surplus_restant, plafond_kw=plafond,
                              justification=justification, pas_heures=pas)
    seul = plafond_injection(surplus_brut, plafond_kw=plafond,
                             justification=justification, pas_heures=pas)
    injection = list(apres['surplus_apres_ecretage'])
    return injection, {
        'plafond_kw': plafond,
        'justification': justification,
        'energie_ecretee_kwh': apres['energie_ecretee_kwh'],
        'energie_ecretee_sans_batterie_kwh': seul['energie_ecretee_kwh'],
        'heures_ecretees': apres['heures_ecretees'],
        'injection_max_kw': (round(max(injection) / pas, 3) if injection
                             else None),
    }


def simuler_batterie(charge_horaire, production_horaire, *, strategie,
                     capacite_utile_kwh, puissance_charge_kw,
                     puissance_decharge_kw, rendement_ar_pct=None,
                     seuil_effacement_kw=None, heures_charge=None,
                     heures_decharge=None, fenetres=None,
                     reserve_backup_kwh=None, part_effacable_pct=None,
                     plafond_effacable_kw=None,
                     couplage='ac', ecretage_horaire=None,
                     plafond_injection_kw=None,
                     plafond_injection_justification='',
                     tou_heures=None, mois_des_heures=None,
                     etat_initial_kwh=0.0, pas_heures=1.0,
                     heure_de_depart=0, _trace=None):
    """Fait TOURNER la batterie heure par heure selon la stratégie retenue.

    Args:
        strategie: ``autoconso`` | ``peak_shaving`` | ``backup`` |
            ``decalage`` | ``plafond_injection`` | ``heures_tarif``.
        couplage / ecretage_horaire: CALX63 — ``couplage='dc'`` (batterie
            sur le bus continu d'un onduleur hybride) : l'énergie ÉCRÊTÉE par
            l'onduleur à chaque pas (kWh, la colonne ``ecretage_kw`` de
            CALX172 × la durée du pas) est offerte à la charge AVANT le
            surplus alternatif, dans la limite de la puissance de charge de
            fiche (et de l'état de charge visé d'une fenêtre). ``ac`` (le
            défaut, le comportement d'aujourd'hui) : l'écrêtage n'atteint
            jamais la batterie.
        plafond_injection_kw / plafond_injection_justification: CALX63 —
            SAISIS au raccordement (CALX190), obligatoires pour
            ``plafond_injection`` : seul le surplus AU-DESSUS du plafond est
            stocké, puis l'injection est plafonnée par la fonction de
            CALX190. Ils ne pilotent aucune autre stratégie.
        tou_heures / mois_des_heures: CALX63 — la grille horaire SAISIE par
            la société (:func:`heures_tarif_societe`, libellés seulement) et
            le mois de chaque pas, pour ``heures_tarif`` : charge RÉSEAU sur
            les heures ``creuse``, décharge sur les heures ``pointe`` ; le
            surplus solaire est stocké dès qu'il existe (le stocker ne
            soutire rien au réseau). Grille absente ⇒ refus
            (``parametres.tou_heures``). Un pas dont le mois n'est couvert
            par aucune saison saisie n'a pas de tranche : ni charge réseau ni
            décharge, et le motif est publié.
        seuil_effacement_kw: SAISI — obligatoire pour ``peak_shaving`` (on
            n'efface pas au-dessus d'un seuil que personne n'a choisi).
        heures_charge / heures_decharge: SAISIES — obligatoires pour
            ``decalage`` (à moins que ``fenetres`` ne les remplace) ; elles
            valent une fenêtre unique SANS état de charge visé.
        fenetres: CALX268 — la commande horaire à SOC cible (PV*SOL « Timed
            control », https://help.valentin-software.com/pvsol/en/pages/battery-system/timed-control/),
            ``{charge: [{heures, soc_cible_pct}], decharge: [{heures,
            soc_cible_pct}]}``, au plus :data:`FENETRES_MAX` de chaque, toutes
            SAISIES, pour la stratégie ``decalage``. La charge d'une fenêtre
            s'arrête à son état de charge visé ; la décharge ne descend pas
            sous le sien. La charge reste celle du SURPLUS solaire (aucune
            charge sur le réseau n'est introduite ici). Deux fenêtres qui se
            recouvrent ⇒ refus nommant la seconde (``fenetres.charge[1]``).
        reserve_backup_kwh: la réserve à ne jamais entamer, SAISIE —
            obligatoire pour ``backup``. CALX270 : elle s'accepte aussi sous
            la forme que rend :func:`reserve_depuis_appareils` (la réserve
            DÉDUITE des appareils réellement secourus), à la place du nombre
            nu — son ``energie_kwh`` devient la réserve, et le détail est
            publié sous ``parametres['reserve_appareils']``.
        part_effacable_pct / plafond_effacable_kw: CALX270 — SAISIS, ils
            bornent la part de la charge d'un pas que la batterie peut
            servir (un tableau de secours partiel ne porte pas toute la
            maison : « Load Offsettable (%) » et « Load Offsettable Cap
            (kW) » d'OpenSolar). Non saisis ⇒ aucune borne, comportement
            d'aujourd'hui.
        _trace: usage INTERNE (CALX267, :func:`simuler_groupes`) — un dict
            qui reçoit, pas par pas, l'énergie entrée (``entree``) et sortie
            (``sortie``) de la batterie. Il ne change RIEN au résultat rendu :
            c'est ce qui permet au groupe suivant de tourner sur le RÉSIDU du
            précédent sans seconde arithmétique de dispatch.

    Returns:
        dict — ``strategie``, ``objectif_dimensionnant``, ``heures``,
        ``charge_batterie_kwh``, ``decharge_batterie_kwh``,
        ``import_reseau_kwh``, ``surplus_injecte_kwh``, ``pertes_stockage_kwh``,
        ``etat_de_charge_kwh`` (série), ``energie_effacee_kwh`` (peak shaving),
        ``pointe_avant_kw``, ``pointe_apres_kw``,
        ``heures_au_dessus_du_seuil``, ``depassements_residuels`` (CALX269 —
        effacement de pointe seulement, ``None`` sinon : la pointe que la
        prime de puissance facture, avant et après la batterie, et chaque
        pas où la batterie n'a pas suffi ``{rang, heure, soutirage_kw,
        depassement_kw}``), ``batterie`` (CALX404 — ``{rendement_ar_pct,
        source, rendement_un_sens}`` : le rendement RETENU, sa provenance
        ``fiche`` | ``hypothese`` | ``saisie`` et la racine appliquée à
        chaque sens), ``parametres``. CALX63 : ``ecretage_recupere_kwh``
        (l'écrêtage stocké par un groupe DC, ``None`` hors couplage DC ou
        sans série d'écrêtage), ``charge_reseau_kwh`` (la charge sur le
        réseau des heures creuses, ``None`` hors ``heures_tarif`` ; elle est
        COMPTÉE dans ``import_reseau_kwh`` et dans ``charge_batterie_kwh``),
        ``ecretage_injection`` (``plafond_injection`` seulement :
        ``{plafond_kw, justification, energie_ecretee_kwh,
        energie_ecretee_sans_batterie_kwh, heures_ecretees,
        injection_max_kw}`` — ``surplus_injecte_kwh`` est alors l'injection
        APRÈS plafond) et ``tranches_horaires`` (``heures_tarif`` seulement :
        ``{heures_creuses, heures_pointe, heures_sans_tranche,
        motifs_sans_tranche, source}``, des nombres de PAS).

    Raises:
        StrategieInvalide: stratégie inconnue, paramètre saisi manquant,
            capacité ou puissance absente (on ne fait pas tourner une batterie
            dont on ignore la taille), rendement aller-retour absent ou non
            numérique (CALX404 — ``rendement_ar_pct`` : jamais un rendement
            de 100 % supposé ; parité OpenSolar, qui lit le rendement sur la
            fiche et en tire chaque sens par sa racine,
            https://support.opensolar.com/hc/en-us/articles/12382460685455-How-OpenSolar-Models-Battery-Energy-Storage).
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
    rendement, source_rendement = _rendement(rendement_ar_pct)
    # Rendement ALLER-RETOUR : la racine de part et d'autre, pour que le
    # produit des deux sens vaille exactement le rendement publié.
    eta = math.sqrt(rendement / 100.0)

    seuil = _nombre(seuil_effacement_kw)
    if strategie == 'peak_shaving' and (seuil is None or seuil < 0):
        raise StrategieInvalide(
            "L'effacement de pointe exige un seuil SAISI (kW) : aucun seuil "
            'n’est deviné, et ce module ne connaît aucun tarif.',
            champ='seuil_effacement_kw')
    fenetres_charge = []
    fenetres_decharge = []
    if strategie == 'decalage':
        fenetres_charge, fenetres_decharge = _fenetres(
            fenetres, heures_charge, heures_decharge)
        heures_charge = set().union(*(f['heures'] for f in fenetres_charge))
        heures_decharge = set().union(
            *(f['heures'] for f in fenetres_decharge))
    elif fenetres is not None:
        raise StrategieInvalide(
            'Les fenêtres de charge et de décharge pilotent la stratégie de '
            f'décalage, pas « {strategie} » : elles ne s’appliquent donc '
            'pas.', champ='fenetres')
    reserve_appareils = None
    if isinstance(reserve_backup_kwh, dict):
        # CALX270 — la réserve DÉDUITE des appareils secourus, telle que
        # :func:`reserve_depuis_appareils` la rend, à la place du nombre nu.
        reserve_appareils = reserve_backup_kwh
        reserve = _nombre(reserve_backup_kwh.get('energie_kwh'))
    else:
        reserve = _nombre(reserve_backup_kwh)
    if strategie == 'backup' and (reserve is None or reserve < 0):
        raise StrategieInvalide(
            'La stratégie de secours exige une réserve SAISIE (kWh) — ou les '
            'appareils secourus dont elle se déduit : la part du parc qu’on '
            'refuse d’entamer pour tenir une coupure.',
            champ='reserve_backup_kwh')
    part_effacable, plafond_effacable = _part_effacable(
        part_effacable_pct, plafond_effacable_kw)

    # ── CALX63 — couplage, écrêtage, plafond d'injection, tranches ───────
    couplage_lu = _texte(couplage).lower() or 'ac'
    if couplage_lu not in COUPLAGES:
        raise StrategieInvalide(
            'Le couplage de la batterie se déclare « ac » (derrière son '
            'propre onduleur-chargeur) ou « dc » (sur le bus continu d’un '
            f'onduleur hybride) — reçu : {couplage!r}.', champ='couplage')
    ecretage = None
    if ecretage_horaire is not None:
        ecretage = _serie(ecretage_horaire, champ='ecretage')
        if len(ecretage) != len(charge):
            raise StrategieInvalide(
                'La série d’écrêtage ne décrit pas la même période que les '
                f'courbes ({len(ecretage)} pas pour {len(charge)}).',
                champ='ecretage')
    plafond = None
    justification = ''
    if strategie == 'plafond_injection':
        plafond, justification = _plafond_valide(
            plafond_injection_kw, plafond_injection_justification, pas)
    elif plafond_injection_kw not in (None, ''):
        raise StrategieInvalide(
            'Le plafond d’injection pilote la stratégie « plafond_injection », '
            f'pas « {strategie} » : il ne s’applique donc pas ici (le bloc '
            'autoconsommation l’applique au point de livraison).',
            champ=CHAMP_PLAFOND)
    tranches = None
    motifs_tranche = []
    if strategie == 'heures_tarif':
        grille = _grille_tou(tou_heures)
        tranches, motifs_tranche = _tranches_par_pas(
            grille, len(charge), heure_de_depart,
            _mois_des_heures(mois_des_heures, len(charge)))

    etat = min(max(0.0, _nombre(etat_initial_kwh) or 0.0), capacite)
    plancher = min(reserve, capacite) if strategie == 'backup' else 0.0

    etats = []
    total_charge = 0.0
    total_decharge = 0.0
    total_import = 0.0
    total_injecte = 0.0
    total_efface = 0.0
    total_ecretage = 0.0
    total_reseau = 0.0
    entrees = []
    entrees_ecretage = []
    entrees_reseau = []
    sorties = []
    deficits = []
    imports = []
    surplus_restants = []

    for rang, (conso, prod) in enumerate(zip(charge, production)):
        heure = (int(heure_de_depart) + rang) % 24
        surplus = max(0.0, prod - conso)
        deficit = max(0.0, conso - prod)
        tranche = tranches[rang] if tranches is not None else None

        # ── charge ───────────────────────────────────────────────────────
        autorise_charge = True
        cible = None
        if strategie == 'decalage':
            fenetre = _fenetre_de(fenetres_charge, heure)
            autorise_charge = fenetre is not None
            if fenetre is not None and fenetre['soc_cible_pct'] is not None:
                cible = capacite * fenetre['soc_cible_pct'] / 100.0

        def _place():
            if cible is None:
                return (capacite - etat) / eta if eta > 0 else 0.0
            # CALX268 — la charge s'arrête à l'état de charge VISÉ.
            return max(0.0, cible - etat) / eta if eta > 0 else 0.0

        budget = p_charge * pas
        # CALX63 — couplage DC : l'écrêtage de l'onduleur est offert EN
        # PREMIER (il serait perdu), dans la limite de la puissance de charge.
        entree_ecretage = 0.0
        if (autorise_charge and couplage_lu == 'dc' and ecretage is not None
                and ecretage[rang] > 0):
            entree_ecretage = max(0.0, min(ecretage[rang], budget, _place()))
            etat += entree_ecretage * eta
            budget -= entree_ecretage
        # CALX63 — plafond d'injection : seul le surplus AU-DESSUS du plafond
        # se stocke ; le reste s'injecte sans passer par la batterie.
        stockable = surplus
        if strategie == 'plafond_injection':
            stockable = max(0.0, surplus - plafond * pas)
        entree = 0.0
        if autorise_charge and stockable > 0:
            entree = min(stockable, budget, _place())
            etat += entree * eta
            surplus -= entree
        # CALX63 — heures du tarif : la charge RÉSEAU des heures creuses,
        # avec la puissance de charge qui reste.
        entree_reseau = 0.0
        if strategie == 'heures_tarif' and tranche == TRANCHE_CHARGE:
            entree_reseau = max(0.0, min(budget - entree, _place()))
            etat += entree_reseau * eta
        total_charge += entree_ecretage + entree + entree_reseau
        total_ecretage += entree_ecretage
        total_reseau += entree_reseau

        # ── décharge ─────────────────────────────────────────────────────
        besoin = deficit
        plancher_du_pas = plancher
        if strategie == 'peak_shaving':
            # On n'efface QUE la part du soutirage au-dessus du seuil saisi.
            besoin = max(0.0, deficit - seuil * pas)
        elif strategie == 'decalage':
            fenetre = _fenetre_de(fenetres_decharge, heure)
            besoin = deficit if fenetre is not None else 0.0
            if fenetre is not None and fenetre['soc_cible_pct'] is not None:
                # CALX268 — la décharge ne descend pas sous l'état VISÉ.
                plancher_du_pas = max(
                    plancher, capacite * fenetre['soc_cible_pct'] / 100.0)
        elif strategie == 'heures_tarif':
            # CALX63 — la décharge est réservée aux heures de POINTE.
            besoin = deficit if tranche == TRANCHE_DECHARGE else 0.0
        # CALX270 — la part de la charge que ce groupe PEUT servir (tableau
        # de secours partiel) : bornée seulement si elle est SAISIE.
        if part_effacable is not None:
            besoin = min(besoin, conso * part_effacable / 100.0)
        if plafond_effacable is not None:
            besoin = min(besoin, plafond_effacable * pas)

        sortie = 0.0
        if besoin > 0:
            disponible = max(0.0, etat - plancher_du_pas) * eta
            sortie = min(besoin, p_decharge * pas, disponible)
            etat -= (sortie / eta) if eta > 0 else 0.0
            total_decharge += sortie
            if strategie == 'peak_shaving':
                total_efface += sortie

        # La charge réseau des heures creuses EST un soutirage.
        total_import += max(0.0, deficit - sortie) + entree_reseau
        total_injecte += surplus
        etats.append(round(etat, 4))
        entrees.append(entree)
        entrees_ecretage.append(entree_ecretage)
        entrees_reseau.append(entree_reseau)
        sorties.append(sortie)
        deficits.append(deficit)
        imports.append(max(0.0, deficit - sortie) + entree_reseau)
        surplus_restants.append(surplus)

    # CALX63 — plafond d'injection : l'injection APRÈS stockage est
    # plafonnée par la fonction de CALX190, et comparée à CALX190 seul.
    injections = surplus_restants
    ecretage_injection = None
    if strategie == 'plafond_injection':
        surplus_brut = [max(0.0, prod - conso)
                        for conso, prod in zip(charge, production)]
        injections, ecretage_injection = _ecretage_injection(
            surplus_restants, surplus_brut,
            plafond=plafond, justification=justification, pas=pas)
        total_injecte = sum(injections)

    if isinstance(_trace, dict):
        _trace['entree'] = entrees
        _trace['entree_ecretage'] = entrees_ecretage
        _trace['entree_reseau'] = entrees_reseau
        _trace['sortie'] = sorties
        _trace['etat'] = etats
        _trace['import'] = imports
        _trace['surplus'] = surplus_restants
        _trace['injection'] = list(injections)
        _trace['ecretage_injection'] = [
            max(0.0, avant - apres)
            for avant, apres in zip(surplus_restants, injections)]

    # CALX269 — la pointe AVANT et APRÈS effacement, lue sur la série
    # d'import que le dispatch vient de produire (aucun montant n'entre).
    pointe = (_pointe(deficits, imports, seuil=seuil, pas=pas,
                      heure_de_depart=heure_de_depart)
              if strategie == 'peak_shaving' else dict(_POINTE_ABSENTE))

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
        'plafond_injection': (
            'Stocker le surplus AU-DESSUS du plafond d’injection SAISI de '
            f'{plafond} kW avant qu’il ne soit écrêté, puis le restituer à la '
            'consommation.'),
        'heures_tarif': (
            'Charger sur les heures CREUSES et décharger sur les heures de '
            'POINTE de la grille horaire SAISIE par la société (libellés '
            'd’heures seulement — aucun montant n’entre).'),
    }[strategie]

    tarif_horaire = None
    if tranches is not None:
        tarif_horaire = {
            'heures_creuses': sum(1 for tranche in tranches
                                  if tranche == TRANCHE_CHARGE),
            'heures_pointe': sum(1 for tranche in tranches
                                 if tranche == TRANCHE_DECHARGE),
            'heures_sans_tranche': sum(1 for tranche in tranches
                                       if tranche is None),
            'motifs_sans_tranche': motifs_tranche,
            'source': CHAMP_TOU_HEURES,
        }

    return {
        'strategie': strategie,
        'objectif_dimensionnant': objectif,
        'heures': len(charge),
        'charge_batterie_kwh': round(total_charge, 3),
        'decharge_batterie_kwh': round(total_decharge, 3),
        'import_reseau_kwh': round(total_import, 3),
        'surplus_injecte_kwh': round(total_injecte, 3),
        # CALX63 — ce que le couplage DC a récupéré de l'écrêtage, et la
        # charge réseau des heures creuses (``None`` : sans objet ici).
        'ecretage_recupere_kwh': (round(total_ecretage, 3)
                                  if couplage_lu == 'dc'
                                  and ecretage is not None else None),
        'charge_reseau_kwh': (round(total_reseau, 3)
                              if strategie == 'heures_tarif' else None),
        'ecretage_injection': ecretage_injection,
        'tranches_horaires': tarif_horaire,
        'pertes_stockage_kwh': round(
            max(0.0, total_charge - total_decharge
                - (etats[-1] - min(max(0.0, _nombre(etat_initial_kwh) or 0.0),
                                   capacite))), 3),
        'etat_de_charge_kwh': etats,
        'energie_effacee_kwh': (round(total_efface, 3)
                                if strategie == 'peak_shaving' else None),
        **pointe,
        # CALX404 — le rendement RETENU et sa provenance : jamais un 100 %
        # muet ; chaque sens vaut sa racine carrée.
        'batterie': {
            'rendement_ar_pct': rendement,
            'source': source_rendement,
            'rendement_un_sens': round(eta, 6),
        },
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
            'fenetres': ({'charge': _publier_fenetres(fenetres_charge),
                          'decharge': _publier_fenetres(fenetres_decharge)}
                         if strategie == 'decalage' else None),
            'reserve_backup_kwh': reserve if strategie == 'backup' else None,
            'reserve_appareils': (reserve_appareils if strategie == 'backup'
                                  else None),
            'part_effacable_pct': part_effacable,
            'plafond_effacable_kw': plafond_effacable,
            # CALX63 — le couplage retenu et le plafond d'injection (sa
            # justification SAISIE avec lui), ``None`` hors de sa stratégie.
            'couplage': couplage_lu,
            'plafond_injection_kw': plafond,
            'plafond_injection_justification': justification or None,
        },
    }


# ── CALX267 — plusieurs groupes de batteries, chacun avec son couplage ─────

#: Les couplages déclarables d'un groupe : côté ALTERNATIF (derrière son
#: propre onduleur-chargeur) ou côté CONTINU (sur le bus DC d'un onduleur
#: hybride — qu'il faut alors nommer).
COUPLAGES = ('ac', 'dc')

#: La valeur publiée en ``agregat['strategie']`` quand les groupes ne suivent
#: pas la même stratégie : l'agrégat n'en a alors pas UNE.
STRATEGIE_PLUSIEURS = 'plusieurs'

#: Les paramètres de dispatch qu'un groupe porte lui-même — ceux de
#: :func:`simuler_batterie`, hors les deux courbes (le RÉSIDU les remplace),
#: hors la chronologie commune (``pas_heures``, ``heure_de_depart``) et hors
#: ce que le SITE porte pour tous les groupes (CALX63 : l'écrêtage de
#: l'onduleur, la grille horaire de la société, le mois des pas).
_HORS_GROUPE = frozenset({'charge_horaire', 'production_horaire',
                          'pas_heures', 'heure_de_depart', '_trace',
                          'ecretage_horaire', 'tou_heures',
                          'mois_des_heures'})

#: Les paramètres de l'agrégat qui S'ADDITIONNENT d'un groupe à l'autre —
#: les autres ne sont publiés que s'ils sont identiques partout.
_PARAMETRES_CUMULES = ('capacite_utile_kwh', 'puissance_charge_kw',
                       'puissance_decharge_kw')

MENTION_AGREGAT = '« agrégat de capacités — approximation »'


def _parametres_de_groupe():
    """``(admis, obligatoires)`` — lus sur la signature de simuler_batterie."""
    import inspect

    parametres = inspect.signature(simuler_batterie).parameters
    admis = tuple(nom for nom in parametres if nom not in _HORS_GROUPE)
    obligatoires = tuple(nom for nom in admis
                         if parametres[nom].default is inspect.Parameter.empty)
    return admis, obligatoires


def _texte(valeur):
    return str(valeur).strip() if valeur not in (None, '') else ''


def _groupes_valides(groupes):
    """Les groupes déclarés, VÉRIFIÉS avant tout dispatch."""
    if not isinstance(groupes, (list, tuple)) or not groupes:
        raise StrategieInvalide(
            'Aucun groupe de batteries n’est déclaré : il en faut au moins '
            'un pour simuler un stockage.', champ='groupes')
    lus = []
    for rang, groupe in enumerate(groupes):
        if not isinstance(groupe, dict):
            raise StrategieInvalide(
                f'Le groupe n°{rang + 1} n’est pas une déclaration lisible '
                f'(reçu : {groupe!r}).', champ=f'groupes[{rang}]')
        couplage = _texte(groupe.get('couplage')).lower()
        if couplage not in COUPLAGES:
            raise StrategieInvalide(
                f'Le couplage du groupe n°{rang + 1} doit être DÉCLARÉ : '
                '« ac » (derrière son propre onduleur-chargeur) ou « dc » '
                '(sur le bus continu d’un onduleur hybride) — reçu : '
                f'{groupe.get("couplage")!r}. Il ne se devine pas.',
                champ=f'groupes[{rang}].couplage')
        onduleur = _texte(groupe.get('onduleur_ref'))
        if couplage == 'dc' and not onduleur:
            raise StrategieInvalide(
                f'Le groupe n°{rang + 1} est couplé côté CONTINU : il vit sur '
                'le bus DC d’un onduleur hybride, qu’il faut nommer '
                '(référence de l’onduleur affecté).',
                champ=f'groupes[{rang}].onduleur_ref')
        lus.append({
            'groupe': _texte(groupe.get('groupe')) or f'Groupe {rang + 1}',
            'couplage': couplage,
            'onduleur_ref': onduleur or None,
            'modele': _texte(groupe.get('modele')) or None,
            'declaration': groupe,
        })
    return lus


def _mention_agregat(lus):
    """La mention d'approximation, ou ``None`` (un seul modèle, un groupe)."""
    if len(lus) < 2:
        return None
    sans_modele = [ligne['groupe'] for ligne in lus if not ligne['modele']]
    if sans_modele:
        return (f'{MENTION_AGREGAT} : le modèle de batterie n’est pas déclaré '
                f'pour {", ".join(f"« {nom} »" for nom in sans_modele)} — '
                'rien n’établit que les groupes portent le même modèle ; '
                'leurs rendements et leurs bornes de puissance ne '
                's’additionnent pas, les capacités et puissances cumulées de '
                'l’agrégat sont donc une approximation.')
    modeles = []
    for ligne in lus:
        if ligne['modele'] not in modeles:
            modeles.append(ligne['modele'])
    if len(modeles) < 2:
        return None
    return (f'{MENTION_AGREGAT} : les groupes portent des modèles de batterie '
            f'différents ({", ".join(modeles)}) ; leurs rendements et leurs '
            'bornes de puissance ne s’additionnent pas, les capacités et '
            'puissances cumulées de l’agrégat sont donc une approximation.')


def _commun(valeurs):
    """La valeur partagée par tous, sinon ``None`` (jamais une moyenne)."""
    premiere = valeurs[0]
    return premiere if all(valeur == premiere for valeur in valeurs) else None


def _somme(valeurs, decimales=3):
    if any(valeur is None for valeur in valeurs):
        return None
    return round(sum(valeurs), decimales)


def _pointe_agregee(resultats, imports, *, deficits, pas, heure_de_depart):
    """CALX269 — la pointe de l'agrégat : avant TOUS les groupes, après TOUS.

    ``None`` partout si aucun groupe n'efface de pointe ; seuils saisis
    différents d'un groupe à l'autre ⇒ les deux pointes sont publiées, mais
    ni heures au-dessus du seuil ni dépassements (il n'y a pas UN seuil).
    ``imports`` est le soutirage AU POINT DE LIVRAISON, pas par pas
    (:func:`_trace_agregee`).
    """
    seuils = [resultat['parametres']['seuil_effacement_kw']
              for resultat in resultats
              if resultat['strategie'] == 'peak_shaving']
    if not seuils:
        return dict(_POINTE_ABSENTE)
    return _pointe(deficits, imports, seuil=_commun(seuils),
                   pas=pas, heure_de_depart=heure_de_depart)


def _plafond_commun(resultats):
    """CALX63 — ``(plafond, justification)`` des groupes ``plafond_injection``.

    Un seul point de livraison, un seul plafond : deux groupes qui en
    déclarent deux différents sont refusés en nommant le second. Aucun
    groupe de cette stratégie ⇒ ``(None, '')``.
    """
    retenu = None
    for rang, resultat in enumerate(resultats):
        if resultat['strategie'] != 'plafond_injection':
            continue
        lu = (resultat['parametres']['plafond_injection_kw'],
              resultat['parametres']['plafond_injection_justification'])
        if retenu is None:
            retenu = lu
        elif lu != retenu:
            raise StrategieInvalide(
                'Deux groupes déclarent deux plafonds d’injection différents : '
                'le site n’a qu’un point de livraison, donc un seul plafond.',
                champ=f'groupes[{rang}].{CHAMP_PLAFOND}')
    return retenu if retenu is not None else (None, '')


def _trace_agregee(traces, *, surplus_brut, plafond, justification, pas):
    """CALX63 — les flux AU POINT DE LIVRAISON, pas par pas, tous groupes passés.

    Les entrées et sorties de batterie s'additionnent ; le soutirage est
    celui qui reste après le DERNIER groupe, plus la charge réseau des
    groupes précédents ; l'injection est le surplus qui reste après le
    dernier groupe — plafonnée, s'il y a un plafond, par la fonction de
    CALX190 appliquée au point de livraison (et non groupe par groupe).
    """
    longueur = len(traces[-1]['sortie'])

    def somme(cle):
        return [sum(trace[cle][rang] for trace in traces)
                for rang in range(longueur)]

    reseau_avant = [sum(trace['entree_reseau'][rang] for trace in traces[:-1])
                    for rang in range(longueur)]
    surplus = list(traces[-1]['surplus'])
    injection = surplus
    ecretage = None
    if plafond is not None:
        injection, ecretage = _ecretage_injection(
            surplus, surplus_brut, plafond=plafond,
            justification=justification, pas=pas)
    return {
        'entree': somme('entree'),
        'entree_ecretage': somme('entree_ecretage'),
        'entree_reseau': somme('entree_reseau'),
        'sortie': somme('sortie'),
        'etat': [round(sum(etats), 4)
                 for etats in zip(*(trace['etat'] for trace in traces))],
        'import': [valeur + avant for valeur, avant
                   in zip(traces[-1]['import'], reseau_avant)],
        'surplus': surplus,
        'injection': list(injection),
        'ecretage_injection': [max(0.0, avant - apres) for avant, apres
                               in zip(surplus, injection)],
        '_bloc_plafond': ecretage,
    }


def _somme_publiee(valeurs):
    """La somme des valeurs PUBLIÉES, ou ``None`` si aucune ne l'est."""
    lues = [valeur for valeur in valeurs if valeur is not None]
    return round(sum(lues), 3) if lues else None


def _agreger(lus, resultats, traces, agregee, *, deficits, pas,
             heure_de_depart):
    """L'agrégat de plusieurs groupes — mêmes clés que :func:`simuler_batterie`.

    Les énergies de batterie s'additionnent (chaque groupe a tourné sur le
    résidu du précédent : aucune n'est comptée deux fois) ; l'import et
    l'injection sont ceux du DERNIER groupe, c'est-à-dire ce qui reste au
    point de livraison une fois tous les groupes passés — plus, CALX63, la
    charge réseau des groupes précédents, et le plafond d'injection appliqué
    au point de livraison (``agregee`` : :func:`_trace_agregee`).
    """
    dernier = resultats[-1]
    strategies = [resultat['strategie'] for resultat in resultats]
    strategie = _commun(strategies) or STRATEGIE_PLUSIEURS
    if strategie != STRATEGIE_PLUSIEURS:
        objectif = resultats[0]['objectif_dimensionnant']
    else:
        objectif = ' ; '.join(
            f'« {ligne["groupe"]} » : {resultat["objectif_dimensionnant"]}'
            for ligne, resultat in zip(lus, resultats))

    efface = [resultat['energie_effacee_kwh'] for resultat in resultats
              if resultat['energie_effacee_kwh'] is not None]

    parametres = {}
    for nom in resultats[0]['parametres']:
        valeurs = [resultat['parametres'][nom] for resultat in resultats]
        parametres[nom] = (_somme(valeurs) if nom in _PARAMETRES_CUMULES
                           else _commun(valeurs))

    agregat = {}
    for cle in resultats[0]:
        valeurs = [resultat[cle] for resultat in resultats]
        agregat[cle] = _commun(valeurs)
    # CALX63 — la charge réseau des groupes PRÉCÉDENTS le dernier est un
    # soutirage que le dernier groupe ne voit pas : elle s'ajoute ici.
    reseau_avant = _somme_publiee([resultat['charge_reseau_kwh']
                                   for resultat in resultats[:-1]])
    import_reseau = dernier['import_reseau_kwh']
    if reseau_avant:
        import_reseau = round(import_reseau + reseau_avant, 3)
    bloc_plafond = agregee.get('_bloc_plafond')
    agregat.update({
        'strategie': strategie,
        'objectif_dimensionnant': objectif,
        'heures': dernier['heures'],
        'charge_batterie_kwh': round(
            sum(sum(trace['entree']) + sum(trace['entree_ecretage'])
                + sum(trace['entree_reseau']) for trace in traces), 3),
        'decharge_batterie_kwh': round(
            sum(sum(trace['sortie']) for trace in traces), 3),
        'import_reseau_kwh': import_reseau,
        'surplus_injecte_kwh': (round(sum(agregee['injection']), 3)
                                if bloc_plafond is not None
                                else dernier['surplus_injecte_kwh']),
        'pertes_stockage_kwh': round(
            sum(resultat['pertes_stockage_kwh'] for resultat in resultats), 3),
        'etat_de_charge_kwh': agregee['etat'],
        'energie_effacee_kwh': round(sum(efface), 3) if efface else None,
        'ecretage_recupere_kwh': _somme_publiee(
            [resultat['ecretage_recupere_kwh'] for resultat in resultats]),
        'charge_reseau_kwh': _somme_publiee(
            [resultat['charge_reseau_kwh'] for resultat in resultats]),
        'ecretage_injection': bloc_plafond,
        'parametres': parametres,
    })
    agregat.update(_pointe_agregee(resultats, agregee['import'],
                                   deficits=deficits, pas=pas,
                                   heure_de_depart=heure_de_depart))
    # CALX404 — le rendement de l'agrégat : publié s'il est COMMUN, sinon
    # ``None`` champ par champ (jamais une moyenne qui flatterait le parc).
    agregat['batterie'] = {
        cle: _commun([resultat['batterie'][cle] for resultat in resultats])
        for cle in resultats[0]['batterie']}
    return agregat


def simuler_groupes(charge_horaire, production_horaire, groupes, *,
                    pas_heures=1.0, heure_de_depart=0,
                    ecretage_horaire=None, tou_heures=None,
                    mois_des_heures=None, _trace=None):
    """CALX267 — fait tourner PLUSIEURS groupes de batteries, dans l'ordre.

    Le premier groupe tourne sur les deux courbes reçues ; chaque groupe
    suivant tourne sur le RÉSIDU du précédent — la consommation que le
    précédent n'a pas servie, la production qu'il n'a pas stockée. Aucune
    règle de dispatch n'est réécrite : chaque groupe passe par
    :func:`simuler_batterie`, tel quel.

    Parité : PV*SOL 2024 (plusieurs systèmes de batteries par projet —
    https://valentin-software.com/en/product-news-blog-en/pvsol-premium-2024-available-now/)
    et OpenSolar sur le couplage
    (https://support.opensolar.com/hc/en-us/articles/12382460685455-How-OpenSolar-Models-Battery-Energy-Storage).
    Cette fonction pose la STRUCTURE (couplage déclaré, onduleur affecté,
    agrégat) ; ce que le couplage DC change au dispatch — l'énergie écrêtée
    offerte à la charge — est traité par CALX63, sur ces groupes.

    Args:
        groupes: la liste ORDONNÉE des groupes. Chacun porte ``couplage``
            (``ac`` | ``dc``, DÉCLARÉ), ``onduleur_ref`` (OBLIGATOIRE en
            ``dc``), ``groupe`` (libellé), ``modele`` (le modèle de batterie,
            pour la mention d'approximation) et les paramètres de
            :func:`simuler_batterie` (``strategie``, ``capacite_utile_kwh``,
            puissances, rendement, seuil/heures/réserve…).
        pas_heures, heure_de_depart: la chronologie COMMUNE aux deux courbes.
        ecretage_horaire: CALX63 — l'énergie ÉCRÊTÉE par l'onduleur à chaque
            pas (kWh). Elle est offerte aux groupes ``dc``, DANS L'ORDRE, et
            chaque groupe ne voit que ce que le précédent n'a pas stocké ;
            un groupe ``ac`` ne la voit jamais.
        tou_heures, mois_des_heures: CALX63 — la grille horaire SAISIE par la
            société et le mois de chaque pas, communs à tous les groupes
            (stratégie ``heures_tarif``). Grille absente alors qu'un groupe
            suit cette stratégie ⇒ refus ``parametres.tou_heures`` (non
            préfixé : c'est un réglage de la société, pas du groupe).
        _trace: usage INTERNE (``etapes/batterie.py``) — reçoit les flux AU
            POINT DE LIVRAISON pas par pas (:func:`_trace_agregee`).

    Returns:
        dict — ``groupes`` (chaque groupe SÉPARÉMENT : ``groupe``,
        ``couplage``, ``onduleur_ref``, ``modele`` et son ``resultat``, le
        dict de :func:`simuler_batterie`), ``agregat`` (mêmes clés que
        :func:`simuler_batterie`) et ``mention_agregat``. Un SEUL groupe :
        ``agregat`` est, clé à clé, le résultat d'aujourd'hui de
        :func:`simuler_batterie` — aucune clé ajoutée ni retirée — et
        ``mention_agregat`` vaut ``None``. Deux modèles différents ⇒ la
        mention « agrégat de capacités — approximation » et sa raison, parce
        que les rendements et les bornes de puissance ne s'additionnent pas
        (même limite publiée par Aurora :
        https://help.aurorasolar.com/hc/en-us/articles/51222791731603-Running-and-interpreting-storage-simulations).

    Raises:
        StrategieInvalide: aucun groupe, couplage non déclaré, groupe DC sans
            onduleur (``groupes[i].onduleur_ref``), ou un paramètre refusé
            par :func:`simuler_batterie` — son champ est alors PRÉFIXÉ du
            groupe (``groupes[i].<champ>``).
    """
    lus = _groupes_valides(groupes)
    charge = _serie(charge_horaire, champ='consommation')
    production = _serie(production_horaire, champ='production')
    if len(charge) != len(production):
        raise StrategieInvalide(
            'Les deux courbes ne décrivent pas la même période '
            f'(consommation : {len(charge)} h, production : '
            f'{len(production)} h).', champ='production')

    autorises, obligatoires = _parametres_de_groupe()
    for rang, ligne in enumerate(lus):
        for nom in obligatoires:
            if nom not in ligne['declaration']:
                raise StrategieInvalide(
                    f'Le groupe « {ligne["groupe"]} » ne déclare pas « {nom} » '
                    ': un groupe de batteries se simule avec ses propres '
                    'grandeurs, jamais avec celles d’un voisin.',
                    champ=f'groupes[{rang}].{nom}')

    # CALX63 — ce que le SITE porte pour tous les groupes, vérifié une fois
    # et refusé SANS préfixe de groupe (ce n'est la saisie d'aucun groupe).
    ecretage_restant = None
    if ecretage_horaire is not None:
        ecretage_restant = _serie(ecretage_horaire, champ='ecretage')
        if len(ecretage_restant) != len(charge):
            raise StrategieInvalide(
                'La série d’écrêtage ne décrit pas la même période que les '
                f'courbes ({len(ecretage_restant)} pas pour {len(charge)}).',
                champ='ecretage')
    if any(ligne['declaration'].get('strategie') == 'heures_tarif'
           for ligne in lus):
        _grille_tou(tou_heures)
    mois = _mois_des_heures(mois_des_heures, len(charge))

    deficits = [max(0.0, conso - prod)
                for conso, prod in zip(charge, production)]
    surplus_brut = [max(0.0, prod - conso)
                    for conso, prod in zip(charge, production)]
    conso_restante = charge_horaire
    prod_restante = production_horaire
    resultats = []
    traces = []
    for rang, ligne in enumerate(lus):
        parametres = {nom: valeur
                      for nom, valeur in ligne['declaration'].items()
                      if nom in autorises}
        # Le couplage VÉRIFIÉ par _groupes_valides, jamais la saisie brute.
        parametres['couplage'] = ligne['couplage']
        trace = {}
        try:
            resultat = simuler_batterie(
                conso_restante, prod_restante, pas_heures=pas_heures,
                heure_de_depart=heure_de_depart,
                ecretage_horaire=ecretage_restant, tou_heures=tou_heures,
                mois_des_heures=mois, _trace=trace, **parametres)
        except StrategieInvalide as refus:
            champ = (f'groupes[{rang}].{refus.champ}' if refus.champ
                     else f'groupes[{rang}]')
            raise StrategieInvalide(
                f'Groupe « {ligne["groupe"]} » : {refus.motif}',
                champ=champ) from refus
        resultats.append(resultat)
        traces.append(trace)
        charge = [max(0.0, conso - sortie)
                  for conso, sortie in zip(charge, trace['sortie'])]
        production = [max(0.0, prod - entree)
                      for prod, entree in zip(production, trace['entree'])]
        if ecretage_restant is not None:
            ecretage_restant = [
                max(0.0, valeur - stockee) for valeur, stockee
                in zip(ecretage_restant, trace['entree_ecretage'])]
        conso_restante = charge
        prod_restante = production

    plafond, justification = _plafond_commun(resultats)
    pas_lu = _nombre(pas_heures) or 1.0
    pas_lu = pas_lu if pas_lu > 0 else 1.0
    agregee = _trace_agregee(traces, surplus_brut=surplus_brut,
                             plafond=plafond, justification=justification,
                             pas=pas_lu)
    if isinstance(_trace, dict):
        _trace.update({cle: valeur for cle, valeur in agregee.items()
                       if not cle.startswith('_')})

    publies = [{
        'groupe': ligne['groupe'],
        'couplage': ligne['couplage'],
        'onduleur_ref': ligne['onduleur_ref'],
        'modele': ligne['modele'],
        'resultat': resultat,
    } for ligne, resultat in zip(lus, resultats)]

    if len(resultats) == 1:
        agregat = copy.deepcopy(resultats[0])
    else:
        agregat = _agreger(lus, resultats, traces, agregee,
                           deficits=deficits, pas=pas_lu,
                           heure_de_depart=heure_de_depart)

    return {
        'groupes': publies,
        'agregat': agregat,
        'mention_agregat': _mention_agregat(lus),
    }


# ── CALX271 — des capacités CANDIDATES, classées par la motivation ─────────

#: Les trois motivations d'OpenSolar (Battery Design Assistant —
#: https://support.opensolar.com/hc/en-us/articles/10632948081551-Battery-Design-Assistant-on-OpenSolar-UK-AU-US),
#: chacune avec l'indicateur PHYSIQUE qui la classe. « Maximize Savings »
#: devient ici la COUVERTURE : ce module ne connaît aucun prix (D5), il dit
#: quelle capacité évite le plus de kWh importés, jamais combien elle
#: rapporte.
MOTIVATIONS = {
    'autoconso': {
        'libelle': 'Autoconsommation',
        'parite': 'Self-Consumption',
        'indicateur': 'taux_autoconsommation',
        'ordre': 'decroissant',
        'strategie': 'autoconso',
        'critere': (
            'Taux d’autoconsommation : la part de la production solaire '
            'consommée sur place, directement ou restituée par la batterie. '
            'Classement du plus élevé au plus faible ; à égalité, la plus '
            'petite capacité d’abord.'),
    },
    'couverture': {
        'libelle': 'Couverture des besoins',
        'parite': 'Maximize Savings',
        'indicateur': 'taux_couverture',
        'ordre': 'decroissant',
        'strategie': 'autoconso',
        'critere': (
            'Taux de couverture : la part de la consommation servie sans le '
            'réseau (production directe et restitution de la batterie). '
            'Aucun montant n’entre : le classement dit quelle capacité évite '
            'le plus de kWh importés, jamais combien elle rapporte. '
            'Classement du plus élevé au plus faible ; à égalité, la plus '
            'petite capacité d’abord.'),
    },
    'pointe': {
        'libelle': 'Effacement de pointe',
        'parite': 'Peak Demand Shaving',
        'indicateur': 'pointe_apres_kw',
        'ordre': 'croissant',
        'strategie': 'peak_shaving',
        'critere': (
            'Pointe de soutirage après effacement (kW), la batterie ne '
            'servant que le soutirage au-dessus du seuil SAISI de {seuil} kW. '
            'Classement de la plus basse à la plus haute ; à égalité, la '
            'plus petite capacité d’abord.'),
    },
}


def candidates_omises(motivation, motif):
    """La forme d'une comparaison OMISE — mêmes clés, aucun chiffre."""
    regle = MOTIVATIONS.get(motivation) or {}
    return {
        'motivation': motivation,
        'libelle': regle.get('libelle'),
        'indicateur': regle.get('indicateur'),
        'ordre': regle.get('ordre'),
        'critere': None,
        'strategie_simulee': regle.get('strategie'),
        'candidates': [],
        'avertissements': [],
        'motif_absence': motif,
    }


def _candidate_saisie(brute, rang, communs):
    """Une capacité candidate : un nombre SAISI, ou une fiche du stock."""
    champ = f'capacites_kwh[{rang}]'
    if isinstance(brute, dict):
        capacite = _nombre(brute.get('capacite_utile_kwh'))
        if capacite is None or capacite <= 0:
            raise StrategieInvalide(
                f'La capacité candidate n°{rang + 1} ne publie pas de '
                'capacité UTILE lisible : elle se lit sur la fiche, elle ne '
                'se suppose pas.', champ=f'{champ}.capacite_utile_kwh')
        candidate = dict(communs)
        for cle in ('puissance_charge_kw', 'puissance_decharge_kw',
                    'rendement_ar_pct'):
            if brute.get(cle) is not None:
                candidate[cle] = brute[cle]
        candidate.update({
            'libelle': _texte(brute.get('libelle')) or f'{capacite:g} kWh',
            'source': _texte(brute.get('source')) or 'saisie',
            'capacite_utile_kwh': capacite,
        })
        return candidate
    capacite = _nombre(brute)
    if capacite is None or capacite <= 0:
        raise StrategieInvalide(
            f'La capacité candidate n°{rang + 1} est illisible (reçu : '
            f'{brute!r}) : une capacité SAISIE est un nombre de kWh utiles '
            'strictement positif.', champ=champ)
    candidate = dict(communs)
    candidate.update({'libelle': f'{capacite:g} kWh', 'source': 'saisie',
                      'capacite_utile_kwh': capacite})
    return candidate


def _taux(numerateur, denominateur):
    if denominateur <= _EPSILON:
        return None
    return round(max(0.0, numerateur) / denominateur, 4)


def capacites_candidates(charge_horaire, production_horaire, *, motivation,
                         capacites_kwh, puissance_charge_kw=None,
                         puissance_decharge_kw=None, rendement_ar_pct=None,
                         seuil_effacement_kw=None, pas_heures=1.0,
                         heure_de_depart=0):
    """CALX271 — des capacités CANDIDATES classées par la motivation du client.

    Fait tourner le dispatch EXISTANT (:func:`simuler_batterie`) sur une
    LISTE de capacités SAISIES — issues du stock, jamais inventées — et les
    classe par l'indicateur de la motivation (:data:`MOTIVATIONS` :
    ``taux_autoconsommation``, ``taux_couverture`` ou ``pointe_apres_kw``).
    Aucun montant, aucun prix, aucune recommandation UNIQUE : une liste
    ordonnée avec son critère écrit en toutes lettres.

    Args:
        motivation: ``autoconso`` | ``couverture`` | ``pointe``.
        capacites_kwh: la liste des candidates — un nombre de kWh utiles
            SAISI, ou ``{libelle, capacite_utile_kwh, puissance_charge_kw,
            puissance_decharge_kw, rendement_ar_pct, source}`` lu sur une
            fiche du stock.
        puissance_charge_kw / puissance_decharge_kw / rendement_ar_pct: les
            grandeurs COMMUNES des candidates qui ne portent pas les leurs
            (rien n'est supposé : une candidate sans elles est ÉCARTÉE avec
            son motif, jamais simulée à 100 %).
        seuil_effacement_kw: SAISI — obligatoire pour ``pointe``.

    Returns:
        dict — ``motivation``, ``libelle``, ``indicateur``, ``ordre``,
        ``critere``, ``strategie_simulee``, ``candidates`` (ordonnées :
        ``rang``, ``libelle``, ``source``, ``capacite_utile_kwh``,
        ``valeur`` — l'indicateur du critère —, ``taux_autoconsommation``,
        ``taux_couverture``, ``pointe_apres_kw``, ``energie_restituee_kwh``,
        ``import_reseau_kwh``, ``motif_absence``), ``avertissements``,
        ``motif_absence``.

    Raises:
        StrategieInvalide: motivation inconnue (``motivation``), liste vide
            (``capacites_kwh``), capacité illisible (``capacites_kwh[i]``),
            seuil absent pour ``pointe`` (``seuil_effacement_kw``), courbes
            absentes ou de périodes différentes.
    """
    regle = MOTIVATIONS.get(motivation)
    if regle is None:
        raise StrategieInvalide(
            f'Motivation inconnue : « {motivation} ». Motivations admises : '
            f'{", ".join(MOTIVATIONS)}.', champ='motivation')
    if not isinstance(capacites_kwh, (list, tuple)) or not capacites_kwh:
        raise StrategieInvalide(
            'Aucune capacité candidate n’est fournie : la comparaison porte '
            'sur des capacités du stock de la société, jamais sur des '
            'capacités inventées.', champ='capacites_kwh')

    charge = _serie(charge_horaire, champ='consommation')
    production = _serie(production_horaire, champ='production')
    if not charge or not production:
        raise StrategieInvalide(
            'La comparaison de capacités exige les DEUX courbes horaires '
            '(consommation et production).', champ='production')
    if len(charge) != len(production):
        raise StrategieInvalide(
            'Les deux courbes ne décrivent pas la même période '
            f'(consommation : {len(charge)} h, production : '
            f'{len(production)} h).', champ='production')

    seuil = None
    critere = regle['critere']
    if regle['strategie'] == 'peak_shaving':
        seuil = _nombre(seuil_effacement_kw)
        if seuil is None or seuil < 0:
            raise StrategieInvalide(
                'Classer des capacités par la pointe exige un seuil '
                'd’effacement SAISI (kW) : aucun seuil n’est deviné.',
                champ='seuil_effacement_kw')
        critere = critere.format(seuil=f'{seuil:g}')

    communs = {'puissance_charge_kw': puissance_charge_kw,
               'puissance_decharge_kw': puissance_decharge_kw,
               'rendement_ar_pct': rendement_ar_pct}
    saisies = [_candidate_saisie(brute, rang, communs)
               for rang, brute in enumerate(capacites_kwh)]

    total_conso = sum(charge)
    total_prod = sum(production)
    lignes = []
    avertissements = []
    for rang, candidate in enumerate(saisies):
        ligne = {
            'libelle': candidate['libelle'],
            'source': candidate['source'],
            'capacite_utile_kwh': candidate['capacite_utile_kwh'],
            'valeur': None,
            'taux_autoconsommation': None,
            'taux_couverture': None,
            'pointe_apres_kw': None,
            'energie_restituee_kwh': None,
            'import_reseau_kwh': None,
            'motif_absence': '',
        }
        try:
            resultat = simuler_batterie(
                charge, production, strategie=regle['strategie'],
                capacite_utile_kwh=candidate['capacite_utile_kwh'],
                puissance_charge_kw=candidate['puissance_charge_kw'],
                puissance_decharge_kw=candidate['puissance_decharge_kw'],
                rendement_ar_pct=candidate['rendement_ar_pct'],
                seuil_effacement_kw=seuil, pas_heures=pas_heures,
                heure_de_depart=heure_de_depart)
        except StrategieInvalide as refus:
            ligne['motif_absence'] = (
                f'{refus.motif} (champ : capacites_kwh[{rang}].'
                f'{refus.champ}).')
            avertissements.append(
                f'« {candidate["libelle"]} » est ÉCARTÉE du classement : '
                f'{refus.motif}')
            lignes.append(ligne)
            continue
        ligne.update({
            'taux_autoconsommation': _taux(
                total_prod - resultat['surplus_injecte_kwh'], total_prod),
            'taux_couverture': _taux(
                total_conso - resultat['import_reseau_kwh'], total_conso),
            'pointe_apres_kw': resultat['pointe_apres_kw'],
            'energie_restituee_kwh': resultat['decharge_batterie_kwh'],
            'import_reseau_kwh': resultat['import_reseau_kwh'],
        })
        ligne['valeur'] = ligne[regle['indicateur']]
        lignes.append(ligne)

    signe = -1.0 if regle['ordre'] == 'decroissant' else 1.0
    classees = sorted(
        lignes, key=lambda ligne: (
            ligne['valeur'] is None,
            signe * ligne['valeur'] if ligne['valeur'] is not None else 0.0,
            ligne['capacite_utile_kwh']))

    return {
        'motivation': motivation,
        'libelle': regle['libelle'],
        'indicateur': regle['indicateur'],
        'ordre': regle['ordre'],
        'critere': critere,
        'strategie_simulee': regle['strategie'],
        'candidates': [{'rang': rang, **ligne}
                       for rang, ligne in enumerate(classees, start=1)],
        'avertissements': avertissements,
        'motif_absence': '',
    }


# ── CALX63 — la grille horaire de la SOCIÉTÉ, libellés seulement ───────────

def heures_tarif_societe(company):
    """CALX63 — les LIBELLÉS d'heures de la grille TOU saisie par la société.

    Lue par ``apps.parametres.selectors.tou_pour(company)`` (CALX274/275 —
    ``parametres`` est une app de fondation, l'import direct est admis). SEULE
    la clé ``heures`` en sort : les tarifs, la source et sa date restent dans
    ``parametres`` — aucun prix n'entre dans le dispatch (D5).

    Returns:
        La liste de 24 libellés, ou ``{saison: [24 libellés]}`` (CALX275) —
        ou ``None`` quand la société n'a rien saisi (ou sans société) : la
        stratégie ``heures_tarif`` est alors refusée en nommant
        ``parametres.tou_heures``. JAMAIS ``DEFAULT_HOUR_TRANCHES`` en repli.
    """
    if company is None:
        return None
    from apps.parametres.selectors import tou_pour

    grille = tou_pour(company)
    if not isinstance(grille, dict):
        return None
    heures = grille.get('heures')
    return copy.deepcopy(heures) if heures else None


# ── CALX63 — le vieillissement de la batterie PAR CYCLES ───────────────────

#: Les deux champs de fiche lus — sous les noms que ``specs_batterie`` publie
#: (``bat_cycles_publies`` et ``bat_retention_fin_de_vie_pct``, publiée
#: ``eol_pct`` par le sélecteur du stock, CALX60).
CHAMP_CYCLES_FICHE = 'fiche_batterie.cycles_publies'
CHAMP_EOL_FICHE = 'fiche_batterie.eol_pct'
CHAMP_CYCLES_ANNUELS = 'cycles_annuels'

MODELE_VIEILLISSEMENT = 'lineaire_par_cycles'

REFERENCE_VIEILLISSEMENT = (
    'OpenSolar — dégradation de la batterie par le débit d’énergie '
    '(https://support.opensolar.com/hc/en-us/articles/12382460685455-How-'
    'OpenSolar-Models-Battery-Energy-Storage) ; HelioScope — dégradation par '
    'profondeur de décharge et cycles '
    '(https://help-center.helioscope.com/hc/en-us/articles/8198547156371-'
    'Energy-Storage).')

MENTION_CALENDAIRE = (
    'Seul le vieillissement PAR CYCLES est publié : le vieillissement '
    'calendaire n’est pas publié par la fiche, il n’est donc pas supposé.')


def _vieillissement_omis(motif, *, champ, cycles_annuels=None,
                         cycles_fiche=None, eol_pct_fiche=None):
    return {
        'modele': None,
        'cycles_annuels': cycles_annuels,
        'cycles_fiche': cycles_fiche,
        'eol_pct_fiche': eol_pct_fiche,
        'annee_fin_de_vie': None,
        'annees': [],
        'reference': REFERENCE_VIEILLISSEMENT,
        'mention': MENTION_CALENDAIRE,
        'champ': champ,
        'motif_absence': motif,
    }


def _capacite_de_l_annee(annee, *, cycles_annuels, cycles_fiche, eol_pct):
    """``(cycles cumulés, capacité %)`` au DÉBUT de l'année ``annee``.

    La capacité va LINÉAIREMENT de 100 % (aucun cycle) à la rétention de fin
    de vie PUBLIÉE (au nombre de cycles PUBLIÉ) — les deux seuls points que
    la fiche donne. Au-delà des cycles publiés, la fiche ne dit rien : la
    capacité est ``None``, jamais extrapolée.
    """
    cumul = cycles_annuels * (annee - 1)
    if cumul > cycles_fiche + _EPSILON:
        return cumul, None
    return cumul, 100.0 - (100.0 - eol_pct) * cumul / cycles_fiche


def vieillissement_batterie(cycles_annuels, cycles_fiche, eol_pct_fiche, *,
                            horizon_annees=None):
    """CALX63 — la capacité de la batterie année par année, par ses CYCLES.

    Parité : OpenSolar (dégradation par le débit) et HelioScope (dégradation
    par cycles) — :data:`REFERENCE_VIEILLISSEMENT`. Le modèle est celui que
    les deux chiffres de la fiche définissent : la capacité décroît
    linéairement avec les cycles cumulés, de 100 % à ``eol_pct_fiche`` au
    bout de ``cycles_fiche`` cycles. L'année N se lit à son DÉBUT : l'année 1
    vaut 100 %, la capacité que le dispatch a fait tourner.

    Args:
        cycles_annuels: les cycles équivalents pleins d'UNE année, tirés du
            dispatch (énergie restituée ÷ capacité utile sur une année
            entière).
        cycles_fiche: le nombre de cycles PUBLIÉ par la fiche
            (``cycles_publies``).
        eol_pct_fiche: la rétention de fin de vie PUBLIÉE (``eol_pct``, en %
            de la capacité).
        horizon_annees: le nombre d'années à publier (l'horizon de la
            projection de production). ``None`` ⇒ jusqu'à l'année où les
            cycles publiés sont atteints.

    Returns:
        dict — ``modele``, ``cycles_annuels``, ``cycles_fiche``,
        ``eol_pct_fiche``, ``annee_fin_de_vie`` (la dernière année dont le
        début reste dans les cycles publiés), ``annees`` (``[{annee,
        cycles_cumules, capacite_batterie_pct, au_dela_fiche}]`` —
        ``capacite_batterie_pct`` ``None`` au-delà des cycles publiés),
        ``reference``, ``mention``, ``champ`` et ``motif_absence``. Cycles ou
        rétention absents de la fiche ⇒ ``annees`` vide, ``champ`` qui NOMME
        le champ de fiche manquant et son motif — jamais un 80 % supposé.
    """
    annuels = _nombre(cycles_annuels)
    vie = _nombre(cycles_fiche)
    eol = _nombre(eol_pct_fiche)
    identite = {'cycles_annuels': annuels, 'cycles_fiche': vie,
                'eol_pct_fiche': eol}

    manquants = []
    if vie is None or vie <= 0:
        manquants.append(CHAMP_CYCLES_FICHE)
    if eol is None or not 0 < eol <= 100:
        manquants.append(CHAMP_EOL_FICHE)
    if manquants:
        noms = ', '.join(f'« {nom} »' for nom in manquants)
        return _vieillissement_omis(
            'La fiche de la batterie ne publie pas ce qu’il faut pour son '
            f'vieillissement par cycles — non renseigné(s) : {noms}. La '
            'capacité année par année est OMISE : aucune durée de vie ni '
            'aucune rétention de fin de vie n’est supposée.',
            champ=manquants[0], **identite)
    if annuels is None or annuels <= 0:
        return _vieillissement_omis(
            'Les cycles annuels de la batterie ne sont pas connus : ils se '
            'lisent sur le dispatch d’une année ENTIÈRE (énergie restituée ÷ '
            'capacité utile). La capacité année par année est OMISE.',
            champ=CHAMP_CYCLES_ANNUELS, **identite)

    fin_de_vie = int(math.floor(vie / annuels + _EPSILON)) + 1
    horizon = None
    if horizon_annees is not None:
        lu = _nombre(horizon_annees)
        if lu is None or lu < 1:
            raise StrategieInvalide(
                'L’horizon du vieillissement se compte en années entières, au '
                f'moins une (reçu : {horizon_annees!r}).',
                champ='horizon_annees')
        horizon = int(lu)
    annees = []
    for annee in range(1, (horizon or fin_de_vie) + 1):
        cumul, capacite = _capacite_de_l_annee(
            annee, cycles_annuels=annuels, cycles_fiche=vie, eol_pct=eol)
        annees.append({
            'annee': annee,
            'cycles_cumules': round(cumul, 1),
            'capacite_batterie_pct': (round(capacite, 2)
                                      if capacite is not None else None),
            'au_dela_fiche': capacite is None,
        })
    return {
        'modele': MODELE_VIEILLISSEMENT,
        **identite,
        'annee_fin_de_vie': fin_de_vie,
        'annees': annees,
        'reference': REFERENCE_VIEILLISSEMENT,
        'mention': MENTION_CALENDAIRE,
        'champ': '',
        'motif_absence': '',
    }


def capacite_batterie_par_annee(annees, vieillissement):
    """CALX63 — chaque ligne annuelle, COPIÉE, avec sa ``capacite_batterie_pct``.

    ``annees`` : les lignes de la projection pluriannuelle
    (``etapes/vieillissement.py::tableau_pluriannuel``, ``{annee: rang,
    …}``) ; ``vieillissement`` : ce que rend :func:`vieillissement_batterie`.
    La capacité de chaque ligne se calcule par le MÊME modèle (jamais par
    une recherche dans un autre tableau) ; vieillissement omis ou année
    au-delà des cycles publiés ⇒ ``None``. Les lignes reçues ne sont jamais
    modifiées.
    """
    publiable = (isinstance(vieillissement, dict)
                 and vieillissement.get('modele') == MODELE_VIEILLISSEMENT)
    lignes = []
    for ligne in annees or []:
        copie = dict(ligne) if isinstance(ligne, dict) else {'annee': ligne}
        capacite = None
        rang = _nombre(copie.get('annee'))
        if publiable and rang is not None and rang >= 1:
            _cumul, valeur = _capacite_de_l_annee(
                int(rang), cycles_annuels=vieillissement['cycles_annuels'],
                cycles_fiche=vieillissement['cycles_fiche'],
                eol_pct=vieillissement['eol_pct_fiche'])
            capacite = round(valeur, 2) if valeur is not None else None
        copie['capacite_batterie_pct'] = capacite
        lignes.append(copie)
    return lignes
