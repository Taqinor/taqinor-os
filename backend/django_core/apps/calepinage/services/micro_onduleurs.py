"""CALX209 — LE RÉGIME MICRO-ONDULEUR : DES BRANCHES AC, PLUS DE CHAÎNES DC.

CE QUI MANQUAIT
----------------
``services/electrique.py::regle_de_chaine`` ne connaît que deux régimes,
``voc_module`` et ``sortie_regulee_optimiseur`` — tous deux raisonnent sur
une chaîne DC qui monte vers un onduleur. Un champ à MICRO-ONDULEURS n'a ni
chaîne DC ni entrée MPPT : il a N unités qui rendent directement de
l'alternatif, regroupées sur des BRANCHES. ``core/electrique/cables.py`` ne
produisait d'ailleurs que ``W1`` (DC de chaîne) et ``W2`` (liaison AC unique)
— aucune branche n'existait nulle part.

Parité OpenSolar : le nombre de micro-onduleurs se déduit du nombre de
modules, les modules se regroupent par orientation sur des entrées séparées,
et **les données MPPT ne sont alors plus affichées**
(https://support.opensolar.com/hc/en-us/articles/12382487281935-Inverter-sizing-and-stringing-recommendations).
C'est pour cela que ce module publie ``ecran_mppt: False`` : l'écran MPPT ne
décrit rien dans ce régime, et l'afficher vide serait pire que l'omettre.

CE QUI BORNE UNE BRANCHE — ET CE QUI NE LA BORNE PAS (D-CALX 7)
-----------------------------------------------------------------
Trois cas, déclarés dans cet ordre, et AUCUN ne pose de chiffre :

1. la fiche publie ``opt_ac_unites_max_par_branche`` — c'est LE plafond du
   constructeur, il s'applique tel quel ;
2. la fiche ne publie que ``opt_ac_i_max_a`` (courant AC maximal d'UNE
   unité) : la branche est alors bornée par son COURANT CUMULÉ, sous le plus
   grand calibre normalisé du barème de disjoncteurs du dépôt
   (``core.electrique.protections.CALIBRES_DISJONCTEUR_A``, NF C 15-100 /
   IEC 60947-2). Ce n'est PAS une recommandation constructeur, et le
   ``motif_de_coupure`` de chaque branche le dit en toutes lettres ;
3. la fiche est muette sur les deux : la branche n'est PAS bornée. Une seule
   branche porte toutes les unités, son courant d'emploi vaut ``null``, et
   le service DIT « borne non publiée sur la fiche — nombre par branche non
   vérifiable » au lieu d'inventer un plafond.

CE QUE LE MODULE NE CALCULE PAS LUI-MÊME
------------------------------------------
Le calibre d'une branche sort de ``core.electrique.protections``
(``calibre_disjoncteur``, NF C 15-100 §433.1) et sa section de
``core.electrique.cables`` (``dimensionner_cables(branches_ac=…)``, CALX210) :
aucun barème neuf n'est écrit ici. Une branche dont la LONGUEUR n'est pas
relevée sur le plan ni saisie n'est pas dimensionnée — elle sort en
omission, nommant ``longueur_m``.
"""
from __future__ import annotations

__all__ = [
    'REGIME_BRANCHE_AC', 'CHAMP_UNITES_MAX', 'CHAMP_I_MAX',
    'ORIGINE_BORNE_FICHE', 'ORIGINE_BORNE_CALIBRE', 'MOTIF_SANS_BORNE',
    'MOTIF_ECRAN_MPPT', 'REFERENCE_OPENSOLAR', 'est_micro_onduleur',
    'branches_du_champ', 'equipement_ac',
]

#: Le NOM du régime, publié tel quel à côté des deux régimes de chaîne
#: existants (``voc_module``, ``sortie_regulee_optimiseur``).
REGIME_BRANCHE_AC = 'branche_ac_par_module'

#: Les champs de FICHE que ce module lit, nommés comme l'écran de fiche les
#: affiche — c'est ce nom-là qu'une omission doit prononcer.
CHAMP_UNITES_MAX = 'FicheTechnique.opt_ac_unites_max_par_branche'
CHAMP_I_MAX = 'FicheTechnique.opt_ac_i_max_a'

#: Les clés de sortie du sélecteur ``apps.stock.selectors.specs_for_produit``
#: pour une fiche de type « optimiseur » (les ``ac_*`` ne se remplissent que
#: sur un MICRO-ONDULEUR — sortie alternative — cf. ``stock/models.py``).
_CLES_AC = ('ac_kw', 'ac_tension_v', 'ac_i_max_a',
            'ac_unites_max_par_branche')

#: D'où vient la borne du nombre d'unités par branche.
ORIGINE_BORNE_FICHE = 'fiche'
ORIGINE_BORNE_CALIBRE = 'calibre normalisé'

MOTIF_SANS_BORNE = (
    "borne non publiée sur la fiche — nombre par branche non vérifiable : "
    "ni le plafond d'unités « %s » ni le courant AC maximal « %s » ne sont "
    "renseignés. Une seule branche est publiée, et aucun plafond n'est "
    "supposé à leur place." % (CHAMP_UNITES_MAX, CHAMP_I_MAX))

