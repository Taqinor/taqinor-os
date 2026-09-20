"""CAL124 — les chaînes du calepinage, groupées PAN PAR PAN.

LE DÉFAUT CORRIGÉ
-----------------
``apps/ventes/solar_design.py::string_design`` répartit N panneaux sur les
entrées MPPT sans savoir D'OÙ ils viennent. Sur une toiture à plusieurs pans,
cela autorise une chaîne qui mélange deux orientations — une faute que PVsyst
interdit par construction (une orientation par sous-champ) : deux azimuts
n'atteignent pas leur point de puissance maximale au même instant, et la perte
est PERMANENTE et invisible au bordereau.

LA RÈGLE, ÉCRITE NOIR SUR BLANC
--------------------------------
* **deux azimuts ne partagent JAMAIS une CHAÎNE** — c'est une règle de
  physique, elle ne se négocie pas ;
* **deux groupes PEUVENT partager une entrée MPPT** quand la fiche onduleur
  l'autorise (polystring : plusieurs chaînes par entrée, ce que les hybrides
  résidentiels font couramment — clé ``chaines_max_par_mppt`` de la fiche,
  CAL115). Sans autorisation publiée sur la fiche, le partage est signalé
  comme un DÉPASSEMENT et le message NOMME l'onduleur et le pan en trop.

Le verdict dit toujours laquelle des deux s'applique.

AUCUN SECOND ALGORITHME DE DIMENSIONNEMENT
-------------------------------------------
Le découpage lui-même (fenêtre de tension à froid/à chaud, longueur de chaîne,
allocation des entrées MPPT, verdicts de courant) est celui du noyau pur
``core.electrique.chaines.concevoir_chaines`` — déjà un port À L'IDENTIQUE de
``string_design``, mais qui, lui, raisonne PAR PAN (``GroupePan``). Ce service
ne recalcule rien : il TRADUIT le document de conception et les fiches
techniques en ``EntreeElectrique``, puis publie le résultat. Écrire ici une
seconde règle de longueur de chaîne ferait deux vérités pour une même toiture
(c'est exactement ce que CAL170 réconcilie).

ZÉRO CHIFFRE INVENTÉ : une fiche technique muette ne produit pas un verdict
par défaut — elle produit un SILENCE nommé (``manquantes``), et l'appelant
affiche ce qui manque au lieu d'un faux vert.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from core.electrique.chaines import concevoir_chaines
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

__all__ = [
    'PanPose', 'Conception', 'REGLE_UNE_ORIENTATION_PAR_CHAINE',
    'pans_poses', 'groupes_electriques', 'specs_module', 'specs_onduleur',
    'entree_electrique', 'concevoir_par_pan',
]

#: La règle de physique, citée telle quelle dans les verdicts publiés.
REGLE_UNE_ORIENTATION_PAR_CHAINE = (
    "une CHAÎNE ne porte qu'une seule orientation : deux azimuts en série "
    "suivraient le plus faible des deux toute la journée (règle PVsyst d'une "
    "orientation par sous-champ)")

#: Les clés de fiche MODULE sans lesquelles aucune fenêtre de tension n'est
#: calculable. Libellés FRANÇAIS : ce sont eux que l'écran affiche.
CHAMPS_MODULE = (
    ('vmp_v', 'tension au point de puissance maximale (Vmp)'),
    ('voc_v', 'tension à vide (Voc)'),
    ('isc_a', 'courant de court-circuit (Isc)'),
    ('imp_a', 'courant au point de puissance maximale (Imp)'),
    ('pmax_wc', 'puissance crête (Pmax)'),
)

#: Idem côté ONDULEUR (CAL115 — bloc ``onduleur`` de ``specs_for_produit``).
CHAMPS_ONDULEUR = (
    ('n_mppt', "nombre d'entrées MPPT"),
    ('mppt_v_min', 'bas de plage MPPT'),
    ('mppt_v_max', 'haut de plage MPPT'),
    ('v_max_abs', 'tension DC maximale absolue'),
    ('i_max_mppt_a', "courant d'entrée admissible par MPPT"),
    ('ac_kw', 'puissance AC'),
)


@dataclass(frozen=True)
class PanPose:
    """Un pan du document de conception, avec les modules RÉELLEMENT posés.

    ``source_orientation`` dit d'où viennent l'azimut et l'inclinaison
    (``'geometrie'`` = plan de pose calculé, ``'saisie'`` = champs du pan,
    ``None`` = inconnue). Un pan sans orientation connue n'est JAMAIS fusionné
    avec un autre : à défaut de savoir qu'ils sont orientés pareil, on les
    traite comme différents (le coût est une chaîne de plus, jamais une perte
    permanente).
    """

    label: str
    modules: int
    azimut_deg: Optional[float] = None
    inclinaison_deg: Optional[float] = None
    source_orientation: Optional[str] = None


@dataclass(frozen=True)
class Conception:
    """Le chaînage d'un calepinage — ou le SILENCE nommé qui en tient lieu."""

    pans: Tuple[PanPose, ...] = ()
    resultat: object = None
    bloquants: Tuple[str, ...] = ()
    alertes: Tuple[str, ...] = ()
    #: Libellés français des données de fiche qui manquent (CAL128 : fiche
    #: incomplète ⇒ aucun verdict, jamais un faux vert).
    manquantes: Tuple[str, ...] = ()
    #: Le verdict de partage d'entrée MPPT : quelle règle s'applique ici.
    regle_mppt: str = ''
    partage_mppt: bool = False
    temperatures: object = None
    entree: object = None
    _drapeaux: Tuple[str, ...] = field(default=(), repr=False)

    @property
    def fiche_incomplete(self):
        """Vrai quand une fiche muette empêche tout verdict (CAL128)."""
        return bool(self.manquantes)

    @property
    def chaines(self):
        return getattr(self.resultat, 'chaines', ()) or ()

    @property
    def repartitions(self):
        return getattr(self.resultat, 'repartitions', ()) or ()


