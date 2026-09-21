"""CALX189 — la COURBE DE CHARGE horaire du calepinage, VE et PAC compris.

LE CONSTAT
----------
Le dépôt savait déjà TOUT faire, et ne le faisait JAMAIS :
``services/charges.py`` produit la courbe horaire d'un véhicule électrique
(``courbe_vehicule``) et d'une pompe à chaleur (``courbe_pac``, COP interpolé
par la température depuis CALX264) et sait les additionner
(``ajouter_charges``) ; ``services/consommation.py`` sait lire la courbe 24 h
saisie à l'atelier (``profil_depuis_layout``, CALX255) et ramener un import
CSV à pas variable au pas horaire (``apercu_courbe_csv``) ;
``services/profils_types.py`` sait donner la FORME d'une journée. Aucun de ces
services n'avait d'appelant : la batterie (``services/batterie.py``) et
l'autoconsommation (``services/autoconsommation.py``) attendaient une courbe
que personne n'assemblait.

Ce module est le seul assembleur. Il rend une courbe de charge horaire
POINT POUR POINT sur la série météo (8 760 ou 8 784 points) : c'est le
calendrier de la série qui commande (``annee/mois/jour/heure``, déjà en heure
locale du site — CALX59 s'en charge en amont), jamais un calendrier recalculé
ici.

LES RÈGLES POSÉES ICI
---------------------
1. **Aucune consommation n'est inventée** (D-CALX 7). Quatre sources SAISIES,
   dans cet ordre de priorité (décision fondateur Q14 du 21/09 : une valeur
   saisie prime toujours) :

   * ``layout`` — la courbe 24 h saisie dans l'atelier (CALX255) ;
   * ``import_intervalle`` — un relevé de compteur importé, déjà ramené à
     l'heure par ``consommation.apercu_courbe_csv`` ;
   * ``profil_mensuel`` — les kWh SAISIS mois par mois, mis en forme par le
     profil type quand la société en a un ;
   * ``profil_type`` — la forme de la journée, calée sur une énergie ANNUELLE
     saisie (une forme seule ne porte aucun kWh : elle ne suffit jamais).

   Aucune de ces quatre n'est disponible ⇒ le bloc ``consommation`` est OMIS,
   et avec lui la batterie et l'autoconsommation, CHACUN avec son motif. Une
   consommation supposée fausserait le taux d'autoconsommation, donc la
   batterie vendue, donc le devis : l'omission est le seul comportement juste.
2. **La provenance est PUBLIÉE** (``courbe_origine``) : on doit pouvoir dire
   au client d'où vient sa courbe sans rouvrir le calcul.
3. **Chaque charge reste visible séparément**, avec son énergie annuelle et sa
   MÉTHODE en clair. Une charge incomplète est REFUSÉE en NOMMANT le champ
   manquant (``charges.ChargeInvalide``) — jamais complétée.

LES DÉCISIONS FONDATEUR DU 21/09 QUE CE MODULE APPLIQUE
--------------------------------------------------------
* **Q2** — un véhicule seulement PRÉVU compte quand même : la charge porte
  ``planifie`` et la mention « avec votre future voiture » suit le devis.
* **Q3** — l'énergie de recharge qui tombe à des heures SANS production est
  chiffrée (``kwh_hors_production_an``) pour que le dimensionnement de la
  batterie (CALX188) la couvre ; le chiffre se lit sur la série, il n'est
  pas supposé.
* **Q4** — une fenêtre de recharge sans puissance de borne saisie ⇒ l'énergie
  est répartie UNIFORMÉMENT sur la fenêtre (mention de ``charges.py``).
* **Q10** — le chauffe-eau se déclare en (kW, plage horaire).
* **Q11** — une charge qui ne tient pas dans sa fenêtre à la puissance saisie
  est PLAFONNÉE à ce que la fenêtre peut délivrer, et le dit.
* **Q12** — climatisation et piscine ne tournent que de mai à octobre.
* **Q24** — une facture bimestrielle est ramenée au mois (÷ 2).

Module PUR : aucune base, aucun réseau, aucun prix (D-CALX 5).
"""
from __future__ import annotations

from .autoconsommation import MOTIF_SANS_COURBE as MOTIF_AUTOCONSOMMATION
from .charges import (ChargeInvalide, ajouter_charges, courbe_pac,
                      courbe_vehicule)
from .consommation import profil_depuis_layout
from .profils_types import courbe_journaliere

__all__ = ['CourbeChargeInvalide', 'MOTIF_AUTOCONSOMMATION',
           'MOTIF_BATTERIE', 'MOTIF_CONSOMMATION', 'MOIS_SAISON_CHAUDE',
           'ORIGINES', 'PERIODICITES', 'TYPES_DE_CHARGE',
           'construire_courbe_charge']

