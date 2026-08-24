# -*- coding: utf-8 -*-
"""PV34 — des modules d'un PAN aux CHAÎNES série, dans la fenêtre de tension.

Physique portée À L'IDENTIQUE de ``apps/ventes/solar_design.py::string_design``
(le calcul historique, éprouvé en production) :

* les tensions dérivent LINÉAIREMENT avec la température de cellule
  (``V(T) = V_stc × (1 + coeff/100 × (T − 25))``) ; le coefficient est négatif,
  donc **à froid la tension MONTE** — c'est le cas dimensionnant de la borne
  haute, et c'est le seul dont le dépassement DÉTRUIT l'onduleur ;
* la longueur de chaîne admissible est encadrée par QUATRE bornes : Voc à froid
  sous la tension maximale absolue, Vmp à froid sous le haut de plage MPPT, Vmp
  à chaud au-dessus du bas de plage MPPT, Vmp à chaud au-dessus de la tension de
  démarrage ;
* la répartition privilégie des chaînes ÉGALES dont le nombre est multiple des
  entrées MPPT, puis les chaînes les plus longues (moins de câblage).

Ce que le noyau AJOUTE au calcul historique — et qui n'y était pas :

1. **Un groupe par PAN, jamais mélangé sur une entrée MPPT.** Deux orientations
   n'atteignent pas leur point de puissance maximale au même instant : un MPPT
   commun suivrait le plus faible des deux toute la journée. La perte est
   permanente et invisible au bordereau — elle est donc NOMMÉE ici.
2. **La longueur imposée passe par la physique.** ``longueur_chaine_forcee``
   n'est acceptée que DANS la plage admissible calculée ; hors plage, elle est
   refusée AVEC MOTIF en français (et le calcul retombe sur la longueur
   physique) plutôt que d'être appliquée en silence.
3. **Le courant d'entrée MPPT choisit la répartition** (PV85). Les chaînes
   d'une même entrée additionnent leur Imp : deux chaînes de modules 710 Wc
   (2 × 17,59 A) sur une entrée admettant 26 A écrêtent EN PERMANENCE. La
   répartition « une chaîne par entrée » l'emporte donc sur l'équilibrage et
   sur la longueur ; quand aucune répartition ne tient, l'avertissement de
   conformité est prononcé au lieu d'un silence.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from core.electrique.types import Chaine, fr, fr_a, fr_v

__all__ = [
    "FenetreChaine", "RepartitionPan", "ResultatChaines",
    "fenetre_admissible", "concevoir_chaines",
]


def _entier(valeur, defaut=0):
    """Entier tolérant — le moteur ne lève JAMAIS sur une entrée dégradée."""
    try:
        n = int(valeur)
    except (TypeError, ValueError):
        return defaut
    return n if n >= 0 else defaut


@dataclass(frozen=True)
class FenetreChaine:
    """Plage de longueurs de chaîne ADMISSIBLE, avec les 4 bornes qui la ferment.

    Les quatre bornes intermédiaires sont conservées : la note de calcul doit
    pouvoir dire LAQUELLE ferme la plage (« 20 modules max — c'est le haut de
    plage MPPT qui limite, pas la tension maximale »).
    """

    longueur_min: int
    longueur_max: int
    voc_froid_unitaire_v: float
    vmp_froid_unitaire_v: float
    vmp_chaud_unitaire_v: float
    max_par_voc: int
    max_par_mppt: int
    min_par_mppt: int
    min_par_demarrage: int
    temp_froid_c: float
    temp_chaud_c: float
    trop_etroite: bool = False
    motif: str = ""

    def admet(self, longueur):
        """La longueur tient-elle dans la plage admissible ?"""
        return self.longueur_min <= longueur <= self.longueur_max

    @property
    def texte(self):
        """« 12 à 20 modules par chaîne »."""
        return ("%d à %d modules par chaîne"
                % (self.longueur_min, self.longueur_max))


@dataclass(frozen=True)
class RepartitionPan:
    """Découpage d'UN pan — le reste est ANNONCÉ, jamais dissimulé."""

    pan: str
    nb_modules: int
    longueur_chaine: int
    nb_chaines: int
    reste: int
    mppt: Tuple[int, ...] = ()
    homogene: bool = True

    @property
    def modules_en_chaine(self):
        return self.nb_chaines * self.longueur_chaine


