# -*- coding: utf-8 -*-
"""AOF54 — recommandations APPLIQUABLES à gain RECALCULÉ, jamais un conseil.

Une recommandation qui dit « vous gagneriez sans doute quelques modules en
autorisant les kits mixtes » ne vaut rien : personne ne la mettra en œuvre, et
si quelqu'un le fait, le chiffre annoncé sera faux. Ici, chaque proposition
porte :

* un ``patch_entree`` DÉCLARATIF, applicable en un clic
  (``appliquer_patch``) — c'est la même structure qui voyage jusqu'à l'écran ;
* un ``gain_modules`` obtenu en REJOUANT le moteur sur l'entrée patchée —
  jamais estimé, jamais extrapolé ;
* une ``question_a_poser`` pré-remplie de son impact chiffré, qui alimente
  directement le workflow de questions/réponses au maître d'ouvrage.

La contre-épreuve de kit est OBLIGATOIRE : on ne propose pas un kit alternatif
sans avoir vérifié qu'il ne fait pas MOINS bien (``n_alt <= n_show`` du script
d'origine — chiffres publiés S2 paysage 34 contre portrait 24, S3 paysage 44
contre portrait 36 ; aucun n'est écrit à la main).
"""

from dataclasses import dataclass, replace
from typing import Tuple

from core.calepinage.allee_gratuite import chercher_allee_gratuite
from core.calepinage.obstacles import appliquer_regles
from core.calepinage.orientation import ErreurOrientation, verifier_kit
from core.calepinage.perf import caper, optimiser_economique
from core.calepinage.types import (
    Axe,
    Confiance,
    Provenance,
    Recommandation,
    remplacer,
)

__all__ = [
    "EntreeMoteur", "appliquer_patch", "proposer", "PROVENANCES_A_ARBITRER",
    "PLAFOND_RECOMMANDATIONS",
]

#: Provenances qu'il faut faire arbitrer par le maître d'ouvrage.
PROVENANCES_A_ARBITRER = (Provenance.PLAN, Provenance.DEVINE,
                          Provenance.RELEVE_DOUTEUX)

#: Chaque recommandation rejoue le moteur : le balayage est CAPÉ (AOF48).
PLAFOND_RECOMMANDATIONS = 12


@dataclass(frozen=True)
class EntreeMoteur:
    """L'entrée complète d'un calepinage — ce qu'un patch transforme."""

    surface: object
    parametres: object
    obstacles: Tuple[object, ...] = ()
    zones: Tuple[object, ...] = ()

    def compter(self, politique=None):
        return optimiser_economique(self.surface, self.parametres,
                                    self.obstacles, self.zones,
                                    politique).modules


def _kits_par_codes(catalogue, codes):
    par_code = {kit.code: kit for kit in catalogue}
    manquants = [c for c in codes if c not in par_code]
    if manquants:
        raise KeyError("kit inconnu dans le patch : %s" % ", ".join(manquants))
    return tuple(par_code[c] for c in codes)


