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
    'affectation', 'empreinte_entree', 'bloc_electrique', 'bloc_pose',
    # CAL234 — affectation IMPOSÉE (manuelle) et son verdict.
    'SOURCE_AUTO', 'SOURCE_MANUELLE', 'AffectationInvalide',
    'normaliser_affectation_imposee', 'verdict_affectation',
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


# ═══════════════════════════════════════════════════════════════════════════
# CAL125 — L'AFFECTATION NOMINATIVE : module → chaîne → MPPT → onduleur
# ═══════════════════════════════════════════════════════════════════════════
#
# Le layout décrit des panneaux POSÉS sans aucune identité électrique, et le
# noyau calepinage dit lui-même que « le stringing détaillé reste HORS moteur »
# (``core/calepinage/electrique.py``) : rien ne relie un panneau dessiné à sa
# chaîne. Sans cette table, l'écran qui teinte les modules par chaîne (CAL126)
# recalculerait SA partition — donc une AUTRE partition que celle qui a été
# dimensionnée.
#
# La forme est celle du contrat committé
# ``contract_samples/calepinage_resultat.json`` (CAL244, parti SEUL sur
# ``main`` avant cette tâche — PACT10) : ``{module, pan, chaine, onduleur,
# mppt}``, et un module NON affecté garde ses quatre clés à ``null`` (il est
# gris à l'écran et compté dans la légende, il ne DISPARAÎT pas).
#
# REPRODUCTIBILITÉ : à entrée identique, affectation identique. L'ordre est
# celui des pans du document puis celui des chaînes du noyau — aucun ensemble
# non ordonné, aucun identifiant d'objet, aucune horloge.

def affectation(conception, *, imposee=None):
    """La table module → chaîne → MPPT → onduleur, dans l'ordre du document.

    CAL234 — ``imposee`` est une affectation MANUELLE (déjà normalisée par
    ``normaliser_affectation_imposee``) : elle ÉCRASE l'automatique, ligne par
    ligne, et chaque ligne touchée porte ``source = « affectation manuelle »``
    (les autres restent ``« automatique »``). Un module imposé qui n'existe
    pas dans le document est IGNORÉ ici — c'est ``verdict_affectation`` qui le
    REFUSE en le nommant, et une table ne refuse pas, elle décrit.

    Un module au-delà des chaînes de son pan (la « réserve d'appoint » du
    noyau) est publié avec ``chaine``/``mppt``/``onduleur`` à ``null`` : il est
    posé, il n'est simplement câblé à rien.

    ``onduleur`` vaut ``1`` quand un seul onduleur est retenu. Dès qu'il y en a
    plusieurs, le noyau ne dit PAS lequel reçoit quelle chaîne (il dimensionne
    un MODÈLE d'onduleur, pas des exemplaires) : la clé vaut alors ``null``
    plutôt qu'un numéro inventé, et ``bloc_electrique`` publie l'avertissement
    correspondant.
    """
    chaines_par_pan = {}
    for chaine in conception.chaines:
        chaines_par_pan.setdefault(chaine.pan, []).append(chaine)

    evaluation = evaluer_onduleurs(conception)
    nombre = evaluation.nombre if evaluation is not None else 0
    numero_onduleur = 1 if nombre == 1 else None

    lignes = []
    for pan in conception.pans:
        rang_module = 0
        for chaine in chaines_par_pan.get(pan.label, ()):
            for _ in range(chaine.nb_modules):
                rang_module += 1
                lignes.append({
                    'module': '%s#%d' % (pan.label, rang_module),
                    'pan': pan.label,
                    'chaine': _numero_chaine(chaine),
                    'onduleur': numero_onduleur,
                    'mppt': chaine.mppt,
                    'source': SOURCE_AUTO,
                })
        while rang_module < pan.modules:
            rang_module += 1
            lignes.append({
                'module': '%s#%d' % (pan.label, rang_module),
                'pan': pan.label,
                'chaine': None, 'onduleur': None, 'mppt': None,
                'source': SOURCE_AUTO,
            })
    return tuple(_appliquer_imposee(lignes, imposee))


def _appliquer_imposee(lignes, imposee):
    """CAL234 — l'affectation manuelle ÉCRASE l'automatique, et se voit."""
    par_module = {ligne['module']: ligne for ligne in (imposee or ())}
    if not par_module:
        return lignes
    for ligne in lignes:
        impose = par_module.get(ligne['module'])
        if impose is None:
            continue
        ligne['chaine'] = impose['chaine']
        ligne['mppt'] = impose['mppt']
        ligne['onduleur'] = impose['onduleur']
        ligne['source'] = SOURCE_MANUELLE
    return lignes


