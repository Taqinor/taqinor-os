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
from .models import (
    ActionCorrectivePreventive, Audit, NonConformite, NotationFinChantier,
    ReleveControle, ReleveCourbeIV,
)


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


# ── QHSE8 — Photos de contrôle (avant / pendant / après) ───────────────────

# Phases de prise de vue d'un relevé de contrôle, alignées sur la galerie
# groupée de ``records.Attachment`` (champ ``phase``).
PHASES_PHOTO = ('avant', 'pendant', 'apres')


def photos_controle(releve):
    """Pièces jointes (photos) rattachées à un ``ReleveControle``, scopées société.

    Lit les ``records.Attachment`` ciblant ce relevé via ContentType (records
    est une app de fondation — pas un import cross-app de domaine) en se bornant
    à la société du relevé. Renvoie un queryset trié (le plus récent d'abord,
    via le ``Meta`` du modèle Attachment). Lecture seule.
    """
    from django.contrib.contenttypes.models import ContentType
    from apps.records.models import Attachment

    ct = ContentType.objects.get_for_model(releve.__class__)
    return Attachment.objects.filter(
        company=releve.company,
        content_type=ct,
        object_id=releve.id,
    )


def photos_controle_par_phase(releve):
    """Photos d'un relevé de contrôle, regroupées par phase (QHSE8).

    Renvoie un dict ``{'avant': [...], 'pendant': [...], 'apres': [...],
    'autres': [...]}`` où chaque valeur est la liste ordonnée des
    ``records.Attachment`` du relevé pour cette phase ; ``autres`` rassemble les
    pièces sans phase ou hors nomenclature. Lecture seule, scopée société.
    """
    groupes = {phase: [] for phase in PHASES_PHOTO}
    groupes['autres'] = []
    for att in photos_controle(releve):
        phase = (att.phase or '').strip().lower()
        if phase in groupes:
            groupes[phase].append(att)
        else:
            groupes['autres'].append(att)
    return groupes


# ── QHSE12 — Relances CAPA en retard ───────────────────────────────────────

# Statuts CAPA considérés comme NON résolus (donc relançables s'ils sont
# échus) : une CAPA réalisée ou vérifiée n'est plus en retard.
STATUTS_CAPA_OUVERTS = (
    ActionCorrectivePreventive.Statut.A_FAIRE,
    ActionCorrectivePreventive.Statut.EN_COURS,
)


def capa_en_retard(company, today=None):
    """Actions correctives/préventives (CAPA) en retard d'une société.

    Une CAPA est *en retard* quand son échéance (``echeance``) est strictement
    passée (``< today``) ET que son statut reste ouvert (à faire / en cours).
    Les CAPA réalisées ou vérifiées, ou sans échéance, sont exclues. Renvoie un
    queryset scopé société, échéance la plus ancienne d'abord. Lecture seule.
    """
    from django.utils import timezone
    if today is None:
        today = timezone.localdate()
    return (ActionCorrectivePreventive.objects
            .filter(company=company,
                    echeance__isnull=False,
                    echeance__lt=today,
                    statut__in=STATUTS_CAPA_OUVERTS)
            .select_related('non_conformite', 'responsable')
            .order_by('echeance', 'id'))


# ── QHSE17 — Gate de clôture (grille de notation fin de chantier) ───────────

def chantier_peut_cloturer(chantier_id, company):
    """Gate advisory : le chantier est-il autorisé à clôturer ?

    Consulte la notation fin de chantier (``NotationFinChantier``) la plus récente
    pour ce chantier et cette société. Renvoie ``True`` si :

    * aucune notation n'a encore été créée pour ce chantier (pas de blocage par
      défaut — la gate est advisory, non bloquante) ;
    * OU la notation la plus récente a un ``verdict = 'passe'``.

    Renvoie ``False`` uniquement si la notation la plus récente existe avec un
    ``verdict = 'echec'`` (score < seuil_passage). Un verdict ``None`` (score pas
    encore calculé) est traité comme un non-blocage (la gate n'est advisory que
    sur un verdict calculé).

    Aucun import cross-app : référence lâche par ``chantier_id``. Lecture seule.
    """
    notation = (
        NotationFinChantier.objects
        .filter(company=company, chantier_id=chantier_id)
        .order_by('-id')
        .first()
    )
    if notation is None:
        return True
    if notation.verdict == NotationFinChantier.Verdict.ECHEC:
        return False
    return True


def notation_fin_chantier_latest(chantier_id, company):
    """Notation fin de chantier la plus récente d'un chantier (ou None).

    Lecture seule, scopée société. Référence lâche par ``chantier_id``.
    """
    return (
        NotationFinChantier.objects
        .filter(company=company, chantier_id=chantier_id)
        .order_by('-id')
        .first()
    )


# ── LITIGE4 — Portail lecture NCR / Audit pour les litiges qualité ──────────
#
# Hooks de lecture seule consommés par ``apps.litiges`` (via import local) pour
# afficher la non-conformité (NCR) et l'audit fin de chantier rattachés à un
# litige qualité — référence lâche par id, jamais un import cross-app des
# modèles QHSE depuis litiges. Tout est scopé société.

def ncr_by_id(ncr_id, company):
    """Non-conformité (NCR) d'une société par id, ou ``None``.

    Référence lâche par ``ncr_id``. Renvoie l'instance ``NonConformite`` scopée
    ``company`` si elle existe, sinon ``None`` (id absent ou société différente).
    Lecture seule, aucune mutation.
    """
    if not ncr_id:
        return None
    return NonConformite.objects.filter(company=company, id=ncr_id).first()


def audit_by_id(audit_id, company):
    """Audit (exécution) d'une société par id, ou ``None``.

    Référence lâche par ``audit_id`` (un ``Audit`` peut être un audit fin de
    chantier). Renvoie l'instance ``Audit`` scopée ``company`` si elle existe,
    sinon ``None``. Lecture seule, aucune mutation.
    """
    if not audit_id:
        return None
    return Audit.objects.filter(company=company, id=audit_id).first()


def ncr_apercu(ncr_id, company):
    """Aperçu sérialisable d'une NCR pour un litige (ou ``None``).

    Renvoie un petit dict (id/référence/titre/gravité/statut + libellés) prêt à
    exposer côté API, ou ``None`` si la NCR n'existe pas pour cette société.
    Lecture seule.
    """
    ncr = ncr_by_id(ncr_id, company)
    if ncr is None:
        return None
    return {
        'id': ncr.id,
        'reference': ncr.reference,
        'titre': ncr.titre,
        'gravite': ncr.gravite,
        'gravite_display': ncr.get_gravite_display(),
        'statut': ncr.statut,
        'statut_display': ncr.get_statut_display(),
        'chantier_id': ncr.chantier_id,
    }


def audit_apercu(audit_id, company):
    """Aperçu sérialisable d'un audit fin de chantier pour un litige (ou ``None``).

    Renvoie un petit dict (id/grille/date/statut/score/chantier) prêt à exposer
    côté API, ou ``None`` si l'audit n'existe pas pour cette société. Lecture
    seule.
    """
    audit = audit_by_id(audit_id, company)
    if audit is None:
        return None
    return {
        'id': audit.id,
        'grille': audit.grille.nom,
        'date_audit': audit.date_audit,
        'statut': audit.statut,
        'statut_display': audit.get_statut_display(),
        'score': audit.score,
        'chantier_id': audit.chantier_id,
    }
