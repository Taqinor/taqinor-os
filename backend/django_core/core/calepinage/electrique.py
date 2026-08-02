# -*- coding: utf-8 -*-
"""AOF56 — modules → kWc → chaînes → onduleurs, ET la contrainte qui reboucle.

La chaîne de dimensionnement est simple ; ce qui l'est moins, c'est qu'elle
REBOUCLE sur le calepinage. Sur le dossier FRDISI, la règle « aucun onduleur
au-dessus de 60 kWc » a imposé de DÉPORTER 24 modules de l'arc vers l'aile en L
en courant continu : **un calepinage calculé sans cette contrainte est optimal
et inutilisable.** ``plafond_kwc_par_surface`` est donc une ENTRÉE du
calepinage (``site.Site``), pas une vérification faite après coup.

Le moteur s'arrête là où commence l'étude d'exécution : le stringing détaillé
(quelles tables dans quelle chaîne) et le routage des câbles restent HORS
moteur. Ce qui est ici est ce dont le dossier de dépôt a besoin : la puissance,
le nombre de chaînes, le nombre et le calibre des onduleurs, le ratio, et la
NOTE DE CALCUL qui explique chaque nombre.
"""

from dataclasses import dataclass

from core.calepinage.units import fr

__all__ = [
    "MODULES_PAR_CHAINE", "BORNES_RATIO_AC_DC", "PLAFOND_DC_PAR_ONDULEUR_KWC",
    "Chainage", "Onduleurs", "chainer", "evaluer_onduleurs", "dimensionner",
    "note_de_calcul", "plafond_modules_pour_kwc",
]

#: Longueur de chaîne retenue au dossier (le reste part « en réserve d'appoint »).
MODULES_PAR_CHAINE = 16

#: Bornes du ratio AC/DC (puissance onduleurs / puissance crête), paramétrables
#: — elles sont lues dans l'exigence du CPS quand le marché en impose une.
BORNES_RATIO_AC_DC = (0.75, 1.00)

#: Plafond de puissance CRÊTE raccordable sur UN onduleur (règle du dossier).
PLAFOND_DC_PAR_ONDULEUR_KWC = 60.0


@dataclass(frozen=True)
class Chainage:
    """Découpage en chaînes — le reste est ANNONCÉ, jamais dissimulé."""

    modules: int
    modules_par_chaine: int
    chaines: int
    reste: int
    puissance_module_wc: float

    @property
    def puissance_kwc(self):
        return self.modules * self.puissance_module_wc / 1000.0

    @property
    def modules_en_chaine(self):
        return self.chaines * self.modules_par_chaine


@dataclass(frozen=True)
class Onduleurs:
    """Une configuration d'onduleurs ÉVALUÉE — conforme ou refusée AVEC MOTIF."""

    taille_kw: float
    nombre: int
    puissance_dc_kwc: float
    conforme: bool
    motif: str = ""

    @property
    def puissance_ac_kw(self):
        return self.taille_kw * self.nombre

    @property
    def ratio_ac_dc(self):
        if not self.puissance_dc_kwc:
            return 0.0
        return self.puissance_ac_kw / self.puissance_dc_kwc

    @property
    def ratio_dc_ac(self):
        if not self.puissance_ac_kw:
            return 0.0
        return self.puissance_dc_kwc / self.puissance_ac_kw

    @property
    def dc_par_onduleur_kwc(self):
        return self.puissance_dc_kwc / self.nombre if self.nombre else 0.0


def chainer(modules, puissance_module_wc=625.0,
            modules_par_chaine=MODULES_PAR_CHAINE):
    """``288 modules -> 18 chaînes de 16, reste 0``."""
    if modules_par_chaine <= 0:
        raise ValueError("longueur de chaîne strictement positive")
    chaines = modules // modules_par_chaine
    return Chainage(modules=modules, modules_par_chaine=modules_par_chaine,
                    chaines=chaines,
                    reste=modules - chaines * modules_par_chaine,
                    puissance_module_wc=puissance_module_wc)