@dataclass(frozen=True)
class ResultatChaines:
    """Conception de chaînes complète — chaînes, plage, refus et alertes."""

    chaines: Tuple[Chaine, ...] = ()
    fenetre: Optional[FenetreChaine] = None
    repartitions: Tuple[RepartitionPan, ...] = ()
    bloquants: Tuple[str, ...] = ()
    alertes: Tuple[str, ...] = ()
    longueur_forcee: Optional[int] = None
    longueur_forcee_acceptee: Optional[bool] = None

    @property
    def nb_chaines(self):
        return len(self.chaines)

    @property
    def reste_total(self):
        return sum(r.reste for r in self.repartitions)

    @property
    def puissance_kwc(self):
        return sum(c.puissance_kwc for c in self.chaines)

    @property
    def chaines_par_mppt(self):
        """Nombre de chaînes sur chaque entrée MPPT — clé du courant d'entrée."""
        compte = {}
        for chaine in self.chaines:
            compte[chaine.mppt] = compte.get(chaine.mppt, 0) + 1
        return tuple(compte.get(i, 0)
                     for i in range(1, (max(compte) + 1) if compte else 1))


# ----------------------------------------------------------- fenêtre de tension
def fenetre_admissible(module, onduleur, temp_froid_c, temp_chaud_c):
    """Plage [longueur_min, longueur_max] admissible pour le couple module/onduleur.

    Port À L'IDENTIQUE des quatre bornes de ``string_design`` :

    * ``max_par_voc``       = ⌊V_max_abs / Voc(froid)⌋ — sécurité MATÉRIEL ;
    * ``max_par_mppt``      = ⌊V_mppt_max / Vmp(froid)⌋ — écrêtage sinon ;
    * ``min_par_mppt``      = ⌈V_mppt_min / Vmp(chaud)⌉ — MPPT hors plage sinon ;
    * ``min_par_demarrage`` = ⌈V_démarrage / Vmp(chaud)⌉ — l'onduleur ne part pas.

    Quand la plage est VIDE (max < min), la fenêtre est déclarée « trop étroite »
    AVEC MOTIF : aucun couple module/onduleur ne satisfait à la fois la borne
    haute à froid et le démarrage à chaud. Le calcul continue quand même, borné
    par la seule sécurité matériel — mais le verdict, lui, est bloquant.
    """
    voc_froid = module.tension_voc_a(temp_froid_c)
    vmp_froid = module.tension_vmp_a(temp_froid_c)
    vmp_chaud = module.tension_vmp_a(temp_chaud_c)
    v_demarrage = onduleur.tension_demarrage_v

    max_par_voc = (int(math.floor(onduleur.v_max_abs / voc_froid))
                   if voc_froid > 0 else 1)
    max_par_mppt = (int(math.floor(onduleur.mppt_v_max / vmp_froid))
                    if vmp_froid > 0 else 1)
    min_par_mppt = (int(math.ceil(onduleur.mppt_v_min / vmp_chaud))
                    if vmp_chaud > 0 else 1)
    min_par_demarrage = (int(math.ceil(v_demarrage / vmp_chaud))
                         if vmp_chaud > 0 else 1)

    longueur_min = max(1, min_par_mppt, min_par_demarrage)
    longueur_max = max(1, min(max_par_voc, max_par_mppt))

    trop_etroite = longueur_max < longueur_min
    motif = ""
    if trop_etroite:
        motif = (
            "fenêtre de tension trop étroite pour ce couple module/onduleur : "
            "il faut au moins %d modules pour démarrer le MPPT à %s °C "
            "(Vmp chaud %s) et au plus %d pour rester sous la borne haute à "
            "%s °C (Voc froid %s, Vmp froid %s) — aucune longueur de chaîne ne "
            "satisfait les deux"
            % (longueur_min, fr(temp_chaud_c, 0), fr_v(vmp_chaud),
               longueur_max, fr(temp_froid_c, 0), fr_v(voc_froid),
               fr_v(vmp_froid)))
        # Repli « meilleur effort » : on ne garde que la sécurité MATÉRIEL.
        longueur_max = max(1, max_par_voc)
        longueur_min = 1

    return FenetreChaine(
        longueur_min=longueur_min,
        longueur_max=longueur_max,
        voc_froid_unitaire_v=voc_froid,
        vmp_froid_unitaire_v=vmp_froid,
        vmp_chaud_unitaire_v=vmp_chaud,
        max_par_voc=max_par_voc,
        max_par_mppt=max_par_mppt,
        min_par_mppt=min_par_mppt,
        min_par_demarrage=min_par_demarrage,
        temp_froid_c=temp_froid_c,
        temp_chaud_c=temp_chaud_c,
        trop_etroite=trop_etroite,
        motif=motif,
    )


