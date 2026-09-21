"""CALX241 — LE POINT DE RACCORDEMENT : l'élévation de tension, et sa limite.

CE QUI MANQUAIT
---------------
``grep -n "elevation"`` sur ``core/electrique/`` et sur
``apps/calepinage/services/`` ne rendait rien : le moteur calculait la CHUTE
de tension (consommateur en bout de ligne) et jamais la REMONTÉE que crée un
onduleur qui INJECTE dans cette même ligne. Toutes les briques étaient
pourtant posées — la résistivité du cuivre (``core/electrique/cables.py``,
guide UTE C 15-105), la formule ``u = k·ρ·L·I/S``, les longueurs et sections
des tronçons, la tension nominale.

LA RÈGLE DURE : UNE LIMITE EST UNE SAISIE, ET ELLE PORTE SA SOURCE
--------------------------------------------------------------------
``limite_elevation_pct`` n'est PAS un barème du code. C'est une valeur
SAISIE, accompagnée obligatoirement de ``source_limite`` (texte réglementaire
ou contrat de raccordement). Sans elle, ``elevation_pct`` est calculée et
PUBLIÉE — le chiffre existe, il est vrai, il se lit — mais le verdict vaut
``non_verifiable`` (publié ``omis``) et son motif dit ce qui manque. Aucune
limite n'est supposée pour le Maroc : ni 3 %, ni 10 %, ni aucun barème
étranger (D-CALX 7, D1 ``services/norme.py::norme_applicable``). Une limite
saisie SANS source est REFUSÉE en nommant le champ : un seuil sans
provenance n'est pas opposable.

CE QUI FAIT OMETTRE LE CALCUL LUI-MÊME
----------------------------------------
Une longueur, une section, un courant ou une tension nominale absents
rendent ``elevation_pct`` à ``None`` en NOMMANT le champ et le tronçon
fautifs. Une somme partielle serait pire qu'une absence : elle sous-estimerait
l'élévation réelle tout en ayant l'air d'un résultat.

CE MODULE NE LIT NI BASE NI RÉSEAU. Les tronçons lui sont DONNÉS (la lane
``services/troncons.py``, CALX224-226, les construit) : ici, ce sont des
dicts, et la forme lue est décrite sur :func:`elevation_de_tension`.

Contrat de sortie : ``contract_samples/calepinage_raccordement.json``
(CALX205) — trois blocs ``saisie`` / ``calcul`` / ``verdicts``, cinq verdicts
TOUJOURS présents. Aucun prix, aucun kWh (D-CALX 5, W3).
"""
from __future__ import annotations

import math

from core.electrique.cables import RHO_CUIVRE_20C, chute_tension_v
from core.electrique.types import (
    NATURE_MATERIELLE, STATUT_BLOQUANT, STATUT_NON_VERIFIABLE, STATUT_OK,
    VerdictElectrique, fr,
)

__all__ = [
    'RaccordementInvalide', 'CODE_ELEVATION', 'LIBELLES',
    'elevation_de_tension',
]

# ── les cinq contrôles du contrat CALX205, et leur intitulé d'écran ────────
CODE_ELEVATION = 'elevation_tension'
CODE_PUISSANCE_SOUSCRITE = 'puissance_souscrite'
CODE_REGIME_PHASES = 'regime_phases'
CODE_TENSION_NOMINALE = 'tension_nominale'
CODE_DESEQUILIBRE = 'desequilibre_phases'

#: Intitulés publiés par le contrat CALX205 (clé ``libelle`` de chaque
#: verdict). Ils vivent ici pour qu'un écran et un test les lisent au même
#: endroit ; la PHRASE motivée, elle, est générée à partir des nombres.
LIBELLES = {
    CODE_ELEVATION: 'Élévation de tension au point de raccordement',
    CODE_PUISSANCE_SOUSCRITE: 'Puissance injectée face à la puissance '
                              'souscrite',
    CODE_REGIME_PHASES: "Régime de l'onduleur face au branchement",
    CODE_TENSION_NOMINALE: 'Tension nominale employée par le calcul',
    CODE_DESEQUILIBRE: 'Déséquilibre entre les phases',
}

