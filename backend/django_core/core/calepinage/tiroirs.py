# -*- coding: utf-8 -*-
"""PV48 — la charge utile des 4 tiroirs DÉBUTANT, CALCULÉE et jamais rédigée.

Les quatre tiroirs de l'atelier (``TiroirKits``, ``TiroirAllees`` +
``AlleeGratuiteChart``, ``TiroirRives``, ``TiroirOrientation``) portent une
garde de code explicite : **aucun chiffre de comparaison n'est saisi ni
recalculé côté écran**. Tout ce qu'ils affichent — comptes de contre-épreuve,
plateau d'allée gratuite, impact d'une rive, motif de refus d'orientation —
doit donc être produit ICI, par le moteur, et voyager tel quel.

Trois disciplines gouvernent ce module :

* **Rien d'inventé.** Le moteur n'a pas de jeu de kits par segment : la seule
  granularité publiée est « toute la toiture ». Il n'a pas non plus de modèle
  de découpage en segments ni de traitement du L : ces deux groupes sortent
  VIDES plutôt que meublés d'options qu'aucun calcul ne sait honorer.
* **Rien de rédigé.** Le motif d'une orientation refusée est repris VERBATIM
  de ``orientation.motif_orientation`` (via ``ErreurOrientation``) : le seul
  endroit du dépôt qui sache dire pourquoi une table dos-à-dos est-ouest est
  inconstructible.
* **Rien d'estimé.** Chaque impact chiffré est un appel moteur rejoué. Quand
  le budget d'appels est épuisé, l'impact n'est PAS produit — l'écran affiche
  alors sa phrase prévue (« impact non chiffré par le moteur pour cette
  valeur »), ce qui est honnête, là où une estimation ne le serait pas.

**Coût.** Un tiroir doit rendre en moins de 500 ms (contrat AOF48) et chaque
comparaison rejoue un DP complet : ``donnees_tiroirs`` porte donc un
``budget_appels`` et RAPPORTE le nombre d'appels consommés. Le budget par
défaut (12) couvre la contre-épreuve des kits, les ancres de rives et la
variante conservatrice. La recherche d'allée gratuite est comptée à part
(``recherches_allee``) : sa dichotomie est bornée par ``allee_gratuite`` et non
par ce budget — la cacher dans le compteur donnerait un chiffre faux.
"""

from dataclasses import dataclass, replace

from core.calepinage.allee_gratuite import (
    PAS_ARRONDI_M,
    chercher_allee_gratuite,
)
from core.calepinage.orientation import ErreurOrientation, verifier_kit
from core.calepinage.perf import optimiser_economique
from core.calepinage.types import (
    Axe,
    MethodePreuve,
    OrientationModule,
    remplacer,
)
from core.calepinage.units import fr, fr_m

__all__ = [
    "DonneesTiroirs", "donnees_tiroirs", "BUDGET_APPELS_DEFAUT",
    "ANCRES_RIVES_M", "VARIANTE_CONSERVATRICE", "CHAMPS_RIVES",
]

#: Appels moteur que ``donnees_tiroirs`` s'autorise. 12 = les 2 contre-épreuves
#: de kit + les 8 ancres de rive + la variante conservatrice + un point de
#: bascule du graphe : au-delà, l'atelier ne rendrait plus sous les 500 ms du
#: contrat de performance.
BUDGET_APPELS_DEFAUT = 12

#: Écarts CAPÉS auxquels une rive est chiffrée, de part et d'autre de la valeur
#: courante. Balayer plus finement coûterait un DP par centimètre pour une
#: information que personne ne lit.
ANCRES_RIVES_M = (0.05, 0.10)

#: Les anciens défauts (1,50 / 0,50 / 0,50), proposés à titre de COMPARAISON —
#: jamais comme un réglage recommandé. Les valeurs sont celles du préréglage
#: « Variante conservatrice » ; le gain, lui, est rejoué ici.
VARIANTE_CONSERVATRICE = (("rive_laterale_m", 1.50),
                          ("rive_extremite_m", 0.50),
                          ("allee_m", 0.50))

#: (code, libellé, chiffrable) des champs du tiroir « Rives & dégagements ».
#: Les deux dégagements ne sont PAS chiffrables ici : les obstacles reçus
#: portent déjà leur dégagement dérivé (``obstacles.appliquer_regles`` a tourné
#: en amont), si bien que rejouer le moteur avec un autre défaut rendrait le
#: même compte — publier « aucun changement » serait un mensonge, pas une
#: mesure.
CHAMPS_RIVES = (
    ("rive_laterale_m", "Rive latérale", True),
    ("rive_extremite_m", "Rive d'extrémité", True),
    ("degagement_defaut_m", "Dégagement standard", False),
    ("degagement_nature_inconnue_m", "Dégagement « nature inconnue »", False),
)