# --------------------------------------------------------------- répartition
def _surcharge_mppt(nb_chaines, n_mppt, imp_a, i_max_mppt_a):
    """Le paquet de chaînes le plus chargé dépasse-t-il le courant d'entrée ?

    La répartition est la plus égale possible : l'entrée la plus chargée porte
    ``⌈nb_chaines / n_mppt⌉`` chaînes, donc autant de fois l'Imp d'une chaîne.
    Sans limite connue (``i_max_mppt_a = 0``), la question ne se pose pas — le
    moteur ne fabrique jamais une contrainte qu'aucune fiche ne donne.
    """
    if i_max_mppt_a <= 0 or imp_a <= 0:
        return False
    par_entree = -(-nb_chaines // max(1, n_mppt))    # division par excès
    return par_entree * imp_a > i_max_mppt_a + 1e-9


def _choisir_longueur(nb_modules, n_mppt, longueur_min, longueur_max,
                      imp_a=0.0, i_max_mppt_a=0.0):
    """``(longueur, nb_chaines)`` — chaînes ÉGALES, longueur admissible.

    On cherche une partition de ``nb_modules`` en chaînes ÉGALES dont la
    longueur tient dans la plage admissible. ``(0, 0)`` si aucune partition
    égale n'existe.

    DEUX critères, dans cet ordre, et RIEN d'autre :

    1. **Le courant d'entrée MPPT** (PV85). Une partition qui obligerait à
       empiler deux chaînes sur une entrée trop étroite (deux chaînes de
       CS7N-710 = 35,18 A sur les 26 A d'un Deye SG05LP3) est reléguée
       derrière toute partition qui tient UNE chaîne par entrée — l'écrêtage
       qui en résulterait est permanent et n'apparaîtrait sur aucune ligne du
       bordereau. Quand AUCUNE partition ne tient (plus de chaînes que
       d'entrées, quoi qu'on fasse), ce critère ne départage plus rien et
       ``_verdicts_courant`` prononce l'avertissement de conformité.
    2. **La chaîne la plus LONGUE**, donc le MOINS de chaînes possible.

    RÈGLE FONDATEUR 24/08/2026 — LE CRITÈRE « nombre de chaînes multiple des
    entrées MPPT » EST SUPPRIMÉ. Il passait AVANT la longueur et coupait donc
    en deux tout champ dont la moitié tenait encore dans la fenêtre de tension :
    8 panneaux sur un onduleur à 2 entrées ressortaient en 2 chaînes de 4 alors
    qu'une chaîne unique de 8 est électriquement valide — et c'est ainsi que
    l'installateur câble. Un champ n'est SPLITÉ que lorsque la physique
    l'impose (la fenêtre de tension ferme la longueur, ou le courant d'entrée
    MPPT ci-dessus) ou lorsque les modules sont sur des PANS distincts (traité
    en amont : un pan ne partage jamais une entrée). « Occuper les deux
    entrées » n'est pas une exigence électrique : c'est un confort de câblage
    qui coûtait un départ DC, un jeu de connecteurs et une longueur de câble
    en plus, sur chaque dossier.
    """
    meilleur = (0, 0)
    meilleur_score = None
    for nb_chaines in range(1, nb_modules + 1):
        if nb_modules % nb_chaines != 0:
            continue
        longueur = nb_modules // nb_chaines
        if longueur < longueur_min or longueur > longueur_max:
            continue
        surcharge = 1 if _surcharge_mppt(nb_chaines, n_mppt, imp_a,
                                         i_max_mppt_a) else 0
        score = (surcharge, -longueur)
        if meilleur_score is None or score < meilleur_score:
            meilleur_score = score
            meilleur = (longueur, nb_chaines)
    return meilleur


def _repartir(nb_chaines, entrees):
    """Répartit ``nb_chaines`` sur ``entrees`` entrées, le plus également possible."""
    nombre = max(1, len(entrees))
    base = nb_chaines // nombre
    extra = nb_chaines % nombre
    return tuple(base + (1 if i < extra else 0) for i in range(nombre))


def _allouer_mppt(nb_pans, n_mppt):
    """Alloue les entrées MPPT aux pans — un pan ne PARTAGE jamais une entrée.

    Chaque pan reçoit un BLOC d'entrées consécutives ; quand il y a plus de pans
    que d'entrées, les pans excédentaires retombent en boucle sur les entrées
    existantes et le partage qui en résulte est NOMMÉ par l'appelant (c'est une
    perte de production, pas un détail de câblage).
    """
    n_mppt = max(1, n_mppt)
    if nb_pans <= 0:
        return ()
    if nb_pans > n_mppt:
        return tuple((i % n_mppt + 1,) for i in range(nb_pans))
    part = n_mppt // nb_pans
    extra = n_mppt % nb_pans
    blocs = []
    curseur = 1
    for i in range(nb_pans):
        taille = part + (1 if i < extra else 0)
        blocs.append(tuple(range(curseur, curseur + taille)))
        curseur += taille
    return tuple(blocs)


# ------------------------------------------------------------------- conception
def concevoir_chaines(entree):
    """PV34 — conçoit les chaînes de TOUS les pans d'une ``EntreeElectrique``.

    Retourne un ``ResultatChaines`` : les chaînes repérées (CH1, CH2…) avec leur
    pan et leur entrée MPPT, la fenêtre de tension, le découpage par pan, et les
    verdicts séparés en BLOQUANTS (matériel en danger, aucune longueur possible)
    et ALERTES (production dégradée). Ne lève jamais.
    """
    module = entree.module
    onduleur = entree.onduleur
    fenetre = fenetre_admissible(module, onduleur,
                                 entree.temp_froid_c, entree.temp_chaud_c)

    bloquants = []
    alertes = []
    if fenetre.trop_etroite:
        bloquants.append(fenetre.motif)

    # ── Longueur imposée : acceptée seulement DANS la plage admissible ────────
    forcee = entree.longueur_chaine_forcee
    forcee_acceptee = None
    if forcee is not None:
        forcee = _entier(forcee, 0)
        if forcee <= 0:
            forcee_acceptee = False
            bloquants.append(
                "longueur de chaîne imposée invalide (%d) — une chaîne compte "
                "au moins 1 module" % forcee)
        elif fenetre.trop_etroite:
            forcee_acceptee = False
            bloquants.append(
                "longueur de chaîne imposée de %d modules non vérifiable : la "
                "fenêtre de tension est vide (voir le motif ci-dessus)" % forcee)
        elif not fenetre.admet(forcee):
            forcee_acceptee = False
            bloquants.append(
                "longueur de chaîne imposée de %d modules REFUSÉE : hors de la "
                "plage admissible (%s). Voc à froid unitaire %s → %d modules "
                "maximum sous %s ; Vmp à chaud unitaire %s → %d modules minimum "
                "pour démarrer le MPPT à %s"
                % (forcee, fenetre.texte, fr_v(fenetre.voc_froid_unitaire_v),
                   fenetre.max_par_voc, fr_v(onduleur.v_max_abs),
                   fr_v(fenetre.vmp_chaud_unitaire_v), fenetre.min_par_mppt,
                   fr_v(onduleur.mppt_v_min)))
        else:
            forcee_acceptee = True

    groupes = tuple(g for g in entree.groupes if _entier(g.nb_modules) > 0)
    if not groupes:
        return ResultatChaines(
            fenetre=fenetre,
            bloquants=tuple(bloquants),
            alertes=tuple(alertes) + ("aucun module à répartir",),
            longueur_forcee=forcee,
            longueur_forcee_acceptee=forcee_acceptee,
        )

    n_mppt = max(1, _entier(onduleur.n_mppt, 1))
    blocs = _allouer_mppt(len(groupes), n_mppt)
    if len(groupes) > n_mppt:
        alertes.append(
            "%d pans pour %d entrée(s) MPPT : des pans d'orientations "
            "différentes partagent une entrée — le suiveur de puissance suivra "
            "le pan le plus faible toute la journée (prévoir un onduleur à plus "
            "d'entrées ou des optimiseurs)" % (len(groupes), n_mppt))

    chaines = []
    repartitions = []
    numero = 0
    for index, groupe in enumerate(groupes):
        nb_modules = _entier(groupe.nb_modules)
        entrees = blocs[index] if index < len(blocs) else (1,)
        # L'équilibrage vise les entrées RÉELLEMENT allouées à ce pan.
        if forcee_acceptee:
            longueur = forcee
            nb_chaines = nb_modules // longueur
        else:
            longueur, nb_chaines = _choisir_longueur(
                nb_modules, len(entrees), fenetre.longueur_min,
                fenetre.longueur_max, module.imp_a, onduleur.i_max_mppt_a)

        homogene = True
        if longueur <= 0 or nb_chaines <= 0:
            # Aucun découpage égal — repli borné par la plage, reste annoncé.
            homogene = False
            longueur = max(1, min(nb_modules, fenetre.longueur_max))
            nb_chaines = nb_modules // longueur
            if nb_chaines <= 0:
                nb_chaines = 1
                longueur = nb_modules
            alertes.append(
                "pan « %s » : aucune découpe en chaînes ÉGALES de %s — retenu "
                "%d chaîne(s) de %d module(s), %d module(s) en réserve"
                % (groupe.label, fenetre.texte, nb_chaines, longueur,
                   nb_modules - nb_chaines * longueur))

        reste = nb_modules - nb_chaines * longueur
        if reste and homogene:
            alertes.append(
                "pan « %s » : %d module(s) en réserve d'appoint (hors chaîne)"
                % (groupe.label, reste))

        par_entree = _repartir(nb_chaines, entrees)
        for rang, entree_mppt in enumerate(entrees):
            for _ in range(par_entree[rang]):
                numero += 1
                chaines.append(Chaine(
                    repere="CH%d" % numero,
                    pan=groupe.label,
                    nb_modules=longueur,
                    mppt=entree_mppt,
                    voc_froid_v=fenetre.voc_froid_unitaire_v * longueur,
                    vmp_froid_v=fenetre.vmp_froid_unitaire_v * longueur,
                    vmp_chaud_v=fenetre.vmp_chaud_unitaire_v * longueur,
                    vmp_stc_v=module.vmp_v * longueur,
                    isc_a=module.isc_a,
                    imp_a=module.imp_a,
                    puissance_kwc=longueur * module.pmax_wc / 1000.0,
                ))

        repartitions.append(RepartitionPan(
            pan=groupe.label, nb_modules=nb_modules, longueur_chaine=longueur,
            nb_chaines=nb_chaines, reste=reste, mppt=tuple(entrees),
            homogene=homogene))

    bloquants.extend(_verdicts_tension(chaines, onduleur, fenetre, alertes))
    bloquants.extend(_verdicts_courant(chaines, onduleur, alertes))

    return ResultatChaines(
        chaines=tuple(chaines),
        fenetre=fenetre,
        repartitions=tuple(repartitions),
        bloquants=tuple(bloquants),
        alertes=tuple(alertes),
        longueur_forcee=forcee,
        longueur_forcee_acceptee=forcee_acceptee,
    )


def _verdicts_tension(chaines, onduleur, fenetre, alertes):
    """Les 4 contrôles de ``string_design``, au niveau CHAÎNE.

    Seul le dépassement de la tension maximale ABSOLUE est bloquant : il détruit
    l'onduleur. Les trois autres coûtent de la production, ils alertent.
    """
    bloquants = []
    if not chaines:
        return bloquants
    plus_longue = max(chaines, key=lambda c: c.nb_modules)
    plus_courte = min(chaines, key=lambda c: c.nb_modules)

    if plus_longue.voc_froid_v > onduleur.v_max_abs:
        bloquants.append(
            "Voc à froid %s > tension maximale onduleur %s (chaîne %s de %d "
            "modules à %s °C) — RISQUE matériel, réduire la longueur de chaîne"
            % (fr_v(plus_longue.voc_froid_v), fr_v(onduleur.v_max_abs),
               plus_longue.repere, plus_longue.nb_modules,
               fr(fenetre.temp_froid_c, 0)))
    if plus_longue.vmp_froid_v > onduleur.mppt_v_max:
        alertes.append(
            "Vmp à froid %s > haut de plage MPPT %s — l'onduleur écrête, perte "
            "de production"
            % (fr_v(plus_longue.vmp_froid_v), fr_v(onduleur.mppt_v_max)))
    if plus_courte.vmp_chaud_v < onduleur.mppt_v_min:
        alertes.append(
            "Vmp à chaud %s < bas de plage MPPT %s — chaîne trop courte, MPPT "
            "hors plage en été"
            % (fr_v(plus_courte.vmp_chaud_v), fr_v(onduleur.mppt_v_min)))
    if plus_courte.vmp_chaud_v < onduleur.tension_demarrage_v:
        alertes.append(
            "Vmp à chaud %s < tension de démarrage onduleur %s"
            % (fr_v(plus_courte.vmp_chaud_v),
               fr_v(onduleur.tension_demarrage_v)))
    return bloquants


def _verdicts_courant(chaines, onduleur, alertes):
    """Courant d'entrée MPPT : les chaînes d'une même entrée s'ADDITIONNENT.

    DEUX bornes, deux natures — la fiche constructeur publie les deux et le
    moteur ne les confond NI dans le calcul, NI dans la SÉVÉRITÉ :

    * la somme des **Isc** contre ``isc_max_mppt_a`` — borne MATÉRIELLE, la
      seule qui parle du court-circuit. La dépasser, c'est sortir de la
      SPÉCIFICATION de l'appareil : ce n'est pas une perte de production, c'est
      une configuration que la fiche constructeur n'autorise pas. Elle est donc
      **BLOQUANTE**, au même titre que le Voc à froid au-dessus de la tension
      maximale absolue (incident DEV-202608-0016 : 25 × CS7N-710, Isc 18,59 A
      par chaîne, sur un Deye 5 kW mono dont chaque entrée admet 17 A — une
      chaîne SEULE sort déjà de la borne, et le schéma se dessinait quand
      même) ;
    * la somme des **Imp** contre ``i_max_mppt_a`` — borne de FONCTIONNEMENT.
      Deux chaînes de gros modules sur une entrée large mais pas assez (deux
      chaînes de CS7N-710 : 2 × 17,59 = 35,18 A sur une entrée Deye SG05LP3 à
      26 A, Isc 37,18 A sous les 39 A admis) : l'onduleur ne casse pas, il
      écrête toute l'année. C'est une pratique LÉGITIME dont la perte n'apparaît
      nulle part au bordereau — elle reste donc une **ALERTE**.

    Ordre et non-répétition : la borne matérielle parle la PREMIÈRE et seule
    (l'écrêtage ne masque plus le dépassement de spécification, et ne le
    redouble pas non plus — la configuration est refusée de toute façon).

    **Aucun seuil n'est inventé ici** (règle fondateur du 21/08/2026) : chaque
    contrôle compare deux chiffres de FICHE et ne s'évalue QUE si sa propre
    borne est publiée. ``isc_max_mppt_a`` absent ⇒ aucun bloquant : le repli
    prudent ``courant_isc_max_a`` (qui recopie ``i_max_mppt_a``) reste ce qu'il
    a toujours été, une ALERTE — refuser un dossier sur une borne substituée
    reviendrait à refuser sur un nombre que le constructeur n'a jamais écrit.
    """
    bloquants = []
    if not chaines:
        return bloquants
    par_mppt = {}
    for chaine in chaines:
        par_mppt.setdefault(chaine.mppt, []).append(chaine)
    # Borne d'Isc PUBLIÉE par la fiche (``None`` = non publiée), à ne pas
    # confondre avec le repli ``courant_isc_max_a``.
    isc_publie = onduleur.isc_max_mppt_a
    for entree_mppt in sorted(par_mppt):
        lot = par_mppt[entree_mppt]
        courant_imp = sum(c.imp_a for c in lot)
        courant_isc = sum(c.isc_a for c in lot)

        # 1. Borne MATÉRIELLE publiée — dépassement = hors spécification.
        if isc_publie is not None and isc_publie > 0 \
                and courant_isc > isc_publie + 1e-9:
            bloquants.append(
                "entrée MPPT %d : %d chaîne(s) en parallèle → Isc cumulé %s > "
                "%s maxi admissible en court-circuit sur l'entrée MPPT %d "
                "(fiche constructeur) — configuration HORS SPÉCIFICATION, "
                "réduire le nombre de chaînes sur cette entrée ou prendre un "
                "onduleur à entrées plus larges"
                % (entree_mppt, len(lot), fr_a(courant_isc),
                   fr_a(isc_publie), entree_mppt))
            continue

        # 2. Borne de FONCTIONNEMENT — écrêtage, légitime mais jamais tu.
        if onduleur.i_max_mppt_a > 0 \
                and courant_imp > onduleur.i_max_mppt_a + 1e-9:
            alertes.append(
                "entrée MPPT %d : %d chaînes en parallèle → Imp cumulé %s > "
                "courant d'entrée admissible %s (Isc cumulé %s) — ÉCRÊTAGE "
                "permanent, répartir une chaîne par entrée MPPT ou prendre un "
                "onduleur à entrées plus larges"
                % (entree_mppt, len(lot), fr_a(courant_imp),
                   fr_a(onduleur.i_max_mppt_a), fr_a(courant_isc)))
            continue

        # 3. Fiche muette sur l'Isc : le repli PRUDENT alerte, il ne bloque pas.
        if isc_publie is None and onduleur.i_max_mppt_a > 0 \
                and courant_isc > onduleur.courant_isc_max_a + 1e-9:
            alertes.append(
                "entrée MPPT %d : %d chaînes en parallèle → Isc cumulé %s > "
                "courant d'entrée admissible %s — répartir les chaînes sur "
                "d'autres entrées"
                % (entree_mppt, len(lot), fr_a(courant_isc),
                   fr_a(onduleur.courant_isc_max_a)))
    return bloquants
