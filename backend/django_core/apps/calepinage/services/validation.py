"""CALX195 — L'ÉCART INFORMATIF entre notre chaîne et PVGIS lui-même.

CE QUI MANQUAIT
----------------
Le dépôt possède DEUX chemins vers une production PVGIS —
``services/pvgis_serie.py`` (``seriescalc``) et
``apps/parametres/pvgis_profils.py`` (``PVcalc`` mensuel, employé par le
pompage) — et rien, nulle part, ne compare jamais leurs résultats à ceux de
notre propre chaîne de pertes. Le risque de double comptage thermique
(l'audit ``a3`` §3.1) n'est donc tranché par aucun test : notre cascade peut
dériver de plusieurs points sans que personne ne le voie.

CE QUE CE MODULE FAIT, ET CE QU'IL NE FAIT PAS
------------------------------------------------
Il MESURE un écart et le PUBLIE. Il ne valide rien, il ne corrige rien, il
ne bloque rien.

* **Jamais une « validation ».** PVGIS n'accepte qu'un ``loss`` PLAT : notre
  cascade a des postes, la sienne un seul pourcentage. L'égalité poste à
  poste est donc IMPOSSIBLE par construction, et le nombre publié est un
  ÉCART INFORMATIF, à lire par un humain. PVsyst publie ses propres
  validations et reconnaît n'avoir « connaissance d'aucune mesure de
  validation par un tiers », pour une précision annuelle de l'ordre de ±5 %
  (https://www.pvsyst.com/help/validations/index.html) ; HelioScope publie
  un écart « inférieur à 1 % » vis-à-vis de PVsyst sur 8 projets
  (https://help-center.helioscope.com/hc/en-us/articles/39323166747667-P90-P95-and-P99-Values-Accuracy-Study).
  Ces deux chiffres sont cités, jamais employés comme seuil.
* **Aucun seuil codé.** Le VERDICT n'existe que si la société a SAISI sa
  tolérance (réglage ``tolerance_validation_pct``, CALX145, avec sa
  provenance). Sans elle, l'écart est publié TEL QUEL, sans verdict, et le
  motif le dit — un seuil de confort serait un chiffre inventé (D-CALX 7).
* **Un dépassement AVERTIT, il n'ajuste pas.** Au-delà de la tolérance, le
  bloc porte un avertissement nommé, qui part aussi dans
  ``resultat['avertissements']`` pour être VU. Aucune production n'est
  retouchée : corriger en silence un écart de modèle reviendrait à effacer
  la mesure qui vient d'être prise.
* **À perte totale égale, sinon c'est dit.** L'écart ne se lit comme un
  écart de MODÈLE que si les deux chemins déclarent la même perte totale.
  Le bloc publie donc les deux pertes totales et dit si elles sont égales ;
  quand elles ne le sont pas, le motif prévient que l'écart mélange deux
  causes.

CE QUE LE BLOC ``resultat['validation']`` PORTE
------------------------------------------------
Les huit clés du contrat ``contract_samples/calepinage_simulation.json``
(``faite_le``, ``total_chaine_locale_kwh``, ``total_pvcalc_kwh``,
``ecart_pct``, ``tolerance_pct``, ``verdict``, ``avertissement``, ``motif``)
et trois clés que la tâche demande en plus, à ajouter au contrat par la lane
qui en est propriétaire : ``tolerance_source`` (la provenance de la
tolérance saisie — une valeur sans source n'entre nulle part),
``pertes_totales`` (les deux pertes totales et leur égalité) et ``mensuel``
(l'écart MOIS PAR MOIS, qui est ce qui rend un écart lisible : un écart
d'été est un écart thermique, un écart d'hiver ne l'est pas).

QUI L'APPELLE, ET AVEC QUOI
-----------------------------
``services/simulation.py`` (CALX5), qui est le seul à savoir ouvrir la base
et à appeler PVGIS. La tâche nomme ce point d'entrée ``ecart_vs_pvcalc``
mais ne peut pas lui passer le ``Calepinage`` lui-même : ce module est PUR
(aucun accès base, aucun réseau), ce qui est la condition pour que le
harnais tourne hors ligne sur des réponses PVGIS ENREGISTRÉES. CALX5 lui
passe donc les trois pièces qu'il a déjà en main : la série d'entrée de la
chaîne, le contexte de la chaîne, et la réponse PVGIS qui porte une
production.
"""
from __future__ import annotations

import datetime

from apps.calepinage.services import etapes as _etapes
from apps.calepinage.services.chaine_pertes import (
    DECIMALES_KWH, appliquer_chaine,
)