#: Libellés des axes et des orientations de table — nommés, jamais devinés.
#: Des TUPLES et non des dictionnaires : aucune globale mutable dans le noyau
#: pur (``test_calepinage_purete``), et l'ordre d'affichage est alors le
#: contrat, pas un effet de bord de l'implémentation des tables de hachage.
_LIBELLE_AXE = ((Axe.NORD_SUD, "Rangées nord-sud"),
                (Axe.EST_OUEST, "Rangées est-ouest"))
_LIBELLE_ORIENTATION = ((OrientationModule.PORTRAIT, "Tables en portrait"),
                        (OrientationModule.PAYSAGE, "Tables en paysage"))


# ================================================================== compteur
class _Compteur:
    """Garde-fou de coût : compte les appels moteur et REFUSE de dépasser.

    Épuisé, il rend ``None`` au lieu d'un compte. Aucun appelant ne peut donc
    confondre « pas chiffré » et « chiffré à zéro » : le tiroir omet l'impact
    et l'écran le dit.
    """

    def __init__(self, budget):
        if budget < 0:
            raise ValueError("budget d'appels négatif")
        self.budget = int(budget)
        self.appels = 0

    @property
    def epuise(self):
        return self.appels >= self.budget

    def compter(self, surface, parametres, obstacles=(), zones=()):
        if self.epuise:
            return None
        self.appels += 1
        return optimiser_economique(surface, parametres, obstacles,
                                    zones).modules


def _texte_impact(delta):
    """« +4 modules » / « -3 modules » / « aucun changement » + son sens."""
    if delta > 0:
        return ("+%d modules" % delta, "gain")
    if delta < 0:
        return ("%d modules" % delta, "perte")
    return ("aucun changement", "neutre")


def _rives_appliquees(entree, **champs):
    """Applique des rives à la fois aux paramètres ET à la surface.

    Le piège est là : les bornes utiles viennent de la SURFACE
    (``bornes_transversales_utiles``). Ne changer que les paramètres rendrait
    un impact nul pour toute rive — un tiroir qui affiche « aucun changement »
    quoi qu'on saisisse. ``recommandations.appliquer_patch`` fait exactement
    cette double application ; on la reprend telle quelle.
    """
    rives = replace(entree.parametres.rives, **champs)
    return (replace(entree.surface, rives=rives),
            remplacer(entree.parametres, rives=rives))


# ================================================================ tiroir kits
def _tiroir_kits(entree, resultat, catalogue, azimut, compteur):
    """Kits admis + contre-épreuve : ce que DONNERAIT chaque kit, rejoué."""
    comptes = []
    for kit in catalogue:
        compte = compteur.compter(entree.surface,
                                  remplacer(entree.parametres, kits=(kit,)),
                                  entree.obstacles, entree.zones)
        comptes.append((kit, compte))

    chiffres = [(kit, compte) for kit, compte in comptes if compte is not None]
    constructibles = []
    for kit, compte in chiffres:
        try:
            verifier_kit(kit, entree.parametres.axe_rangee, azimut)
        except ErreurOrientation:
            continue  # le motif vit dans le tiroir « Orientation »
        constructibles.append((kit, compte))

    donnees = {
        "kits": [{"code": kit.code, "libelle": kit.libelle,
                  "recommande": False} for kit in catalogue],
        # Le moteur n'a AUCUN jeu de kits par zone, rangée ou segment : la
        # seule granularité qu'il sache honorer est la toiture entière.
        "granularites": [{"code": "site", "libelle": "Toute la toiture"}],
        # AOF119 : l'argument d'approvisionnement n'est pas un slogan. Tant
        # qu'aucun contrôle ne l'a confirmé, il reste FAUX et rien ne s'affiche.
        "approvisionnement": {"confirme": False},
    }

    if constructibles:
        meilleur = max(constructibles, key=lambda couple: couple[1])[1]
        gagnants = [kit for kit, compte in constructibles if compte == meilleur]
        recommande = min(gagnants, key=lambda kit: kit.code)
        for ligne in donnees["kits"]:
            ligne["recommande"] = ligne["code"] == recommande.code
        donnees["recommandation"] = {"code": recommande.code,
                                     "libelle": recommande.libelle}

    composition = _composition(resultat, catalogue)
    if composition is not None:
        donnees["composition"] = composition

    # Une contre-épreuve d'UNE option ne compare rien : on ne la publie pas.
    if len(chiffres) > 1:
        repere = getattr(entree.surface, "repere", "")
        options = [{"code": kit.code, "libelle": kit.libelle,
                    "texte": "%d modules" % compte}
                   for kit, compte in chiffres]
        donnees["contre_epreuve"] = [{
            "id": "kits-%s" % (repere or "site"),
            "segment": repere or "Toute la toiture",
            "options": options,
            "motif": _motif_contre_epreuve(chiffres),
        }]
    return donnees


