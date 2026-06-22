"""Sélecteurs QHSE — lectures et calculs de gating (lecture seule).

QHSE6 — Points d'arrêt bloquants (hold points). Un point de contrôle marqué
``hold_point`` est un point d'arrêt : tant qu'il n'est pas LEVÉ, les travaux ne
peuvent pas avancer au-delà de sa phase.

DÉCISION (règle de blocage) — un point d'arrêt est **bloquant** (non levé) tant
que son relevé est *non résolu* :

* relevé **absent** (jamais matérialisé sur le plan chantier), OU
* relevé présent mais ``conforme`` n'est **pas** ``True`` (``None`` = pas encore
  relevé, ``False`` = non conforme).

Un point d'arrêt est **levé** (débloque) dès que son relevé existe avec
``conforme=True``. Les non-conformités sur des points qui ne sont PAS des points
d'arrêt n'entrent JAMAIS dans le calcul — elles ne bloquent pas l'avancement.

Ce module ne mute RIEN et ne touche aucune autre app : il expose un *portail*
interrogeable (``peut_avancer`` + liste des points bloquants, globalement et par
phase). Le câblage éventuel vers l'avancement chantier de ``installations`` est
un suivi à part : un appelant consulte cette porte, il ne la franchit pas ici.
"""
from .models import ReleveControle, ReleveCourbeIV


def _bloquant(releve):
    """Un point d'arrêt non levé est bloquant.

    ``releve`` est le ``ReleveControle`` du point d'arrêt sur le plan chantier,
    ou ``None`` s'il manque. Bloquant si le relevé est absent ou si ``conforme``
    n'est pas ``True`` (``None`` = pas encore relevé, ``False`` = non conforme).
    """
    if releve is None:
        return True
    return releve.conforme is not True


def hold_points_status(plan_chantier):
    """État de gating des points d'arrêt d'un ``PlanInspectionChantier``.

    Parcourt TOUS les points d'arrêt (``hold_point=True``) du modèle d'ITP du
    plan, apparie chacun à son relevé sur ce plan chantier (s'il existe) et
    calcule, par point, s'il bloque l'avancement. Renvoie un dict :

    * ``peut_avancer`` — ``True`` si AUCUN point d'arrêt n'est bloquant ;
    * ``nb_hold_points`` — nombre total de points d'arrêt du plan ;
    * ``nb_bloquants`` — nombre de points d'arrêt bloquants ;
    * ``points_bloquants`` — liste détaillée (point + état du relevé) des points
      d'arrêt non levés, ordonnée par ``ordre`` puis ``id`` du point ;
    * ``phases_bloquees`` — liste triée des phases portant au moins un point
      d'arrêt bloquant.

    Lecture seule : aucune mutation, aucune dépendance cross-app.
    """
    modele = plan_chantier.modele
    points = list(
        modele.points.filter(hold_point=True).order_by('ordre', 'id'))

    # Un relevé par point (le service d'instanciation en garantit l'unicité) ;
    # on indexe par point_id pour un appariement O(1) sans requête par point.
    releves = {
        r.point_id: r
        for r in ReleveControle.objects.filter(
            plan_chantier=plan_chantier,
            point__hold_point=True,
        ).select_related('point')
    }

    points_bloquants = []
    phases_bloquees = set()
    for point in points:
        releve = releves.get(point.id)
        if not _bloquant(releve):
            continue
        if point.phase:
            phases_bloquees.add(point.phase)
        points_bloquants.append({
            'point_id': point.id,
            'intitule': point.intitule,
            'phase': point.phase,
            'ordre': point.ordre,
            'releve_id': releve.id if releve is not None else None,
            'releve_present': releve is not None,
            'conforme': releve.conforme if releve is not None else None,
        })

    return {
        'peut_avancer': not points_bloquants,
        'nb_hold_points': len(points),
        'nb_bloquants': len(points_bloquants),
        'points_bloquants': points_bloquants,
        'phases_bloquees': sorted(phases_bloquees),
    }


def phase_peut_avancer(plan_chantier, phase):
    """``True`` si AUCUN point d'arrêt bloquant n'est rattaché à ``phase``.

    Gate par phase : l'avancement au-delà d'une phase donnée est autorisé tant
    qu'aucun point d'arrêt de cette phase n'est bloquant. Une phase sans point
    d'arrêt n'est jamais bloquée.
    """
    status = hold_points_status(plan_chantier)
    return phase not in set(status['phases_bloquees'])


# ── QHSE7 — Relevés courbe I-V par string (lecture seule) ──────────────────

def courbes_iv_for_chantier(company, chantier_id):
    """Relevés de courbe I-V d'un chantier, scopés société.

    Référence lâche au chantier par ``chantier_id`` — aucun import cross-app de
    ``installations``. Renvoie un queryset (ordonné par le ``Meta`` du modèle,
    le plus récent d'abord) restreint à ``company`` ; jamais les courbes d'une
    autre société. Lecture seule, aucune mutation.
    """
    return ReleveCourbeIV.objects.filter(
        company=company, chantier_id=chantier_id)