#: La clé du bloc dans ``Calepinage.resultat``.
CLE_VALIDATION = 'validation'

#: Le réglage société (CALX145) qui porte la tolérance. Il est nommé ici
#: sous la forme que l'écran de réglages affiche : un motif qui dit
#: « tolérance non saisie » sans dire OÙ la saisir ne sert à rien.
CLE_TOLERANCE = 'tolerance_validation_pct'
CHAMP_TOLERANCE = 'parametres.simulation.tolerance_validation_pct'

#: Les deux verdicts, et il n'y en a pas de troisième. ``None`` n'est pas un
#: verdict : c'est l'absence de tolérance saisie.
VERDICT_DANS_LA_TOLERANCE = 'dans_la_tolerance'
VERDICT_HORS_TOLERANCE = 'hors_tolerance'

#: Les clés du bloc, dans l'ordre du contrat puis les trois ajouts.
CLES_VALIDATION = (
    'faite_le', 'total_chaine_locale_kwh', 'total_pvcalc_kwh', 'ecart_pct',
    'tolerance_pct', 'verdict', 'avertissement', 'motif',
    'tolerance_source', 'pertes_totales', 'mensuel',
)

#: Les décimales publiées : les totaux au dixième de kWh (la cadence de
#: ``chaine_pertes``), l'écart au centième de point.
DECIMALES_ECART = 2

#: L'epsilon d'ÉGALITÉ des deux pertes totales. Ce n'est pas un seuil
#: métier : la cascade arrondit ses énergies au dixième de kWh
#: (``DECIMALES_KWH``), ce qui déplace son pourcentage total de quelques
#: centièmes de point. Comparer les deux pertes au dixième de point est donc
#: de l'arithmétique d'arrondi, et aucun chiffre publié n'en dépend.
EPSILON_PERTE_PCT = 0.1

MOTIF_ECART_INFORMATIF = (
    'ÉCART INFORMATIF contre PVcalc à perte totale égale — jamais une '
    '« validation », jamais un ajustement.')

MOTIF_SANS_ECART = (
    "Aucune simulation lancée : aucun écart n'a été mesuré contre PVcalc.")

MOTIF_SANS_TOLERANCE = (
    " Aucune tolérance d'écart n'est saisie pour cette société "
    '(« {champ} ») : l\'écart est publié SANS VERDICT. Un seuil codé en dur '
    'serait un chiffre inventé, et le chiffre publié par un concurrent '
    'serait le sien, pas le nôtre.')

MOTIF_PERTES_INEGALES = (
    " Les deux pertes totales ne sont PAS égales (chaîne {chaine} %, PVGIS "
    "{pvgis} %) : l'écart ci-dessus additionne la différence de MODÈLE et la "
    'différence de pertes DÉCLARÉES — il ne se lit pas comme un écart de '
    'modèle.')

MOTIF_PVGIS_SANS_PRODUCTION = (
    'La réponse PVGIS fournie ne porte aucune production : ni '
    '« outputs.hourly[].P » (seriescalc sous pvcalculation=1), ni '
    "« outputs.monthly.fixed[].E_m » (PVcalc). Aucun écart n'est mesuré.")

MOTIF_CHAINE_SANS_ENERGIE = (
    "La chaîne locale ne rend aucune énergie lisible (aucune colonne de "
    'puissance sur la série de sortie) : aucun écart n\'est mesuré. Un 0 se '
    'lirait « la toiture ne produit rien », ce qui n\'est pas ce qui est '
    'observé.')

MOTIF_PUISSANCES_DIFFERENTES = (
    'La réponse PVGIS a été demandée pour {pvgis} kWc alors que '
    "l'installation en compte {locale} : les deux totaux ne décrivent pas la "
    "même installation, et aucun écart n'est mesuré. Redemandez PVGIS avec "
    'la puissance crête du calepinage.')

AVERTISSEMENT_HORS_TOLERANCE = (
    "L'écart mesuré contre PVGIS ({ecart} %) dépasse la tolérance déclarée "
    'par la société ({tolerance} %). Rien n\'est ajusté et rien n\'est '
    'bloqué : la simulation est publiée telle quelle, et l\'écart est à '
    'trancher par un humain.')