# ─────────────────────────────────────────────────────── lecture du document
def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _entier(valeur):
    nombre = _nombre(valeur)
    if nombre is None or nombre < 0:
        return None
    return int(nombre)


def _modules_du_pan(pan):
    """Le compte POSÉ prime sur le compte souhaité (schéma v2, CAL232).

    ``geometry.panels`` est la vérité la plus fine (les cellules RÉELLEMENT
    occupées, PV27) ; ``geometry.count`` vient ensuite, puis le ``result`` de
    zone, et seulement à défaut le compte SOUHAITÉ ``neededPanels``.
    """
    geometrie = pan.get('geometry') if isinstance(pan, dict) else None
    if isinstance(geometrie, dict):
        panneaux = geometrie.get('panels')
        if isinstance(panneaux, (list, tuple)) and panneaux:
            return len(panneaux)
        compte = _entier(geometrie.get('count'))
        if compte is not None:
            return compte
    resultat = pan.get('result') if isinstance(pan, dict) else None
    if isinstance(resultat, dict):
        compte = _entier(resultat.get('count'))
        if compte is not None:
            return compte
    return _entier(pan.get('neededPanels')) or 0


def _orientation_du_pan(pan):
    """``(azimut, inclinaison, source)`` — jamais une orientation devinée."""
    geometrie = pan.get('geometry') if isinstance(pan, dict) else None
    if isinstance(geometrie, dict):
        azimut = _nombre(geometrie.get('azimuthDeg'))
        pente = _nombre(geometrie.get('tiltDeg'))
        if azimut is not None or pente is not None:
            return (azimut, pente, 'geometrie')
    azimut = _nombre(pan.get('facingAzimuthDeg'))
    pente = _nombre(pan.get('pitchDeg'))
    if azimut is not None or pente is not None:
        return (azimut, pente, 'saisie')
    return (None, None, None)


def pans_poses(layout):
    """Les pans du document qui portent au moins un module POSÉ.

    Un pan par ``zone`` du document : deux zones ne sont JAMAIS fusionnées,
    même orientées pareil — le document dessine deux surfaces, le chaînage en
    respecte le découpage (fusionner ferait une chaîne qui saute d'un pan à
    l'autre sans que personne ne l'ait demandé).
    """
    if not isinstance(layout, dict):
        return ()
    zones = layout.get('zones')
    if not isinstance(zones, (list, tuple)):
        return ()
    pans = []
    for rang, zone in enumerate(zones, start=1):
        if not isinstance(zone, dict):
            continue
        modules = _modules_du_pan(zone)
        if not modules:
            continue
        azimut, pente, source = _orientation_du_pan(zone)
        libelle = (zone.get('label') or zone.get('id')
                   or 'PAN-%d' % rang)
        pans.append(PanPose(label=str(libelle), modules=modules,
                            azimut_deg=azimut, inclinaison_deg=pente,
                            source_orientation=source))
    return tuple(pans)