#: Les provenances possibles de la courbe de BASE, dans l'ordre de priorité
#: (décision fondateur Q14 du 21/09 : la saisie la plus proche du client
#: gagne).
ORIGINES = ('layout', 'import_intervalle', 'profil_mensuel', 'profil_type')

#: Les charges additionnelles déclarables. ``vehicule`` et ``pac`` sont
#: produites par ``services/charges.py`` ; les trois autres sont des appareils
#: déclarés en (puissance, plage horaire) — décisions fondateur Q10 et Q12 du
#: 21/09.
TYPES_DE_CHARGE = ('vehicule', 'pac', 'chauffe_eau', 'clim', 'piscine')

#: Les appareils déclarés en (kW, plage horaire) et leur libellé client.
LIBELLES_APPAREIL = {
    'chauffe_eau': 'Chauffe-eau',
    'clim': 'Climatisation',
    'piscine': 'Piscine',
}

#: Mai à octobre — la saison où climatisation et piscine tournent, TRANCHÉE
#: par le fondateur le 21/09. Ce n'est pas un coefficient inventé : c'est une
#: décision, elle est datée, et la charge peut la remplacer en saisissant
#: ``mois_actifs``.
MOIS_SAISON_CHAUDE = (5, 6, 7, 8, 9, 10)

#: Les types de charge dont la saison par défaut est MOIS_SAISON_CHAUDE.
TYPES_SAISONNIERS = ('clim', 'piscine')

#: Les périodicités de facture admises, et le diviseur qui ramène au MOIS
#: (décision fondateur Q24 du 21/09 : une facture bimestrielle se lit sur deux
#: mois, elle n'est pas un mois de consommation).
PERIODICITES = {'mensuelle': 1.0, 'bimestrielle': 2.0}

#: Le pas de la série météo PVGIS — une série qui porte le sien prime.
PAS_MINUTES_DEFAUT = 60

MOTIF_CONSOMMATION = (
    "Aucune courbe de consommation n'est disponible : ni courbe saisie dans "
    "l'atelier, ni relevé de compteur importé, ni kWh mensuels saisis, ni "
    'énergie annuelle saisie à caler sur un profil type. Le bloc '
    '« consommation » est OMIS — une consommation supposée fausserait le taux '
    "d'autoconsommation, donc la batterie proposée, donc le devis.")

MOTIF_BATTERIE = (
    "Aucune courbe de consommation n'est disponible : le dispatch de la "
    'batterie se joue heure par heure entre production et consommation — sans '
    'la seconde, aucun kWh stocké ne peut être publié. Le bloc « batterie » '
    'est OMIS.')

#: La mention portée par une charge de véhicule seulement PRÉVUE (Q2).
MENTION_VEHICULE_PLANIFIE = (
    "Véhicule seulement PRÉVU : la courbe le compte quand même, et le devis "
    'le dit — « avec votre future voiture ».')

#: La mention portée quand une charge est plafonnée par sa fenêtre (Q11).
MENTION_PLAFOND = (
    'La charge demandée ne tient pas dans la fenêtre saisie à la puissance '
    'saisie : elle est PLAFONNÉE à ce que la fenêtre peut délivrer '
    '({plafond} kWh/jour au lieu de {demande} kWh/jour), et le dit plutôt que '
    "de faire déborder l'énergie sur des heures que personne n'a déclarées.")