#: Le motif publié quand aucune limite d'élévation n'est saisie — texte du
#: contrat CALX205, mot pour mot, pour qu'un écran ne le réécrive pas.
MOTIF_SANS_LIMITE = (
    "aucune limite d'élévation n'est saisie pour ce site : l'élévation est "
    "publiée, mais aucun verdict n'est prononcé. Aucun barème marocain n'est "
    "présent dans ce dépôt et aucune limite n'est supposée — saisissez "
    "« limite_elevation_pct » avec sa source (texte réglementaire ou contrat "
    "de raccordement) dans les réglages du calepinage.")

#: Le refus opposé à une limite saisie SANS source (clé ``source_limite`` de
#: ``refus_limite_sans_source``, contrat CALX205).
REFUS_LIMITE_SANS_SOURCE = (
    "Une limite d'élévation de tension ne peut pas être enregistrée sans sa "
    "source : indiquez le texte réglementaire ou le contrat de raccordement "
    "qui la fixe — un seuil sans provenance n'est pas opposable.")


class RaccordementInvalide(ValueError):
    """Refus métier sur la saisie de raccordement — champ fautif NOMMÉ."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


# ── lectures tolérantes (aucune valeur substituée, jamais) ────────────────
def _nombre(valeur):
    """Le flottant d'une saisie, ou ``None`` — jamais un repli."""
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _positif(valeur):
    """Un nombre STRICTEMENT positif, ou ``None`` (0 n'est pas une longueur)."""
    nombre = _nombre(valeur)
    if nombre is None or nombre <= 0:
        return None
    return nombre


def _entier(valeur):
    nombre = _nombre(valeur)
    return None if nombre is None else int(nombre)


def _longueur_m(troncon):
    """La longueur d'un tronçon, nombre nu ou ``Longueur.en_dict()``.

    ``services/cables.py`` publie une longueur AVEC son origine
    (``{valeur_m, origine, detail}``) ; un tronçon peut porter l'une ou
    l'autre forme, et aucune n'est devinée quand les deux manquent.
    """
    brute = troncon.get('longueur_m')
    if isinstance(brute, dict):
        return _positif(brute.get('valeur_m'))
    return _positif(brute)


def _origine_longueur(troncon):
    """D'où vient la longueur du tronçon — jamais un nombre nu (lot 4)."""
    brute = troncon.get('longueur_m')
    if isinstance(brute, dict):
        return (brute.get('origine') or brute.get('detail') or '')
    return (troncon.get('origine_longueur') or troncon.get('origine')
            or troncon.get('source') or '')


def _coefficient(phases):
    """2 en continu et en monophasé (aller-retour), √3 en triphasé.

    Convention de ``core/electrique/cables.py::chute_tension_v`` : c'est le
    COEFFICIENT qui porte l'aller-retour, jamais la longueur. Un régime non
    saisi ne se devine pas — la fonction rend ``None`` et l'appelant OMET.
    """
    regime = _entier(phases)
    if regime == 3:
        return math.sqrt(3.0)
    if regime == 1:
        # 2 = aller-retour d'une liaison à deux conducteurs chargés : une
        # valeur de FORME de la formule, pas un seuil électrique.
        return 2.0
    return None


def _parcouru(troncon):
    """Le tronçon est-il traversé par le courant INJECTÉ ?

    Absent = oui : l'appelant ne transmet que les tronçons du chemin
    d'injection. La clé existe pour qu'un cheminement complet puisse être
    passé tel quel sans que les antennes non parcourues soient comptées.
    """
    marque = troncon.get('parcouru')
    return True if marque is None else bool(marque)


