# -*- coding: utf-8 -*-
"""PV35 — les PROTECTIONS, chacune posée par une RÈGLE qui reste citée.

Un dossier de raccordement se défend organe par organe : un bureau de contrôle
ne demande pas « pourquoi un parafoudre » mais « en vertu de quoi, et pourquoi ce
calibre-là ». Chaque ``Protection`` produite ici porte donc son ``regle_source``,
et aucune règle n'est appliquée « parce que c'est l'habitude » :

* **fusible de chaîne** — EXIGÉ seulement à partir de 3 chaînes en parallèle
  (IEC 62548 §7.3.3 : à 2 chaînes, le courant inverse maximal que peut subir une
  chaîne défaillante vaut l'Isc de l'autre, sous la tenue du module ; à 3, il
  double et la protection devient nécessaire). Poser un fusible sur 2 chaînes est
  une dépense inutile, ne pas en poser sur 3 est un défaut ;
* **parafoudre DC Type 2** — EXIGÉ dès que la liaison DC dépasse 10 m, ou en zone
  kéraunique (UTE C 15-712-1 : la longueur critique de liaison dépend de la
  densité de foudroiement ; 10 m est le seuil retenu ici, valeur de la pratique
  du guide pour les installations BT courantes) ;
* **sectionneur DC** — TOUJOURS : un onduleur doit pouvoir être isolé de son
  champ en charge (UTE C 15-712-1 §5.4 / IEC 62548 §5.3) ;
* **disjoncteur AC** — calibre normalisé immédiatement ≥ Ib, Ib déduit de la
  puissance AC et du nombre de phases (230 V mono, 400 V·√3 tri) ;
* **parafoudre AC Type 2** — à l'origine de la partie AC (NF C 15-100 §534) ;
* **DDR type A 300 mA** — régime TT (NF C 15-100 §411.5 : en TT la protection
  contre les contacts indirects repose sur un différentiel) ; type A parce qu'un
  onduleur PV peut injecter une composante continue (IEC 62109) ;
* **mise à la terre** — prise de terre + liaison équipotentielle des masses
  (NF C 15-100 §542 / UTE C 15-712-1).

AUCUN PRIX : ce module produit des calibres et des quantités.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from core.electrique.types import Protection, REGIME_TT, fr, fr_a

__all__ = [
    "CALIBRES_FUSIBLE_GPV_A", "CALIBRES_DISJONCTEUR_A",
    "SEUIL_CHAINES_PARALLELES_FUSIBLE", "FACTEUR_FUSIBLE_MIN",
    "FACTEUR_FUSIBLE_MAX", "FACTEUR_FUSIBLE_PLANCHER",
    "LONGUEUR_DC_SANS_PARAFOUDRE_M", "SENSIBILITE_DDR_MA",
    "ResultatProtections", "calibre_fusible_chaine", "calibre_disjoncteur",
    "courant_emploi_ac", "concevoir_protections",
]

#: Calibres normalisés de fusibles gPV (IEC 60269-6 — fusibles dédiés PV).
CALIBRES_FUSIBLE_GPV_A = (4, 6, 8, 10, 12, 15, 16, 20, 25, 30, 32)

#: Calibres normalisés de disjoncteurs BT (NF C 15-100 / IEC 60947-2).
CALIBRES_DISJONCTEUR_A = (6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125,
                          160, 200, 250)

#: Nombre de chaînes en PARALLÈLE à partir duquel le fusible devient exigé
#: (IEC 62548 §7.3.3 — en deçà, le courant inverse reste sous la tenue module).
SEUIL_CHAINES_PARALLELES_FUSIBLE = 3

#: Encadrement du calibre de fusible de chaîne (IEC 62548 §7.3.3) :
#: 1,5 × Isc ≤ In ≤ 2,4 × Isc, et jamais sous 1,25 × Isc (NF C 15-100 §433 —
#: un fusible qui fond au courant d'emploi coupe une chaîne saine).
FACTEUR_FUSIBLE_MIN = 1.5
FACTEUR_FUSIBLE_MAX = 2.4
FACTEUR_FUSIBLE_PLANCHER = 1.25

#: Longueur de liaison DC au-delà de laquelle le parafoudre est exigé
#: (UTE C 15-712-1 — critère de longueur critique de la boucle DC).
LONGUEUR_DC_SANS_PARAFOUDRE_M = 10.0

#: Sensibilité du différentiel de tête en régime TT (NF C 15-100 §531.2).
SENSIBILITE_DDR_MA = 300


@dataclass(frozen=True)
class ResultatProtections:
    """Les organes retenus + ce que la règle n'a pas pu satisfaire."""

    protections: Tuple[Protection, ...] = ()
    bloquants: Tuple[str, ...] = ()
    alertes: Tuple[str, ...] = ()
    #: Calibre du disjoncteur AC retenu (A) — repris par le calcul de câble.
    calibre_ac_a: Optional[float] = None
    #: Courant d'emploi AC (A) — Ib de la vérification Ib ≤ In ≤ Iz.
    courant_ac_ib_a: float = 0.0
    #: Calibre de fusible de chaîne retenu (A), ``None`` si non exigé.
    calibre_fusible_a: Optional[float] = None
    fusibles_exiges: bool = False


