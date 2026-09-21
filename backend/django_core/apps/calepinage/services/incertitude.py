"""CALX185 — DE QUOI σ EST FAIT : la composition en quadrature.

LE CONSTAT
----------
``services/p50p90.py`` n'employait qu'UN écart-type, la variabilité météo, et
le passait tel quel au moteur de quantiles : l'incertitude du MODÈLE et le
biais long terme de la source météo n'existaient nulle part. Une banque qui
demande « de quoi votre σ est-il fait ? » ne trouvait pas la réponse dans le
résultat.

LA PARITÉ VISÉE
---------------
PVsyst compose TROIS sources d'incertitude — variabilité d'une année à
l'autre, incertitude de simulation et de paramètres, biais de mesure long
terme du fichier météo — et les ajoute « in quadrature »
(https://www.pvsyst.com/help/project-design/p50-p90-evaluations.html).

CE QUE CE MODULE TIENT
-----------------------
* ``sigma_total = sqrt(Σ σᵢ²)`` sur les composantes **SOURCÉES uniquement** ;
* chaque composante est publiée avec ``nom``, ``sigma_relatif``, ``source``,
  ``reference`` et ``annees`` — la forme arrêtée par le contrat
  ``contract_samples/calepinage_incertitude.json`` (CALX144) ;
* les composantes « modèle » et « biais météo » viennent des réglages société
  (CALX145) et sont **ABSENTES** tant qu'elles ne sont pas saisies : σ vaut
  alors la seule composante météo, et le résultat le dit ;
* une composante saisie SANS provenance est **REFUSÉE en la nommant**
  (``IncertitudeInvalide``), jamais comptée ni ignorée en silence ;
* aucune composante sourcée ⇒ ``sigma_total`` reste ``null``, les quantiles
  déduits de σ aussi, et ``motif_refus`` dit en français quoi renseigner.
  P50 n'est pas déduit de σ — c'est la production simulée elle-même — il reste
  donc servi. JAMAIS un P50 recopié en P90.

LA PORTÉE EST DÉCLARÉE
-----------------------
``portee = 'annuelle'`` : ces quantiles valent pour UNE année d'exploitation,
pas pour la durée de vie de l'installation. Sans cette clé, un P90 annuel
finirait cité comme une garantie sur vingt ans.

Module PUR : aucune base, aucun réseau, aucun prix.
"""
from __future__ import annotations

import math
import statistics

__all__ = ['COMPOSANTE_BIAIS', 'COMPOSANTE_METEO', 'COMPOSANTE_MODELE',
           'DEPASSEMENTS', 'IncertitudeInvalide', 'METHODE_QUADRATURE',
           'ORIGINE_ABSENTE', 'ORIGINE_MESUREE', 'ORIGINE_SAISIE',
           'PORTEE_ANNUELLE', 'SOURCE_PVGIS', 'SOURCE_SOCIETE',
           'SOURCE_TEXTE', 'bloc_incertitude', 'sigma_mesure']

#: σ a été MESURÉ sur les productions annuelles réellement observées.
ORIGINE_MESUREE = 'mesuree'
#: σ a été SAISI par la société, avec sa provenance (réglage CALX145).
ORIGINE_SAISIE = 'saisie'
#: σ n'existe pas : ni mesuré, ni saisi. Les quantiles sont REFUSÉS.
ORIGINE_ABSENTE = 'absente'

#: Les TROIS provenances admises d'une composante publiée (CALX144) :
#: mesurée sur la série, arrêtée par la société, ou tirée d'un texte cité.
SOURCE_PVGIS = 'pvgis'
SOURCE_SOCIETE = 'societe'
SOURCE_TEXTE = 'texte'

#: Les noms des composantes, ceux que l'écran affiche et que le refus NOMME.
COMPOSANTE_METEO = 'variabilite_interannuelle'
COMPOSANTE_MODELE = 'modele_simulation'
COMPOSANTE_BIAIS = 'biais_long_terme'