def _motif_contre_epreuve(chiffres):
    """Phrase GÉNÉRÉE à partir des deux meilleurs comptes rejoués."""
    classes = sorted(chiffres, key=lambda couple: (-couple[1], couple[0].code))
    (premier, compte_premier), (second, compte_second) = classes[0], classes[1]
    if compte_premier == compte_second:
        return ("%s et %s rendent le même compte (%d modules) — comptes "
                "rejoués par le moteur" % (premier.code, second.code,
                                           compte_premier))
    return ("%s l'emporte de %d modules sur %s (%d contre %d) — comptes "
            "rejoués par le moteur, aucun chiffre saisi"
            % (premier.code, compte_premier - compte_second, second.code,
               compte_premier, compte_second))


def _composition(resultat, catalogue):
    """« 8 rangées : 8 × AO_PORTRAIT » + le total, tirés du plan RETENU."""
    plan = getattr(resultat, "plan", None)
    rangees = tuple(getattr(plan, "rangees", ()) or ())
    if not rangees:
        return None
    par_code = {}
    for rangee in rangees:
        par_code[rangee.kit_code] = par_code.get(rangee.kit_code, 0) + 1
    detail = " + ".join("%d × %s" % (nombre, code)
                        for code, nombre in sorted(par_code.items()))
    composition = {"texte": "%d rangées : %s" % (len(rangees), detail)}
    kwc = _kwc(rangees, catalogue)
    modules = sum(rangee.modules for rangee in rangees)
    composition["total_texte"] = (
        "%d modules" % modules if kwc is None
        else "%d modules — %s kWc" % (modules, fr(kwc, 2)))
    return composition


def _kwc(rangees, catalogue):
    """Puissance du plan, ou ``None`` si un kit du plan n'est pas au catalogue.

    Sans le kit, la puissance ne se devine pas : on publie le compte seul.
    """
    par_code = {kit.code: kit for kit in catalogue}
    total = 0.0
    for rangee in rangees:
        kit = par_code.get(rangee.kit_code)
        if kit is None:
            return None
        total += rangee.modules * kit.puissance_module_wc
    return total / 1000.0


# ============================================================== tiroir allées
def _tiroir_allees(entree, compteur):
    """Largeur d'allée + plateau GRATUIT : la règle produit gravée d'AOF50.

    Les deux points certains du graphe (l'allée de référence et l'allée
    publiable) sont ceux que la recherche a DÉJÀ mesurés : les redemander au
    moteur serait payer deux fois le même DP.
    """
    if compteur.budget <= 0:
        return {"presets": []}, 0

    gratuite = chercher_allee_gratuite(entree.surface, entree.parametres,
                                       entree.obstacles, entree.zones)
    minimale = gratuite.allee_min_m
    publiable = gratuite.allee_publiable_m
    # Le plateau n'est publié que s'il est VALIDE : une allée large qui casse
    # un garde-fou ne devient pas un bouton « appliquer » (AOF50).
    offerte = (gratuite.gratuite and gratuite.valide
               and publiable > minimale)

    presets = [{"code": "minimale",
                "libelle": "Allée minimale (%s)" % fr_m(minimale),
                "largeur_m": minimale}]
    if offerte:
        presets.append({"code": "offerte",
                        "libelle": "Allée offerte (%s)" % fr_m(publiable),
                        "largeur_m": publiable})

    mesures = [(minimale, gratuite.compte_reference),
               (publiable, gratuite.compte_publiable)]
    # Le point de bascule DOIT être mesuré : c'est le seul du graphe qui dit
    # pourquoi le plateau s'arrête là.
    bascule = gratuite.allee_max_m + PAS_ARRONDI_M
    compte = compteur.compter(
        entree.surface, remplacer(entree.parametres, allee_m=bascule),
        entree.obstacles, entree.zones)
    if compte is not None:
        mesures.append((bascule, compte))

    donnees = {"presets": presets}
    points = _points_graphe(mesures)
    if points:
        graphe = {"points": points}
        if offerte:
            graphe["plateau"] = {
                "debut_m": minimale,
                "fin_m": gratuite.allee_max_m,
                "texte_debut": fr_m(minimale),
                "texte_fin": fr_m(gratuite.allee_max_m),
                "resume": ("le compte reste à %d modules de %s à %s : %s "
                           "d'allée de maintenance offerts"
                           % (gratuite.compte_reference, fr_m(minimale),
                              fr_m(gratuite.allee_max_m),
                              fr_m(gratuite.gain_m))),
                "largeur_offerte_m": publiable,
                "libelle_bouton": ("appliquer %s d'allée (aucun module perdu)"
                                   % fr_m(publiable)),
            }
        donnees["graphe"] = graphe
    return donnees, 1