def elevation_de_tension(troncons, injection):
    """CALX241 — l'élévation au point de raccordement, tronçon par tronçon.

    Args:
        troncons: la liste des tronçons de la liaison, chacun un dict
            ``{repere, longueur_m, section_mm2}`` — ``longueur_m`` accepte
            aussi la forme ``Longueur.en_dict()`` de ``services/cables.py``.
            Clés facultatives : ``courant_a`` (le courant PROPRE au tronçon,
            à défaut celui de l'injection), ``phases`` (à défaut celui de
            l'injection), ``rho`` (résistivité, à défaut celle du guide
            UTE C 15-105 publiée par le noyau) et ``parcouru``.
        injection: la saisie du branchement enrichie du courant injecté —
            ``{courant_a, tension_nominale_v, phases, limite_elevation_pct,
            source_limite}``.

    Returns:
        ``{elevation_pct, elevation_v, par_troncon, limite_pct,
        source_limite, marge_pct, tension_nominale_v, verdict, omissions}``.
        ``elevation_pct`` est la SOMME des contributions publiées ; elle vaut
        ``None`` dès qu'un tronçon parcouru n'est pas calculable, avec
        l'omission qui NOMME le champ et le tronçon.

    Raises:
        RaccordementInvalide: limite saisie sans ``source_limite``.

    Fonction PURE : aucune base, aucun réseau, aucune horloge.
    """
    injection = injection if isinstance(injection, dict) else {}
    limite, source_limite = _limite_saisie(injection)
    tension = _positif(injection.get('tension_nominale_v'))
    courant_global = _nombre(injection.get('courant_a'))

    omissions = []
    if tension is None:
        omissions.append(
            "« tension_nominale_v » n'est pas saisie : l'élévation ne peut "
            "pas être exprimée en pourcentage d'une tension inconnue.")

    lignes, manques = _contributions(troncons, injection, tension,
                                     courant_global)
    omissions.extend(manques)

    calculable = tension is not None and not manques and lignes
    total_v = sum(ligne['elevation_v'] for ligne in lignes) if calculable \
        else None
    total_pct = sum(ligne['elevation_pct'] for ligne in lignes) \
        if calculable else None
    if not lignes and not manques:
        omissions.append(
            "aucun tronçon n'est parcouru par le courant injecté : il n'y a "
            "pas de liaison sur laquelle une élévation se calcule. Saisissez "
            "le cheminement du raccordement.")

    marge = (None if (total_pct is None or limite is None)
             else round(limite - total_pct, 4))
    return {
        'elevation_pct': None if total_pct is None else round(total_pct, 4),
        'elevation_v': None if total_v is None else round(total_v, 4),
        'par_troncon': lignes,
        'limite_pct': limite,
        'source_limite': source_limite,
        # `marge_pct` est une DIFFÉRENCE, pas un confort : `null` tant
        # qu'aucune limite n'est saisie — `0` se lirait « limite atteinte ».
        'marge_pct': marge,
        'tension_nominale_v': tension,
        'verdict': _verdict_elevation(total_pct, limite, source_limite,
                                      omissions),
        'omissions': omissions,
    }


def _limite_saisie(injection):
    """``(limite, source)`` — une limite sans source est REFUSÉE, pas ignorée.

    L'ignorer silencieusement laisserait croire à une absence de saisie alors
    que quelqu'un a bel et bien posé un chiffre : le refus NOMME le champ.
    """
    limite = _nombre(injection.get('limite_elevation_pct'))
    source = (injection.get('source_limite') or '').strip() \
        if isinstance(injection.get('source_limite'), str) else ''
    if limite is not None and not source:
        raise RaccordementInvalide(REFUS_LIMITE_SANS_SOURCE,
                                   champ='raccordement.source_limite')
    return (limite, source or None)