#: La méthode de composition publiée, pour qu'un lecteur n'ait pas à deviner
#: si les composantes s'additionnent ou se composent.
METHODE_QUADRATURE = 'quadrature'

#: La portée des quantiles — UNE année d'exploitation (PVsyst le dit aussi).
PORTEE_ANNUELLE = 'annuelle'

#: Les quantiles publiés et leur probabilité de DÉPASSEMENT : P90 est « la
#: valeur atteinte ou dépassée 90 % du temps » (HelioScope,
#: https://help-center.helioscope.com/hc/en-us/articles/39323166747667-P90-P95-and-P99-Values-Accuracy-Study).
DEPASSEMENTS = (('p75_kwh', 0.75), ('p90_kwh', 0.90))

#: ``{nom de composante: (clé du réglage CALX145, libellé français)}`` — les
#: deux composantes qui ne peuvent venir QUE d'une saisie sourcée.
REGLAGES_COMPOSANTES = {
    COMPOSANTE_MODELE: ('sigma_modele_pct',
                        'Incertitude de simulation (σ modèle)'),
    COMPOSANTE_BIAIS: ('sigma_biais_meteo_pct',
                       'Biais long terme de la source météo (σ)'),
}

#: Le réglage qui porte un σ météo SAISI, employé quand la fenêtre ne permet
#: pas de le mesurer.
CLE_SIGMA_METEO_SAISI = 'sigma_meteo_saisi_pct'
LIBELLE_SIGMA_METEO_SAISI = 'Variabilité interannuelle saisie (σ météo)'


class IncertitudeInvalide(ValueError):
    """Une composante d'incertitude refusée, en NOMMANT le champ fautif.

    Règle fondateur du 08/09/2026 : une erreur désigne le champ, jamais un
    « non enregistré » générique.
    """

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ
        self.motif = message


def sigma_mesure(totaux_par_annee):
    """σ RELATIF mesuré sur les productions annuelles, ou rien.

    Args:
        totaux_par_annee: ``{annee: kWh}`` — les totaux RÉELLEMENT observés
            dans la fenêtre demandée à PVGIS.

    Returns:
        ``(sigma, origine, annees)``. Moins de deux années complètes ⇒
        ``(None, 'absente', n)`` : un écart-type sur une seule valeur n'a pas
        de sens, et en fabriquer un serait un chiffre inventé.
    """
    valeurs = [float(v) for v in (totaux_par_annee or {}).values()
               if v is not None and float(v) > 0]
    if len(valeurs) < 2:
        return None, ORIGINE_ABSENTE, len(valeurs)
    moyenne = sum(valeurs) / len(valeurs)
    if moyenne <= 0:
        return None, ORIGINE_ABSENTE, len(valeurs)
    return (statistics.stdev(valeurs) / moyenne, ORIGINE_MESUREE,
            len(valeurs))


