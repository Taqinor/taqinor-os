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
    COTE_AC, NATURE_FONCTIONNELLE, NATURE_MATERIELLE, STATUT_ALERTE,
    STATUT_BLOQUANT, STATUT_NON_VERIFIABLE, STATUT_OK, VerdictElectrique, fr,
)

__all__ = [
    'RaccordementInvalide', 'CODE_ELEVATION', 'LIBELLES',
    'elevation_de_tension', 'verdicts_raccordement',
    'repartition_des_phases',
    'bloc_raccordement',  # CALX244
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

#: Le refus opposé à un cos φ imposé SANS source (clé ``source_cos_phi`` de
#: ``refus_cos_phi_sans_source``, contrat CALX205). Le cos φ imposé par le
#: contrat de raccordement de CE site n'est PAS le réglage société
#: ``cos_phi_par_defaut`` (registre CALX145) : deux grandeurs, deux noms.
REFUS_COS_PHI_SANS_SOURCE = (
    "Un cos φ imposé ne peut pas être enregistré sans sa source : indiquez "
    "le contrat de raccordement ou la prescription du gestionnaire de réseau "
    "qui l'impose.")

#: CALX242 — les motifs d'omission des trois contrôles de branchement, textes
#: du contrat CALX205 (état ``exemple_vide``).
MOTIF_SANS_PUISSANCE_SOUSCRITE = (
    "« puissance_souscrite_kva » n'est pas saisie : rien ne peut être "
    "comparé à la puissance injectée. Saisissez la puissance souscrite du "
    "contrat de raccordement.")
MOTIF_SANS_PHASES = (
    "« phases » n'est pas saisi : le régime du branchement est inconnu, et "
    "il n'est pas supposé. Saisissez 1 ou 3 phases.")
MOTIF_SANS_TENSION_NOMINALE = (
    "« tension_nominale_v » n'est pas saisie : ni 230 V ni 400 V ne sont "
    "supposés. Saisissez la tension nominale du branchement.")


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


# ═══════════════════════════════════════════════════════════════════════════
# CALX242 — PUISSANCE DE RACCORDEMENT ET RÉGIME MONO/TRI
# ═══════════════════════════════════════════════════════════════════════════
#
# ``entree.phases`` ne servait qu'à CHOISIR un barème d'ampacité et un
# coefficient de protection (``core/electrique/cables.py``,
# ``core/electrique/protections.py``) : rien ne comparait la puissance
# injectée à une puissance souscrite, et rien ne signalait un onduleur
# TRIPHASÉ posé sur un abonnement MONOPHASÉ — un dossier impossible à
# raccorder, qui ne se découvrait que le jour de la mise en service.
#
# TROIS CONTRÔLES, TROIS GRAVITÉS DIFFÉRENTES, ET ELLES NE SE CONFONDENT PAS :
#
# * la PUISSANCE souscrite dépassée est une ALERTE — un dépassement se
#   NÉGOCIE avec le gestionnaire de réseau (augmentation d'abonnement,
#   bridage), il n'empêche pas la conception d'exister ;
# * le RÉGIME (onduleur triphasé sur un branchement monophasé) est BLOQUANT —
#   il ne se négocie pas, aucun réglage ne le rattrape. L'inverse (onduleurs
#   MONOphasés sur un réseau triphasé) est parfaitement normal : c'est
#   l'équilibrage des phases (CALX243) qui s'en occupe, pas un refus ;
# * la TENSION nominale saisie qui DIVERGE de celle que le calcul emploie est
#   BLOQUANTE — toutes les chutes et toute l'élévation déjà publiées portent
#   alors sur une tension que personne n'a sur son compteur.
#
# Saisie absente ⇒ contrôle OMIS avec son motif. Aucun contrôle ne suppose
# 230 V, 400 V, ni un régime : c'est exactement ce que le contrat CALX205
# publie dans son état `exemple_vide`.

def verdicts_raccordement(conception, saisie):
    """CALX242 — les trois contrôles du branchement, chacun NOMMANT son champ.

    Args:
        conception: la ``Conception`` de CAL124 (``services/chaines.py``),
            ou ``None`` — seuls l'onduleur retenu, son régime et la tension
            que le calcul emploie sont lus.
        saisie: le bloc ``saisie`` du contrat CALX205 —
            ``{puissance_souscrite_kva, phases, tension_nominale_v,
            cos_phi_impose, source_cos_phi, …}``.

    Returns:
        ``{puissance_injectee_kva, source_puissance, phases_onduleur,
        tension_employee_v, verdicts}`` — ``verdicts`` est le tuple des trois
        ``VerdictElectrique`` (puissance souscrite, régime, tension), dans
        l'ordre du contrat.

    Raises:
        RaccordementInvalide: ``cos_phi_impose`` saisi sans
            ``source_cos_phi``.

    Fonction PURE : aucune base, aucun réseau, aucune horloge.
    """
    saisie = saisie if isinstance(saisie, dict) else {}
    cos_phi, source_cos_phi = _cos_phi_saisi(saisie)
    injectee, source_puissance, motif_puissance = _puissance_injectee_kva(
        conception, cos_phi, source_cos_phi)
    phases_onduleur = _phases_onduleur(conception)
    tension_employee = _tension_employee_v(conception)

    return {
        'puissance_injectee_kva': (None if injectee is None
                                   else round(injectee, 3)),
        'source_puissance': source_puissance,
        'phases_onduleur': phases_onduleur,
        'tension_employee_v': tension_employee,
        'verdicts': (
            _verdict_puissance_souscrite(saisie, injectee, source_puissance,
                                         motif_puissance),
            _verdict_regime_phases(saisie, phases_onduleur),
            _verdict_tension_nominale(saisie, tension_employee),
        ),
    }


def _cos_phi_saisi(saisie):
    """``(cos_phi, source)`` — un cos φ sans source est REFUSÉ, pas ignoré.

    C'est le couple que l'étape d'écrêtage (CALX172) lira pour borner la
    puissance : le laisser passer sans provenance ferait entrer un chiffre
    non défendable dans la simulation.
    """
    cos_phi = _nombre(saisie.get('cos_phi_impose'))
    brut = saisie.get('source_cos_phi')
    source = brut.strip() if isinstance(brut, str) else ''
    if cos_phi is not None and not source:
        raise RaccordementInvalide(REFUS_COS_PHI_SANS_SOURCE,
                                   champ='raccordement.source_cos_phi')
    return (cos_phi, source or None)


def _evaluation(conception):
    """L'``EvaluationOnduleurs`` de la conception, ou ``None``."""
    if conception is None:
        return None
    from .chaines import evaluer_onduleurs

    try:
        return evaluer_onduleurs(conception)
    except Exception:  # noqa: BLE001 — une conception incomplète ne fait pas
        # tomber la page de raccordement : elle rend le contrôle OMIS.
        return None


def _puissance_injectee_kva(conception, cos_phi, source_cos_phi):
    """``(kVA, source, motif)`` — la puissance APPARENTE réellement injectée.

    Deux provenances, dans cet ordre, et AUCUN repli au-delà :

    1. la fiche onduleur publie ``s_max_kva`` (champ CALX60) — c'est la
       puissance apparente que le constructeur garantit ;
    2. à défaut, la puissance ACTIVE de la fiche divisée par le ``cos φ``
       IMPOSÉ et sourcé du contrat de raccordement.

    Sans l'un ni l'autre, la valeur vaut ``None`` en NOMMANT les deux champs :
    supposer un cos φ de 1 présenterait une puissance active pour une
    puissance apparente.
    """
    evaluation = _evaluation(conception)
    if evaluation is None or not evaluation.nombre:
        return (None, '', "aucun onduleur n'est retenu par la conception : "
                          "il n'y a pas de puissance injectée à comparer.")
    onduleur = conception.entree.onduleur
    s_max = _positif(getattr(onduleur, 's_max_kva', None))
    if s_max is not None:
        return (evaluation.nombre * s_max,
                'fiche onduleur — s_max_kva', '')
    active = _positif(evaluation.puissance_ac_kw)
    if active is None:
        return (None, '', "la puissance AC de l'onduleur n'est pas "
                          "renseignée : « ac_kw » manque sur la fiche.")
    if cos_phi is not None and cos_phi > 0:
        return (active / cos_phi,
                'saisie — cos_phi_impose, source : %s' % source_cos_phi, '')
    return (None, '',
            "la puissance APPARENTE injectée n'est pas calculable : la fiche "
            "onduleur ne publie pas « s_max_kva » et aucun « cos_phi_impose » "
            "n'est saisi. Aucun cos φ n'est supposé — une puissance active "
            "n'est pas une puissance apparente.")


def _phases_onduleur(conception):
    """Le régime de l'onduleur RETENU (1 ou 3), ou ``None`` si non publié."""
    if conception is None or getattr(conception, 'entree', None) is None:
        return None
    return _entier(getattr(conception.entree.onduleur, 'phases', None))


def _tension_employee_v(conception):
    """La tension que le CALCUL emploie (``EntreeElectrique``), ou ``None``.

    Elle n'est pas une saisie : c'est la tension sur laquelle les chutes et
    l'élévation ont déjà été calculées. Tout l'objet du verdict est de la
    confronter à celle du branchement RÉEL.
    """
    if conception is None or getattr(conception, 'entree', None) is None:
        return None
    return _positif(getattr(conception.entree, 'tension_reseau_v', None))


def _mot_regime(phases):
    """« monophasé » / « triphasé » — jamais un chiffre nu à l'écran."""
    return 'triphasé' if _entier(phases) == 3 else 'monophasé'


def _verdict_puissance_souscrite(saisie, injectee, source, motif):
    """Dépassement = ALERTE : une puissance souscrite se RENÉGOCIE."""
    souscrite = _positif(saisie.get('puissance_souscrite_kva'))
    if souscrite is None:
        return VerdictElectrique(
            code=CODE_PUISSANCE_SOUSCRITE, nature=NATURE_FONCTIONNELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle=MOTIF_SANS_PUISSANCE_SOUSCRITE,
            borne=None, valeur=injectee, source='')
    if injectee is None:
        return VerdictElectrique(
            code=CODE_PUISSANCE_SOUSCRITE, nature=NATURE_FONCTIONNELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle="la puissance souscrite de %s kVA est saisie, mais %s"
                    % (fr(souscrite, 1), motif),
            borne=souscrite, valeur=None,
            source='saisie — puissance_souscrite_kva')
    if injectee <= souscrite:
        return VerdictElectrique(
            code=CODE_PUISSANCE_SOUSCRITE, nature=NATURE_FONCTIONNELLE,
            statut=STATUT_OK,
            libelle="%s kVA injectés pour %s kVA souscrits : la puissance "
                    "souscrite saisie couvre l'injection."
                    % (fr(injectee, 1), fr(souscrite, 1)),
            borne=souscrite, valeur=injectee,
            source='saisie — puissance_souscrite_kva (%s)' % source)
    return VerdictElectrique(
        code=CODE_PUISSANCE_SOUSCRITE, nature=NATURE_FONCTIONNELLE,
        statut=STATUT_ALERTE,
        libelle="%s kVA injectés pour %s kVA souscrits : « "
                "puissance_souscrite_kva » est dépassée de %s kVA — "
                "augmentez l'abonnement ou bridez l'injection avant le dépôt "
                "du dossier de raccordement."
                % (fr(injectee, 1), fr(souscrite, 1),
                   fr(injectee - souscrite, 1)),
        borne=souscrite, valeur=injectee,
        source='saisie — puissance_souscrite_kva (%s)' % source)


def _verdict_regime_phases(saisie, phases_onduleur):
    """Onduleur TRIPHASÉ sur branchement MONOPHASÉ = BLOQUANT."""
    phases_saisies = _entier(saisie.get('phases'))
    if phases_saisies not in (1, 3):
        return VerdictElectrique(
            code=CODE_REGIME_PHASES, nature=NATURE_MATERIELLE,
            statut=STATUT_NON_VERIFIABLE, libelle=MOTIF_SANS_PHASES,
            borne=None, valeur=None, source='')
    if phases_onduleur not in (1, 3):
        return VerdictElectrique(
            code=CODE_REGIME_PHASES, nature=NATURE_MATERIELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle="le branchement est saisi à %d phase(s), mais la fiche "
                    "onduleur ne publie pas son régime : « phases » manque "
                    "sur la fiche, et aucun régime n'est supposé."
                    % phases_saisies,
            borne=float(phases_saisies), valeur=None, source='saisie — phases')
    if phases_onduleur == 3 and phases_saisies == 1:
        return VerdictElectrique(
            code=CODE_REGIME_PHASES, nature=NATURE_MATERIELLE,
            statut=STATUT_BLOQUANT,
            libelle="onduleur triphasé sur un branchement saisi à 1 phase : "
                    "ce raccordement est impossible en l'état. Corrigez "
                    "« phases » si l'abonnement est en réalité triphasé, ou "
                    "retenez un onduleur monophasé.",
            borne=float(phases_saisies), valeur=float(phases_onduleur),
            source='saisie — phases')
    if phases_onduleur == phases_saisies:
        return VerdictElectrique(
            code=CODE_REGIME_PHASES, nature=NATURE_MATERIELLE,
            statut=STATUT_OK,
            libelle="onduleur %s sur un branchement saisi à %d phase(s) : "
                    "les deux régimes concordent."
                    % (_mot_regime(phases_onduleur), phases_saisies),
            borne=float(phases_saisies), valeur=float(phases_onduleur),
            source='saisie — phases')
    # Onduleur(s) MONOphasé(s) sur un réseau triphasé : configuration normale
    # — c'est la répartition des phases (CALX243) qui la surveille.
    return VerdictElectrique(
        code=CODE_REGIME_PHASES, nature=NATURE_MATERIELLE, statut=STATUT_OK,
        libelle="onduleur monophasé sur un branchement saisi à 3 phases : "
                "configuration admise — la répartition des onduleurs entre "
                "les phases est traitée par le contrôle de déséquilibre.",
        borne=float(phases_saisies), valeur=float(phases_onduleur),
        source='saisie — phases')


def _verdict_tension_nominale(saisie, tension_employee):
    """Une tension saisie qui DIVERGE de celle du calcul est BLOQUANTE."""
    saisie_v = _positif(saisie.get('tension_nominale_v'))
    if saisie_v is None:
        return VerdictElectrique(
            code=CODE_TENSION_NOMINALE, nature=NATURE_MATERIELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle=MOTIF_SANS_TENSION_NOMINALE,
            borne=None, valeur=tension_employee, source='')
    if tension_employee is None:
        return VerdictElectrique(
            code=CODE_TENSION_NOMINALE, nature=NATURE_MATERIELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle="%s V sont saisis, mais aucune conception n'est "
                    "calculée : il n'y a pas encore de tension employée à "
                    "confronter." % fr(saisie_v, 0),
            borne=saisie_v, valeur=None,
            source='saisie — tension_nominale_v')
    if abs(tension_employee - saisie_v) <= 1e-6:
        return VerdictElectrique(
            code=CODE_TENSION_NOMINALE, nature=NATURE_MATERIELLE,
            statut=STATUT_OK,
            libelle="%s V saisis, %s V employés par le calcul de chute et "
                    "d'élévation : aucune divergence."
                    % (fr(saisie_v, 0), fr(tension_employee, 0)),
            borne=saisie_v, valeur=tension_employee,
            source='saisie — tension_nominale_v')
    return VerdictElectrique(
        code=CODE_TENSION_NOMINALE, nature=NATURE_MATERIELLE,
        statut=STATUT_BLOQUANT,
        libelle="« tension_nominale_v » vaut %s V alors que le calcul de "
                "chute et d'élévation emploie %s V : toutes les chutes "
                "publiées portent sur une tension qui n'est pas celle du "
                "branchement. Corrigez la saisie ou le régime retenu."
                % (fr(saisie_v, 0), fr(tension_employee, 0)),
        borne=saisie_v, valeur=tension_employee,
        source='saisie — tension_nominale_v')


# ═══════════════════════════════════════════════════════════════════════════
# CALX243 — L'ÉQUILIBRAGE DES PHASES
# ═══════════════════════════════════════════════════════════════════════════
#
# ``dimensionner_onduleurs`` (``core/electrique/onduleurs.py``) COMPTE les
# onduleurs et calcule deux ratios, mais n'attribue aucune phase ;
# ``courant_emploi_ac`` (``core/electrique/protections.py``) traite l'ensemble
# comme UNE charge. Un parc de trois onduleurs monophasés sur un abonnement
# triphasé pouvait donc être posé en ENTIER sur une seule phase sans qu'un mot
# soit dit — le neutre chauffe, le compteur déséquilibre, personne ne l'a lu.
#
# CE QUI EST ATTRIBUÉ, ET COMMENT. Rien d'imposé ⇒ TOURNIQUET : les onduleurs
# monophasés prennent L1, L2, L3, L1… dans l'ordre du parc (déterministe : à
# parc identique, répartition identique). Une attribution SAISIE par onduleur
# l'emporte et se VOIT (``source``). Un onduleur TRIPHASÉ ne prend pas de
# phase : il charge les trois, et sa puissance se répartit sur les trois.
#
# LE SEUIL N'EST PAS DANS LE CODE. Le déséquilibre est publié TOUJOURS ; le
# verdict n'est prononcé que si le réglage société ``seuil_desequilibre_pct``
# (registre ``services/parametres_cles.py``, section « electrique_societe »,
# CALX145) est posé AVEC sa source. Absent ⇒ chiffre publié, verdict omis, et
# le motif nomme la clé à régler.

#: La clé du registre des réglages société (section « electrique_societe »)
#: qui porte le seuil de déséquilibre acceptable. Aucune valeur ici : le
#: registre dit quelles clés EXISTENT, jamais ce qu'elles valent.
CLE_SEUIL_DESEQUILIBRE = 'seuil_desequilibre_pct'

#: Les trois phases d'un branchement triphasé, dans l'ordre du tourniquet.
PHASES_TRIPHASE = (1, 2, 3)

#: Le motif publié quand le seuil de déséquilibre n'est pas réglé — texte du
#: contrat CALX205.
MOTIF_SANS_SEUIL_DESEQUILIBRE = (
    "le seuil de déséquilibre acceptable n'est pas réglé pour la société : "
    "le déséquilibre est publié, aucun verdict n'est prononcé. Réglez "
    "« seuil_desequilibre_pct » avec sa source dans les réglages du module.")

#: Le motif publié sur un branchement MONOPHASÉ : il n'y a rien à équilibrer.
MOTIF_RESEAU_MONOPHASE = (
    "branchement monophasé : il n'y a qu'une seule phase, donc aucune "
    "répartition à calculer et aucun déséquilibre à mesurer.")


def _puissance_onduleur(onduleur):
    """``(valeur, cle)`` — la puissance d'un onduleur ET la clé qui la porte.

    Deux clés admises, jamais mélangées dans un même parc : ``puissance_kva``
    (apparente) ou ``ac_kw`` (active). Le déséquilibre est un RAPPORT, donc
    l'unité se simplifie — à condition qu'elle soit la MÊME pour tous, ce que
    :func:`repartition_des_phases` vérifie au lieu de le supposer.
    """
    for cle in ('puissance_kva', 'ac_kw'):
        valeur = _positif(onduleur.get(cle))
        if valeur is not None:
            return (valeur, cle)
    return (None, '')


def _phase_imposee(onduleur):
    """La phase SAISIE d'un onduleur (1/2/3), ou ``None``.

    « L1 »/« L2 »/« L3 » sont admis : c'est ainsi qu'un schéma unifilaire les
    nomme, et refuser cette écriture ferait ressaisir l'évidence.
    """
    brut = onduleur.get('phase_imposee')
    if brut is None:
        return None
    if isinstance(brut, str):
        chiffres = ''.join(c for c in brut if c.isdigit())
        brut = chiffres or None
    numero = _entier(brut)
    return numero if numero in PHASES_TRIPHASE else None


def _reglage(reglages, cle):
    """``(valeur, source)`` d'un réglage ``{valeur, source}``, sinon vide.

    Une valeur SANS source est traitée comme NON saisie : c'est la règle du
    registre CALX145, et un seuil dont personne ne dit d'où il sort ne peut
    pas fonder un verdict.
    """
    saisie = (reglages or {}).get(cle)
    if not isinstance(saisie, dict):
        return (None, '')
    valeur = _nombre(saisie.get('valeur'))
    source = saisie.get('source') or ''
    if valeur is None or not source:
        return (None, '')
    return (valeur, source)


def repartition_des_phases(onduleurs, phases_reseau, *, reglages=None):
    """CALX243 — qui est sur quelle phase, et de combien ça déséquilibre.

    Args:
        onduleurs: la liste des onduleurs POSÉS, chacun un dict
            ``{repere, puissance_kva | ac_kw}`` ; clés facultatives
            ``phases`` (1 ou 3 — un triphasé charge les trois) et
            ``phase_imposee`` (1/2/3 ou « L1 »/« L2 »/« L3 »).
        phases_reseau: le régime SAISI du branchement (1 ou 3). ``None`` ⇒
            aucun calcul, et le motif nomme « phases ».
        reglages: la section société « electrique_societe »
            ``{clé: {valeur, source}}`` — seul ``seuil_desequilibre_pct`` y
            est lu, et seulement s'il porte sa source.

    Returns:
        ``{affectation, par_phase, desequilibre_pct, seuil_pct,
        source_seuil, verdict, omissions}``. ``desequilibre_pct`` est l'écart
        entre la phase la plus chargée et la moins chargée, EN POURCENTAGE DE
        LA PLUS CHARGÉE.

    Fonction PURE : aucune base, aucun réseau, aucune horloge.
    """
    seuil, source_seuil = _reglage(reglages, CLE_SEUIL_DESEQUILIBRE)
    vide = {'affectation': [], 'par_phase': {}, 'desequilibre_pct': None,
            'seuil_pct': seuil, 'source_seuil': source_seuil or None}

    regime = _entier(phases_reseau)
    if regime not in (1, 3):
        return dict(vide, omissions=[MOTIF_SANS_PHASES],
                    verdict=_verdict_desequilibre(None, seuil, source_seuil,
                                                  MOTIF_SANS_PHASES))
    if regime == 1:
        return dict(vide, omissions=[MOTIF_RESEAU_MONOPHASE],
                    verdict=_verdict_desequilibre(None, seuil, source_seuil,
                                                  MOTIF_RESEAU_MONOPHASE))

    affectation, charges, omissions = _attribuer(onduleurs)
    if omissions:
        return dict(vide, affectation=affectation, omissions=omissions,
                    verdict=_verdict_desequilibre(None, seuil, source_seuil,
                                                  omissions[0]))

    plus_chargee = max(charges.values())
    if plus_chargee <= 0:
        motif = ("aucune puissance n'est posée sur les phases : il n'y a pas "
                 "de déséquilibre à mesurer.")
        return dict(vide, affectation=affectation, par_phase=charges,
                    omissions=[motif],
                    verdict=_verdict_desequilibre(None, seuil, source_seuil,
                                                  motif))
    desequilibre = round(
        (plus_chargee - min(charges.values())) / plus_chargee * 100.0, 4)
    return {
        'affectation': affectation,
        'par_phase': charges,
        'desequilibre_pct': desequilibre,
        'seuil_pct': seuil,
        'source_seuil': source_seuil or None,
        'verdict': _verdict_desequilibre(desequilibre, seuil, source_seuil,
                                         ''),
        'omissions': [],
    }


def _attribuer(onduleurs):
    """``(affectation, charges, omissions)`` — tourniquet, saisie honorée."""
    affectation = []
    charges = {phase: 0.0 for phase in PHASES_TRIPHASE}
    omissions = []
    unites = set()
    rang_tourniquet = 0
    for rang, onduleur in enumerate(onduleurs or (), start=1):
        if not isinstance(onduleur, dict):
            continue
        repere = str(onduleur.get('repere') or 'onduleur n°%d' % rang)
        puissance, cle = _puissance_onduleur(onduleur)
        if puissance is None:
            omissions.append(
                "%s : aucune puissance n'est publiée (« puissance_kva » ou "
                "« ac_kw ») — la répartition des phases ne se calcule pas sur "
                "une puissance supposée." % repere)
            continue
        unites.add(cle)
        if _entier(onduleur.get('phases')) == 3:
            # Un onduleur triphasé ne « prend » pas une phase : il charge les
            # trois. Sa puissance se répartit également entre elles.
            for phase in PHASES_TRIPHASE:
                charges[phase] += puissance / len(PHASES_TRIPHASE)
            affectation.append({
                'repere': repere, 'phase': None, 'phases': 3,
                'puissance': puissance, 'unite': cle,
                'source': 'onduleur triphasé — charge les trois phases'})
            continue
        imposee = _phase_imposee(onduleur)
        if imposee is None:
            phase = PHASES_TRIPHASE[rang_tourniquet % len(PHASES_TRIPHASE)]
            rang_tourniquet += 1
            source = 'tourniquet — aucune phase imposée'
        else:
            phase = imposee
            source = 'saisie — phase_imposee'
        charges[phase] += puissance
        affectation.append({
            'repere': repere, 'phase': phase, 'phases': 1,
            'puissance': puissance, 'unite': cle, 'source': source})

    if len(unites) > 1:
        omissions.append(
            "le parc mélange « puissance_kva » et « ac_kw » : un déséquilibre "
            "se mesure entre grandeurs de MÊME nature. Publiez la même clé "
            "pour tous les onduleurs.")
    charges = {phase: round(valeur, 4) for phase, valeur in charges.items()}
    return (affectation, charges, omissions)


def _verdict_desequilibre(desequilibre, seuil, source_seuil, motif):
    """Le verdict CALX215 du déséquilibre — omis tant que le seuil manque."""
    if seuil is None:
        return VerdictElectrique(
            code=CODE_DESEQUILIBRE, nature=NATURE_FONCTIONNELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle=MOTIF_SANS_SEUIL_DESEQUILIBRE,
            borne=None, valeur=desequilibre, source='')
    source = 'réglage société — %s, source : %s' % (CLE_SEUIL_DESEQUILIBRE,
                                                    source_seuil)
    if desequilibre is None:
        return VerdictElectrique(
            code=CODE_DESEQUILIBRE, nature=NATURE_FONCTIONNELLE,
            statut=STATUT_NON_VERIFIABLE,
            libelle="le seuil de %s %% est réglé, mais le déséquilibre n'est "
                    "pas calculable : %s" % (fr(seuil, 1), motif),
            borne=seuil, valeur=None, source=source)
    if desequilibre <= seuil:
        return VerdictElectrique(
            code=CODE_DESEQUILIBRE, nature=NATURE_FONCTIONNELLE,
            statut=STATUT_OK,
            libelle="%s %% de déséquilibre entre les phases pour un seuil "
                    "réglé à %s %% : la répartition tient."
                    % (fr(desequilibre), fr(seuil, 1)),
            borne=seuil, valeur=desequilibre, source=source)
    return VerdictElectrique(
        code=CODE_DESEQUILIBRE, nature=NATURE_FONCTIONNELLE,
        statut=STATUT_ALERTE,
        libelle="%s %% de déséquilibre entre les phases pour un seuil réglé "
                "à %s %% : répartissez les onduleurs monophasés autrement "
                "(« phase_imposee ») ou corrigez le seuil."
                % (fr(desequilibre), fr(seuil, 1)),
        borne=seuil, valeur=desequilibre, source=source)


# ═══════════════════════════════════════════════════════════════════════════
# CALX244 — LES TROIS BLOCS DU CONTRAT, ASSEMBLÉS UNE SEULE FOIS
# ═══════════════════════════════════════════════════════════════════════════
#
# Les trois calculs ci-dessus répondent chacun à UNE question ; l'écran, lui,
# lit UN document — ``{saisie, calcul, verdicts}`` du contrat CALX205
# (``contract_samples/calepinage_raccordement.json``). Assembler ce document
# dans la vue mettrait la forme du contrat dans une couche HTTP, où aucun
# test ne peut l'atteindre sans base de données ; il est donc assemblé ICI,
# par une fonction PURE que la vue se contente d'appeler.
#
# CE QUE CETTE FONCTION N'INVENTE PAS. Le courant qui traverse un tronçon
# n'est JAMAIS fabriqué : il est lu sur le tronçon publié par
# ``services/troncons.py`` (``ib_a``, le courant d'emploi que la conception
# électrique justifie). Absent, c'est l'omission NOMMÉE de
# :func:`elevation_de_tension` qui est publiée — pas une élévation partielle.
#
# CE QUI EST PARCOURU. Seul le côté ALTERNATIF remonte la tension au point de
# livraison : c'est le courant INJECTÉ par l'onduleur qui traverse la liaison
# jusqu'au compteur. Les tronçons continus sont donc marqués non parcourus —
# ils ne sont pas « oubliés », ils sont en amont de l'onduleur.

#: Les sept champs de la saisie du contrat CALX205, dans son ordre.
CHAMPS_SAISIE = ('puissance_souscrite_kva', 'phases', 'tension_nominale_v',
                 'limite_elevation_pct', 'source_limite', 'cos_phi_impose',
                 'source_cos_phi')

#: Les champs saisis et leur intitulé français : un refus les NOMME tels que
#: l'écran les affiche (règle fondateur du 08/09/2026 — l'erreur désigne le
#: champ fautif, jamais un « non enregistré » générique).
INTITULES_SAISIE = {
    'puissance_souscrite_kva': 'la puissance souscrite (kVA)',
    'tension_nominale_v': 'la tension nominale (V)',
    'limite_elevation_pct': "la limite d'élévation (%)",
    'cos_phi_impose': 'le cos φ imposé',
    'phases': 'le nombre de phases du branchement',
}

#: Le statut PUBLIÉ pour un contrôle qui n'a pas eu lieu. Le noyau le nomme
#: ``non_verifiable`` (``core/electrique/types.py``) ; le contrat CALX205 le
#: publie ``omis``. Une seule traduction, à un seul endroit.
STATUT_PUBLIE_OMIS = 'omis'

#: Le préfixe des champs nommés par un refus : l'écran sait ainsi sous quel
#: champ poser le message, sans découper une phrase.
PREFIXE_CHAMP = 'raccordement.'


def _refus_saisie(champ, phrase):
    return RaccordementInvalide(phrase, champ=PREFIXE_CHAMP + champ)


def _texte_saisi(valeur, champ):
    """Un texte de provenance, ou ``None`` — jamais un objet quelconque."""
    if valeur is None:
        return None
    if not isinstance(valeur, str):
        raise _refus_saisie(
            champ, "La provenance doit être un texte : indiquez le document "
                   "qui fixe cette valeur (texte réglementaire, contrat de "
                   "raccordement ou prescription du gestionnaire de réseau).")
    return valeur.strip() or None


def _nombre_saisi(valeur, champ):
    """Un nombre STRICTEMENT positif, ``None``, ou un refus qui NOMME."""
    if valeur is None or valeur == '':
        return None
    nombre = _nombre(valeur)
    if nombre is None:
        raise _refus_saisie(
            champ, "%s n'est pas un nombre : saisissez une valeur chiffrée, "
                   "ou laissez le champ vide si elle n'est pas connue."
                   % INTITULES_SAISIE[champ].capitalize())
    if nombre <= 0:
        raise _refus_saisie(
            champ, "%s doit être strictement positive : « %s » ne décrit "
                   "aucun branchement réel."
                   % (INTITULES_SAISIE[champ].capitalize(), fr(nombre)))
    return nombre


def _phases_saisies(valeur):
    """1 ou 3 — un régime hors de ces deux-là est REFUSÉ, jamais ignoré."""
    if valeur is None or valeur == '':
        return None
    nombre = _nombre(valeur)
    if nombre is None or nombre != int(nombre) or int(nombre) not in (1, 3):
        raise _refus_saisie(
            'phases', "Un branchement est monophasé (1) ou triphasé (3) : "
                      "saisissez 1 ou 3, ou laissez le champ vide tant que "
                      "le régime n'est pas connu.")
    return int(nombre)


def _saisie_publiee(brute):
    """Les SEPT champs du contrat, normalisés — aucun autre n'est retenu.

    Une clé inconnue du corps est ignorée : le contrat CALX205 fige la
    saisie à sept champs, et accepter une huitième clé la ferait vivre dans
    la base sans qu'aucun écran ni aucun calcul ne la lise jamais.
    """
    brute = brute if isinstance(brute, dict) else {}
    saisie = {
        'phases': _phases_saisies(brute.get('phases')),
        'source_limite': _texte_saisi(brute.get('source_limite'),
                                      'source_limite'),
        'source_cos_phi': _texte_saisi(brute.get('source_cos_phi'),
                                       'source_cos_phi'),
    }
    for champ in ('puissance_souscrite_kva', 'tension_nominale_v',
                  'limite_elevation_pct', 'cos_phi_impose'):
        saisie[champ] = _nombre_saisi(brute.get(champ), champ)
    return {champ: saisie[champ] for champ in CHAMPS_SAISIE}


def _injection(saisie):
    """Ce que :func:`elevation_de_tension` lit de la saisie.

    Aucun ``courant_a`` global n'est posé : le courant vient du TRONÇON, et
    son absence est une omission nommée, jamais une valeur de confort.
    """
    return {
        'tension_nominale_v': saisie['tension_nominale_v'],
        'phases': saisie['phases'],
        'limite_elevation_pct': saisie['limite_elevation_pct'],
        'source_limite': saisie['source_limite'],
    }


def _troncons_pour_elevation(troncons):
    """Les tronçons de ``services/troncons.py``, lus par l'élévation.

    La longueur garde son ORIGINE (discipline ``Longueur``,
    ``services/cables.py``) : elle voyage en dict, jamais en nombre nu.
    """
    lignes = []
    for troncon in troncons or ():
        if not isinstance(troncon, dict):
            continue
        lignes.append({
            'repere': troncon.get('id') or troncon.get('repere'),
            'longueur_m': {'valeur_m': troncon.get('longueur_m'),
                           'origine': troncon.get('longueur_origine') or ''},
            'section_mm2': troncon.get('section_mm2'),
            'courant_a': troncon.get('ib_a'),
            'parcouru': troncon.get('cote') == COTE_AC,
        })
    return lignes


def _parc_onduleurs(conception):
    """Le parc RETENU par la conception, onduleur par onduleur.

    Le nombre vient du dimensionnement (``evaluer_onduleurs``) et la
    puissance de la FICHE : ``s_max_kva`` quand elle la publie, sinon
    ``ac_kw``. Ni l'une ni l'autre ⇒ l'onduleur entre sans puissance, et
    :func:`repartition_des_phases` OMET en le nommant.

    Aucune phase n'est imposée ici : le document v2 (CALX201) ne porte
    aucune affectation de phase, donc le tourniquet s'applique et il le dit
    dans la ``source`` de chaque ligne.
    """
    evaluation = _evaluation(conception)
    if evaluation is None or not evaluation.nombre:
        return []
    onduleur = conception.entree.onduleur
    s_max = _positif(getattr(onduleur, 's_max_kva', None))
    active = _positif(getattr(onduleur, 'ac_kw', None))
    phases = _entier(getattr(onduleur, 'phases', None))
    parc = []
    for rang in range(1, int(evaluation.nombre) + 1):
        ligne = {'repere': 'Onduleur %d' % rang}
        if s_max is not None:
            ligne['puissance_kva'] = s_max
        elif active is not None:
            ligne['ac_kw'] = active
        if phases is not None:
            ligne['phases'] = phases
        parc.append(ligne)
    return parc


def _verdict_publie(verdict):
    """Un ``VerdictElectrique`` (CALX215) dans la forme du contrat CALX205.

    ``libelle`` est l'INTITULÉ du contrôle (toujours le même) et ``detail``
    la phrase motivée par les nombres : les confondre priverait l'écran d'un
    titre stable, ou le test d'une phrase qui dit POURQUOI.
    """
    return {
        'code': verdict.code,
        'libelle': LIBELLES.get(verdict.code, verdict.code),
        'statut': (STATUT_PUBLIE_OMIS
                   if verdict.statut == STATUT_NON_VERIFIABLE
                   else verdict.statut),
        'detail': verdict.libelle,
        'source': verdict.source or None,
    }


def bloc_raccordement(conception, saisie, troncons, reglages=None):
    """CALX244 — le document ``{saisie, calcul, verdicts}`` du raccordement.

    Args:
        conception: la ``Conception`` de CAL124, ou ``None``.
        saisie: le corps SAISI (les sept champs du contrat CALX205) ; les
            clés inconnues sont ignorées, les valeurs illisibles REFUSÉES en
            nommant leur champ.
        troncons: les tronçons publiés par
            ``services/troncons.py::troncons_du_calepinage`` (clé
            ``troncons``) — leur ``ib_a`` est le seul courant lu.
        reglages: la section société « electrique_societe » du registre
            (``services/parametres_cles.py``), ``{clé: {valeur, source}}``.

    Returns:
        ``{saisie, calcul, verdicts}`` — les CINQ verdicts sont toujours
        présents, dans l'ordre du contrat, et un contrôle qui n'a pas eu
        lieu vaut ``omis`` avec le motif qui nomme ce qui manque.

    Raises:
        RaccordementInvalide: saisie illisible, limite sans
            ``source_limite``, cos φ sans ``source_cos_phi``.

    Fonction PURE : aucune base, aucun réseau, aucune horloge.
    """
    saisie = _saisie_publiee(saisie)
    elevation = elevation_de_tension(_troncons_pour_elevation(troncons),
                                     _injection(saisie))
    branchement = verdicts_raccordement(conception, saisie)
    equilibrage = repartition_des_phases(_parc_onduleurs(conception),
                                         saisie['phases'],
                                         reglages=reglages)
    verdicts = ((elevation['verdict'],) + tuple(branchement['verdicts'])
                + (equilibrage['verdict'],))
    return {
        'saisie': saisie,
        'calcul': {
            'elevation_pct': elevation['elevation_pct'],
            'marge_pct': elevation['marge_pct'],
            'puissance_injectee_kva': branchement['puissance_injectee_kva'],
            'desequilibre_pct': equilibrage['desequilibre_pct'],
        },
        'verdicts': [_verdict_publie(verdict) for verdict in verdicts],
    }