def groupes_electriques(layout):
    """Les ``GroupePan`` du noyau — UN groupe par pan, jamais deux mélangés."""
    return tuple(
        GroupePan(label=pan.label, nb_modules=pan.modules,
                  azimut_deg=pan.azimut_deg if pan.azimut_deg is not None
                  else 0.0,
                  inclinaison_deg=pan.inclinaison_deg
                  if pan.inclinaison_deg is not None else 0.0)
        for pan in pans_poses(layout))


# ──────────────────────────────────────────────────────── fiches techniques
def _manquantes(specs, champs):
    specs = specs if isinstance(specs, dict) else {}
    return tuple(libelle for cle, libelle in champs
                 if _nombre(specs.get(cle)) is None)


def specs_module(specs, designation=''):
    """``(SpecModule | None, manquantes)`` depuis un bloc ``module`` du stock.

    Les blocs viennent de ``apps.stock.selectors.specs_for_produit`` (lecture
    cross-app par SÉLECTEUR — jamais un import des modèles de stock). Les
    coefficients de température gardent les défauts documentés du noyau quand
    la fiche ne les publie pas : ce sont des valeurs du NOYAU, pas un troisième
    jeu de constantes inventé ici.
    """
    manquantes = _manquantes(specs, CHAMPS_MODULE)
    if manquantes:
        return (None, manquantes)
    specs = dict(specs)
    optionnels = {}
    for cle in ('temp_coeff_voc_pct_c', 'temp_coeff_pmax_pct_c'):
        valeur = _nombre(specs.get(cle))
        if valeur is not None:
            optionnels[cle] = valeur
    return (SpecModule(
        vmp_v=float(specs['vmp_v']), voc_v=float(specs['voc_v']),
        isc_a=float(specs['isc_a']), imp_a=float(specs['imp_a']),
        pmax_wc=float(specs['pmax_wc']), designation=designation or '',
        **optionnels), ())


def specs_onduleur(specs, designation=''):
    """``(SpecOnduleur | None, manquantes)`` depuis un bloc ``onduleur``."""
    manquantes = _manquantes(specs, CHAMPS_ONDULEUR)
    if manquantes:
        return (None, manquantes)
    specs = dict(specs)
    optionnels = {}
    for cle in ('rendement_euro_pct', 'v_demarrage_v', 'isc_max_mppt_a'):
        valeur = _nombre(specs.get(cle))
        if valeur is not None:
            optionnels[cle] = valeur
    phases = _entier(specs.get('phases'))
    return (SpecOnduleur(
        n_mppt=int(specs['n_mppt']), mppt_v_min=float(specs['mppt_v_min']),
        mppt_v_max=float(specs['mppt_v_max']),
        v_max_abs=float(specs['v_max_abs']),
        i_max_mppt_a=float(specs['i_max_mppt_a']),
        ac_kw=float(specs['ac_kw']), phases=phases or 1,
        designation=designation or '', **optionnels), ())


def chaines_max_par_mppt(specs):
    """Le nombre de chaînes admis par entrée MPPT, ou ``None`` si non publié.

    CAL115 — la fiche onduleur publie ``chaines_max_par_mppt`` (et, à défaut,
    ``entrees_par_mppt``). Absent = NON PUBLIÉ : on ne suppose pas qu'une
    entrée accepte deux chaînes, et on ne suppose pas non plus qu'elle n'en
    accepte qu'une — on le DIT (cf. ``concevoir_par_pan``).
    """
    specs = specs if isinstance(specs, dict) else {}
    for cle in ('chaines_max_par_mppt', 'entrees_par_mppt'):
        valeur = _entier(specs.get(cle))
        if valeur:
            return valeur
    return None


# ─────────────────────────────────────────────────────────── la conception
def entree_electrique(layout, module, onduleur, temperatures, *,
                      dc_m=0.0, ac_m=0.0, phases=None, longueur_forcee=None,
                      zone_keraunique=False, inclure_prise_terre=False,
                      plafond_kwc_par_onduleur=None):
    """L'``EntreeElectrique`` du noyau, construite depuis le CALEPINAGE.

    Les températures viennent de CAL123 (``services.electrique``) : elles sont
    passées EXPLICITEMENT au noyau, jamais laissées au défaut — c'est tout
    l'objet de CAL123.
    """
    return EntreeElectrique(
        module=module, onduleur=onduleur,
        groupes=groupes_electriques(layout),
        dc_m=float(dc_m or 0.0), ac_m=float(ac_m or 0.0),
        phases=int(phases or getattr(onduleur, 'phases', 1) or 1),
        temp_froid_c=temperatures.froid_c, temp_chaud_c=temperatures.chaud_c,
        longueur_chaine_forcee=longueur_forcee,
        zone_keraunique=bool(zone_keraunique),
        inclure_prise_terre=bool(inclure_prise_terre),
        plafond_kwc_par_onduleur=plafond_kwc_par_onduleur,
    )


