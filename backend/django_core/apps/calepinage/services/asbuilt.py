"""CAL212 — l'AS-BUILT : le posé réel comparé à la variante retenue.

LA RÈGLE, ET ELLE EST TOUTE LA TÂCHE
-------------------------------------
L'écart affiché est la DIFFÉRENCE DE DEUX SAISIES RÉELLES :

* le PRÉVU vient de la variante RETENUE du calepinage (CAL9/CAL209) — le
  document que le chantier a reçu, pas un dimensionnement souhaité ;
* le POSÉ vient de ``PoseReelle``, saisi sur le chantier.

Un pan SANS saisie de pose n'affiche AUCUN écart. Pas un zéro : un zéro dirait
« conforme » alors que personne n'a compté. C'est le même refus que partout
dans ce module — on préfère le trou visible au chiffre rassurant.

LE CHANTIER RESTE LE CHANTIER
------------------------------
Le module ``installations`` ne porte aucun champ calepinage (règle fondateur
12/09/2026 : « le module chantier ne garde QUE son cœur ») : il se branche sur
``apps.calepinage.selectors.calepinage_retenu_pour_devis`` par son propre
sélecteur ``calepinage_retenu_du_chantier`` (CAL209). Ce module ne fait donc
JAMAIS le chemin inverse en important ``apps.installations`` — il travaille
sur le calepinage qu'on lui donne.

La comparaison elle-même (``comparer``) ne connaît que des dictionnaires :
elle se teste sans base.
"""
from __future__ import annotations

SOURCE_VARIANTE = 'variante retenue'
SOURCE_CALEPINAGE = 'document du calepinage'

MENTION_SANS_SAISIE = (
    "Aucun relevé de pose n'a été saisi pour ce pan : l'écart n'est pas "
    "affiché (il serait supposé, pas mesuré)."
)
MENTION_SANS_PREVU = (
    "Ce pan n'existe pas dans la variante retenue : il n'y a rien à quoi "
    "comparer le posé."
)

__all__ = [
    'SOURCE_VARIANTE', 'SOURCE_CALEPINAGE', 'MENTION_SANS_SAISIE',
    'comparer', 'pans_prevus', 'ecarts_du_calepinage',
]


def comparer(prevus, saisies):
    """``[{pan, prevu, pose, ecart, ecarts_position, releve_le, mention}]``.

    Args:
        prevus: ``[{pan, modules}]`` — les pans de la variante retenue.
        saisies: ``[{pan, modules_poses, ecarts_position, releve_le}]``.

    Un pan prévu SANS saisie sort avec ``pose = None`` et ``ecart = None`` ;
    un pan SAISI qui n'existe pas au prévu sort avec ``prevu = None`` — les
    deux cas sont VISIBLES, aucun n'est silencieusement écarté.
    """
    par_pan = {}
    for saisie in saisies or []:
        pan = str((saisie or {}).get('pan') or '').strip()
        if pan:
            par_pan[pan] = saisie

    lignes, vus = [], set()
    for prevu in prevus or []:
        pan = str((prevu or {}).get('pan') or '').strip()
        vus.add(pan)
        lignes.append(_ligne(pan, prevu.get('modules'), par_pan.get(pan)))
    for pan, saisie in par_pan.items():
        if pan not in vus:
            lignes.append(_ligne(pan, None, saisie))
    return lignes


def _entier(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return int(valeur)
    return None


def _ligne(pan, modules_prevus, saisie):
    prevu = _entier(modules_prevus)
    pose = _entier((saisie or {}).get('modules_poses'))
    if pose is None:
        mention = MENTION_SANS_SAISIE
    elif prevu is None:
        mention = MENTION_SANS_PREVU
    else:
        mention = ''
    return {
        'pan': pan,
        'prevu': prevu,
        'pose': pose,
        # L'écart n'existe QUE quand les deux nombres sont des saisies
        # réelles — jamais une différence avec un zéro supposé.
        'ecart': (pose - prevu if pose is not None and prevu is not None
                  else None),
        'ecarts_position': ((saisie or {}).get('ecarts_position') or ''),
        'releve_le': (saisie or {}).get('releve_le'),
        'mention': mention,
    }


def pans_prevus(calepinage):
    """Les pans PRÉVUS : ceux de la variante RETENUE, sinon du document.

    Renvoie ``(pans, source)`` — la source est PUBLIÉE pour qu'un écart lu
    sur le document du calepinage ne se lise jamais comme un écart avec la
    variante contractuelle.
    """
    from .production import pans_du_layout

    variante = (calepinage.variantes.filter(retenue=True).first()
                if hasattr(calepinage, 'variantes') else None)
    if variante is not None and variante.roof_layout:
        return (pans_du_layout(variante.roof_layout), SOURCE_VARIANTE)
    return (pans_du_layout(getattr(calepinage, 'roof_layout', None)),
            SOURCE_CALEPINAGE)


def ecarts_du_calepinage(calepinage):
    """L'as-built COMPLET d'un calepinage : prévu, posé, écart, totaux.

    Lecture PURE, bornée société par l'appelant. ``ecart_total`` n'existe que
    si AU MOINS un pan a été relevé — sinon il vaudrait « 0 » sur un chantier
    dont personne n'a compté un seul module.
    """
    from ..models import PoseReelle

    prevus, source = pans_prevus(calepinage)
    saisies = [
        {'pan': pose.pan, 'modules_poses': pose.modules_poses,
         'ecarts_position': pose.ecarts_position, 'releve_le': pose.releve_le}
        for pose in PoseReelle.objects.filter(calepinage=calepinage)
    ]
    lignes = comparer([{'pan': pan['pan'], 'modules': pan['modules']}
                       for pan in prevus], saisies)
    releves = [ligne for ligne in lignes if ligne['pose'] is not None]
    comparables = [ligne for ligne in lignes if ligne['ecart'] is not None]
    return {
        'calepinage': calepinage.pk,
        'source_prevu': source,
        'pans': lignes,
        'pans_releves': len(releves),
        'total_prevu': sum(ligne['prevu'] for ligne in lignes
                           if ligne['prevu'] is not None),
        'total_pose': (sum(ligne['pose'] for ligne in releves)
                       if releves else None),
        'ecart_total': (sum(ligne['ecart'] for ligne in comparables)
                        if comparables else None),
    }