def _contributions(troncons, injection, tension, courant_global):
    """``(lignes, omissions)`` — la remontée de CHAQUE tronçon parcouru."""
    lignes = []
    omissions = []
    for rang, troncon in enumerate(troncons or (), start=1):
        if not isinstance(troncon, dict) or not _parcouru(troncon):
            continue
        repere = str(troncon.get('repere') or 'tronçon n°%d' % rang)
        longueur = _longueur_m(troncon)
        section = _positif(troncon.get('section_mm2'))
        courant = _nombre(troncon.get('courant_a'))
        if courant is None:
            courant = courant_global
        coefficient = _coefficient(
            troncon.get('phases') if troncon.get('phases') is not None
            else injection.get('phases'))

        for valeur, champ, quoi in ((longueur, 'longueur_m', 'longueur'),
                                    (section, 'section_mm2', 'section'),
                                    (courant, 'courant_a', 'courant injecté'),
                                    (coefficient, 'phases', 'régime')):
            if valeur is None:
                omissions.append(
                    "%s : « %s » manque — la %s du tronçon n'est ni lue du "
                    "plan ni saisie, et l'élévation ne se calcule pas sur une "
                    "valeur supposée." % (repere, champ, quoi))
        if longueur is None or section is None or courant is None \
                or coefficient is None:
            continue

        rho = _positif(troncon.get('rho')) or RHO_CUIVRE_20C
        volts = chute_tension_v(longueur, courant, section, coefficient, rho)
        lignes.append({
            'repere': repere,
            'longueur_m': round(longueur, 3),
            'origine_longueur': _origine_longueur(troncon),
            'section_mm2': section,
            'courant_a': round(courant, 3),
            'coefficient': round(coefficient, 4),
            'elevation_v': round(volts, 4),
            'elevation_pct': (None if tension is None
                              else round(volts / tension * 100.0, 4)),
        })
    if tension is None:
        for ligne in lignes:
            ligne['elevation_pct'] = None
    return (lignes, omissions)


def _verdict_elevation(elevation_pct, limite, source_limite, omissions):
    """Le verdict CALX215 de l'élévation — ``omis`` quand la limite manque."""
    if limite is None:
        return VerdictElectrique(
            code=CODE_ELEVATION, nature=NATURE_MATERIELLE,
            statut=STATUT_NON_VERIFIABLE, libelle=MOTIF_SANS_LIMITE,
            borne=None, valeur=elevation_pct, source='')
    if elevation_pct is None:
        return VerdictElectrique(
            code=CODE_ELEVATION, nature=NATURE_MATERIELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle="la limite de %s %% est saisie, mais l'élévation n'est "
                    "pas calculable : %s"
                    % (fr(limite, 1), omissions[0] if omissions
                       else "une entrée du cheminement manque."),
            borne=limite, valeur=None, source=_source_limite(source_limite))
    source = _source_limite(source_limite)
    if elevation_pct <= limite:
        return VerdictElectrique(
            code=CODE_ELEVATION, nature=NATURE_MATERIELLE, statut=STATUT_OK,
            libelle="%s %% d'élévation pour une limite saisie de %s %% : il "
                    "reste %s points de marge."
                    % (fr(elevation_pct), fr(limite, 1),
                       fr(limite - elevation_pct)),
            borne=limite, valeur=elevation_pct, source=source)
    # Une élévation au-dessus de la limite du contrat de raccordement ne se
    # NÉGOCIE pas comme un dépassement de puissance souscrite : elle sort de
    # la condition à laquelle le gestionnaire de réseau accepte l'injection.
    return VerdictElectrique(
        code=CODE_ELEVATION, nature=NATURE_MATERIELLE,
        statut=STATUT_BLOQUANT,
        libelle="%s %% d'élévation au point de raccordement pour une limite "
                "saisie de %s %% : la limite est franchie de %s points — "
                "augmentez la section de la liaison ou rapprochez le point "
                "de livraison."
                % (fr(elevation_pct), fr(limite, 1),
                   fr(elevation_pct - limite)),
        borne=limite, valeur=elevation_pct, source=source)


def _source_limite(source_limite):
    """« saisie — limite_elevation_pct, source : … » (contrat CALX205)."""
    if not source_limite:
        return ''
    return 'saisie — limite_elevation_pct, source : %s' % source_limite