def _verdict_mppt(pans, onduleur, specs_onduleur_brut):
    """``(regle, partage, messages)`` — QUI a le droit de partager une entrée.

    Trois cas, et le verdict les nomme :

    * autant (ou moins) de pans que d'entrées MPPT → aucun partage, rien à
      arbitrer ;
    * plus de pans que d'entrées ET la fiche publie le polystring → le partage
      est AUTORISÉ, on le dit en citant la fiche ;
    * plus de pans que d'entrées SANS autorisation publiée → DÉPASSEMENT : le
      message nomme l'onduleur et le(s) pan(s) en trop.
    """
    n_mppt = max(1, int(getattr(onduleur, 'n_mppt', 1) or 1))
    nom = getattr(onduleur, 'designation', '') or "l'onduleur retenu"
    if len(pans) <= n_mppt:
        return ("un pan par entrée MPPT (%d pan(s) pour %d entrée(s)) ; %s"
                % (len(pans), n_mppt, REGLE_UNE_ORIENTATION_PAR_CHAINE),
                False, ())
    en_trop = tuple(pan.label for pan in pans[n_mppt:])
    maxi = chaines_max_par_mppt(specs_onduleur_brut)
    if maxi and maxi > 1:
        return (
            "partage d'entrée MPPT AUTORISÉ par la fiche de %s (%d chaîne(s) "
            "par entrée) : %d pan(s) pour %d entrée(s) — %s"
            % (nom, maxi, len(pans), n_mppt,
               REGLE_UNE_ORIENTATION_PAR_CHAINE),
            True, ())
    return (
        "partage d'entrée MPPT NON autorisé : la fiche de %s ne publie aucune "
        "capacité polystring (%s) — %s"
        % (nom,
           'clé « chaines_max_par_mppt » absente' if maxi is None
           else 'une seule chaîne par entrée',
           REGLE_UNE_ORIENTATION_PAR_CHAINE),
        False,
        ("%s n'a que %d entrée(s) MPPT pour %d pan(s) : le(s) pan(s) « %s » "
         "n'a/ont pas d'entrée dédiée — prévoir un onduleur à plus d'entrées, "
         "des optimiseurs, ou une fiche publiant la capacité polystring"
         % (nom, n_mppt, len(pans), ', '.join(en_trop)),))


def concevoir_par_pan(layout, *, module_specs, onduleur_specs, temperatures,
                      module_designation='', onduleur_designation='',
                      **options):
    """CAL124 — le chaînage COMPLET d'un document de conception.

    Args:
        layout: le document ``roof_layout`` (schéma v2).
        module_specs / onduleur_specs: les blocs de fiche technique rendus par
            ``apps.stock.selectors.specs_for_produit`` (dicts PLATS).
        temperatures: le ``TemperaturesSite`` de CAL123 — sa source voyage
            avec le résultat.
        options: passées à ``entree_electrique`` (longueurs, phases, plafond…).

    Returns:
        Une ``Conception``. Fiche incomplète ⇒ ``manquantes`` renseigné,
        ``resultat`` à ``None`` et AUCUN verdict (jamais un faux vert).
    """
    pans = pans_poses(layout)
    module, manque_module = specs_module(module_specs, module_designation)
    onduleur, manque_onduleur = specs_onduleur(onduleur_specs,
                                               onduleur_designation)
    manquantes = tuple(['module : %s' % m for m in manque_module]
                       + ['onduleur : %s' % m for m in manque_onduleur])
    if manquantes:
        return Conception(pans=pans, manquantes=manquantes,
                          temperatures=temperatures)
    if not pans:
        return Conception(
            pans=(), temperatures=temperatures,
            alertes=("aucun module posé : il n'y a rien à chaîner",))

    entree = entree_electrique(layout, module, onduleur, temperatures,
                               **options)
    resultat = concevoir_chaines(entree)
    regle, partage, messages = _verdict_mppt(pans, onduleur, onduleur_specs)
    return Conception(
        pans=pans, resultat=resultat, entree=entree,
        bloquants=tuple(resultat.bloquants),
        alertes=tuple(resultat.alertes) + messages,
        regle_mppt=regle, partage_mppt=partage, temperatures=temperatures)