class CourbeChargeInvalide(ValueError):
    """Un assemblage refusé, en français et en NOMMANT le champ fautif."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


# ── lectures de la série météo (jamais un calendrier recalculé ici) ──────

def _points(serie):
    points = (serie or {}).get('points') or []
    return [point for point in points if isinstance(point, dict)]


def _heure(point):
    try:
        return int(point.get('heure') or 0) % 24
    except (TypeError, ValueError):
        return 0


def _mois(point):
    try:
        return int(point.get('mois') or 0)
    except (TypeError, ValueError):
        return 0


def _pas_minutes(serie):
    valeur = (serie or {}).get('pas_minutes')
    try:
        pas = int(valeur)
    except (TypeError, ValueError):
        return PAS_MINUTES_DEFAUT
    return pas if pas > 0 else PAS_MINUTES_DEFAUT


def _heures_contigues(points):
    """La série avance-t-elle heure par heure sans trou ?

    ``charges.courbe_pac`` place ses heures par ``(heure_de_depart + rang)``
    quand le COP dépend de la température : cette convention n'est exacte que
    sur une série contiguë. On le VÉRIFIE au lieu de l'espérer.
    """
    if not points:
        return False
    depart = _heure(points[0])
    return all(_heure(point) == (depart + rang) % 24
               for rang, point in enumerate(points))


def _colonne_production(serie, points):
    """La colonne qui dit s'il y a de la production à cette heure, ou ``None``.

    La colonne d'énergie DÉCLARÉE par la série prime (CALX142) ; à défaut,
    l'irradiance dans le plan des modules. Aucune colonne lisible ⇒ on
    s'abstient de chiffrer l'énergie « hors production » plutôt que de la
    deviner.
    """
    declaree = (serie or {}).get('colonne_energie')
    if declaree and points and declaree in points[0]:
        return declaree
    for nom in ('p_ac_kw', 'p_dc_kw', 'p_w', 'gi_w_m2'):
        if points and nom in points[0]:
            return nom
    return None


def _sans_production(points, colonne):
    """Les rangs de la série où la production est NULLE (jamais « inconnue »).

    Un point dont la colonne vaut ``None`` n'est pas un point sans soleil :
    c'est un point qu'on ne sait pas lire. Il n'entre donc dans aucun des deux
    camps.
    """
    if colonne is None:
        return None
    rangs = set()
    for rang, point in enumerate(points):
        valeur = point.get(colonne)
        if valeur is None:
            continue
        try:
            if float(valeur) <= 0.0:
                rangs.add(rang)
        except (TypeError, ValueError):
            continue
    return rangs


# ── la courbe de BASE, par ordre de priorité ─────────────────────────────

def _etaler_forme(points, forme24, energie, rangs=None):
    """Cale ``energie`` sur la FORME d'une journée, exactement.

    Les rangs concernés reçoivent ``forme24[heure]`` renormalisé pour que la
    somme rendue vaille EXACTEMENT ``energie`` : la forme donne le relief, la
    saisie donne les kWh. Forme de somme nulle ⇒ répartition uniforme sur les
    mêmes rangs, et l'appelant le dit.
    """
    concernes = list(range(len(points))) if rangs is None else sorted(rangs)
    courbe = [0.0] * len(points)
    if not concernes:
        return courbe, False
    total_forme = sum(forme24[_heure(points[rang])] for rang in concernes)
    if total_forme <= 0:
        part = float(energie) / len(concernes)
        for rang in concernes:
            courbe[rang] = part
        return courbe, True
    facteur = float(energie) / total_forme
    for rang in concernes:
        courbe[rang] = forme24[_heure(points[rang])] * facteur
    return courbe, False


def _forme_du_profil(profil_type, *, saison='annuel'):
    """La forme 24 h du profil type, ou ``None`` avec son motif."""
    if not profil_type:
        return None, ('Aucun profil type fourni : la journée est répartie '
                      'uniformément, et cette hypothèse est annoncée.')
    forme, diagnostic = courbe_journaliere(profil_type, saison=saison)
    if not forme or len(forme) != 24:
        return None, (diagnostic or {}).get('motif') or (
            'Le profil type ne porte pas de courbe exploitable pour cette '
            'saison : la journée est répartie uniformément, et cette '
            'hypothèse est annoncée.')
    return list(forme), (
        'Forme de la journée : profil type « {cle} » ({source}).'.format(
            cle=profil_type.get('cle', ''),
            source=(diagnostic or {}).get('source') or 'source non déclarée'))


def _base_layout(points, declaration, avertissements):
    """La courbe 24 h SAISIE dans l'atelier, répétée jour après jour."""
    layout = declaration.get('layout')
    if not layout:
        return None
    profil = profil_depuis_layout(layout)
    courbe24 = profil.get('courbe24')
    if courbe24 is None:
        avertissements.extend(profil.get('avertissements') or [])
        return None
    avertissements.append(
        "Courbe de base : les 24 valeurs horaires SAISIES dans l'atelier "
        '(méthode « {methode} »), répétées pour chaque jour de '
        "l'année — aucune saisonnalité n'est inventée.".format(
            methode=profil.get('methode') or 'non renseignée'))
    return [float(courbe24[_heure(point)]) for point in points]


def _base_import(points, declaration, avertissements):
    """Un relevé de compteur importé, déjà ramené à l'heure (CAL148)."""
    importe = declaration.get('import_intervalle')
    if not importe:
        return None
    valeurs = importe.get('valeurs') if isinstance(importe, dict) else importe
    if not valeurs:
        return None
    if len(valeurs) != len(points):
        raise CourbeChargeInvalide(
            'La courbe importée compte {lus} point(s) alors que la série '
            'météo en compte {attendus} : elles ne décrivent pas la même '
            "année. Elle est refusée plutôt que tronquée ou complétée.".format(
                lus=len(valeurs), attendus=len(points)),
            champ='consommation.import_intervalle.valeurs')
    origine = (importe.get('origine') if isinstance(importe, dict)
               else None) or 'non renseignée'
    avertissements.append(
        'Courbe de base : relevé de compteur importé (origine : {origine}), '
        'repris heure par heure tel qu\'il a été lu.'.format(origine=origine))
    try:
        return [max(0.0, float(valeur)) for valeur in valeurs]
    except (TypeError, ValueError):
        raise CourbeChargeInvalide(
            'La courbe importée porte au moins une valeur illisible : elle '
            "est refusée plutôt que remplacée par un zéro (un zéro se lit "
            "« ce client n'a rien consommé »).",
            champ='consommation.import_intervalle.valeurs')