def _points_graphe(mesures):
    """Points TRIÉS et dédoublonnés — un même x deux fois n'est pas une courbe."""
    vus = {}
    for largeur, compte in mesures:
        vus.setdefault(round(largeur, 6), compte)
    return [{"largeur_m": largeur, "compte": compte,
             "texte_largeur": fr_m(largeur),
             "texte_compte": "%d modules" % compte}
            for largeur, compte in sorted(vus.items())]


# =============================================================== tiroir rives
def _tiroir_rives(entree, reference, compteur):
    """Rives & dégagements, impacts chiffrés aux ancres CAPÉES uniquement."""
    parametres = entree.parametres
    courantes = {
        "rive_laterale_m": parametres.rives.laterale_m,
        "rive_extremite_m": parametres.rives.extremite_m,
        "degagement_defaut_m": parametres.degagement_defaut_m,
        "degagement_nature_inconnue_m": parametres.degagement_nature_inconnue_m,
    }
    champs = []
    for code, libelle, chiffrable in CHAMPS_RIVES:
        champ = {
            "code": code, "libelle": libelle, "unite": "m", "min": 0.0,
            # Borne = AVERTISSEMENT, jamais un rejet : le moteur refuse une
            # rive négative (``Rives.__post_init__``), c'est tout ce qu'on sait.
            "message_borne": "une rive ou un dégagement ne se compte pas en "
                             "négatif",
        }
        if chiffrable and reference is not None:
            champ["impacts"] = _impacts_rive(entree, code, courantes[code],
                                             reference, compteur)
        champs.append(champ)

    donnees = {"champs": champs}
    variante = _variante_conservatrice(entree, reference, compteur)
    if variante is not None:
        donnees["variante_conservatrice"] = variante
    return donnees


def _impacts_rive(entree, code, courante, reference, compteur):
    """La valeur courante (impact nul, par définition) + les ancres capées."""
    impacts = [_impact(courante, 0)]
    valeurs = []
    for pas in ANCRES_RIVES_M:
        valeurs.extend([round(courante - pas, 6), round(courante + pas, 6)])
    champ = "laterale_m" if code == "rive_laterale_m" else "extremite_m"
    for valeur in valeurs:
        if valeur < 0:
            continue  # une rive négative n'existe pas : rien à chiffrer
        surface, parametres = _rives_appliquees(entree, **{champ: valeur})
        compte = compteur.compter(surface, parametres, entree.obstacles,
                                  entree.zones)
        if compte is None:
            break  # budget épuisé : l'écran dira « impact non chiffré »
        impacts.append(_impact(valeur, compte - reference))
    return sorted(impacts, key=lambda impact: impact["valeur"])


def _impact(valeur, delta):
    texte, sens = _texte_impact(delta)
    return {"valeur": valeur, "texte_valeur": fr_m(valeur),
            "impact_texte": texte, "sens": sens}


def _variante_conservatrice(entree, reference, compteur):
    """La variante 1,50 / 0,50 / 0,50, REJOUÉE — sinon elle n'est pas publiée."""
    if reference is None:
        return None
    valeurs = dict(VARIANTE_CONSERVATRICE)
    surface, parametres = _rives_appliquees(
        entree, laterale_m=valeurs["rive_laterale_m"],
        extremite_m=valeurs["rive_extremite_m"])
    parametres = remplacer(parametres, allee_m=valeurs["allee_m"])
    compte = compteur.compter(surface, parametres, entree.obstacles,
                              entree.zones)
    if compte is None:
        return None  # jamais un bouton sans son chiffre
    texte, _sens = _texte_impact(compte - reference)
    return {
        "libelle": "comparer à la variante conservatrice (%s / %s / %s)"
                   % (fr_m(valeurs["rive_laterale_m"]),
                      fr_m(valeurs["rive_extremite_m"]),
                      fr_m(valeurs["allee_m"])),
        "valeurs": valeurs,
        "comparaison_texte": "%d modules contre %d aujourd'hui — %s"
                             % (compte, reference, texte),
    }