__all__ = [
    'CLE_VALIDATION', 'CLE_TOLERANCE', 'CHAMP_TOLERANCE',
    'VERDICT_DANS_LA_TOLERANCE', 'VERDICT_HORS_TOLERANCE',
    'CLES_VALIDATION', 'DECIMALES_ECART', 'EPSILON_PERTE_PCT',
    'MOTIF_ECART_INFORMATIF', 'MOTIF_SANS_ECART', 'MOTIF_SANS_TOLERANCE',
    'MOTIF_PERTES_INEGALES', 'MOTIF_PVGIS_SANS_PRODUCTION',
    'MOTIF_CHAINE_SANS_ENERGIE', 'MOTIF_PUISSANCES_DIFFERENTES',
    'AVERTISSEMENT_HORS_TOLERANCE', 'ecart_vs_pvcalc',
]


def ecart_vs_pvcalc(serie, contexte, reponse_pvgis, *, kwc=None,
                    resultat=None, maintenant=None):
    """Rejoue la même installation des deux côtés et PUBLIE l'écart.

    D'un côté notre chaîne (``appliquer_chaine`` sur ``serie``), de l'autre
    la production que PVGIS a calculée lui-même pour le même site, le même
    plan et la même fenêtre. Les deux totaux, l'écart annuel en pourcentage,
    l'écart mois par mois, la tolérance saisie et — seulement si elle l'est
    — le verdict.

    Args:
        serie: la série d'ENTRÉE de la chaîne (document CALX142). Elle n'est
            pas modifiée : ``appliquer_chaine`` travaille sur des copies.
        contexte: le contexte de chaîne décrit en tête de
            ``services/etapes/__init__.py``. C'est lui qui porte les
            réglages société, donc la tolérance.
        reponse_pvgis: la réponse PVGIS BRUTE qui porte une production —
            ``seriescalc`` sous ``pvcalculation=1`` (colonne ``P``) ou
            ``PVcalc`` (``outputs.monthly.fixed[].E_m``). Les deux formes
            sont lues ; aucune autre n'est devinée.
        kwc: la puissance crête de l'installation. À défaut, la somme des
            ``kwc`` des pans du contexte. Elle doit être celle qui a été
            demandée à PVGIS, sinon les deux totaux ne parlent pas de la
            même installation et aucun écart n'est publié.
        resultat: le ``Calepinage.resultat`` en cours d'écriture. Fourni, le
            bloc y est posé sous ``validation`` et l'avertissement éventuel
            rejoint ``resultat['avertissements']``.
        maintenant: l'horodatage de la mesure (les tests le figent). À
            défaut, l'instant courant en UTC.

    Returns:
        dict — le bloc ``validation`` des clés :data:`CLES_VALIDATION`.
    """
    if not reponse_pvgis:
        # Aucune réponse à confronter : c'est l'état « jamais simulé » du
        # contrat, pas une réponse illisible. Les deux se distinguent par
        # leur motif, jamais par un total à 0.
        return _publier(resultat, _bloc_vide(MOTIF_SANS_ECART))

    mesure_pvgis = _production_pvgis(reponse_pvgis)
    if mesure_pvgis is None:
        return _publier(resultat, _bloc_vide(MOTIF_PVGIS_SANS_PRODUCTION))

    puissance = _puissance_crete(kwc, contexte)
    if not _memes_puissances(puissance, mesure_pvgis['kwc']):
        return _publier(resultat, _bloc_vide(
            MOTIF_PUISSANCES_DIFFERENTES.format(
                pvgis=mesure_pvgis['kwc'], locale=puissance)))

    sortie, cascade = appliquer_chaine(serie, contexte)
    total_local = _etapes.energie_kwh(sortie)
    if total_local is None:
        return _publier(resultat, _bloc_vide(MOTIF_CHAINE_SANS_ENERGIE))

    total_pvgis = mesure_pvgis['annuel_kwh']
    pertes = _pertes_totales(cascade, mesure_pvgis)
    motif = MOTIF_ECART_INFORMATIF
    if not pertes['egales']:
        motif += MOTIF_PERTES_INEGALES.format(chaine=pertes['chaine_pct'],
                                              pvgis=pertes['pvgis_pct'])

    ecart = _ecart_pct(total_local, total_pvgis)
    tolerance = _etapes.reglage(contexte, CLE_TOLERANCE)
    verdict, avertissement, motif = _verdict(ecart, tolerance, motif)

    bloc = {
        'faite_le': _horodatage_iso(maintenant),
        'total_chaine_locale_kwh': _arrondi_kwh(total_local),
        'total_pvcalc_kwh': _arrondi_kwh(total_pvgis),
        'ecart_pct': ecart,
        'tolerance_pct': _valeur_tolerance(tolerance),
        'verdict': verdict,
        'avertissement': avertissement,
        'motif': motif,
        'tolerance_source': (tolerance or {}).get('source'),
        'pertes_totales': pertes,
        'mensuel': _mensuel(sortie, mesure_pvgis['mensuel_kwh']),
    }
    return _publier(resultat, bloc)