def calibre_fusible_chaine(isc_a):
    """``(calibre, motif)`` — plus petit gPV dans [1,5 ; 2,4] × Isc.

    Le calibre doit être ASSEZ GRAND pour ne pas fondre au courant d'emploi
    (≥ 1,25 × Isc, et la règle PV impose ≥ 1,5 × Isc) et ASSEZ PETIT pour
    protéger le câble et le module (≤ 2,4 × Isc). Quand aucun calibre normalisé
    ne tient dans la fourchette, on retient le premier au-dessus du minimum et on
    le DIT — un calibre hors fourchette silencieux serait indéfendable.
    """
    isc = float(isc_a or 0.0)
    if isc <= 0:
        return (None, "courant de court-circuit module inconnu — calibre de "
                      "fusible de chaîne à confirmer")
    mini = FACTEUR_FUSIBLE_MIN * isc
    maxi = FACTEUR_FUSIBLE_MAX * isc
    plancher = FACTEUR_FUSIBLE_PLANCHER * isc
    for calibre in CALIBRES_FUSIBLE_GPV_A:
        if calibre + 1e-9 >= mini and calibre >= plancher:
            if calibre <= maxi + 1e-9:
                return (float(calibre), "")
            return (float(calibre),
                    "calibre de fusible %s au-dessus de %s (2,4 × Isc) — aucun "
                    "calibre normalisé gPV ne tient dans la fourchette "
                    "[%s ; %s], à faire valider"
                    % (fr_a(calibre, 0), fr_a(maxi), fr_a(mini), fr_a(maxi)))
    return (None,
            "aucun calibre gPV normalisé ≥ %s (1,5 × Isc) — fusible de chaîne à "
            "définir hors barème courant" % fr_a(mini))


def calibre_disjoncteur(ib_a):
    """Plus petit calibre normalisé ≥ Ib (NF C 15-100 §433.1 : Ib ≤ In)."""
    ib = float(ib_a or 0.0)
    for calibre in CALIBRES_DISJONCTEUR_A:
        if calibre + 1e-9 >= ib:
            return float(calibre)
    return float(CALIBRES_DISJONCTEUR_A[-1])


def courant_emploi_ac(puissance_ac_kw, phases):
    """Ib côté AC : P / U en monophasé 230 V, P / (U·√3) en triphasé 400 V."""
    puissance = float(puissance_ac_kw or 0.0) * 1000.0
    if puissance <= 0:
        return 0.0
    if int(phases or 1) == 3:
        return puissance / (400.0 * math.sqrt(3.0))
    return puissance / 230.0


def _chaines_paralleles_max(resultat_chaines):
    """Plus grand nombre de chaînes en PARALLÈLE sur une même entrée MPPT."""
    if resultat_chaines is None or not resultat_chaines.chaines:
        return 0
    compte = {}
    for chaine in resultat_chaines.chaines:
        compte[chaine.mppt] = compte.get(chaine.mppt, 0) + 1
    return max(compte.values())


