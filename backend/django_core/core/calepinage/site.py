# -*- coding: utf-8 -*-
"""AOF41 — le SITE : N surfaces, un total CALCULÉ, des contraintes inter-bâtiments.

Un dossier d'appel d'offres ne se joue jamais sur un bâtiment : FRDISI compte
152 + 120 + 288 = 560 modules sur trois toitures. Le total d'un site n'est donc
JAMAIS un nombre saisi quelque part — c'est une propriété calculée, sans quoi
la première correction de calepinage rend le récapitulatif faux en silence.

Deux contraintes vivent au niveau du site et nulle part ailleurs :

* ``plafond_kwc`` — la règle « aucun onduleur au-dessus de 60 kWc » a imposé de
  déporter 24 modules de l'arc vers l'aile L en DC. Un calepinage calculé sans
  cette contrainte est optimal ET INUTILISABLE ;
* ``Deport`` — le transfert explicite de N modules d'un bâtiment vers un autre,
  qui doit conserver le total du site au module près.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

__all__ = ["CompteSurface", "Deport", "Site", "AgregatSite", "agreger"]


@dataclass(frozen=True)
class CompteSurface:
    """Ce qu'une surface apporte au site — jamais recopié depuis un écran."""

    repere: str
    modules: int
    puissance_module_wc: float = 625.0
    engageable: bool = True
    motifs: Tuple[str, ...] = ()

    @property
    def kwc(self):
        return self.modules * self.puissance_module_wc / 1000.0


@dataclass(frozen=True)
class Deport:
    """N modules calepinés sur ``depuis`` mais raccordés sur ``vers`` (DC)."""

    depuis: str
    vers: str
    modules: int
    motif: str = ""

    def __post_init__(self):
        if self.modules <= 0:
            raise ValueError("un déport porte au moins un module")
        if self.depuis == self.vers:
            raise ValueError("un déport relie deux bâtiments DIFFÉRENTS")


@dataclass(frozen=True)
class Site:
    """Le site : ses surfaces, son engagement global, ses contraintes."""

    repere: str
    surfaces: Tuple[object, ...] = ()
    engagement_modules: Optional[int] = None
    plafond_kwc_par_surface: Optional[float] = None
    deports: Tuple[Deport, ...] = ()

    @property
    def reperes(self):
        return tuple(getattr(s, "repere", "") for s in self.surfaces)


@dataclass(frozen=True)
class AgregatSite:
    """Total du site — ``modules`` et ``kwc`` sont CALCULÉS, jamais stockés."""

    repere: str
    comptes: Tuple[CompteSurface, ...]
    engagement_modules: Optional[int] = None
    deports_appliques: Tuple[Deport, ...] = ()
    motifs: Tuple[str, ...] = ()

    @property
    def modules(self):
        return sum(c.modules for c in self.comptes)

    @property
    def kwc(self):
        return sum(c.kwc for c in self.comptes)

    @property
    def engageable(self):
        return all(c.engageable for c in self.comptes) and not self.motifs

    @property
    def tenu(self):
        if self.engagement_modules is None:
            return True
        return self.modules >= self.engagement_modules

    def compte(self, repere):
        for c in self.comptes:
            if c.repere == repere:
                return c
        raise KeyError("aucune surface %r dans le site %s" % (repere, self.repere))


def _plafonner(comptes, plafond_kwc):
    """Applique un plafond kWc PAR SURFACE et rend les motifs NOMMÉS."""
    if plafond_kwc is None:
        return comptes, ()
    sortie, motifs = [], []
    for c in comptes:
        if c.kwc <= plafond_kwc + 1e-9:
            sortie.append(c)
            continue
        maxi = int(plafond_kwc * 1000.0 / c.puissance_module_wc)
        motifs.append(
            "%s : %d modules (%.1f kWc) dépassent le plafond de %.1f kWc — "
            "%d modules à déporter" % (c.repere, c.modules, c.kwc, plafond_kwc,
                                       c.modules - maxi))
        sortie.append(CompteSurface(repere=c.repere, modules=maxi,
                                    puissance_module_wc=c.puissance_module_wc,
                                    engageable=c.engageable, motifs=c.motifs))
    return tuple(sortie), tuple(motifs)


def _deporter(comptes, deports):
    """Déplace des modules d'un bâtiment à l'autre — le TOTAL est conservé."""
    par_repere = {c.repere: c for c in comptes}
    for d in deports:
        if d.depuis not in par_repere or d.vers not in par_repere:
            raise KeyError("déport %s -> %s : bâtiment inconnu"
                           % (d.depuis, d.vers))
        source = par_repere[d.depuis]
        if source.modules < d.modules:
            raise ValueError("déport %s -> %s : %d modules demandés, %d posés"
                             % (d.depuis, d.vers, d.modules, source.modules))
        cible = par_repere[d.vers]
        par_repere[d.depuis] = CompteSurface(
            repere=source.repere, modules=source.modules - d.modules,
            puissance_module_wc=source.puissance_module_wc,
            engageable=source.engageable, motifs=source.motifs)
        par_repere[d.vers] = CompteSurface(
            repere=cible.repere, modules=cible.modules + d.modules,
            puissance_module_wc=cible.puissance_module_wc,
            engageable=cible.engageable, motifs=cible.motifs)
    return tuple(par_repere[c.repere] for c in comptes)


def agreger(site, comptes):
    """Agrège les comptes d'un site : plafond, déports, engagement global.

    L'invariant ``somme(bâtiments) == total`` n'est pas une convention : c'est
    la définition de ``AgregatSite.modules``.
    """
    comptes = tuple(comptes)
    reperes = [c.repere for c in comptes]
    if len(set(reperes)) != len(reperes):
        raise ValueError("deux comptes portent le même repère de surface")
    comptes, motifs = _plafonner(comptes, site.plafond_kwc_par_surface)
    if site.deports:
        comptes = _deporter(comptes, site.deports)
    return AgregatSite(repere=site.repere, comptes=comptes,
                       engagement_modules=site.engagement_modules,
                       deports_appliques=tuple(site.deports), motifs=motifs)
