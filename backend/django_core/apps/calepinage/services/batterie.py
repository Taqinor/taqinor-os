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
"""
from __future__ import annotations

import copy
import math

__all__ = ['COUPLAGES', 'FENETRES_MAX', 'GRANDEURS_BATTERIE', 'MOTIVATIONS',
           'SOURCES_RENDEMENT', 'STRATEGIES',
           'StrategieInvalide', 'candidates_omises', 'capacites_candidates',
           'reserve_depuis_appareils',
           'simuler_batterie', 'simuler_groupes', 'specs_batterie',
           'tranches_horaires']

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


def simuler_batterie(charge_horaire, production_horaire, *, strategie,
                     capacite_utile_kwh, puissance_charge_kw,
                     puissance_decharge_kw, rendement_ar_pct=None,
                     seuil_effacement_kw=None, heures_charge=None,
                     heures_decharge=None, fenetres=None,
                     reserve_backup_kwh=None, part_effacable_pct=None,
                     plafond_effacable_kw=None,
                     etat_initial_kwh=0.0, pas_heures=1.0,
                     heure_de_depart=0, _trace=None):
    """Fait TOURNER la batterie heure par heure selon la stratégie retenue.

    Args:
        strategie: ``autoconso`` | ``peak_shaving`` | ``backup`` |
            ``decalage``.
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
        chaque sens), ``parametres``.

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

    etat = min(max(0.0, _nombre(etat_initial_kwh) or 0.0), capacite)
    plancher = min(reserve, capacite) if strategie == 'backup' else 0.0

    etats = []
    total_charge = 0.0
    total_decharge = 0.0
    total_import = 0.0
    total_injecte = 0.0
    total_efface = 0.0
    entrees = []
    sorties = []
    deficits = []
    imports = []

    for rang, (conso, prod) in enumerate(zip(charge, production)):
        heure = (int(heure_de_depart) + rang) % 24
        surplus = max(0.0, prod - conso)
        deficit = max(0.0, conso - prod)

        # ── charge ───────────────────────────────────────────────────────
        autorise_charge = True
        cible = None
        if strategie == 'decalage':
            fenetre = _fenetre_de(fenetres_charge, heure)
            autorise_charge = fenetre is not None
            if fenetre is not None and fenetre['soc_cible_pct'] is not None:
                cible = capacite * fenetre['soc_cible_pct'] / 100.0
        entree = 0.0
        if autorise_charge and surplus > 0:
            if cible is None:
                place = (capacite - etat) / eta if eta > 0 else 0.0
            else:
                # CALX268 — la charge s'arrête à l'état de charge VISÉ.
                place = max(0.0, cible - etat) / eta if eta > 0 else 0.0
            entree = min(surplus, p_charge * pas, place)
            etat += entree * eta
            total_charge += entree
            surplus -= entree

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

        total_import += max(0.0, deficit - sortie)
        total_injecte += surplus
        etats.append(round(etat, 4))
        entrees.append(entree)
        sorties.append(sortie)
        deficits.append(deficit)
        imports.append(max(0.0, deficit - sortie))

    if isinstance(_trace, dict):
        _trace['entree'] = entrees
        _trace['sortie'] = sorties
        _trace['etat'] = etats
        _trace['import'] = imports

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
#: :func:`simuler_batterie`, hors les deux courbes (le RÉSIDU les remplace)
#: et hors la chronologie commune (``pas_heures``, ``heure_de_depart``).
_HORS_GROUPE = frozenset({'charge_horaire', 'production_horaire',
                          'pas_heures', 'heure_de_depart', '_trace'})

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


def _pointe_agregee(resultats, traces, *, deficits, pas, heure_de_depart):
    """CALX269 — la pointe de l'agrégat : avant TOUS les groupes, après TOUS.

    ``None`` partout si aucun groupe n'efface de pointe ; seuils saisis
    différents d'un groupe à l'autre ⇒ les deux pointes sont publiées, mais
    ni heures au-dessus du seuil ni dépassements (il n'y a pas UN seuil).
    """
    seuils = [resultat['parametres']['seuil_effacement_kw']
              for resultat in resultats
              if resultat['strategie'] == 'peak_shaving']
    if not seuils:
        return dict(_POINTE_ABSENTE)
    return _pointe(deficits, traces[-1]['import'], seuil=_commun(seuils),
                   pas=pas, heure_de_depart=heure_de_depart)


def _agreger(lus, resultats, traces, *, deficits, pas, heure_de_depart):
    """L'agrégat de plusieurs groupes — mêmes clés que :func:`simuler_batterie`.

    Les énergies de batterie s'additionnent (chaque groupe a tourné sur le
    résidu du précédent : aucune n'est comptée deux fois) ; l'import et
    l'injection sont ceux du DERNIER groupe, c'est-à-dire ce qui reste au
    point de livraison une fois tous les groupes passés.
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
    agregat.update({
        'strategie': strategie,
        'objectif_dimensionnant': objectif,
        'heures': dernier['heures'],
        'charge_batterie_kwh': round(
            sum(sum(trace['entree']) for trace in traces), 3),
        'decharge_batterie_kwh': round(
            sum(sum(trace['sortie']) for trace in traces), 3),
        'import_reseau_kwh': dernier['import_reseau_kwh'],
        'surplus_injecte_kwh': dernier['surplus_injecte_kwh'],
        'pertes_stockage_kwh': round(
            sum(resultat['pertes_stockage_kwh'] for resultat in resultats), 3),
        'etat_de_charge_kwh': [round(sum(etats), 4) for etats in
                               zip(*(trace['etat'] for trace in traces))],
        'energie_effacee_kwh': round(sum(efface), 3) if efface else None,
        'parametres': parametres,
    })
    agregat.update(_pointe_agregee(resultats, traces, deficits=deficits,
                                   pas=pas, heure_de_depart=heure_de_depart))
    # CALX404 — le rendement de l'agrégat : publié s'il est COMMUN, sinon
    # ``None`` champ par champ (jamais une moyenne qui flatterait le parc).
    agregat['batterie'] = {
        cle: _commun([resultat['batterie'][cle] for resultat in resultats])
        for cle in resultats[0]['batterie']}
    return agregat


def simuler_groupes(charge_horaire, production_horaire, groupes, *,
                    pas_heures=1.0, heure_de_depart=0):
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

    deficits = [max(0.0, conso - prod)
                for conso, prod in zip(charge, production)]
    conso_restante = charge_horaire
    prod_restante = production_horaire
    resultats = []
    traces = []
    for rang, ligne in enumerate(lus):
        parametres = {nom: valeur
                      for nom, valeur in ligne['declaration'].items()
                      if nom in autorises}
        trace = {}
        try:
            resultat = simuler_batterie(
                conso_restante, prod_restante, pas_heures=pas_heures,
                heure_de_depart=heure_de_depart, _trace=trace, **parametres)
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
        conso_restante = charge
        prod_restante = production

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
        pas = _nombre(pas_heures) or 1.0
        agregat = _agreger(lus, resultats, traces, deficits=deficits,
                           pas=pas if pas > 0 else 1.0,
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