def appliquer_patch(entree, patch, catalogue_kits=()):
    """Applique un patch DÉCLARATIF et rend une NOUVELLE entrée (immuable).

    Clés reconnues — toute autre clé lève, car un patch silencieusement ignoré
    afficherait un gain que l'application ne produirait jamais :

    * ``allee_m``            — nouvelle largeur d'allée ;
    * ``kits``               — codes de kits séparés par ``+`` ;
    * ``rive_laterale_m`` / ``rive_extremite_m`` ;
    * ``ecarter``            — repère d'obstacle à sortir du compte ;
    * ``confirmer``          — repère d'obstacle à passer en RELEVÉ ;
    * ``axe_rangee``         — ``NORD_SUD`` / ``EST_OUEST``.
    """
    surface = entree.surface
    parametres = entree.parametres
    obstacles = tuple(entree.obstacles)
    catalogue = tuple(catalogue_kits) or tuple(parametres.kits)

    for cle, valeur in patch:
        if cle == "allee_m":
            parametres = remplacer(parametres, allee_m=float(valeur))
        elif cle == "kits":
            parametres = remplacer(
                parametres,
                kits=_kits_par_codes(catalogue, str(valeur).split("+")))
        elif cle in ("rive_laterale_m", "rive_extremite_m"):
            champ = ("laterale_m" if cle == "rive_laterale_m"
                     else "extremite_m")
            rives = replace(parametres.rives, **{champ: float(valeur)})
            parametres = remplacer(parametres, rives=rives)
            surface = replace(surface, rives=rives)
        elif cle == "ecarter":
            obstacles = tuple(
                remplacer(o, provenance=Provenance.ECARTE)
                if o.repere == valeur else o for o in obstacles)
        elif cle == "confirmer":
            obstacles = tuple(
                remplacer(o, provenance=Provenance.RELEVE, degagement_m=None)
                if o.repere == valeur else o for o in obstacles)
        elif cle == "axe_rangee":
            parametres = remplacer(parametres, axe_rangee=Axe(valeur))
        else:
            raise KeyError("clé de patch inconnue : %r" % (cle,))
    return EntreeMoteur(surface=surface, parametres=parametres,
                        obstacles=appliquer_regles(obstacles),
                        zones=tuple(entree.zones))


def _gain(entree, patch, reference, catalogue):
    """Le gain est REJOUÉ, jamais estimé — c'est toute la tâche."""
    patchee = appliquer_patch(entree, patch, catalogue)
    return patchee.compter() - reference


def _kwc(entree, modules):
    kit = entree.parametres.kits[0]
    return modules * kit.puissance_module_wc / 1000.0