# ── la production que PVGIS a calculée lui-même ─────────────────────────

def _production_pvgis(reponse):
    """Le total annuel, les douze mois, la perte plate et la puissance.

    Deux formes de réponse sont lues, et deux seulement : ``seriescalc``
    sous ``pvcalculation=1``, dont chaque heure porte ``P`` en watts, et
    ``PVcalc``, dont chaque mois porte ``E_m`` en kWh. ``None`` quand la
    réponse ne porte aucune des deux — jamais un total à zéro.
    """
    if not isinstance(reponse, dict):
        return None
    entrees = reponse.get('inputs') or {}
    module = entrees.get('pv_module') or {}
    base = {
        'loss_pct': _flottant(module.get('system_loss')),
        'kwc': _flottant(module.get('peak_power')),
    }
    sorties = reponse.get('outputs') or {}

    mensuel = _mensuel_pvcalc(sorties)
    if mensuel is None:
        mensuel = _mensuel_horaire(sorties)
    if mensuel is None:
        return None

    base['mensuel_kwh'] = mensuel
    base['annuel_kwh'] = sum(valeur for valeur in mensuel.values()
                             if valeur is not None)
    return base


def _mensuel_pvcalc(sorties):
    """Les douze ``E_m`` de ``PVcalc``, en kWh, ou ``None``."""
    lignes = ((sorties.get('monthly') or {}).get('fixed')
              if isinstance(sorties.get('monthly'), dict) else None)
    if not isinstance(lignes, list) or not lignes:
        return None
    mensuel = {}
    for rang, ligne in enumerate(lignes, start=1):
        if not isinstance(ligne, dict):
            continue
        # ``month`` quand la réponse le porte ; à défaut le RANG, puisque
        # PVcalc sert ses douze mois dans l'ordre. Deviner autre chose
        # déplacerait un mois d'été sur un mois d'hiver.
        mois = _entier(ligne.get('month'))
        if mois is None:
            mois = rang
        energie = _flottant(ligne.get('E_m'))
        if energie is None:
            continue
        mensuel[mois] = mensuel.get(mois, 0.0) + energie
    return mensuel or None


def _mensuel_horaire(sorties):
    """Les douze mois d'une série ``seriescalc`` à ``P``, en kWh, ou ``None``.

    ``P`` est une puissance en watts sur un pas d'une heure : l'énergie du
    pas vaut donc ``P / 1000`` kWh, exactement comme ``etapes.energie_kwh``
    la lit sur la colonne ``p_w``.
    """
    lignes = sorties.get('hourly')
    if not isinstance(lignes, list) or not lignes:
        return None
    mensuel = {}
    for ligne in lignes:
        if not isinstance(ligne, dict):
            continue
        moment = _horodatage_pvgis(ligne.get('time'))
        puissance = _flottant(ligne.get('P'))
        if moment is None or puissance is None:
            continue
        mois = moment[1]
        mensuel[mois] = mensuel.get(mois, 0.0) + puissance / 1000.0
    return mensuel or None


def _horodatage_pvgis(valeur):
    """``'20200115:0009'`` → ``(2020, 1, 15, 0)``, ou ``None``."""
    texte = str(valeur or '')
    if len(texte) < 11 or ':' not in texte:
        return None
    try:
        return (int(texte[0:4]), int(texte[4:6]), int(texte[6:8]),
                int(texte[9:11]))
    except ValueError:
        return None


# ── les deux totaux, et ce qui les sépare ───────────────────────────────

def _mensuel(sortie, mensuel_pvgis):
    """Les douze lignes d'écart mensuel — ``None`` quand un mois manque.

    Un mois que l'un des deux chemins ne couvre pas reste à ``null`` : un
    écart de −100 % se lirait « ce mois-là notre chaîne ne produit rien ».
    """
    colonne = _etapes.colonne_energie(sortie)
    facteur = _etapes.FACTEURS_KW.get(colonne) if colonne else None
    pas_minutes = (sortie or {}).get('pas_minutes') or _etapes.PAS_MINUTES_PVGIS
    heures = float(pas_minutes) / 60.0

    local = {}
    if facteur is not None:
        for point in (sortie.get('points') or ()):
            if not isinstance(point, dict):
                continue
            mois = _entier(point.get('mois'))
            valeur = _flottant(point.get(colonne))
            if mois is None or valeur is None:
                continue
            local[mois] = local.get(mois, 0.0) + valeur * facteur * heures

    lignes = []
    for mois in range(1, 13):
        cote_local = local.get(mois)
        cote_pvgis = (mensuel_pvgis or {}).get(mois)
        lignes.append({
            'mois': mois,
            'chaine_locale_kwh': _arrondi_kwh(cote_local),
            'pvcalc_kwh': _arrondi_kwh(cote_pvgis),
            'ecart_pct': (_ecart_pct(cote_local, cote_pvgis)
                          if cote_local is not None and cote_pvgis is not None
                          else None),
        })
    return lignes


