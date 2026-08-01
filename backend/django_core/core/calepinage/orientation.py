# -*- coding: utf-8 -*-
"""AOF45 — refus MOTEUR d'une orientation INCONSTRUCTIBLE.

Le cas historique, et il a coûté une planche entière. Une table dos-à-dos
est-ouest porte deux modules, l'un face EST l'autre face OUEST : son FAÎTAGE
est forcément NORD-SUD, donc ses rangées courent NORD-SUD. La v1 de la planche
du bâtiment A avait calepiné la barre en rangées EST-OUEST — faîtage est-ouest,
donc un module face NORD : inconstructible. TOUTE la planche a dû être refaite.

Traiter ce piège UNIQUEMENT côté écran (un tiroir « Orientation ») ne suffit
pas : un appel d'API, un import CSV ou le chemin villa contournent l'écran et
produisent un livrable FAUX EN SILENCE. Le contrôle vit donc ici, il s'exécute
AVANT tout calcul, et ``garde_fous.valider`` le rejoue sur le plan fini.
"""

from core.calepinage.types import Axe

__all__ = [
    "ErreurOrientation", "axe_rangee_impose", "verifier_kit", "verifier",
    "parametres_avec_axe_derive", "motif_orientation",
]


class ErreurOrientation(ValueError):
    """Orientation inconstructible — jamais un plan silencieux."""


def axe_rangee_impose(kit, azimut_deg=180.0):
    """Axe que le KIT impose à ses rangées.

    * table dos-à-dos (≥ 2 modules) : les faces sont est/ouest, le faîtage est
      nord-sud, les rangées courent NORD-SUD ;
    * module unique (villa) : les rangées courent PERPENDICULAIREMENT à la
      direction visée par les modules — plein sud ⇒ rangées est-ouest.
    """
    if kit.modules_par_table >= 2:
        return Axe.NORD_SUD
    reste = abs(float(azimut_deg)) % 180.0
    return Axe.EST_OUEST if reste < 45.0 or reste > 135.0 else Axe.NORD_SUD


def motif_orientation(kit, axe_demande, azimut_deg=180.0):
    """Phrase GÉNÉRÉE expliquant le refus — jamais un texte rédigé ailleurs."""
    impose = axe_rangee_impose(kit, azimut_deg)
    if kit.modules_par_table >= 2:
        cause = ("une table dos-à-dos porte un module face EST et un face "
                 "OUEST : son faîtage est NORD-SUD")
    else:
        cause = ("un module unique orienté à %.0f° impose des rangées "
                 "perpendiculaires à sa pente" % azimut_deg)
    return ("kit %s : %s, donc les rangées courent %s — %s demandé "
            "(inconstructible)" % (kit.code, cause, impose.value,
                                   axe_demande.value))


def verifier_kit(kit, axe_rangee, azimut_deg=180.0):
    """LÈVE ``ErreurOrientation`` si l'axe demandé est inconstructible."""
    impose = axe_rangee_impose(kit, azimut_deg)
    if axe_rangee is not impose:
        raise ErreurOrientation(motif_orientation(kit, axe_rangee, azimut_deg))
    return impose


def verifier(parametres, surfaces=()):
    """Contrôle AVANT tout calcul : chaque kit contre l'axe des paramètres.

    Les surfaces sont vérifiées AUSSI : une surface qui déclare son propre
    ``axe_rangee`` (multi-pans) doit rester cohérente avec les paramètres,
    sinon l'écran et l'API divergent en silence.
    """
    for surface in surfaces:
        azimut = getattr(surface, "azimut_deg", 180.0)
        axe_surface = getattr(surface, "axe_rangee", parametres.axe_rangee)
        if axe_surface is not parametres.axe_rangee:
            raise ErreurOrientation(
                "surface %s : axe de rangée %s incompatible avec les "
                "paramètres (%s)" % (getattr(surface, "repere", "?"),
                                     axe_surface.value,
                                     parametres.axe_rangee.value))
        for kit in parametres.kits:
            verifier_kit(kit, axe_surface, azimut)
    if not surfaces:
        for kit in parametres.kits:
            verifier_kit(kit, parametres.axe_rangee)
    return True


def parametres_avec_axe_derive(parametres, azimut_deg=180.0):
    """Rend des ``Parametres`` dont l'axe est DÉRIVÉ des kits, jamais deviné.

    Tous les kits d'un même jeu doivent imposer le même axe : mélanger une
    table dos-à-dos et un module unique plein sud dans un seul calepinage est
    une incohérence, pas un arbitrage.
    """
    from core.calepinage.types import remplacer

    axes = {axe_rangee_impose(kit, azimut_deg) for kit in parametres.kits}
    if len(axes) > 1:
        raise ErreurOrientation(
            "kits d'axes incompatibles dans le même calepinage : %s"
            % ", ".join(sorted(a.value for a in axes)))
    return remplacer(parametres, axe_rangee=axes.pop())