def proposer(entree, catalogue_kits=(), plafond=PLAFOND_RECOMMANDATIONS):
    """Balaye les leviers connus et rend les propositions à gain RECALCULÉ.

    Les propositions de gain nul sont conservées quand elles apportent autre
    chose qu'un module (l'allée gratuite en est le cas type) ; aucune n'est
    rendue sans avoir été rejouée.
    """
    catalogue = tuple(catalogue_kits) or tuple(entree.parametres.kits)
    reference = entree.compter()
    propositions = []

    # ------------------------------------------------ 1. allée gratuite
    gratuite = chercher_allee_gratuite(entree.surface, entree.parametres,
                                       entree.obstacles, entree.zones)
    if gratuite.gratuite and gratuite.allee_publiable_m > entree.parametres.allee_m:
        patch = (("allee_m", "%.2f" % gratuite.allee_publiable_m),)
        gain = _gain(entree, patch, reference, catalogue)
        propositions.append(Recommandation(
            code="ALLEE_GRATUITE",
            titre="élargir les allées à %.2f m sans perdre un module "
                  "(maintenance offerte)" % gratuite.allee_publiable_m,
            gain_modules=gain, gain_kwc=_kwc(entree, gain),
            cout_qualitatif="aucun — le compte est identique jusqu'à %.2f m"
                            % gratuite.allee_max_m,
            confiance=Confiance.HAUTE, patch_entree=patch,
            question_a_poser="Souhaitez-vous des allées de maintenance de "
                             "%.2f m ? Elles ne coûtent aucun module."
                             % gratuite.allee_publiable_m))

    # ------------------------------------------- 2. kits mixtes + contre-épreuve
    codes = tuple(kit.code for kit in catalogue)
    if len(codes) > 1 and len(entree.parametres.kits) < len(codes):
        patch = (("kits", "+".join(codes)),)
        gain = _gain(entree, patch, reference, catalogue)
        contre_epreuves = []
        for kit in catalogue:
            seul = _gain(entree, (("kits", kit.code),), reference, catalogue)
            contre_epreuves.append((kit.code, seul))
            # contre-épreuve OBLIGATOIRE : un kit seul ne bat jamais le mixte
            if seul > gain:
                raise AssertionError(
                    "contre-épreuve en échec : le kit %s seul (%+d) bat le jeu "
                    "mixte (%+d)" % (kit.code, seul, gain))
        if gain > 0:
            propositions.append(Recommandation(
                code="KITS_MIXTES",
                titre="autoriser les kits mixtes (%s)" % ", ".join(codes),
                gain_modules=gain, gain_kwc=_kwc(entree, gain),
                cout_qualitatif="deux références de structure à approvisionner",
                confiance=Confiance.HAUTE, patch_entree=patch,
                question_a_poser="Acceptez-vous deux types de tables sur la "
                                 "même toiture ? Gain chiffré : %+d modules."
                                 % gain))

    # ------------------------- 3. arbitrage de CHAQUE emprise non mesurée
    for o in entree.obstacles:
        if o.provenance not in PROVENANCES_A_ARBITRER:
            continue
        patch = (("ecarter", o.repere),)
        gain = _gain(entree, patch, reference, catalogue)
        confirme = _gain(entree, (("confirmer", o.repere),), reference,
                         catalogue)
        propositions.append(Recommandation(
            code="ARBITRER_%s" % o.repere,
            titre="faire arbitrer l'emprise %s (provenance %s)"
                  % (o.repere, o.provenance.value),
            gain_modules=gain, gain_kwc=_kwc(entree, gain),
            cout_qualitatif="une confirmation de relevé — impact chiffré des "
                            "DEUX côtés : retirée %+d, confirmée %+d"
                            % (gain, confirme),
            confiance=Confiance.MOYENNE, patch_entree=patch,
            question_a_poser="L'emprise %s existe-t-elle réellement ? Si non, "
                             "%+d modules ; si oui et mesurée, %+d."
                             % (o.repere, gain, confirme)))

    # --------------------------------------------- 4. relâchement de rive
    rives = entree.parametres.rives
    if rives.laterale_m > 0.30:
        patch = (("rive_laterale_m", "%.2f" % (rives.laterale_m - 0.05)),)
        gain = _gain(entree, patch, reference, catalogue)
        if gain > 0:
            propositions.append(Recommandation(
                code="RIVE_RELACHEE",
                titre="ramener la rive latérale à %.2f m"
                      % (rives.laterale_m - 0.05),
                gain_modules=gain, gain_kwc=_kwc(entree, gain),
                cout_qualitatif="5 cm de moins pour la circulation en rive",
                confiance=Confiance.BASSE, patch_entree=patch,
                question_a_poser="Le maître d'ouvrage accepte-t-il une rive "
                                 "latérale de %.2f m ? Gain : %+d modules."
                                 % (rives.laterale_m - 0.05, gain)))

    # ------------------------------------------ 5. orientation alternative
    autre = (Axe.EST_OUEST if entree.parametres.axe_rangee is Axe.NORD_SUD
             else Axe.NORD_SUD)
    constructible = True
    for kit in entree.parametres.kits:
        try:
            verifier_kit(kit, autre, getattr(entree.surface, "azimut_deg",
                                             180.0))
        except ErreurOrientation:
            constructible = False
            break
    if constructible:
        patch = (("axe_rangee", autre.value),)
        gain = _gain(entree, patch, reference, catalogue)
        if gain > 0:
            propositions.append(Recommandation(
                code="ORIENTATION_ALTERNATIVE",
                titre="basculer les rangées en %s" % autre.value,
                gain_modules=gain, gain_kwc=_kwc(entree, gain),
                cout_qualitatif="réorientation complète du champ",
                confiance=Confiance.MOYENNE, patch_entree=patch,
                question_a_poser="Peut-on orienter les rangées en %s ? "
                                 "Gain : %+d modules." % (autre.value, gain)))

    propositions.sort(key=lambda r: (-r.gain_modules, r.code))
    return caper(propositions, plafond)
