# -*- coding: utf-8 -*-
"""PV36 — sections de câble : DEUX critères, et on dit lequel a tranché.

Une section n'est jamais choisie par un seul critère. Elle doit satisfaire :

1. **l'échauffement** — le courant admissible du câble (Iz) doit tenir le
   courant que la protection laisse passer, d'où la chaîne
   ``Ib ≤ In ≤ Iz`` (NF C 15-100 §433.1) : le courant d'emploi sous le calibre
   de protection, le calibre sous le courant admissible du câble. Une seule des
   deux inégalités qui saute et le câble chauffe avant que la protection ne
   coupe ;
2. **la chute de tension** — ``u = 2 × ρ × L × I / S`` en continu et en
   monophasé, ``u = √3 × ρ × L × I / S`` en triphasé (le facteur 2 est le
   trajet ALLER-RETOUR ; en triphasé les trois phases se compensent, d'où √3).

La section retenue est la plus petite qui satisfait les DEUX, et le résultat
NOMME celui qui a tranché : sur une longue liaison c'est presque toujours la
chute de tension, pas l'échauffement — un lecteur qui l'ignore croit pouvoir
descendre d'une section.

Toutes les valeurs normatives portent leur source. Les barèmes d'intensité
admissible supposent la méthode de pose de référence indiquée : un groupement de
circuits ou une ambiance chaude leur applique des facteurs de correction qui
relèvent de l'étude d'exécution, hors moteur.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from core.electrique.types import Cable, fr, fr_a

__all__ = [
    "SECTIONS_MM2", "AMPACITE_H1Z2Z2K", "AMPACITE_U1000R2V_MONO",
    "AMPACITE_U1000R2V_TRI", "RHO_CUIVRE_20C", "COEFF_ISC_DIMENSIONNEMENT",
    "CHUTE_CIBLE_DC_PCT", "CHUTE_MAX_DC_PCT", "CHUTE_CIBLE_AC_PCT",
    "CHUTE_MAX_AC_PCT", "SectionProposee", "ResultatCables",
    "ampacite", "chute_tension_v", "chute_tension_pct", "proposer_section",
    "verifier_ib_in_iz", "dimensionner_cables",
]

#: Sections normalisées retenues par le moteur (mm², cuivre).
SECTIONS_MM2 = (2.5, 4.0, 6.0, 10.0, 16.0, 25.0)

#: Intensité admissible du câble solaire H1Z2Z2-K (EN 50618 / IEC 62930),
#: DEUX câbles jointifs à l'air libre, ambiance 60 °C, âme admise à 120 °C.
#: C'est le barème du câble de chaîne, spécifiquement conçu pour le DC PV.
AMPACITE_H1Z2Z2K = ((2.5, 41.0), (4.0, 55.0), (6.0, 70.0), (10.0, 98.0),
                    (16.0, 132.0), (25.0, 176.0))

#: Intensité admissible du câble AC U-1000 R2V cuivre isolé PR, méthode de
#: référence C (IEC 60364-5-52 tableau B.52.4, reprise NF C 15-100), ambiance
#: 30 °C — DEUX conducteurs chargés (monophasé).
AMPACITE_U1000R2V_MONO = ((2.5, 31.0), (4.0, 42.0), (6.0, 54.0), (10.0, 75.0),
                          (16.0, 100.0), (25.0, 133.0))

#: Idem, TROIS conducteurs chargés (triphasé) — le barème est plus sévère.
AMPACITE_U1000R2V_TRI = ((2.5, 28.0), (4.0, 37.0), (6.0, 48.0), (10.0, 66.0),
                         (16.0, 88.0), (25.0, 117.0))

#: Résistivité du cuivre à 20 °C (Ω·mm²/m) — valeur du guide UTE C 15-105 pour
#: le calcul de chute de tension. En service à chaud, la pratique majore cette
#: valeur ; le moteur reste sur la valeur à 20 °C, comme le guide, et compense
#: par une CIBLE de chute plus basse que le maximum admissible.
RHO_CUIVRE_20C = 0.01851

#: Coefficient de dimensionnement des câbles DC : 1,25 × Isc (IEC 62548 §7.3 —
#: l'ensoleillement peut dépasser 1000 W/m², le courant aussi).
COEFF_ISC_DIMENSIONNEMENT = 1.25

#: Chute de tension côté DC : cible 1,5 %, maximum 3 % (UTE C 15-712-1 —
#: au-delà, la perte de production n'est plus un détail d'installation).
CHUTE_CIBLE_DC_PCT = 1.5
CHUTE_MAX_DC_PCT = 3.0

#: Chute de tension côté AC entre onduleur et tableau : cible 1 %, maximum 2 %
#: (UTE C 15-712-1 ; NF C 15-100 §525 plafonne l'installation entière à 3 %).
CHUTE_CIBLE_AC_PCT = 1.0
CHUTE_MAX_AC_PCT = 2.0

CRITERE_ECHAUFFEMENT = "échauffement (Iz)"
CRITERE_CHUTE = "chute de tension"
CRITERE_LES_DEUX = "échauffement et chute de tension"


@dataclass(frozen=True)
class SectionProposee:
    """Une section proposée AVEC le critère qui l'a imposée."""

    section_mm2: float
    iz_a: float
    chute_pct: float
    critere: str
    section_par_echauffement_mm2: Optional[float] = None
    section_par_chute_mm2: Optional[float] = None
    #: La cible de chute n'est pas tenue même à la plus grosse section du barème.
    hors_bareme: bool = False