MOTIF_ECRAN_MPPT = (
    "Régime micro-onduleur : il n'y a ni chaîne DC ni entrée MPPT à "
    "afficher. L'écran MPPT n'est pas rendu — OpenSolar ne l'affiche pas non "
    "plus dès que le champ est équipé de micro-onduleurs.")

REFERENCE_OPENSOLAR = (
    "OpenSolar — Inverter sizing and stringing recommendations : le nombre "
    "de micro-onduleurs se déduit du nombre de modules et « MPPT data will "
    "not be displayed » (https://support.opensolar.com/hc/en-us/articles/"
    "12382487281935-Inverter-sizing-and-stringing-recommendations)")

MOTIF_COUPURE_FICHE = (
    "plafond d'unités publié par la fiche (« %s ») : %%d unités par branche"
    % CHAMP_UNITES_MAX)

MOTIF_COUPURE_CALIBRE = (
    "aucun plafond d'unités n'est publié sur la fiche : la branche est "
    "bornée par son COURANT CUMULÉ (%%s A par unité, « %s ») sous le plus "
    "grand calibre normalisé du barème de disjoncteurs (%%s A, NF C 15-100 / "
    "IEC 60947-2) — une borne NORMATIVE, pas une recommandation "
    "constructeur ; %%d unités par branche" % CHAMP_I_MAX)


def est_micro_onduleur(specs):
    """Cette fiche « optimiseur » décrit-elle un MICRO-onduleur ?

    Le discriminant n'est pas deviné : ``stock.models`` déclare que les
    champs ``opt_ac_*`` ne se remplissent QUE sur un micro-onduleur (sortie
    alternative), les ``opt_v_out_*``/``opt_i_out_*`` que sur un optimiseur
    (sortie continue). Une fiche qui publie au moins une grandeur de sortie
    ALTERNATIVE décrit donc un micro-onduleur.
    """
    if not isinstance(specs, dict):
        return False
    return any(specs.get(cle) is not None for cle in _CLES_AC)


def branches_du_champ(conception, specs, *, designation=''):
    """CALX209 — les branches AC d'un champ à micro-onduleurs.

    Args:
        conception: la ``Conception`` de CAL124 (ses pans portent les
            modules RÉELLEMENT posés — une unité par module).
        specs: le bloc de fiche du micro-onduleur
            (``apps.stock.selectors.specs_for_produit``).
        designation: la désignation commerciale, pour que les motifs NOMMENT
            le produit.

    Returns:
        ``{regime, applique, designation, unites, unites_max_par_branche,
        borne, branches, ecran_mppt, motif_mppt, motifs, reference}``.
        ``branches`` porte, pour chacune, ``{repere, unites, pans,
        i_branche_a, calibre_a, motif_de_coupure}`` — la forme que CALX210
        consomme.
    """
    unites_par_pan = [(pan.label, int(pan.modules or 0))
                      for pan in conception.pans
                      if int(pan.modules or 0) > 0]
    total = sum(nombre for _label, nombre in unites_par_pan)

    if not est_micro_onduleur(specs):
        return _rendu(applique=False, designation=designation, unites=total,
                      borne=None, branches=[], motifs=[])

    i_unitaire = _nombre((specs or {}).get('ac_i_max_a'))
    borne, motifs = _borne_par_branche(specs, i_unitaire)
    unites_max = borne['unites'] if borne is not None else total

    branches = []
    restant = list(unites_par_pan)
    courantes = []
    while restant:
        label, nombre = restant.pop(0)
        place = unites_max - sum(n for _l, n in courantes)
        if nombre <= place:
            courantes.append((label, nombre))
            if sum(n for _l, n in courantes) == unites_max:
                branches.append(_branche(len(branches) + 1, courantes,
                                         i_unitaire, borne))
                courantes = []
            continue
        if place > 0:
            courantes.append((label, place))
            restant.insert(0, (label, nombre - place))
        branches.append(_branche(len(branches) + 1, courantes, i_unitaire,
                                 borne))
        courantes = []
    if courantes:
        branches.append(_branche(len(branches) + 1, courantes, i_unitaire,
                                 borne))

    return _rendu(applique=True, designation=designation, unites=total,
                  borne=borne, branches=branches, motifs=motifs)


