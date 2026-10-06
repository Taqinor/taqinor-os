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
    COEFFICIENTS_TEMPERATURE, EntreeElectrique, GroupePan, SpecModule,
    SpecOnduleur, fr,
)
from .valeurs import nombre as _nombre

__all__ = [
    'PanPose', 'Conception', 'REGLE_UNE_ORIENTATION_PAR_CHAINE',
    'pans_poses', 'groupes_electriques', 'specs_module', 'specs_onduleur',
    'entree_electrique', 'concevoir_par_pan',
    'affectation', 'empreinte_entree', 'bloc_electrique', 'bloc_pose',
    # CAL234 — affectation IMPOSÉE (manuelle) et son verdict.
    'SOURCE_AUTO', 'SOURCE_MANUELLE', 'AffectationInvalide',
    'normaliser_affectation_imposee', 'verdict_affectation',
    # CALX53 — coefficients de température non sourcés, NOMMÉS jusqu'au verdict.
    'LIBELLES_COEFFICIENTS',
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

#: CALX53 — le LIBELLÉ français de chaque coefficient de température, pour
#: que l'avertissement dise de quoi il parle en plus de nommer la clé de
#: fiche que l'utilisateur doit renseigner.
LIBELLES_COEFFICIENTS = {
    'temp_coeff_voc_pct_c': 'coefficient de la tension à vide (β Voc)',
    'temp_coeff_pmax_pct_c': 'coefficient de la puissance crête (γ Pmax)',
}

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


#: ACAL162 — le motif publié quand le champ est 100 % micro-onduleurs : il
#: n'y a AUCUN onduleur de chaîne, donc aucun verdict de chaîne à prononcer.
MOTIF_MICRO_SEUL = "aucun onduleur de chaîne : régime micro-onduleurs"


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
    #: CALX53 — les coefficients de température qui ont pris le DÉFAUT du
    #: noyau (noms de champ de la fiche). Vides quand la fiche les publie.
    coefficients_non_sources: Tuple[str, ...] = ()
    temperatures: object = None
    entree: object = None
    #: ACAL162 — vrai quand le champ est câblé en micro-onduleurs SEULS
    #: (aucun onduleur de chaîne désigné) : ``resultat`` vaut ``None`` (rien
    #: n'est chaîné) mais ``entree`` existe (module, pans, phases) pour les
    #: branches AC — l'UNIQUE indicateur de ce régime.
    micro_seul: bool = False
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
def _entier(valeur):
    nombre = _nombre(valeur)
    if nombre is None or nombre < 0:
        return None
    return int(nombre)


#: ACAL61 — la provenance de l'orientation d'un pan de toit, lue sur
#: ``ventes.orientation_du_pan`` (``pose`` = géométrie des modules posés,
#: ``toit`` = champs saisis du pan) et republiée sous le vocabulaire
#: historique de ``PanPose.source_orientation``.
SOURCES_ORIENTATION = {'pose': 'geometrie', 'toit': 'saisie'}


def _source_orientation(pan, zones_par_cle):
    """``'geometrie'`` | ``'saisie'`` | ``None`` — d'où vient l'orientation."""
    if pan.get('azimut_deg') is None and pan.get('inclinaison_deg') is None:
        return None
    if pan.get('kind') != 'toit':
        # Une surface de pose (champ au sol, ombrière) porte l'inclinaison et
        # l'azimut de ses rangées : c'est une géométrie de pose.
        return 'geometrie'
    from apps.ventes.services import orientation_du_pan

    zone = zones_par_cle.get(pan.get('cle'))
    if zone is None:
        return None
    return SOURCES_ORIENTATION.get(
        orientation_du_pan(zone).get('source_orientation'))


def pans_poses(layout):
    """Les pans du document qui portent au moins un module POSÉ.

    ACAL61 — adaptateur MINCE de ``apps.ventes.services.pans_du_document``
    (LA primitive, D-ACAL-5) : pans de toit ET surfaces de pose (champ au
    sol, ombrière — un pan à part entière, ``engine.modules``), même
    préséance de compte (``geometry.panels`` > ``geometry.count`` >
    ``result.count`` ; ``neededPanels`` n'est JAMAIS un compte posé : un pan
    non pavé vaut 0 et n'est pas chaîné), même orientation
    (``orientation_du_pan``, azimut de face d'une surface = rangée + 90).

    Un pan par entrée du document : deux pans ne sont JAMAIS fusionnés,
    même orientés pareil — le chaînage respecte le découpage dessiné.
    """
    from apps.ventes.services import pans_du_document

    if not isinstance(layout, dict):
        return ()
    zones = (layout.get('zones') or layout.get('areas')
             or layout.get('pans') or [])
    zones_par_cle = {}
    for index, zone in enumerate(zones if isinstance(zones, list) else []):
        if isinstance(zone, dict):
            zones_par_cle[str(zone.get('id') or 'zone-%d' % (index + 1))] = (
                zone)
    pans = []
    for pan in pans_du_document(layout):
        modules = int(pan.get('modules') or 0)
        if modules <= 0:
            continue
        pans.append(PanPose(
            label=str(pan.get('libelle')), modules=modules,
            azimut_deg=_nombre(pan.get('azimut_deg')),
            inclinaison_deg=_nombre(pan.get('inclinaison_deg')),
            source_orientation=_source_orientation(pan, zones_par_cle)))
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

    CALX53 — et l'ORIGINE de chacun voyage avec la fiche
    (``SpecModule.coefficients_sources``) : un coefficient tombé sur le défaut
    n'est SOURCÉ par rien, et il sera NOMMÉ jusque dans le verdict au lieu de
    passer pour une donnée constructeur. Ils ne deviennent pas obligatoires
    pour autant : les rendre bloquants ferait disparaître tout verdict de
    chaînage sur une fiche par ailleurs complète.
    """
    manquantes = _manquantes(specs, CHAMPS_MODULE)
    if manquantes:
        return (None, manquantes)
    specs = dict(specs)
    optionnels = {}
    sources = []
    for cle in COEFFICIENTS_TEMPERATURE:
        valeur = _nombre(specs.get(cle))
        if valeur is not None:
            optionnels[cle] = valeur
            sources.append(cle)
    return (SpecModule(
        vmp_v=float(specs['vmp_v']), voc_v=float(specs['voc_v']),
        isc_a=float(specs['isc_a']), imp_a=float(specs['imp_a']),
        pmax_wc=float(specs['pmax_wc']), designation=designation or '',
        coefficients_sources=tuple(sources), **optionnels), ())


def specs_onduleur(specs, designation=''):
    """``(SpecOnduleur | None, manquantes)`` depuis un bloc ``onduleur``.

    CALX213 (crochet posé par la phase 2 du lot 4) — ``s_max_kva`` et
    ``dc_max_kwc`` sont publiés par ``apps.stock.selectors.specs_for_produit``
    (champs de fiche CALX60) et recopiés ICI : sans cette recopie, les deux
    bornes n'atteignaient JAMAIS ``SpecOnduleur``, donc ni le verdict
    d'onduleur (``core/electrique/onduleurs.py``) ni la puissance apparente du
    raccordement (``services/raccordement.py``) ne pouvaient les lire. Elles
    restent OPTIONNELLES : une fiche muette ne déclenche aucun contrôle.
    """
    manquantes = _manquantes(specs, CHAMPS_ONDULEUR)
    if manquantes:
        return (None, manquantes)
    specs = dict(specs)
    optionnels = {}
    for cle in ('rendement_euro_pct', 'v_demarrage_v', 'isc_max_mppt_a',
                's_max_kva', 'dc_max_kwc'):
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


# ───────────────────────────────────────────────────────── la batterie
def batterie_du_calepinage(calepinage, donnees, materiel=None, company=None):
    """ACAL166/ACAL168 — LA résolution de la batterie d'un calepinage.

    UNE fonction pour deux lecteurs : la simulation (``simulation._declaration_
    batterie``) et le dessin du schéma (``entree_electrique``) lisent la MÊME
    déclaration, jamais deux copies qui divergeraient.

    La déclaration est celle de l'ENTRÉE électrique enregistrée
    (``donnees['batterie']``). Le PRODUIT et les PACKS prennent, à défaut de
    saisie, la ligne batterie du devis lié (``equipements_du_calepinage``) ;
    leur provenance voyage (``explicite`` | ``devis`` | ``defaut``). Les
    grandeurs viennent de la FICHE du produit : rien n'est supposé.

    Returns:
        ``None`` quand aucun produit batterie n'est résolu (ni saisi, ni sur le
        devis) ; sinon ``{produit, produit_onduleur, packs, provenance, saisie,
        specs, designation, declaree}`` — ``declaree`` : vrai quand l'entrée
        porte une déclaration de batterie (et pas seulement une ligne de devis).
    """
    from apps.stock.selectors import get_produit_scoped

    from .batterie import specs_batterie
    from .equipements import equipements_du_calepinage

    company = company or getattr(calepinage, 'company', None)
    if company is None:
        return None
    saisie = (donnees or {}).get('batterie') if isinstance(
        donnees, dict) else None
    saisie = dict(saisie) if isinstance(saisie, dict) else {}

    equipements = equipements_du_calepinage(calepinage)
    bloc = equipements.get('batterie') if isinstance(equipements,
                                                     dict) else None
    produit_devis = None
    packs_devis = None
    if isinstance(bloc, dict) and bloc.get('produit'):
        produit_devis = bloc['produit']
        quantite = _nombre(bloc.get('quantite'))
        if quantite is not None and quantite >= 1:
            packs_devis = int(round(quantite))
    identifiant = saisie.get('produit')
    if identifiant in (None, ''):
        identifiant = produit_devis
    if identifiant in (None, ''):
        return None
    produit = get_produit_scoped(company, identifiant)
    if produit is None:
        return None
    produit_onduleur = None
    onduleur_id = ((materiel or {}).get('produits') or {}).get('onduleur')
    if onduleur_id not in (None, ''):
        produit_onduleur = get_produit_scoped(company, onduleur_id)

    provenance = {
        'produit': ('explicite' if saisie.get('produit') not in (None, '')
                    else 'devis'),
        'packs': ('explicite' if saisie.get('packs') not in (None, '')
                  else ('devis' if packs_devis else 'defaut')),
    }
    packs = int(_nombre(saisie.get('packs')) or packs_devis or 1) or 1
    return {
        'produit': produit, 'produit_onduleur': produit_onduleur,
        'packs': packs, 'provenance': provenance, 'saisie': saisie,
        'specs': specs_batterie(produit, produit_onduleur=produit_onduleur,
                                nb_packs=packs),
        'designation': ('%s %s' % (
            (getattr(produit, 'marque', '') or '').strip(),
            (getattr(produit, 'nom', '') or '').strip())).strip(),
        'declaree': bool(saisie),
    }


# ─────────────────────────────────────────────────────────── la conception
def entree_electrique(layout, module, onduleur, temperatures, *,
                      dc_m=0.0, ac_m=0.0, phases=None, longueur_forcee=None,
                      zone_keraunique=False, inclure_prise_terre=False,
                      plafond_kwc_par_onduleur=None, regime=None,
                      batterie=False, batterie_designation='',
                      batterie_kwh=None, batterie_v_nominal=None):
    """L'``EntreeElectrique`` du noyau, construite depuis le CALEPINAGE.

    Les températures viennent de CAL123 (``services.electrique``) : elles sont
    passées EXPLICITEMENT au noyau, jamais laissées au défaut — c'est tout
    l'objet de CAL123.

    CALX214 — leur PROVENANCE fait le voyage avec elles (``source`` et
    ``mention`` du ``TemperaturesSite``) : sans elle, le noyau pouvait écrire
    « à −5 °C » dans une phrase sans que rien ne dise d'où venait ce −5.
    """
    return EntreeElectrique(
        module=module, onduleur=onduleur,
        groupes=groupes_electriques(layout),
        dc_m=float(dc_m or 0.0), ac_m=float(ac_m or 0.0),
        phases=int(phases or getattr(onduleur, 'phases', 1) or 1),
        temp_froid_c=temperatures.froid_c, temp_chaud_c=temperatures.chaud_c,
        temp_source=getattr(temperatures, 'source', None),
        temp_mention=getattr(temperatures, 'mention', '') or '',
        longueur_chaine_forcee=longueur_forcee,
        zone_keraunique=bool(zone_keraunique),
        inclure_prise_terre=bool(inclure_prise_terre),
        plafond_kwc_par_onduleur=plafond_kwc_par_onduleur,
        # ACAL152 — le régime SAISI, ou ``None`` (« non précisé ») : jamais
        # le « TT » par défaut du noyau.
        regime=regime or None,
        # ACAL168 — le parc de stockage DÉCLARÉ : le schéma dessine le bloc
        # « Batterie » et nomme son matériel. Le booléen est la seule chose
        # qui pilote les règles ; l'identité, elle, est descriptive.
        batterie=bool(batterie),
        batterie_designation=str(batterie_designation or ''),
        batterie_kwh=float(batterie_kwh or 0.0),
        batterie_v_nominal=float(batterie_v_nominal or 0.0),
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


def _avertissement_coefficients_non_sources(module):
    """CALX53 — le message qui NOMME les coefficients tombés sur le défaut.

    ``''`` quand la fiche publie les deux. Rien n'est remplacé ni omis : les
    bornes de tension de chaîne restent calculées avec le défaut documenté du
    noyau — mais elles sont MARQUÉES, parce qu'un défaut qui se tait finit par
    passer pour une donnée constructeur. C'était le seul endroit du module où
    un littéral se glissait dans un calcul sans que personne ne le sache.
    """
    non_sources = tuple(getattr(module, 'coefficients_non_sources', ()) or ())
    if not non_sources:
        return ''
    nom_module = getattr(module, 'designation', '') or 'le module retenu'
    details = ', '.join(
        '« %s » — %s : %s %%/°C'
        % (nom, LIBELLES_COEFFICIENTS.get(nom, nom),
           fr(getattr(module, nom, 0.0), 3))
        for nom in non_sources)
    return (
        "Coefficients de température NON SOURCÉS sur la fiche de %s (%s). Ces "
        "valeurs sont les défauts du noyau, pas des données constructeur : "
        "les bornes de tension de chaîne restent calculées, mais elles sont "
        "marquées tant que la fiche produit ne publie pas ces coefficients."
        % (nom_module, details))


def concevoir_par_pan(layout, *, module_specs, onduleur_specs, temperatures,
                      module_designation='', onduleur_designation='',
                      optimiseur_specs=None, **options):
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
    # ACAL162 — AUCUN onduleur de chaîne désigné (fiche vide, pas une fiche
    # incomplète) mais un MICRO-onduleur en emplacement optimiseur : le champ
    # est câblé en branches AC. Aucun onduleur fictif n'est construit.
    from .micro_onduleurs import est_micro_onduleur

    if (not manque_module and not onduleur_specs
            and est_micro_onduleur(optimiseur_specs)):
        if not pans:
            return Conception(
                pans=(), temperatures=temperatures,
                alertes=("aucun module posé : il n'y a rien à chaîner",))
        return Conception(
            pans=pans, resultat=None, micro_seul=True,
            entree=entree_electrique(layout, module, None, temperatures,
                                     **options),
            alertes=(MOTIF_MICRO_SEUL,), temperatures=temperatures,
            coefficients_non_sources=tuple(module.coefficients_non_sources))
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
    # CALX53 — l'origine des coefficients de température voyage AVEC le
    # verdict : une alerte de plus, jamais un bloquant (la conception tient,
    # c'est sa SOURCE qui manque).
    coeffs = _avertissement_coefficients_non_sources(module)
    return Conception(
        pans=pans, resultat=resultat, entree=entree,
        bloquants=tuple(resultat.bloquants),
        alertes=(tuple(resultat.alertes) + messages
                 + ((coeffs,) if coeffs else ())),
        regle_mppt=regle, partage_mppt=partage, temperatures=temperatures,
        coefficients_non_sources=tuple(module.coefficients_non_sources))


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

#: ACAL285 — la teinte des chaînes et des entrées MPPT : SOURCE UNIQUE
#: (déplacée de ``documents/plan_cablage.py``, qui l'importe). Servie ligne
#: par ligne dans ``electrique.affectation[]`` : l'écran, la 3D et le plan de
#: câblage colorent tous avec CES valeurs, jamais une copie locale.
PALETTE_CHAINES = (
    'rgb(36, 130, 214)',   # bleu
    'rgb(232, 125, 33)',   # orange
    'rgb(46, 163, 89)',    # vert
    'rgb(184, 64, 158)',   # magenta
    'rgb(0, 153, 158)',    # sarcelle
    'rgb(212, 61, 71)',    # rouge
    'rgb(115, 102, 199)',  # violet
    'rgb(153, 133, 26)',   # ocre
)
#: Le gris d'un module NON affecté — jamais ``null``, jamais une teinte de
#: chaîne voisine.
COULEUR_NON_AFFECTE = 'rgb(140, 143, 148)'


def _colorer(lignes):
    """ACAL285 — ``couleur_chaine`` et ``couleur_mppt`` sur chaque ligne.

    Ordre de PREMIÈRE APPARITION du groupe dans la table (celui de la légende
    du plan de câblage) ; appliqué APRÈS l'affectation manuelle. Déterministe :
    aucun ensemble non ordonné.
    """
    par_chaine, par_mppt = {}, {}
    for ligne in lignes:
        chaine = ligne.get('chaine')
        if chaine is None:
            ligne['couleur_chaine'] = COULEUR_NON_AFFECTE
        else:
            if chaine not in par_chaine:
                par_chaine[chaine] = PALETTE_CHAINES[
                    len(par_chaine) % len(PALETTE_CHAINES)]
            ligne['couleur_chaine'] = par_chaine[chaine]
        if chaine is None or ligne.get('mppt') is None:
            ligne['couleur_mppt'] = COULEUR_NON_AFFECTE
        else:
            cle = (ligne.get('onduleur'), ligne.get('mppt'))
            if cle not in par_mppt:
                par_mppt[cle] = PALETTE_CHAINES[
                    len(par_mppt) % len(PALETTE_CHAINES)]
            ligne['couleur_mppt'] = par_mppt[cle]
    return lignes


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
    # ACAL285 — la teinte est attribuée APRÈS l'affectation manuelle.
    return tuple(_colorer(_appliquer_imposee(lignes, imposee)))


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


def evaluer_onduleurs(conception, *, reglages=None):
    """L'``EvaluationOnduleurs`` du noyau pour cette conception, ou ``None``.

    CALX213 — ``reglages`` est la section ``electrique_societe`` des réglages
    société (``services/parametres_cles.py``), ``{clé: {valeur, source}}``.
    Elle porte les TROIS paliers du ratio DC/AC, dont le seuil BAS qui n'a
    aucune constante de repli. Absente, les bornes du noyau s'appliquent à
    l'identique : le comportement d'aujourd'hui est strictement conservé.
    """
    from core.electrique.onduleurs import dimensionner_onduleurs

    entree = conception.entree
    if entree is None or conception.resultat is None:
        return None
    puissance_dc = (conception.resultat.puissance_kwc
                    if conception.chaines else entree.puissance_kwc)
    return dimensionner_onduleurs(entree, puissance_dc, reglages)


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
    # CALX53 — le même avertissement remonte dans le résultat publié
    # (``resultat['avertissements']``) : l'atelier le lit à côté des bornes
    # de chaîne, sans avoir à relancer une évaluation pour l'apprendre.
    coeffs = _avertissement_coefficients_non_sources(
        getattr(conception.entree, 'module', None))
    if coeffs:
        avertissements.append(coeffs)
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