def _sigma_saisi(reglages, cle, libelle):
    """``(sigma_relatif, source, reference)`` d'un réglage CALX145, ou rien.

    Le réglage porte ``{valeur, source, reference}`` et sa valeur est un
    POURCENTAGE ; on rend un écart-type RELATIF (sans unité).

    Raises:
        IncertitudeInvalide: valeur présente mais sans provenance, illisible
            ou négative — refusée en NOMMANT la clé.
    """
    brut = (reglages or {}).get(cle)
    if brut is None:
        return None, '', ''
    if not isinstance(brut, dict):
        raise IncertitudeInvalide(
            f'« {libelle} » doit être saisi avec sa provenance : '
            '{"valeur": …, "source": …, "reference": "…"}.', champ=cle)
    provenance = str(brut.get('source') or '').strip()
    if not provenance:
        raise IncertitudeInvalide(
            f'« {libelle} » n\'a aucune source : cet écart-type est refusé et '
            "n'entre pas dans le calcul de σ. Renseignez sa provenance "
            '(réglage de la société, publication citée, ou mesure sur la '
            'série), ou retirez-le — aucun écart-type n\'est composé à partir '
            "d'un chiffre sans origine.", champ=cle)
    try:
        pourcent = float(brut.get('valeur'))
    except (TypeError, ValueError):
        raise IncertitudeInvalide(
            f'« {libelle} » doit porter un nombre en % '
            f"(reçu : {brut.get('valeur')!r}).", champ=cle)
    if pourcent < 0:
        raise IncertitudeInvalide(
            f'« {libelle} » ne peut pas être négatif : un écart-type est une '
            'dispersion, jamais un retrait.', champ=cle)
    citation = str(brut.get('reference') or '').strip()
    reference = f'Réglage de simulation « {cle} », provenance {provenance}'
    if citation:
        reference = f'{reference} — {citation}'
    # Une valeur tirée d'un texte garde sa provenance « texte » ; toute autre
    # (société, mesure, document du projet) est une valeur que la SOCIÉTÉ
    # assume, et le détail reste lisible dans ``reference``.
    source = SOURCE_TEXTE if provenance == SOURCE_TEXTE else SOURCE_SOCIETE
    return pourcent / 100.0, source, reference


def _composante(nom, sigma_relatif, source, reference, annees):
    """Une LIGNE de ``composantes[]``, à la forme arrêtée par CALX144."""
    return {'nom': nom, 'sigma_relatif': round(sigma_relatif, 6),
            'source': source, 'reference': reference, 'annees': annees}


def _composante_meteo(totaux_par_annee, reglages):
    """La composante météo : MESURÉE d'abord, SAISIE ensuite, ou rien.

    La mesure prime : deux années réellement observées valent mieux qu'un
    chiffre arrêté au bureau. Le σ saisi ne sert que lorsque la fenêtre ne
    permet aucune mesure.

    Returns:
        ``(composante | None, origine, annees_observees)``.
    """
    sigma, origine, annees = sigma_mesure(totaux_par_annee)
    if sigma is not None:
        return (_composante(COMPOSANTE_METEO, sigma, SOURCE_PVGIS,
                            f'seriescalc, {annees} années observées', annees),
                ORIGINE_MESUREE, annees)
    saisi, source, reference = _sigma_saisi(reglages, CLE_SIGMA_METEO_SAISI,
                                            LIBELLE_SIGMA_METEO_SAISI)
    if saisi is None:
        return None, ORIGINE_ABSENTE, annees
    # ``annees = None`` : une valeur saisie n'a été mesurée sur AUCUNE année,
    # et écrire 0 se lirait « mesurée sur zéro année » (CALX144).
    return (_composante(COMPOSANTE_METEO, saisi, source, reference, None),
            ORIGINE_SAISIE, annees)


def _composantes(totaux_par_annee, reglages):
    """Toutes les composantes SOURCÉES, dans l'ordre de PVsyst."""
    composantes = []
    meteo, origine, annees = _composante_meteo(totaux_par_annee, reglages)
    if meteo is not None:
        composantes.append(meteo)
    for nom, (cle, libelle) in REGLAGES_COMPOSANTES.items():
        sigma, source, reference = _sigma_saisi(reglages, cle, libelle)
        if sigma is None:
            continue
        composantes.append(_composante(nom, sigma, source, reference, None))
    return composantes, origine, annees


def _quadrature(composantes):
    """``sqrt(Σ σᵢ²)`` — la composition de PVsyst, ou ``None`` sans composante.

    Une seule composante ⇒ σ vaut EXACTEMENT cette composante : la racine du
    carré d'un nombre positif est ce nombre.
    """
    if not composantes:
        return None
    return math.sqrt(sum(c['sigma_relatif'] ** 2 for c in composantes))