def _kwh_par_mois(declaration):
    """Les kWh SAISIS mois par mois, ramenés au MOIS (Q24), ou ``{}``."""
    brut = declaration.get('profil_mensuel')
    if isinstance(brut, dict):
        lignes = brut.get('mois') or []
    else:
        lignes = brut or []
    defaut = declaration.get('periodicite') or 'mensuelle'
    mois = {}
    ramenes = []
    for rang, ligne in enumerate(lignes):
        if not isinstance(ligne, dict):
            continue
        if ligne.get('kwh') in (None, ''):
            continue
        try:
            numero = int(ligne.get('mois'))
            valeur = float(ligne.get('kwh'))
        except (TypeError, ValueError):
            raise CourbeChargeInvalide(
                'Le mois n°{rang} du profil mensuel est illisible : ni son '
                'numéro ni ses kWh ne peuvent être devinés.'.format(
                    rang=rang + 1),
                champ='consommation.profil_mensuel[{rang}]'.format(rang=rang))
        periodicite = str(ligne.get('periodicite') or defaut).lower()
        if periodicite not in PERIODICITES:
            raise CourbeChargeInvalide(
                'Périodicité inconnue pour le mois {numero} : « {lue} ». '
                'Périodicités admises : {admises}.'.format(
                    numero=numero, lue=periodicite,
                    admises=', '.join(sorted(PERIODICITES))),
                champ='consommation.profil_mensuel[{rang}].periodicite'.format(
                    rang=rang))
        diviseur = PERIODICITES[periodicite]
        if diviseur != 1.0:
            ramenes.append(str(numero))
        mois[numero] = max(0.0, valeur) / diviseur
    if ramenes:
        declaration.setdefault('_mentions', []).append(
            'Facture bimestrielle ramenée au mois (÷ 2) pour le(s) mois '
            '{mois} — décision fondateur du 21/09.'.format(
                mois=', '.join(ramenes)))
    return mois


def _base_mensuelle(points, declaration, avertissements):
    """Les kWh SAISIS mois par mois, mis en forme par le profil type."""
    par_mois = _kwh_par_mois(declaration)
    if not par_mois:
        return None
    forme, mention = _forme_du_profil(
        declaration.get('profil_type'),
        saison=declaration.get('saison') or 'annuel')
    uniforme = forme is None
    if uniforme:
        forme = [1.0] * 24
    rangs_par_mois = {}
    for rang, point in enumerate(points):
        rangs_par_mois.setdefault(_mois(point), []).append(rang)
    courbe = [0.0] * len(points)
    absents = []
    plat = False
    for numero in sorted(par_mois):
        rangs = rangs_par_mois.get(numero)
        if not rangs:
            absents.append(str(numero))
            continue
        morceau, force_plat = _etaler_forme(points, forme, par_mois[numero],
                                            rangs=rangs)
        plat = plat or force_plat
        for rang in rangs:
            courbe[rang] = morceau[rang]
    avertissements.append(
        'Courbe de base : les kWh SAISIS mois par mois ({nombre} mois '
        'renseignés sur 12), répartis à l\'intérieur de chaque mois.'.format(
            nombre=len(par_mois)))
    avertissements.append(mention)
    if uniforme or plat:
        avertissements.append(
            "À défaut de profil type exploitable, l'énergie de chaque mois "
            'est répartie UNIFORMÉMENT sur ses heures : hypothèse la plus '
            'neutre, et elle est annoncée.')
    if absents:
        avertissements.append(
            'Le(s) mois {mois} sont saisis mais absents de la série météo : '
            'leur énergie n\'est portée par aucune heure et n\'est donc pas '
            'publiée.'.format(mois=', '.join(absents)))
    for mention_q24 in declaration.pop('_mentions', []):
        avertissements.append(mention_q24)
    return courbe


def _base_profil_type(points, declaration, avertissements):
    """Une énergie ANNUELLE saisie, calée sur la forme d'un profil type."""
    annuel = declaration.get('annuel_kwh')
    if annuel in (None, ''):
        return None
    try:
        energie = float(annuel)
    except (TypeError, ValueError):
        raise CourbeChargeInvalide(
            "L'énergie annuelle saisie est illisible (reçu : "
            '{valeur!r}).'.format(valeur=annuel),
            champ='consommation.annuel_kwh')
    if energie < 0:
        raise CourbeChargeInvalide(
            'Une consommation annuelle ne peut pas être négative (reçu : '
            '{valeur}).'.format(valeur=energie),
            champ='consommation.annuel_kwh')
    forme, mention = _forme_du_profil(
        declaration.get('profil_type'),
        saison=declaration.get('saison') or 'annuel')
    uniforme = forme is None
    if uniforme:
        forme = [1.0] * 24
    courbe, plat = _etaler_forme(points, forme, energie)
    avertissements.append(
        'Courbe de base : énergie annuelle SAISIE ({energie} kWh), mise en '
        "forme sur l'année.".format(energie=round(energie, 2)))
    avertissements.append(mention)
    if uniforme or plat:
        avertissements.append(
            "À défaut de profil type exploitable, l'énergie annuelle est "
            'répartie UNIFORMÉMENT sur les heures de la série : hypothèse la '
            'plus neutre, et elle est annoncée.')
    return courbe