def _numero_chaine(chaine):
    """« CH7 » → 7. Le repère du noyau reste la source, jamais un compteur."""
    repere = getattr(chaine, 'repere', '') or ''
    chiffres = ''.join(c for c in repere if c.isdigit())
    return int(chiffres) if chiffres else None


def evaluer_onduleurs(conception):
    """L'``EvaluationOnduleurs`` du noyau pour cette conception, ou ``None``."""
    from core.electrique.onduleurs import dimensionner_onduleurs

    entree = conception.entree
    if entree is None or conception.resultat is None:
        return None
    puissance_dc = (conception.resultat.puissance_kwc
                    if conception.chaines else entree.puissance_kwc)
    return dimensionner_onduleurs(entree, puissance_dc)


def empreinte_entree(layout, *, module_specs, onduleur_specs, temperatures,
                     options=None):
    """SHA-256 de TOUT ce qui décide de l'affectation — rien d'autre.

    Deux calculs de la même toiture avec les mêmes fiches et les mêmes
    températures portent la MÊME empreinte, donc la même affectation : c'est
    ce qui rend le résultat rejouable (et ce que le test de reproductibilité
    vérifie). L'empreinte ne contient ni horodatage, ni identifiant d'objet,
    ni prix.
    """
    import hashlib
    import json

    charge = {
        'pans': [[p.label, p.modules, p.azimut_deg, p.inclinaison_deg]
                 for p in pans_poses(layout)],
        'module': {cle: _nombre((module_specs or {}).get(cle))
                   for cle, _ in CHAMPS_MODULE},
        'onduleur': {cle: _nombre((onduleur_specs or {}).get(cle))
                     for cle, _ in CHAMPS_ONDULEUR},
        'temperatures': [getattr(temperatures, 'froid_c', None),
                         getattr(temperatures, 'chaud_c', None),
                         getattr(temperatures, 'source', None)],
        'options': {cle: valeur for cle, valeur
                    in sorted((options or {}).items())
                    if isinstance(valeur, (int, float, str, bool,
                                           type(None)))},
    }
    brut = json.dumps(charge, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'))
    return hashlib.sha256(brut.encode('utf-8')).hexdigest()


def bloc_pose(conception):
    """Le bloc ``pose`` du contrat : la pose est un FAIT, toujours chiffrée.

    Même sans simulation électrique, les modules et les kWc sont connus — ils
    restent donc des nombres, jamais ``null`` (discipline du null, CAL244).
    """
    module = getattr(conception.entree, 'module', None)
    puissance_module = module.pmax_wc if module is not None else None
    pans = [{
        'pan': pan.label,
        'modules': pan.modules,
        'kwc': (round(pan.modules * puissance_module / 1000.0, 3)
                if puissance_module else None),
        'azimut_deg': pan.azimut_deg,
        'inclinaison_deg': pan.inclinaison_deg,
    } for pan in conception.pans]
    total = sum(pan.modules for pan in conception.pans)
    return {
        'total_modules': total,
        'kwc': (round(total * puissance_module / 1000.0, 3)
                if puissance_module else None),
        'puissance_module_wc': puissance_module,
        'pans': pans,
    }


def _chainage(conception):
    """Le bloc ``chainage`` — ``null`` tant que rien n'a été chaîné."""
    if conception.resultat is None or not conception.chaines:
        return None
    longueurs = {r.longueur_chaine for r in conception.repartitions}
    return {
        'modules': sum(pan.modules for pan in conception.pans),
        # Longueurs différentes d'un pan à l'autre : aucun nombre unique
        # n'est vrai, donc ``null`` (le détail par pan vit dans les
        # répartitions du noyau).
        'modules_par_chaine': (longueurs.pop() if len(longueurs) == 1
                               else None),
        'chaines': conception.resultat.nb_chaines,
        'reste': conception.resultat.reste_total,
        'puissance_module_wc': conception.entree.module.pmax_wc,
    }


def bloc_electrique(conception, *, verdicts=(), imposee=None):
    """Le bloc ``electrique`` du contrat CAL244, affectation comprise.

    Rend ``(bloc, avertissements)``. Les quatre clés du bloc sont TOUJOURS
    présentes : ``chainage`` vaut ``null`` et les trois listes sont vides
    quand rien n'a été chaîné — ce qui se distingue sans ambiguïté d'une liste
    de zéros.
    """
    evaluation = evaluer_onduleurs(conception)
    onduleurs = []
    avertissements = []
    if evaluation is not None and evaluation.nombre:
        onduleur = conception.entree.onduleur
        ratio = evaluation.ratio_dc_ac
        onduleurs.append({
            'reference': onduleur.designation or '',
            'taille_kw': evaluation.ac_kw_unitaire,
            'nombre': evaluation.nombre,
            'puissance_dc_kwc': round(evaluation.puissance_dc_kwc, 3),
            'ratio_dc_ac': (round(ratio.valeur, 3)
                            if ratio is not None and ratio.valeur is not None
                            else None),
            'n_mppt': onduleur.n_mppt,
            'conforme': not evaluation.bloquants,
            'motif': (evaluation.bloquants[0] if evaluation.bloquants else ''),
        })
        if evaluation.nombre > 1:
            avertissements.append(
                "%d onduleurs retenus : l'affectation nomme la chaîne et "
                "l'entrée MPPT, jamais l'exemplaire d'onduleur (le noyau "
                "dimensionne un MODÈLE) — clé « onduleur » laissée vide"
                % evaluation.nombre)
    return ({
        'chainage': _chainage(conception),
        'onduleurs': onduleurs,
        'affectation': list(affectation(conception, imposee=imposee)),
        'verdicts': list(verdicts),
    }, tuple(avertissements))


# ── CAL234 (moitié backend) — L'AFFECTATION IMPOSÉE, ET SON VERDICT ────────
#
# CAL124 affecte AUTOMATIQUEMENT et CAL126 dessine le résultat, mais rien ne
# permettait à un installateur de CORRIGER l'affectation — or choisir une
# suite de modules pour en faire une chaîne est le geste de base des outils
# comparés. Cette moitié-ci pose les deux briques SERVEUR dont l'atelier a
# besoin :
#
# * ``affectation(conception, imposee=…)`` accepte une affectation IMPOSÉE
#   module par module : elle ÉCRASE l'automatique et chaque ligne touchée est
#   MARQUÉE ``source = « affectation manuelle »`` dans la table CAL125 (les
#   autres restent ``« automatique »``) ;
# * ``verdict_affectation`` REFUSE une proposition invalide EN NOMMANT la
#   contrainte, le pan et la chaîne — jamais un « non enregistré » générique.
#
# Le verdict se rend SANS RIEN PERSISTER : l'atelier envoie sa proposition à
# ``POST calepinages/<pk>/evaluer-electrique/`` (garde en LECTURE, rien n'est
# écrit) dans ``entree_electrique.affectation_manuelle`` ; le jour où
# l'utilisateur valide, le MÊME champ part sur ``entree-electrique`` et là,
# il est enregistré. Une seule forme de donnée pour les deux chemins.

#: Les deux origines possibles d'une ligne de la table d'affectation.
SOURCE_AUTO = 'automatique'
SOURCE_MANUELLE = 'affectation manuelle'

#: Les clés admises dans une ligne d'affectation imposée.
CLES_IMPOSEE = ('module', 'chaine', 'mppt', 'onduleur')


class AffectationInvalide(ValueError):
    """Proposition d'affectation refusée — message français, champ nommé."""

    def __init__(self, message, *, champ='affectation_manuelle'):
        super().__init__(message)
        self.champ = champ


def normaliser_affectation_imposee(brut):
    """``[{module, chaine, mppt, onduleur}]`` VALIDÉ, ou ``()``.

    Refuse EN FRANÇAIS, en nommant le champ : une ligne qui n'est pas un
    objet, un module vide, une clé inconnue, un numéro de chaîne qui n'est pas
    un entier positif, ou deux lignes pour le même module (deux chaînes pour
    un seul panneau, c'est un court-circuit sur le papier).
    """
    if brut is None:
        return ()
    if not isinstance(brut, (list, tuple)):
        raise AffectationInvalide(
            "L'affectation manuelle se donne en liste de lignes "
            f"(reçu : {type(brut).__name__}).")
    lignes, vus = [], set()
    for rang, ligne in enumerate(brut, start=1):
        if not isinstance(ligne, dict):
            raise AffectationInvalide(
                f"La ligne n°{rang} de l'affectation manuelle doit être un "
                f"objet (reçu : {type(ligne).__name__}).")
        inconnues = sorted(set(ligne) - set(CLES_IMPOSEE))
        if inconnues:
            raise AffectationInvalide(
                f"Clé inconnue dans l'affectation manuelle : "
                f"« {', '.join(inconnues)} ». Clés admises : "
                f"{', '.join(CLES_IMPOSEE)}.")
        module = str(ligne.get('module') or '').strip()
        if not module:
            raise AffectationInvalide(
                f"La ligne n°{rang} de l'affectation manuelle ne nomme aucun "
                "module.")
        if module in vus:
            raise AffectationInvalide(
                f"Le module « {module} » est affecté deux fois : un panneau "
                "n'appartient qu'à une seule chaîne.")
        vus.add(module)
        lignes.append({
            'module': module,
            'chaine': _numero_impose(ligne.get('chaine'), module, 'chaîne'),
            'mppt': _numero_impose(ligne.get('mppt'), module, 'entrée MPPT'),
            'onduleur': _numero_impose(ligne.get('onduleur'), module,
                                       'onduleur'),
        })
    return tuple(lignes)


def _numero_impose(valeur, module, quoi):
    """Un entier strictement positif, ou ``None`` (module DÉCÂBLÉ à la main)."""
    if valeur is None:
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        raise AffectationInvalide(
            f"Le numéro de {quoi} du module « {module} » doit être un entier "
            f"(reçu : {type(valeur).__name__}).")
    entier = int(valeur)
    if entier != valeur or entier <= 0:
        raise AffectationInvalide(
            f"Le numéro de {quoi} du module « {module} » doit être un entier "
            f"strictement positif (reçu : {valeur}).")
    return entier


def verdict_affectation(conception, imposee, *, specs_onduleur=None):
    """Les REFUS d'une affectation proposée, chacun NOMMANT sa contrainte.

    Ne persiste RIEN et ne modifie RIEN : c'est un verdict. Les contrôles
    portent sur ce que le SERVEUR peut vérifier sans supposer quoi que ce
    soit :

    * un module inconnu du document (personne ne câble un panneau qui n'est
      pas posé) ;
    * une chaîne qui saute d'un pan à l'autre (le document dessine deux
      surfaces, une chaîne ne les traverse pas) ;
    * une chaîne plus longue ou plus courte que la règle de chaîne retenue
      par le dimensionnement (V_max à froid / MPPT) ;
    * plus de chaînes sur une entrée MPPT que la fiche onduleur n'en publie.

    Une donnée NON PUBLIÉE (règle de chaîne inconnue, ``chaines_max_par_mppt``
    absent) ne produit AUCUN refus : le silence, jamais un faux rouge.
    """
    imposee = tuple(imposee or ())
    if not imposee:
        return ()

    auto = affectation(conception)
    pan_par_module = {ligne['module']: ligne['pan'] for ligne in auto}
    refus = []

    modules_par_chaine, pans_par_chaine, chaines_par_mppt = {}, {}, {}
    for ligne in imposee:
        module = ligne['module']
        pan = pan_par_module.get(module)
        if pan is None:
            refus.append(
                "Module inconnu du document : « %s » n'est pas posé sur cette "
                "conception." % module)
            continue
        numero = ligne['chaine']
        if numero is None:
            continue
        modules_par_chaine[numero] = modules_par_chaine.get(numero, 0) + 1
        pans_par_chaine.setdefault(numero, set()).add(pan)
        if ligne['mppt'] is not None:
            chaines_par_mppt.setdefault(
                (ligne['onduleur'], ligne['mppt']), set()).add(numero)

    for numero, pans in sorted(pans_par_chaine.items()):
        if len(pans) > 1:
            refus.append(
                "Chaîne %d : elle traverse les pans %s — une chaîne reste sur "
                "UN pan." % (numero, ', '.join(sorted(pans))))

    bornes = _bornes_de_chaine(conception)
    if bornes is not None:
        mini, maxi = bornes
        for numero, nombre in sorted(modules_par_chaine.items()):
            pan = ', '.join(sorted(pans_par_chaine.get(numero, ())))
            if maxi is not None and nombre > maxi:
                refus.append(
                    "Chaîne %d (pan %s) : %d modules, maximum %d — au-delà, "
                    "la tension à froid dépasse la limite de l'onduleur."
                    % (numero, pan, nombre, maxi))
            elif mini is not None and nombre < mini:
                refus.append(
                    "Chaîne %d (pan %s) : %d modules, minimum %d — en deçà, "
                    "la chaîne ne démarre pas sur la plage MPPT."
                    % (numero, pan, nombre, mini))

    maximum = chaines_max_par_mppt(specs_onduleur)
    if maximum:
        for (onduleur, mppt), chaines in sorted(
                chaines_par_mppt.items(),
                key=lambda couple: (couple[0][0] or 0, couple[0][1] or 0)):
            if len(chaines) > maximum:
                refus.append(
                    "Entrée MPPT %s : %d chaînes affectées, maximum %d publié "
                    "par la fiche onduleur."
                    % (_libelle_mppt(onduleur, mppt), len(chaines), maximum))
    return tuple(refus)


def _libelle_mppt(onduleur, mppt):
    return ('%d (onduleur %d)' % (mppt, onduleur) if onduleur
            else str(mppt))


def _bornes_de_chaine(conception):
    """``(min, max)`` de modules par chaîne, ou ``None`` si non publié.

    Les bornes sont celles que le DIMENSIONNEMENT a retenues : la longueur des
    chaînes réellement conçues. Aucune borne n'est inventée — sans chaîne
    conçue, il n'y a rien à comparer et le contrôle s'abstient.
    """
    longueurs = [chaine.nb_modules for chaine in conception.chaines
                 if getattr(chaine, 'nb_modules', None)]
    if not longueurs:
        return None
    return (min(longueurs), max(longueurs))