def _quantiles(p50_kwh, sigma_total):
    """Les quantiles gaussiens déduits de σ, centrés sur P50.

    ``p50_kwh`` n'est PAS déduit de σ : c'est la production simulée elle-même.
    Il reste donc servi quand σ est refusé, les autres valant ``None``.
    """
    publies = {'p50_kwh': round(p50_kwh, 1) if p50_kwh is not None else None}
    loi = statistics.NormalDist()
    for cle, depassement in DEPASSEMENTS:
        if p50_kwh is None or sigma_total is None:
            publies[cle] = None
            continue
        facteur = 1.0 + loi.inv_cdf(1.0 - depassement) * sigma_total
        # Un σ énorme ne donne pas une production négative.
        publies[cle] = round(p50_kwh * max(0.0, facteur), 1)
    return publies


def _motif_de_refus(p50_kwh, annees):
    """Le texte français qui REMPLACE le repli supprimé par CALX184."""
    quantiles = ', '.join(cle[:3].upper() for cle, _ in DEPASSEMENTS)
    if p50_kwh is None:
        return (
            "Aucune composante d'incertitude sourcée : les quantiles restent "
            'nuls — jamais un P50 recopié en P90.')
    if annees > 1:
        observees = f'{annees} années observées ne dispersent rien de mesurable'
    elif annees == 1:
        observees = "la fenêtre météo ne porte qu'une seule année"
    else:
        observees = "aucune année de production n'a été observée"
    return (
        f"σ n'a pas pu être établi : {observees}, et aucune incertitude n'a "
        f'été saisie pour cette société. {quantiles} restent « non calculés » '
        "— aucune valeur de référence n'est appliquée à leur place. "
        f'Renseignez « {LIBELLE_SIGMA_METEO_SAISI} » dans les réglages de '
        'simulation, avec sa source.')


def bloc_incertitude(p50_kwh, *, totaux_par_annee=None, reglages=None):
    """LE bloc ``resultat['incertitude']`` — point d'entrée de CALX185/186.

    C'est la fonction que l'orchestration de la simulation (CALX5) appelle
    avec la série annuelle et les réglages société ; sa forme est celle du
    contrat ``contract_samples/calepinage_incertitude.json`` (CALX144), à la
    clé près.

    Args:
        p50_kwh: la production annuelle simulée (déjà nette des postes de
            CAL139). ``None`` ⇒ le calepinage n'a jamais été simulé : toutes
            les clés sont présentes et nulles.
        totaux_par_annee: ``{annee: kWh}`` — les totaux annuels réellement
            observés dans la fenêtre PVGIS, pour MESURER la composante météo.
        reglages: la section ``simulation`` des réglages société (CALX145),
            ``{clé: {valeur, source, reference}}``. Absente ⇒ aucune
            composante saisie, ce qui est le comportement d'aujourd'hui.

    Returns:
        dict — ``composantes`` (liste), ``sigma_total``, ``methode``,
        ``quantiles``, ``portee``, ``motif_refus``.

    Raises:
        IncertitudeInvalide: une composante saisie sans provenance, refusée
            en nommant la clé de réglage fautive.
    """
    try:
        base = float(p50_kwh) if p50_kwh is not None else None
    except (TypeError, ValueError):
        base = None
    if base is not None and base <= 0:
        base = None

    composantes, _origine, annees = _composantes(totaux_par_annee, reglages)
    # σ parle des COMPOSANTES, pas de la production : il existe dès qu'une
    # composante est sourcée, même avant qu'une simulation ait tourné. Les
    # quantiles, eux, ont besoin des deux — sans P50 il n'y a rien à décaler.
    sigma_total = _quadrature(composantes)
    return {
        'composantes': composantes,
        'sigma_total': (round(sigma_total, 6) if sigma_total is not None
                        else None),
        'methode': METHODE_QUADRATURE if sigma_total is not None else None,
        'quantiles': _quantiles(base, sigma_total),
        'portee': PORTEE_ANNUELLE if base is not None else None,
        'motif_refus': ('' if sigma_total is not None
                        else _motif_de_refus(base, annees)),
    }