#: Les quatre sources de courbe de base, dans l'ordre de priorité.
_SOURCES_DE_BASE = (
    ('layout', _base_layout),
    ('import_intervalle', _base_import),
    ('profil_mensuel', _base_mensuelle),
    ('profil_type', _base_profil_type),
)


def _courbe_de_base(points, declaration, avertissements):
    """``(courbe, origine)`` de la première source SAISIE disponible."""
    for origine, fabrique in _SOURCES_DE_BASE:
        courbe = fabrique(points, declaration, avertissements)
        if courbe is not None:
            return courbe, origine
    return None, None


# ── les charges déclarées ────────────────────────────────────────────────

def _fenetre_appareil(charge, *, champ):
    heures = charge.get('heures_fonctionnement') or charge.get('plage_horaire')
    if not heures:
        raise ChargeInvalide(
            'La plage horaire est obligatoire : sans elle, on ne sait pas '
            'QUAND la charge pèse sur la courbe — et le taux '
            "d'autoconsommation en dépend entièrement.", champ=champ)
    lues = []
    for valeur in heures:
        try:
            heure = int(valeur)
        except (TypeError, ValueError):
            raise ChargeInvalide(
                'La plage horaire contient une heure illisible (reçu : '
                '{valeur!r}).'.format(valeur=valeur), champ=champ)
        if not 0 <= heure <= 23:
            raise ChargeInvalide(
                'La plage horaire contient une heure hors bornes (reçu : '
                '{heure}) : les heures se comptent de 0 à 23.'.format(
                    heure=heure), champ=champ)
        lues.append(heure)
    return sorted(set(lues))


def _courbe_appareil(charge, code):
    """Un appareil déclaré en (kW, plage horaire) — Q10 et Q12 du 21/09.

    L'énergie d'une heure active vaut la puissance SAISIE : un chauffe-eau de
    2 kW allumé trois heures consomme 6 kWh. Les deux nombres sont saisis,
    aucun n'est supposé.
    """
    champ_puissance = '{code}.puissance_kw'.format(code=code)
    puissance = charge.get('puissance_kw')
    if puissance in (None, ''):
        raise ChargeInvalide(
            'La puissance de « {libelle} » est obligatoire : ce module ne '
            'suppose aucune valeur par défaut pour une charge '
            'additionnelle.'.format(libelle=LIBELLES_APPAREIL[code]),
            champ=champ_puissance)
    try:
        kw = float(puissance)
    except (TypeError, ValueError):
        raise ChargeInvalide(
            'La puissance de « {libelle} » est illisible (reçu : '
            '{valeur!r}).'.format(libelle=LIBELLES_APPAREIL[code],
                                  valeur=puissance),
            champ=champ_puissance)
    if kw <= 0:
        raise ChargeInvalide(
            'La puissance de « {libelle} » doit être strictement positive '
            '(reçu : {kw}).'.format(libelle=LIBELLES_APPAREIL[code], kw=kw),
            champ=champ_puissance)
    heures = _fenetre_appareil(
        charge, champ='{code}.heures_fonctionnement'.format(code=code))
    courbe = [0.0] * 24
    for heure in heures:
        courbe[heure] = kw
    return {
        'type': code,
        'libelle': LIBELLES_APPAREIL[code],
        'courbe': courbe,
        'hypotheses': [
            'Puissance SAISIE ({kw} kW) appliquée sur les heures SAISIES '
            '({heures}) : l\'énergie d\'une heure active est la puissance '
            "elle-même, rien n'est supposé.".format(
                kw=kw, heures=', '.join(str(heure) for heure in heures))],
        'methode': (
            'Puissance saisie × plage horaire saisie ({nombre} h/jour).'.format(
                nombre=len(heures))),
        'heures': heures,
    }