@dataclass(frozen=True)
class ResultatCables:
    cables: Tuple[Cable, ...] = ()
    bloquants: Tuple[str, ...] = ()
    alertes: Tuple[str, ...] = ()


def ampacite(section_mm2, bareme=AMPACITE_H1Z2Z2K):
    """Intensité admissible (A) d'une section, ``None`` hors barème."""
    for section, iz in bareme:
        if abs(section - float(section_mm2)) < 1e-9:
            return iz
    return None


def chute_tension_v(longueur_m, courant_a, section_mm2, coefficient=2.0,
                    rho=RHO_CUIVRE_20C):
    """``u = coefficient × ρ × L × I / S`` (V).

    ``coefficient`` vaut 2 en continu et en monophasé (aller-retour) et √3 en
    triphasé. ``longueur_m`` est la longueur SIMPLE de la liaison : c'est le
    coefficient qui porte l'aller-retour, jamais la longueur.
    """
    section = float(section_mm2 or 0.0)
    if section <= 0:
        return 0.0
    return (coefficient * rho * float(longueur_m or 0.0)
            * float(courant_a or 0.0) / section)


def chute_tension_pct(longueur_m, courant_a, section_mm2, tension_v,
                      coefficient=2.0, rho=RHO_CUIVRE_20C):
    """Chute de tension en % de la tension de service."""
    tension = float(tension_v or 0.0)
    if tension <= 0:
        return 0.0
    chute = chute_tension_v(longueur_m, courant_a, section_mm2, coefficient,
                            rho)
    return chute / tension * 100.0


def verifier_ib_in_iz(ib_a, in_a, iz_a):
    """``Ib ≤ In ≤ Iz`` (NF C 15-100 §433.1) — ``(conforme, motif)``.

    Sans protection dédiée (``in_a`` absent), la règle se réduit à ``Ib ≤ Iz``.
    """
    ib = float(ib_a or 0.0)
    iz = float(iz_a or 0.0)
    if in_a is None:
        if ib <= iz + 1e-9:
            return (True, "")
        return (False, "courant d'emploi %s au-dessus du courant admissible du "
                       "câble %s" % (fr_a(ib), fr_a(iz)))
    calibre = float(in_a)
    if ib > calibre + 1e-9:
        return (False, "Ib %s > In %s — la protection couperait au courant "
                       "d'emploi" % (fr_a(ib), fr_a(calibre)))
    if calibre > iz + 1e-9:
        return (False, "In %s > Iz %s — le câble chaufferait avant que la "
                       "protection ne coupe" % (fr_a(calibre), fr_a(iz)))
    return (True, "")