def _pertes_totales(cascade, mesure_pvgis):
    """Les deux pertes totales, et si elles sont égales à l'arrondi près."""
    chaine = cascade.get('total_pct')
    pvgis = mesure_pvgis.get('loss_pct')
    egales = (chaine is not None and pvgis is not None
              and abs(float(chaine) - float(pvgis)) <= EPSILON_PERTE_PCT)
    return {'chaine_pct': chaine, 'pvgis_pct': pvgis, 'egales': bool(egales)}


def _verdict(ecart, tolerance, motif):
    """``(verdict, avertissement, motif)`` — aucun verdict sans tolérance."""
    valeur = _valeur_tolerance(tolerance)
    if valeur is None or ecart is None:
        return None, None, motif + MOTIF_SANS_TOLERANCE.format(
            champ=CHAMP_TOLERANCE)
    if abs(ecart) <= valeur:
        return VERDICT_DANS_LA_TOLERANCE, '', motif
    return (VERDICT_HORS_TOLERANCE,
            AVERTISSEMENT_HORS_TOLERANCE.format(ecart=ecart,
                                                tolerance=valeur),
            motif)


def _valeur_tolerance(tolerance):
    """La tolérance SAISIE, en points de pourcentage, ou ``None``.

    ``etapes.reglage`` a déjà refusé une valeur sans provenance : ce qui
    arrive ici est saisi et sourcé, ou absent. Une tolérance négative n'a
    pas de sens et est traitée comme absente.
    """
    valeur = _flottant((tolerance or {}).get('valeur'))
    if valeur is None or valeur < 0.0:
        return None
    return valeur


def _puissance_crete(kwc, contexte):
    """La puissance crête déclarée, ou la somme des pans du contexte."""
    explicite = _flottant(kwc)
    if explicite is not None:
        return explicite
    total = None
    for plan in ((contexte or {}).get('plans') or ()):
        if not isinstance(plan, dict):
            continue
        valeur = _flottant(plan.get('kwc'))
        if valeur is None:
            continue
        total = valeur if total is None else total + valeur
    return total


def _memes_puissances(locale, pvgis):
    """Les deux chemins parlent-ils de la même puissance crête ?

    Une puissance inconnue d'un côté n'est pas une divergence : c'est une
    absence, et le reste du bloc reste mesurable.
    """
    if locale is None or pvgis is None:
        return True
    return abs(locale - pvgis) <= 1e-6


def _ecart_pct(local, reference):
    """``(local − reference) / reference`` en pourcentage, ou ``None``."""
    if local is None or reference is None:
        return None
    try:
        denominateur = float(reference)
    except (TypeError, ValueError):
        return None
    if denominateur == 0.0:
        return None
    return round((float(local) - denominateur) / denominateur * 100.0,
                 DECIMALES_ECART)


# ── publication ──────────────────────────────────────────────────────────

def _bloc_vide(motif):
    """Le bloc à ``null``, motivé — jamais un écart à 0 faute de mesure."""
    bloc = {cle: None for cle in CLES_VALIDATION}
    bloc['motif'] = motif
    bloc['mensuel'] = []
    return bloc


def _publier(resultat, bloc):
    """Pose le bloc dans ``resultat`` et fait REMONTER l'avertissement."""
    if isinstance(resultat, dict):
        resultat[CLE_VALIDATION] = bloc
        if bloc.get('avertissement'):
            avertissements = resultat.get('avertissements')
            if not isinstance(avertissements, list):
                avertissements = []
                resultat['avertissements'] = avertissements
            if bloc['avertissement'] not in avertissements:
                avertissements.append(bloc['avertissement'])
    return bloc


def _horodatage_iso(maintenant):
    """L'instant de la mesure, en ISO 8601 UTC."""
    if isinstance(maintenant, str) and maintenant.strip():
        return maintenant
    if isinstance(maintenant, datetime.datetime):
        instant = maintenant
    else:
        instant = datetime.datetime.now(datetime.timezone.utc)
    return instant.replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _arrondi_kwh(valeur):
    return None if valeur is None else round(float(valeur), DECIMALES_KWH)


def _flottant(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if nombre != nombre else nombre


def _entier(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None