def _plafonner(bloc, charge, code, *, champ='puissance_kw'):
    """Q11 — une charge qui déborde de sa fenêtre est PLAFONNÉE, et le dit.

    Le plafond n'est pas un chiffre inventé : c'est la puissance SAISIE
    multipliée par le nombre d'heures SAISIES. Sans puissance saisie, rien
    n'est plafonné (Q4 : l'énergie s'étale sur la fenêtre).
    """
    puissance = charge.get(champ)
    heures = bloc.get('heures') or []
    if puissance in (None, '') or not heures:
        return bloc
    nomme = '{code}.{champ}'.format(code=code, champ=champ)
    try:
        kw = float(puissance)
    except (TypeError, ValueError):
        raise ChargeInvalide(
            'La puissance de charge saisie est illisible (reçu : '
            '{valeur!r}).'.format(valeur=puissance), champ=nomme)
    if kw <= 0:
        raise ChargeInvalide(
            'La puissance de charge doit être strictement positive (reçu : '
            '{kw}).'.format(kw=kw), champ=nomme)
    plafond = kw * len(heures)
    demande = sum(bloc['courbe'])
    if demande <= plafond or demande <= 0:
        return bloc
    facteur = plafond / demande
    bloc = dict(bloc)
    bloc['courbe'] = [valeur * facteur for valeur in bloc['courbe']]
    bloc['hypotheses'] = list(bloc.get('hypotheses') or []) + [
        MENTION_PLAFOND.format(plafond=round(plafond, 3),
                               demande=round(demande, 3))]
    bloc['plafonnee'] = True
    return bloc


def _bloc_de_charge(charge, points, contigues):
    """La forme JOURNALIÈRE (ou annuelle pour la PAC à COP) d'une charge."""
    code = str(charge.get('type') or '').strip().lower()
    if code not in TYPES_DE_CHARGE:
        raise CourbeChargeInvalide(
            'Type de charge inconnu : « {code} ». Types admis : '
            '{admis}.'.format(code=code or '(vide)',
                              admis=', '.join(TYPES_DE_CHARGE)),
            champ='charges.type')

    if code == 'vehicule':
        bloc = courbe_vehicule(
            km_par_jour=charge.get('km_par_jour'),
            kwh_par_100km=charge.get('kwh_par_100km'),
            fenetre_recharge=charge.get('fenetre_recharge'),
            rendement_recharge_pct=charge.get('rendement_recharge_pct'),
            longueur=24, heure_de_depart=0)
        bloc = dict(bloc)
        bloc['heures'] = list(
            bloc['parametres'].get('fenetre_recharge') or [])
        bloc['methode'] = (
            'Kilométrage et consommation saisis, répartis uniformément sur la '
            'fenêtre de recharge saisie ({nombre} h/jour).'.format(
                nombre=len(bloc['heures'])))
        if charge.get('planifie'):
            bloc['hypotheses'] = list(bloc.get('hypotheses') or []) + [
                MENTION_VEHICULE_PLANIFIE]
        champ = ('puissance_borne_kw'
                 if charge.get('puissance_borne_kw') not in (None, '')
                 else 'puissance_kw')
        return _plafonner(bloc, charge, 'vehicule', champ=champ), False

    if code == 'pac':
        if charge.get('cop_points') is not None:
            if not contigues:
                raise CourbeChargeInvalide(
                    'Le COP par température demande une série météo contiguë '
                    "heure par heure : celle-ci ne l'est pas, aucune "
                    'température ne peut être appariée à une heure de marche.',
                    champ='pac.cop_points')
            temperatures = [point.get('t2m_c') for point in points]
            manquantes = sum(1 for valeur in temperatures if valeur is None)
            if manquantes:
                raise CourbeChargeInvalide(
                    'La série météo ne porte pas de température extérieure '
                    "sur {nombre} heure(s) : le COP par température ne peut "
                    'pas y être interpolé, et aucune température n\'est '
                    'devinée.'.format(nombre=manquantes),
                    champ='meteo.t2m_c')
            bloc = courbe_pac(
                puissance_kw=charge.get('puissance_kw'),
                cop=charge.get('cop'),
                cop_points=charge.get('cop_points'),
                temperature_horaire=temperatures,
                heures_fonctionnement=charge.get('heures_fonctionnement'),
                facteur_saison=charge.get('facteur_saison'),
                longueur=len(points),
                heure_de_depart=_heure(points[0]) if points else 0)
            bloc = dict(bloc)
            bloc['methode'] = (
                'COP interpolé linéairement entre les points saisis, à la '
                'température extérieure de chaque heure de la série météo '
                '(aucune extrapolation hors des points saisis).')
            return bloc, True
        bloc = courbe_pac(
            puissance_kw=charge.get('puissance_kw'),
            cop=charge.get('cop'),
            heures_fonctionnement=charge.get('heures_fonctionnement'),
            facteur_saison=charge.get('facteur_saison'),
            longueur=24, heure_de_depart=0)
        bloc = dict(bloc)
        bloc['heures'] = list(
            bloc['parametres'].get('heures_fonctionnement') or [])
        bloc['methode'] = (
            'Puissance thermique saisie ÷ COP saisi, réparti uniformément sur '
            'les heures de marche saisies.')
        return bloc, False

    return _courbe_appareil(charge, code), False