def concevoir_protections(entree, resultat_chaines=None, evaluation=None):
    """PV35 — la liste des organes de protection exigés par l'installation.

    ``evaluation`` (sortie de ``onduleurs.dimensionner_onduleurs``) fournit la
    puissance AC réellement installée ; à défaut on retient celle de l'onduleur
    déclaré.
    """
    protections = []
    alertes = []
    bloquants = []

    nb_chaines = resultat_chaines.nb_chaines if resultat_chaines else 0
    paralleles = _chaines_paralleles_max(resultat_chaines)
    nb_onduleurs = evaluation.nombre if evaluation is not None else (
        1 if nb_chaines else 0)
    puissance_ac_kw = (evaluation.puissance_ac_kw if evaluation is not None
                       else float(entree.onduleur.ac_kw or 0.0))

    # ── 1. Fusibles de chaîne — seulement à partir de 3 chaînes en parallèle ──
    calibre_fusible = None
    fusibles_exiges = paralleles >= SEUIL_CHAINES_PARALLELES_FUSIBLE
    if fusibles_exiges:
        calibre_fusible, motif = calibre_fusible_chaine(entree.module.isc_a)
        if motif:
            alertes.append(motif)
        if calibre_fusible is not None:
            protections.append(Protection(
                repere="F1",
                designation="Fusible gPV de chaîne, sur les deux pôles (+ et −)",
                calibre="%s A / 1000 V DC" % fr(calibre_fusible, 0),
                quantite=2 * nb_chaines,
                regle_source=(
                    "IEC 62548 §7.3.3 — protection exigée dès %d chaînes en "
                    "parallèle (%d ici) ; calibre dans [%s × Isc ; %s × Isc] = "
                    "[%s ; %s]"
                    % (SEUIL_CHAINES_PARALLELES_FUSIBLE, paralleles,
                       fr(FACTEUR_FUSIBLE_MIN, 1), fr(FACTEUR_FUSIBLE_MAX, 1),
                       fr_a(FACTEUR_FUSIBLE_MIN * entree.module.isc_a),
                       fr_a(FACTEUR_FUSIBLE_MAX * entree.module.isc_a))),
            ))
    elif nb_chaines:
        alertes.append(
            "fusibles de chaîne NON exigés : %d chaîne(s) en parallèle au "
            "maximum, le seuil est de %d (IEC 62548 §7.3.3)"
            % (paralleles, SEUIL_CHAINES_PARALLELES_FUSIBLE))

    # ── 2. Parafoudre DC Type 2 — liaison > 10 m ou zone kéraunique ──────────
    dc_m = float(entree.dc_m or 0.0)
    if nb_chaines and (dc_m > LONGUEUR_DC_SANS_PARAFOUDRE_M
                       or entree.zone_keraunique):
        raison = ("zone kéraunique déclarée" if entree.zone_keraunique
                  else "liaison DC de %s m au-dessus du seuil de %s m"
                       % (fr(dc_m, 1), fr(LONGUEUR_DC_SANS_PARAFOUDRE_M, 0)))
        protections.append(Protection(
            repere="PDC1",
            designation="Parafoudre DC Type 2 (coffret de chaînes)",
            calibre="1000 V DC, In 20 kA, Up ≤ 4 kV",
            quantite=max(1, nb_onduleurs),
            regle_source="UTE C 15-712-1 — %s" % raison,
        ))
    elif nb_chaines:
        alertes.append(
            "parafoudre DC non exigé : liaison DC de %s m sous le seuil de %s m "
            "et site hors zone kéraunique (UTE C 15-712-1)"
            % (fr(dc_m, 1), fr(LONGUEUR_DC_SANS_PARAFOUDRE_M, 0)))

    # ── 3. Sectionneur DC — toujours ─────────────────────────────────────────
    if nb_chaines:
        protections.append(Protection(
            repere="QDC1",
            designation="Interrupteur-sectionneur DC en amont de l'onduleur",
            calibre="1000 V DC, %s"
                    % fr_a(_courant_dc_total(resultat_chaines), 0),
            quantite=max(1, nb_onduleurs),
            regle_source=("UTE C 15-712-1 §5.4 / IEC 62548 §5.3 — l'onduleur "
                          "doit pouvoir être isolé de son champ en charge"),
        ))

    # ── 4. Disjoncteur AC — calibre normalisé ≥ Ib ───────────────────────────
    ib_ac = courant_emploi_ac(puissance_ac_kw, entree.phases)
    calibre_ac = None
    if ib_ac > 0:
        calibre_ac = calibre_disjoncteur(ib_ac)
        triphase = int(entree.phases or 1) == 3
        protections.append(Protection(
            repere="QAC1",
            designation="Disjoncteur AC %s courbe C"
                        % ("tétrapolaire" if triphase else "bipolaire"),
            calibre="%s A / %s V" % (fr(calibre_ac, 0),
                                     fr(entree.tension_reseau_v, 0)),
            quantite=1,
            regle_source=("NF C 15-100 §433.1 — Ib ≤ In : Ib = %s pour %s kW "
                          "en %s, calibre normalisé immédiatement supérieur"
                          % (fr_a(ib_ac), fr(puissance_ac_kw, 1),
                             "triphasé 400 V" if triphase
                             else "monophasé 230 V")),
        ))
        if nb_onduleurs > 1:
            alertes.append(
                "%d onduleurs : le calibre ci-dessus est celui de la protection "
                "de TÊTE ; chaque onduleur garde en outre son propre organe de "
                "sectionnement AC" % nb_onduleurs)

    # ── 5. Parafoudre AC Type 2 ──────────────────────────────────────────────
    if ib_ac > 0:
        protections.append(Protection(
            repere="PAC1",
            designation="Parafoudre AC Type 2 %s"
                        % ("triphasé" if int(entree.phases or 1) == 3
                           else "monophasé"),
            calibre="In 20 kA, Up ≤ 1,5 kV",
            quantite=1,
            regle_source=("NF C 15-100 §534 — parafoudre à l'origine de "
                          "l'installation AC (coordination avec le parafoudre "
                          "DC côté champ)"),
        ))

    # ── 6. DDR type A 300 mA — régime TT ─────────────────────────────────────
    regime = (entree.regime or REGIME_TT).upper()
    if ib_ac > 0:
        if regime == REGIME_TT:
            protections.append(Protection(
                repere="DDR1",
                designation="Interrupteur différentiel type A",
                calibre="%d mA, %s A"
                        % (SENSIBILITE_DDR_MA,
                           fr(calibre_ac or 0.0, 0)),
                quantite=1,
                regle_source=("NF C 15-100 §411.5 / §531.2 — en régime TT la "
                              "protection contre les contacts indirects repose "
                              "sur un différentiel ; type A car un onduleur PV "
                              "peut injecter une composante continue "
                              "(IEC 62109)"),
            ))
        else:
            alertes.append(
                "régime de neutre %s : la protection contre les contacts "
                "indirects n'est pas assurée par un différentiel de tête mais "
                "par les temps de coupure des protections (NF C 15-100 §411) — "
                "à confirmer avec le gestionnaire de réseau" % regime)

    # ── 7. Mise à la terre ───────────────────────────────────────────────────
    if nb_chaines or ib_ac > 0:
        protections.append(Protection(
            repere="T1",
            designation="Prise de terre : piquet + barrette de coupure",
            calibre="≤ 100 Ω",
            quantite=1,
            regle_source=("NF C 15-100 §542 — valeur de prise de terre "
                          "compatible avec le différentiel %d mA en régime TT"
                          % SENSIBILITE_DDR_MA),
        ))
        protections.append(Protection(
            repere="T2",
            designation=("Liaison équipotentielle des masses "
                         "(structure, cadres modules, coffrets)"),
            calibre="6 mm² Cu minimum",
            quantite=1,
            regle_source=("UTE C 15-712-1 / NF C 15-100 §542.4 — toutes les "
                          "masses métalliques du champ sont reliées à la même "
                          "barrette de terre"),
        ))

    # ── 8. Parc batterie (le cas échéant) ────────────────────────────────────
    if entree.batterie:
        protections.append(Protection(
            repere="QBAT1",
            designation="Sectionneur-fusible DC batterie",
            calibre="selon courant de décharge du parc",
            quantite=1,
            regle_source=("NF C 15-100 §464 — organe de sectionnement "
                          "d'urgence du parc de stockage (le guide "
                          "UTE C 15-712-1 ne couvre pas le stockage)"),
        ))

    if resultat_chaines is not None:
        bloquants.extend(resultat_chaines.bloquants)
        alertes.extend(resultat_chaines.alertes)
    if evaluation is not None:
        bloquants.extend(evaluation.bloquants)
        alertes.extend(evaluation.alertes)

    return ResultatProtections(
        protections=tuple(protections),
        bloquants=tuple(bloquants),
        alertes=tuple(alertes),
        calibre_ac_a=calibre_ac,
        courant_ac_ib_a=ib_ac,
        calibre_fusible_a=calibre_fusible,
        fusibles_exiges=fusibles_exiges,
    )


def _courant_dc_total(resultat_chaines):
    """Isc cumulé de la plus chargée des entrées MPPT — calibre du sectionneur."""
    if resultat_chaines is None or not resultat_chaines.chaines:
        return 0.0
    par_mppt = {}
    for chaine in resultat_chaines.chaines:
        par_mppt[chaine.mppt] = par_mppt.get(chaine.mppt, 0.0) + chaine.isc_a
    return max(par_mppt.values())