def evaluer_onduleurs(puissance_dc_kwc, taille_kw, nombre,
                      bornes=BORNES_RATIO_AC_DC,
                      plafond_dc_kwc=PLAFOND_DC_PAR_ONDULEUR_KWC):
    """Évalue UNE configuration : conforme, ou refusée avec le MOTIF nommé."""
    if nombre <= 0 or taille_kw <= 0:
        raise ValueError("calibre et nombre d'onduleurs strictement positifs")
    config = Onduleurs(taille_kw=taille_kw, nombre=nombre,
                       puissance_dc_kwc=puissance_dc_kwc, conforme=True)
    mini, maxi = bornes
    if config.ratio_ac_dc < mini - 1e-9:
        return Onduleurs(
            taille_kw=taille_kw, nombre=nombre,
            puissance_dc_kwc=puissance_dc_kwc, conforme=False,
            motif="ratio AC/DC de %s hors bornes [%s ; %s] — %d × %s kW ne "
                  "reprennent pas %s kWc crête"
                  % (fr(config.ratio_ac_dc, 3), fr(mini, 2), fr(maxi, 2),
                     nombre, fr(taille_kw, 0), fr(puissance_dc_kwc, 1)))
    if config.ratio_ac_dc > maxi + 1e-9:
        return Onduleurs(
            taille_kw=taille_kw, nombre=nombre,
            puissance_dc_kwc=puissance_dc_kwc, conforme=False,
            motif="ratio AC/DC de %s au-dessus de la borne %s — onduleurs "
                  "surdimensionnés" % (fr(config.ratio_ac_dc, 3), fr(maxi, 2)))
    if plafond_dc_kwc is not None \
            and config.dc_par_onduleur_kwc > plafond_dc_kwc + 1e-9:
        return Onduleurs(
            taille_kw=taille_kw, nombre=nombre,
            puissance_dc_kwc=puissance_dc_kwc, conforme=False,
            motif="%s kWc par onduleur au-dessus du plafond de %s kWc — "
                  "déport de modules nécessaire"
                  % (fr(config.dc_par_onduleur_kwc, 1), fr(plafond_dc_kwc, 0)))
    return config


def dimensionner(puissance_dc_kwc, calibres_kw=(50.0, 60.0, 80.0),
                 bornes=BORNES_RATIO_AC_DC,
                 plafond_dc_kwc=PLAFOND_DC_PAR_ONDULEUR_KWC, nombre_max=12):
    """Rend ``(retenue, refusées)`` — toute configuration refusée garde son motif.

    La configuration retenue est la CONFORME au plus petit nombre d'onduleurs,
    puis au plus petit calibre : deux critères objectifs, aucun arbitrage caché.
    """
    conformes, refusees = [], []
    for taille in calibres_kw:
        for nombre in range(1, nombre_max + 1):
            config = evaluer_onduleurs(puissance_dc_kwc, taille, nombre,
                                       bornes, plafond_dc_kwc)
            (conformes if config.conforme else refusees).append(config)
    if not conformes:
        return (None, tuple(refusees))
    retenue = min(conformes, key=lambda c: (c.nombre, c.taille_kw))
    return (retenue, tuple(refusees))


def plafond_modules_pour_kwc(plafond_kwc, puissance_module_wc=625.0):
    """Combien de modules tiennent sous un plafond kWc — l'ENTRÉE du calepinage."""
    if plafond_kwc is None:
        return None
    return int(plafond_kwc * 1000.0 / puissance_module_wc)


def note_de_calcul(chainage, onduleurs, refusees=()):
    """Note de calcul GÉNÉRÉE, ligne à ligne — aucun nombre littéral."""
    lignes = [
        "%d modules × %s Wc = %s kWc crête"
        % (chainage.modules, fr(chainage.puissance_module_wc, 0),
           fr(chainage.puissance_kwc, 1)),
        "%d chaînes de %d modules (%d modules en chaîne)"
        % (chainage.chaines, chainage.modules_par_chaine,
           chainage.modules_en_chaine),
    ]
    if chainage.reste:
        lignes.append("%d module(s) en réserve d'appoint (hors chaîne)"
                      % chainage.reste)
    if onduleurs is not None:
        lignes.append(
            "%d onduleurs de %s kW = %s kW AC, ratio AC/DC %s"
            % (onduleurs.nombre, fr(onduleurs.taille_kw, 0),
               fr(onduleurs.puissance_ac_kw, 0), fr(onduleurs.ratio_ac_dc, 3)))
        lignes.append("%s kWc crête par onduleur"
                      % fr(onduleurs.dc_par_onduleur_kwc, 1))
    for refusee in refusees:
        lignes.append("REFUSÉ — %d × %s kW : %s"
                      % (refusee.nombre, fr(refusee.taille_kw, 0),
                         refusee.motif))
    return tuple(lignes)