def _mois_actifs(charge, code):
    """Les mois où la charge tourne — Q12 du 21/09 pour clim et piscine."""
    saisis = charge.get('mois_actifs')
    if saisis:
        lus = []
        for valeur in saisis:
            try:
                numero = int(valeur)
            except (TypeError, ValueError):
                raise CourbeChargeInvalide(
                    'Un mois de la saison saisie est illisible (reçu : '
                    '{valeur!r}).'.format(valeur=valeur),
                    champ='{code}.mois_actifs'.format(code=code))
            if not 1 <= numero <= 12:
                raise CourbeChargeInvalide(
                    'Un mois de la saison saisie est hors bornes (reçu : '
                    '{numero}) : les mois se comptent de 1 à 12.'.format(
                        numero=numero),
                    champ='{code}.mois_actifs'.format(code=code))
            lus.append(numero)
        return tuple(sorted(set(lus))), True
    if code in TYPES_SAISONNIERS:
        return MOIS_SAISON_CHAUDE, False
    return None, False


def _annualiser(bloc, points, mois_actifs, deja_annuelle):
    """La courbe de la charge, POINT POUR POINT sur la série météo."""
    if deja_annuelle:
        courbe = [float(valeur) for valeur in bloc['courbe']]
    else:
        courbe24 = bloc['courbe']
        courbe = [float(courbe24[_heure(point)]) for point in points]
    if mois_actifs is not None:
        actifs = set(mois_actifs)
        courbe = [valeur if _mois(point) in actifs else 0.0
                  for valeur, point in zip(courbe, points)]
    return courbe


def _charges_annuelles(declaration, points, contigues, avertissements):
    """Les charges déclarées, chacune étendue à la série et documentée."""
    blocs = []
    for rang, charge in enumerate(declaration.get('charges') or []):
        if not isinstance(charge, dict):
            raise CourbeChargeInvalide(
                'La charge n°{rang} doit être un objet (reçu : '
                '{type}).'.format(rang=rang + 1, type=type(charge).__name__),
                champ='charges[{rang}]'.format(rang=rang))
        code = str(charge.get('type') or '').strip().lower()
        bloc, deja_annuelle = _bloc_de_charge(charge, points, contigues)
        mois_actifs, saisis = _mois_actifs(charge, code)
        courbe = _annualiser(bloc, points, mois_actifs, deja_annuelle)
        hypotheses = list(bloc.get('hypotheses') or [])
        if mois_actifs is not None:
            hypotheses.append(
                'Charge active de {debut} à {fin} ({origine}).'.format(
                    debut=min(mois_actifs), fin=max(mois_actifs),
                    origine='saison saisie' if saisis else
                    'décision fondateur du 21/09 : climatisation et piscine '
                    'tournent de mai à octobre'))
        blocs.append({
            'type': bloc.get('type') or code,
            'libelle': bloc.get('libelle') or code,
            'courbe': courbe,
            'hypotheses': hypotheses,
            'methode': bloc.get('methode') or '',
            'planifie': bool(charge.get('planifie')),
            'plafonnee': bool(bloc.get('plafonnee')),
        })
        if charge.get('planifie'):
            avertissements.append(
                '« {libelle} » est seulement PRÉVU : sa consommation est '
                'comptée et le devis le dit.'.format(
                    libelle=blocs[-1]['libelle']))
    return blocs


def _profil_mensuel_publie(points, courbe):
    """Les douze mois de la courbe ASSEMBLÉE — dérivés, jamais saisis."""
    totaux = {}
    for point, valeur in zip(points, courbe):
        numero = _mois(point)
        if 1 <= numero <= 12:
            totaux[numero] = totaux.get(numero, 0.0) + float(valeur)
    return [{'mois': numero, 'kwh': round(totaux[numero], 2)}
            for numero in sorted(totaux)]


def _energie_hors_production(courbe, rangs_sans_production):
    if rangs_sans_production is None:
        return None
    return round(sum(valeur for rang, valeur in enumerate(courbe)
                     if rang in rangs_sans_production), 2)


# ── l'entrée unique ──────────────────────────────────────────────────────