def equipement_ac(conception, branches):
    """CALX209/CALX210 — les ``QAC.N`` et ``W2.N`` des branches publiées.

    Le calibre vient de ``protections.calibrer_branches_ac`` et la section de
    ``cables.dimensionner_cables(branches_ac=…)`` : ce service ne fait que
    LEUR PASSER les branches et publier ce qu'ils rendent, omissions
    comprises. Rend ``{protections, cables, omissions}``.
    """
    from core.electrique.cables import dimensionner_cables
    from core.electrique.protections import calibrer_branches_ac

    entree = getattr(conception, 'entree', None)
    if entree is None or not branches:
        return {'protections': [], 'cables': [], 'omissions': []}

    calibres = calibrer_branches_ac(
        branches, phases=entree.phases,
        tension_reseau_v=entree.tension_reseau_v)
    resultat = dimensionner_cables(
        entree, getattr(conception, 'resultat', None), None,
        branches_ac=branches)
    return {
        'protections': [_organe(p) for p in calibres.protections],
        # Le ``W1`` que ``dimensionner_cables`` rend au passage appartient au
        # bloc « cables » du résultat : seules les branches sont publiées ici.
        'cables': [_cable(c) for c in resultat.cables
                   if str(c.repere).startswith('W2.')],
        'omissions': (list(calibres.omissions) + list(resultat.bloquants)
                      + list(resultat.alertes)),
    }


# ── la borne, et ce qui la rend non vérifiable ────────────────────────────

def _borne_par_branche(specs, i_unitaire):
    """``(borne, motifs)`` — ``borne`` vaut ``None`` quand rien ne la publie."""
    plafond = _entier((specs or {}).get('ac_unites_max_par_branche'))
    if plafond:
        return ({'origine': ORIGINE_BORNE_FICHE, 'champ': CHAMP_UNITES_MAX,
                 'unites': plafond,
                 'detail': MOTIF_COUPURE_FICHE % plafond}, [])

    if i_unitaire and i_unitaire > 0:
        from core.electrique.protections import CALIBRES_DISJONCTEUR_A

        calibre_max = float(CALIBRES_DISJONCTEUR_A[-1])
        unites = int(calibre_max // i_unitaire)
        if unites >= 1:
            return ({'origine': ORIGINE_BORNE_CALIBRE, 'champ': CHAMP_I_MAX,
                     'unites': unites,
                     'calibre_plafond_a': calibre_max,
                     'detail': MOTIF_COUPURE_CALIBRE
                     % (i_unitaire, calibre_max, unites)}, [])

    return (None, [MOTIF_SANS_BORNE])


def _branche(rang, unites_par_pan, i_unitaire, borne):
    """Une branche AC — la forme exacte que CALX210 relit."""
    from core.electrique.protections import calibre_disjoncteur

    unites = sum(nombre for _label, nombre in unites_par_pan)
    courant = (round(unites * i_unitaire, 3)
               if i_unitaire and i_unitaire > 0 else None)
    return {
        'repere': 'BR%d' % rang,
        'unites': unites,
        'pans': [label for label, _nombre in unites_par_pan],
        'i_branche_a': courant,
        'calibre_a': (calibre_disjoncteur(courant)
                      if courant is not None else None),
        'motif_de_coupure': (borne['detail'] if borne is not None
                             else MOTIF_SANS_BORNE),
    }


def _rendu(*, applique, designation, unites, borne, branches, motifs):
    """La forme publiée — les onze clés TOUJOURS présentes."""
    return {
        'regime': REGIME_BRANCHE_AC,
        'applique': applique,
        'designation': designation,
        'unites': unites,
        'unites_max_par_branche': (borne['unites'] if borne is not None
                                   else None),
        'borne': borne,
        'branches': branches,
        # OpenSolar cesse d'afficher les données MPPT dans ce régime : nous
        # aussi, et le motif dit pourquoi plutôt que de rendre un écran vide.
        'ecran_mppt': False,
        'motif_mppt': MOTIF_ECRAN_MPPT,
        'motifs': list(motifs),
        'reference': REFERENCE_OPENSOLAR,
    }


def _organe(protection):
    """Un organe du noyau, publié comme la check-list CAL132 le publie.

    Les NEUF clés sont celles de ``services/protections.py::_ligne`` : les
    départs de branches rejoignent ``resultat['protections']`` à côté des
    organes de la check-list, et une liste dont les lignes n'ont pas les
    mêmes clés est exactement ce que PACT10 interdit.
    """
    from .protections import ORIGINE_REGLE

    return {
        'repere': protection.repere,
        'designation': protection.designation,
        'calibre': protection.calibre,
        'quantite': protection.quantite,
        'cote': protection.cote,
        'origine': ORIGINE_REGLE,
        'regle_source': protection.regle_source,
        'motif': '',
        'retenu': True,
    }


def _cable(cable):
    """Un câble de branche, publié avec son critère et sa règle citée."""
    return {
        'repere': cable.repere,
        'designation': cable.designation,
        'section_mm2': cable.section_mm2,
        'nb_conducteurs': cable.nb_conducteurs,
        'longueur_m': round(cable.longueur_m, 2),
        'ib_a': round(cable.ib_a, 2),
        'in_a': cable.in_a,
        'iz_a': cable.iz_a,
        'chute_tension_pct': round(cable.chute_tension_pct, 3),
        'chute_cible_pct': cable.chute_cible_pct,
        'chute_max_pct': cable.chute_max_pct,
        'critere_dimensionnant': cable.critere_dimensionnant,
        'conforme': cable.conforme,
        'regle_source': cable.regle_source,
    }


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _entier(valeur):
    nombre = _nombre(valeur)
    return int(nombre) if nombre and nombre > 0 else 0