def proposer_section(courant_ib_a, longueur_m, tension_v, cible_pct,
                     bareme=AMPACITE_H1Z2Z2K, coefficient=2.0,
                     calibre_in_a=None, courant_service_a=None):
    """Plus petite section qui satisfait Iz ET la cible de chute de tension.

    ``courant_ib_a`` sert au critère d'ÉCHAUFFEMENT (courant de dimensionnement,
    majoré le cas échéant), ``courant_service_a`` au critère de CHUTE (courant
    réellement transporté en fonctionnement) — les deux diffèrent côté DC, où le
    câble se dimensionne sur 1,25 × Isc mais ne transporte que l'Imp.
    """
    courant_chute = (float(courant_ib_a or 0.0) if courant_service_a is None
                     else float(courant_service_a))
    exigence_thermique = max(float(courant_ib_a or 0.0),
                             float(calibre_in_a or 0.0))

    section_thermique = None
    section_chute = None
    for section, iz in bareme:
        if section_thermique is None and iz + 1e-9 >= exigence_thermique:
            section_thermique = section
        chute = chute_tension_pct(longueur_m, courant_chute, section, tension_v,
                                  coefficient)
        if section_chute is None and chute <= cible_pct + 1e-9:
            section_chute = section

    hors_bareme = section_chute is None
    plus_grosse = bareme[-1][0]
    if section_thermique is None:
        section_thermique = plus_grosse
    if section_chute is None:
        section_chute = plus_grosse

    retenue = max(section_thermique, section_chute)
    if section_thermique == section_chute:
        critere = CRITERE_LES_DEUX
    elif retenue == section_chute:
        critere = CRITERE_CHUTE
    else:
        critere = CRITERE_ECHAUFFEMENT

    return SectionProposee(
        section_mm2=retenue,
        iz_a=ampacite(retenue, bareme) or 0.0,
        chute_pct=chute_tension_pct(longueur_m, courant_chute, retenue,
                                    tension_v, coefficient),
        critere=critere,
        section_par_echauffement_mm2=section_thermique,
        section_par_chute_mm2=section_chute,
        hors_bareme=hors_bareme,
    )