def construire_courbe_charge(serie, contexte=None, *, consommation=None):
    """La courbe de charge horaire du calepinage, alignée sur la série météo.

    Args:
        serie: la série de CALX142 (``{points, pas_minutes,
            colonne_energie}``). Ses points portent le calendrier
            (``annee/mois/jour/heure``) DÉJÀ ramené à l'heure locale du site
            (CALX59) : c'est lui qui commande, aucune heure n'est recalculée
            ici.
        contexte: le contexte de simulation (CALX5). Sa clé
            ``consommation`` porte la déclaration décrite ci-dessous.
        consommation: la déclaration, passée explicitement (tests, appel
            direct). Elle prime sur celle du contexte.

    La déclaration porte, toutes facultatives :

    * ``layout`` — le document atelier (``consumption.courbe24``, CALX255) ;
    * ``import_intervalle`` — ``{valeurs, origine}``, déjà au pas horaire ;
    * ``profil_mensuel`` — les kWh SAISIS par mois (``[{mois, kwh,
      periodicite}]``, ou le dict de ``consommation.profil_mensuel``) ;
    * ``annuel_kwh`` — l'énergie annuelle SAISIE ;
    * ``profil_type`` — un profil de ``profils_types`` (la FORME du jour) et
      ``saison`` ;
    * ``charges`` — les charges déclarées (``vehicule``, ``pac``,
      ``chauffe_eau``, ``clim``, ``piscine``).

    Returns:
        dict — ``courbe`` (la charge horaire, point pour point sur la série,
        ou ``None``), ``pas_minutes``, ``consommation`` (le bloc publié du
        contrat ``calepinage_simulation``, ou ``None``), ``omissions``
        (``consommation`` / ``batterie`` / ``autoconsommation``, chacune avec
        SON motif) et ``avertissements``.

    Raises:
        ChargeInvalide: une charge incomplète ou illisible, en NOMMANT le
            champ manquant (un véhicule sans ``km_par_jour``, par exemple).
        CourbeChargeInvalide: une déclaration incohérente avec la série
            (import d'une autre année, type de charge inconnu…), en NOMMANT
            le champ fautif.
    """
    declaration = dict(consommation if consommation is not None
                       else (contexte or {}).get('consommation') or {})
    points = _points(serie)
    avertissements = []

    if not points:
        return _omettre(
            "La série météo est vide : aucune heure sur laquelle poser une "
            'consommation. ' + MOTIF_CONSOMMATION, avertissements)

    pas_minutes = _pas_minutes(serie)
    if pas_minutes != PAS_MINUTES_DEFAUT:
        avertissements.append(
            'La série météo avance par pas de {pas} minutes : les courbes '
            'saisies au pas horaire sont lues heure par heure sur son '
            'calendrier, sans interpolation.'.format(pas=pas_minutes))

    courbe_base, origine = _courbe_de_base(points, declaration, avertissements)
    if courbe_base is None:
        return _omettre(MOTIF_CONSOMMATION, avertissements)

    contigues = _heures_contigues(points)
    charges = _charges_annuelles(declaration, points, contigues,
                                 avertissements)
    bilan = ajouter_charges(courbe_base, charges)

    colonne = _colonne_production(serie, points)
    rangs_sans_production = _sans_production(points, colonne)
    if rangs_sans_production is None and charges:
        avertissements.append(
            "Aucune colonne de production lisible sur la série : l'énergie "
            'des charges qui tombe à des heures sans soleil n\'est PAS '
            'chiffrée (elle serait devinée).')

    detail = []
    for bloc, publiee in zip(charges, bilan['charges']):
        detail.append({
            'code': bloc['type'],
            'libelle': bloc['libelle'],
            'kwh_an': publiee['energie_kwh'],
            'source': 'saisie',
            'methode': bloc['methode'],
            'planifie': bloc['planifie'],
            'plafonnee': bloc['plafonnee'],
            'kwh_hors_production_an': _energie_hors_production(
                bloc['courbe'], rangs_sans_production),
            'hypotheses': bloc['hypotheses'],
        })

    return {
        'courbe': bilan['courbe'],
        'pas_minutes': pas_minutes,
        'consommation': {
            'courbe_origine': origine,
            'pas_minutes': pas_minutes,
            'total_kwh': bilan['total_kwh'],
            'charges': detail,
            'profil_mensuel': _profil_mensuel_publie(points, bilan['courbe']),
            'total_base_kwh': bilan['total_base_kwh'],
            'total_charges_kwh': bilan['total_charges_kwh'],
            'avertissements': avertissements,
        },
        'omissions': {'consommation': '', 'batterie': '',
                      'autoconsommation': ''},
        'avertissements': avertissements,
    }


def _omettre(motif, avertissements):
    """Le bloc OMIS, et les deux blocs qui en dépendent, chacun motivé.

    La batterie et l'autoconsommation ne sont pas « oubliées » : elles sont
    OMISES parce qu'elles se calculent heure par heure CONTRE une
    consommation. Chacune porte le motif de son propre module, pour que
    l'écran dise la même chose que le service.
    """
    return {
        'courbe': None,
        'pas_minutes': None,
        'consommation': None,
        'omissions': {
            'consommation': motif,
            'batterie': MOTIF_BATTERIE,
            'autoconsommation': MOTIF_AUTOCONSOMMATION,
        },
        'avertissements': list(avertissements) + [motif],
    }