# ========================================================= tiroir orientation
def _tiroir_orientation(entree, catalogue, azimut):
    """Refus d'orientation : le motif vient de ``motif_orientation``, verbatim."""
    sens = []
    for axe, libelle in _LIBELLE_AXE:
        motif = ""
        for kit in catalogue:
            try:
                verifier_kit(kit, axe, azimut)
            except ErreurOrientation as erreur:
                motif = str(erreur)
                break
        option = {"code": axe.value, "libelle": libelle,
                  "disponible": not motif}
        if motif:
            option["motif"] = motif
        sens.append(option)

    tables = []
    for orientation, libelle in _LIBELLE_ORIENTATION:
        kits = [kit for kit in catalogue if kit.orientation is orientation]
        if not kits:
            tables.append({"code": orientation.value, "libelle": libelle,
                           "disponible": False,
                           "motif": "aucun kit %s n'est déclaré au catalogue"
                                    % orientation.value.lower()})
            continue
        motif = ""
        for kit in kits:
            try:
                verifier_kit(kit, entree.parametres.axe_rangee, azimut)
                motif = ""
                break
            except ErreurOrientation as erreur:
                motif = str(erreur)
        option = {"code": orientation.value, "libelle": libelle,
                  "disponible": not motif}
        if motif:
            option["motif"] = motif
        tables.append(option)

    # Le moteur n'a NI modèle de découpage en segments NI traitement du L :
    # meubler ces groupes afficherait des choix que rien ne sait appliquer.
    return {"sens_rangees": sens, "orientations_tables": tables,
            "segmentations": [], "formes_l": []}


# ==================================================================== sortie
@dataclass(frozen=True)
class DonneesTiroirs:
    """Les 4 charges utiles + le COÛT qu'elles ont vraiment payé."""

    kits: dict
    allees: dict
    rives: dict
    orientation: dict
    appels_moteur: int = 0
    budget_appels: int = BUDGET_APPELS_DEFAUT
    #: recherches d'allée gratuite lancées (0 ou 1). Leur dichotomie est bornée
    #: par ``allee_gratuite``, pas par ``budget_appels`` : la compter dans le
    #: budget donnerait un chiffre faux, l'omettre en cacherait le coût.
    recherches_allee: int = 0

    @property
    def budget_atteint(self):
        return self.appels_moteur >= self.budget_appels

    def vers_dict(self):
        return {"kits": self.kits, "allees": self.allees, "rives": self.rives,
                "orientation": self.orientation}


def donnees_tiroirs(entree, resultat, catalogue=(),
                    budget_appels=BUDGET_APPELS_DEFAUT):
    """Construit les 4 charges utiles des tiroirs débutant. PUR, sans I/O.

    ``entree`` — tout objet portant ``surface``, ``parametres``, ``obstacles``
    et ``zones`` (typiquement ``recommandations.EntreeMoteur``) ;
    ``resultat`` — le ``ResultatOptimum`` retenu (il donne la composition et,
    s'il vient du DP exact, le compte de référence des impacts) ;
    ``catalogue`` — les kits admissibles (par défaut ceux des paramètres).

    Le compte de référence n'est réutilisé que s'il vient de la MÊME méthode
    que les impacts (DP exact) : comparer un impact DP à un compte heuristique
    publierait un écart qui n'existe pas.
    """
    catalogue = tuple(catalogue) or tuple(entree.parametres.kits)
    compteur = _Compteur(budget_appels)
    azimut = getattr(entree.surface, "azimut_deg", 180.0)

    preuve = getattr(resultat, "preuve", None)
    if preuve is not None and preuve.methode is MethodePreuve.DP_EXACT_1CM:
        reference = resultat.modules
    else:
        reference = compteur.compter(entree.surface, entree.parametres,
                                     entree.obstacles, entree.zones)

    kits = _tiroir_kits(entree, resultat, catalogue, azimut, compteur)
    rives = _tiroir_rives(entree, reference, compteur)
    allees, recherches = _tiroir_allees(entree, compteur)
    orientation = _tiroir_orientation(entree, catalogue, azimut)
    return DonneesTiroirs(kits=kits, allees=allees, rives=rives,
                          orientation=orientation,
                          appels_moteur=compteur.appels,
                          budget_appels=compteur.budget,
                          recherches_allee=recherches)