def dimensionner_cables(entree, resultat_chaines=None,
                        resultat_protections=None):
    """PV36 — le câble de chaîne DC et la liaison AC, dimensionnés et vérifiés."""
    cables = []
    alertes = []
    bloquants = []

    chaines = resultat_chaines.chaines if resultat_chaines else ()
    triphase = int(entree.phases or 1) == 3

    # ── Câble DC de chaîne ───────────────────────────────────────────────────
    if chaines:
        module = entree.module
        # Échauffement : 1,25 × Isc (IEC 62548). Chute : Imp, le courant réel.
        ib_dc = module.isc_a * COEFF_ISC_DIMENSIONNEMENT
        imp = module.imp_a or module.isc_a
        tension_service = min(c.vmp_stc_v for c in chaines)
        calibre = (resultat_protections.calibre_fusible_a
                   if resultat_protections is not None else None)
        proposee = proposer_section(
            courant_ib_a=ib_dc, longueur_m=entree.dc_m,
            tension_v=tension_service, cible_pct=CHUTE_CIBLE_DC_PCT,
            bareme=AMPACITE_H1Z2Z2K, coefficient=2.0, calibre_in_a=calibre,
            courant_service_a=imp)
        conforme, motif = verifier_ib_in_iz(ib_dc, calibre, proposee.iz_a)
        depasse = proposee.chute_pct > CHUTE_MAX_DC_PCT + 1e-9
        if motif:
            bloquants.append("câble DC : %s" % motif)
        if depasse:
            bloquants.append(
                "câble DC : chute de tension de %s %% au-dessus du maximum "
                "admissible de %s %% même en %s mm² — raccourcir la liaison ou "
                "rapprocher l'onduleur"
                % (fr(proposee.chute_pct, 2), fr(CHUTE_MAX_DC_PCT, 1),
                   fr(proposee.section_mm2, 1)))
        elif proposee.hors_bareme:
            alertes.append(
                "câble DC : cible de %s %% non tenue, %s %% retenus en %s mm² "
                "(sous le maximum de %s %%)"
                % (fr(CHUTE_CIBLE_DC_PCT, 1), fr(proposee.chute_pct, 2),
                   fr(proposee.section_mm2, 1), fr(CHUTE_MAX_DC_PCT, 1)))
        cables.append(Cable(
            repere="W1",
            designation="Câble solaire H1Z2Z2-K 1000 V DC (2 conducteurs par "
                        "chaîne, + et −)",
            section_mm2=proposee.section_mm2,
            longueur_m=float(entree.dc_m or 0.0),
            nb_conducteurs=2 * len(chaines),
            ib_a=ib_dc,
            in_a=calibre,
            iz_a=proposee.iz_a,
            chute_tension_pct=proposee.chute_pct,
            chute_cible_pct=CHUTE_CIBLE_DC_PCT,
            chute_max_pct=CHUTE_MAX_DC_PCT,
            conforme=conforme and not depasse,
            critere_dimensionnant=proposee.critere,
            regle_source=(
                "EN 50618 (Iz H1Z2Z2-K) + IEC 62548 §7.3 (Ib = 1,25 × Isc = "
                "%s) + NF C 15-100 §433.1 (Ib ≤ In ≤ Iz) ; chute u = 2 × %s × "
                "L × I / S, cible %s %%, maximum %s %% (UTE C 15-712-1)"
                % (fr_a(ib_dc), fr(RHO_CUIVRE_20C, 5),
                   fr(CHUTE_CIBLE_DC_PCT, 1), fr(CHUTE_MAX_DC_PCT, 1))),
        ))

    # ── Liaison AC onduleur → tableau ────────────────────────────────────────
    ib_ac = (resultat_protections.courant_ac_ib_a
             if resultat_protections is not None else 0.0)
    calibre_ac = (resultat_protections.calibre_ac_a
                  if resultat_protections is not None else None)
    if ib_ac > 0:
        bareme = AMPACITE_U1000R2V_TRI if triphase else AMPACITE_U1000R2V_MONO
        coefficient = math.sqrt(3.0) if triphase else 2.0
        proposee = proposer_section(
            courant_ib_a=ib_ac, longueur_m=entree.ac_m,
            tension_v=entree.tension_reseau_v, cible_pct=CHUTE_CIBLE_AC_PCT,
            bareme=bareme, coefficient=coefficient, calibre_in_a=calibre_ac)
        conforme, motif = verifier_ib_in_iz(ib_ac, calibre_ac, proposee.iz_a)
        depasse = proposee.chute_pct > CHUTE_MAX_AC_PCT + 1e-9
        if motif:
            bloquants.append("câble AC : %s" % motif)
        if depasse:
            bloquants.append(
                "câble AC : chute de tension de %s %% au-dessus du maximum "
                "admissible de %s %% même en %s mm²"
                % (fr(proposee.chute_pct, 2), fr(CHUTE_MAX_AC_PCT, 1),
                   fr(proposee.section_mm2, 1)))
        elif proposee.hors_bareme:
            alertes.append(
                "câble AC : cible de %s %% non tenue, %s %% retenus en %s mm² "
                "(sous le maximum de %s %%)"
                % (fr(CHUTE_CIBLE_AC_PCT, 1), fr(proposee.chute_pct, 2),
                   fr(proposee.section_mm2, 1), fr(CHUTE_MAX_AC_PCT, 1)))
        cables.append(Cable(
            repere="W2",
            designation="Câble AC U-1000 R2V cuivre (%s)"
                        % ("3P + N + T, triphasé" if triphase
                           else "P + N + T, monophasé"),
            section_mm2=proposee.section_mm2,
            longueur_m=float(entree.ac_m or 0.0),
            nb_conducteurs=5 if triphase else 3,
            ib_a=ib_ac,
            in_a=calibre_ac,
            iz_a=proposee.iz_a,
            chute_tension_pct=proposee.chute_pct,
            chute_cible_pct=CHUTE_CIBLE_AC_PCT,
            chute_max_pct=CHUTE_MAX_AC_PCT,
            conforme=conforme and not depasse,
            critere_dimensionnant=proposee.critere,
            regle_source=(
                "IEC 60364-5-52 tableau B.52.4 méthode C (Iz U-1000 R2V) + "
                "NF C 15-100 §433.1 (Ib ≤ In ≤ Iz) ; chute u = %s × %s × L × "
                "I / S, cible %s %%, maximum %s %% (UTE C 15-712-1)"
                % ("√3" if triphase else "2", fr(RHO_CUIVRE_20C, 5),
                   fr(CHUTE_CIBLE_AC_PCT, 1), fr(CHUTE_MAX_AC_PCT, 1))),
        ))

    return ResultatCables(cables=tuple(cables), bloquants=tuple(bloquants),
                          alertes=tuple(alertes))
