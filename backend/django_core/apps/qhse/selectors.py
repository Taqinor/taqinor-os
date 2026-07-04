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
from django.db.models import Avg

from .models import (
    ActionCorrectivePreventive, Audit, ClauseNorme, ConformiteEnvironnementale,
    ControleReception, CritereAudit, DeclarationCnss,
    DemandeActionFournisseur, DiffusionProcedure,
    EtapeDeclarationAt, EvaluationRisque,
    Incident, IndicateurESG, InspectionSecurite, NonConformite,
    NotationFinChantier, ObjectifQhse,
    PermisTravail, PlanInspectionChantier,
    ProcedureQualite, ReleveControle, ReleveCourbeIV, ReponseCritere,
    RetourClientQualite,
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


def hold_points_bloquants_pour_chantier(company, chantier_id):
    """CH2 — points d'arrêt NON LEVÉS de tous les plans d'inspection ouverts
    d'un chantier, scopés société.

    Sélecteur mince consommé par le gating des étapes de chantier
    (``installations`` — référence lâche par ``chantier_id``, jamais d'import
    de modèle cross-app) : agrège ``hold_points_status`` sur chaque
    ``PlanInspectionChantier`` EN COURS du chantier et renvoie la liste plate
    des points d'arrêt bloquants (chacun enrichi de ``plan_chantier_id`` et du
    nom du modèle d'ITP). Liste vide = aucun point d'arrêt ne bloque. Un plan
    CLÔTURÉ ne bloque plus. Lecture seule, aucune mutation.
    """
    bloquants = []
    plans = PlanInspectionChantier.objects.filter(
        company=company, chantier_id=chantier_id,
        statut=PlanInspectionChantier.Statut.EN_COURS,
    ).select_related('modele')
    for plan in plans:
        status = hold_points_status(plan)
        for point in status['points_bloquants']:
            bloquants.append({
                **point,
                'plan_chantier_id': plan.id,
                'plan_nom': plan.modele.nom,
            })
    return bloquants


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


# ── QHSE25 — Alerte d'expiration des permis de travail ─────────────────────

# Statuts de permis considérés comme NON résolus pour l'alerte d'expiration :
# un permis CLÔTURÉ a déjà été soldé (travail terminé) et n'a plus à être
# renouvelé ni signalé. On garde brouillon / validé / expiré, car un permis
# expiré est précisément ce qui doit alerter pour clôture ou renouvellement.
STATUTS_PERMIS_ALERTABLES = (
    PermisTravail.Statut.BROUILLON,
    PermisTravail.Statut.VALIDE,
    PermisTravail.Statut.EXPIRE,
)


def permis_travail_expirant(company, within_days=30, inclure_expires=True):
    """Permis de travail (QHSE25) qui expirent bientôt ou sont déjà expirés.

    Lecture cadrée société : retient les permis NON clôturés (brouillon /
    validé / expiré) dont la ``date_fin`` (fin de validité) est renseignée et
    tombe au plus tard dans ``within_days`` jours (aujourd'hui + ``within_days``
    inclus). Par défaut ``inclure_expires`` est vrai : les permis dont la fenêtre
    de validité est déjà passée (``date_fin`` < aujourd'hui) sont également
    renvoyés, car un permis périmé est exactement ce qui doit alerter pour être
    clôturé ou renouvelé ; passer ``inclure_expires=False`` ne garde que les
    échéances encore à venir dans la fenêtre. Les permis sans ``date_fin`` ou
    déjà clôturés sont exclus. Toujours scopé société (jamais lu du corps de
    requête) ; trié par échéance la plus proche d'abord.
    """
    from django.utils import timezone
    from datetime import timedelta

    if company is None:
        return PermisTravail.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    qs = PermisTravail.objects.filter(
        company=company,
        statut__in=STATUTS_PERMIS_ALERTABLES,
        date_fin__isnull=False,
        date_fin__lte=limite,
    )
    if not inclure_expires:
        qs = qs.filter(date_fin__gte=today)
    return qs.order_by('date_fin', 'id')


# ── QHSE30 — Déclarations CNSS à échéance (approchantes / hors délai) ───────

def declarations_cnss_a_echeance(company, within_days=2, today=None):
    """Déclarations CNSS d'accident du travail à échéance ou déjà hors délai (QHSE30).

    Lecture cadrée société : retient les déclarations NON encore transmises
    (``date_declaration`` vide) dont la ``date_limite`` (échéance légale) tombe au
    plus tard dans ``within_days`` jours (aujourd'hui + ``within_days`` inclus).
    Les déjà-déclarées et celles sans ``date_limite`` sont exclues. Une déclaration
    dont l'échéance est DÉJÀ passée (hors délai) est incluse — c'est précisément
    ce qui doit alerter. Toujours scopé société (jamais lu du corps de requête) ;
    triée par échéance la plus proche d'abord.
    """
    from django.utils import timezone
    from datetime import timedelta

    if company is None:
        return DeclarationCnss.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = DeclarationCnss.DELAI_LEGAL_JOURS
    if within_days < 0:
        within_days = 0
    if today is None:
        today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    return (DeclarationCnss.objects
            .filter(company=company,
                    date_declaration__isnull=True,
                    date_limite__isnull=False,
                    date_limite__lte=limite)
            .select_related('accident_travail')
            .order_by('date_limite', 'id'))


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


# ── QHSE18 — Procédures qualité versionnées (lecture seule) ─────────────────

def procedure_qualite_courante(company, reference):
    """Version « courante » d'une procédure qualité d'une société (ou None).

    La version courante est la version ``en_vigueur`` de la ``reference`` ; à
    défaut (aucune en vigueur), c'est la version au numéro le plus haut. Lecture
    seule, scopée société. Référence lâche au document GED par ``document_id``.
    """
    qs = ProcedureQualite.objects.filter(
        company=company, reference=reference)
    en_vigueur = qs.filter(
        statut=ProcedureQualite.Statut.EN_VIGUEUR).order_by('-version').first()
    if en_vigueur is not None:
        return en_vigueur
    return qs.order_by('-version').first()


def procedure_qualite_versions(company, reference):
    """Toutes les versions d'une procédure qualité (la plus récente d'abord).

    Queryset scopé société pour une ``reference`` donnée. Lecture seule.
    """
    return (ProcedureQualite.objects
            .filter(company=company, reference=reference)
            .order_by('-version', '-id'))


def procedures_qualite_courantes(company):
    """Liste des versions courantes de chaque référence de procédure d'une société.

    Pour chaque ``reference`` distincte de la société, renvoie la version
    courante (cf. ``procedure_qualite_courante``). Lecture seule. Renvoie une
    liste de ``ProcedureQualite`` triée par référence.
    """
    refs = (ProcedureQualite.objects
            .filter(company=company)
            .values_list('reference', flat=True)
            .distinct())
    courantes = [
        procedure_qualite_courante(company, ref) for ref in sorted(set(refs))
    ]
    return [p for p in courantes if p is not None]


# ── QHSE19 — Satisfaction client qualité (agrégat) ──────────────────────────

def satisfaction_moyenne(company, chantier_id=None):
    """Note de satisfaction moyenne des retours client d'une société (ou None).

    Agrège ``note_satisfaction`` sur les ``RetourClientQualite`` de la société,
    optionnellement filtrés sur un ``chantier_id`` (référence lâche). Renvoie un
    ``float`` arrondi à 2 décimales, ou ``None`` si aucun retour. Lecture seule.
    """
    qs = RetourClientQualite.objects.filter(company=company)
    if chantier_id is not None:
        qs = qs.filter(chantier_id=chantier_id)
    moyenne = qs.aggregate(moy=Avg('note_satisfaction'))['moy']
    if moyenne is None:
        return None
    return round(float(moyenne), 2)


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


# ── QHSE20 — Tableau de bord « ISO 9001 readiness » ────────────────────────
#
# Agrégation pure et EN LECTURE SEULE des données QHSE déjà existantes (aucun
# nouveau modèle) en un score de « préparation ISO 9001 » + une ventilation par
# critère, chaque critère étant rattaché à la clause ISO 9001:2015
# correspondante. Tout est scopé société (tous les querysets filtrent par
# ``company``). Aucune division par zéro : un critère sans donnée vaut 0 et est
# marqué ``no_data=True`` (jamais un plantage).

# Cible de satisfaction client (note maximale de RetourClientQualite) pour
# convertir la moyenne 1–5 en pourcentage de critère.
_SATISFACTION_NOTE_MAX = RetourClientQualite.NOTE_MAX


def _pct(numerateur, denominateur):
    """Pourcentage 0–100 (2 décimales) ou ``None`` si le dénominateur est nul.

    Garde anti-division-par-zéro : aucune donnée → ``None`` (pas un plantage,
    pas un 0 trompeur). L'appelant décide comment pondérer un critère sans
    donnée (ici : score 0, ``no_data=True``).
    """
    if not denominateur:
        return None
    return round(100.0 * numerateur / denominateur, 2)


def _critere(cle, libelle, clause, score, detail, poids=1):
    """Construit un dict-critère normalisé pour le tableau de bord.

    ``score`` est un pourcentage 0–100 ou ``None`` (aucune donnée). Un critère
    sans donnée compte pour 0 dans le score global mais est signalé
    (``no_data``) pour ne pas masquer un manque de preuve ISO.
    """
    no_data = score is None
    return {
        'cle': cle,
        'libelle': libelle,
        'clause_iso': clause,
        'poids': poids,
        'score': score,
        'score_effectif': 0.0 if no_data else score,
        'no_data': no_data,
        'detail': detail,
    }


def iso9001_readiness(company):
    """Tableau de bord « ISO 9001 readiness » d'une société (lecture seule).

    Agrège les données QHSE existantes (non-conformités, CAPA, audits,
    procédures qualité, ITP/relevés, retours client) en un score global de
    préparation ISO 9001 et une ventilation par critère, chaque critère étant
    rattaché à la clause ISO 9001:2015 correspondante :

    * **NCR clôturées** (clause 10.2 — non-conformité & action corrective) :
      part des ``NonConformite`` à l'état ``cloturee`` ;
    * **CAPA dans les délais** (clause 10.2) : part des CAPA réalisées/vérifiées
      OU encore dans les délais (échéance non dépassée) — l'inverse des CAPA en
      retard ;
    * **Audits réalisés** (clause 9.2 — audit interne) : part des ``Audit`` à
      l'état ``clos`` ;
    * **Procédures publiées** (clause 7.5 — informations documentées) : part des
      références de procédure qualité dont la version courante est
      ``en_vigueur`` ;
    * **Couverture ITP** (clause 8.5/8.6 — maîtrise & libération) : part des
      relevés de contrôle effectivement renseignés (``conforme`` non nul) ;
    * **Satisfaction client** (clause 9.1.2 — satisfaction du client) : moyenne
      des retours client convertie en pourcentage sur l'échelle 1–5.

    Le ``score_global`` est la moyenne (pondérée par ``poids``) des
    ``score_effectif`` des critères ; un critère **sans donnée** vaut 0 et porte
    ``no_data=True`` (jamais une division par zéro, jamais un plantage). Le
    ``niveau`` est dérivé du score global (≥ 85 « avancé », ≥ 60 « intermédiaire »,
    sinon « initial »). Tout est scopé ``company`` ; aucune mutation.
    """
    from django.utils import timezone

    today = timezone.localdate()

    # ── Critère 1 — NCR clôturées (clause 10.2) ─────────────────────────────
    ncr_qs = NonConformite.objects.filter(company=company)
    ncr_total = ncr_qs.count()
    ncr_cloturees = ncr_qs.filter(
        statut=NonConformite.Statut.CLOTUREE).count()
    crit_ncr = _critere(
        'ncr_cloturees', 'Non-conformités clôturées', '10.2',
        _pct(ncr_cloturees, ncr_total),
        {'total': ncr_total, 'cloturees': ncr_cloturees,
         'ouvertes': ncr_total - ncr_cloturees})

    # ── Critère 2 — CAPA dans les délais (clause 10.2) ──────────────────────
    capa_qs = ActionCorrectivePreventive.objects.filter(company=company)
    capa_total = capa_qs.count()
    capa_en_retard_n = capa_qs.filter(
        echeance__isnull=False,
        echeance__lt=today,
        statut__in=STATUTS_CAPA_OUVERTS,
    ).count()
    capa_a_temps = capa_total - capa_en_retard_n
    crit_capa = _critere(
        'capa_dans_delais', 'CAPA dans les délais', '10.2',
        _pct(capa_a_temps, capa_total),
        {'total': capa_total, 'dans_delais': capa_a_temps,
         'en_retard': capa_en_retard_n})

    # ── Critère 3 — Audits réalisés (clause 9.2) ────────────────────────────
    audit_qs = Audit.objects.filter(company=company)
    audit_total = audit_qs.count()
    audit_clos = audit_qs.filter(statut=Audit.Statut.CLOS).count()
    crit_audit = _critere(
        'audits_realises', 'Audits internes réalisés', '9.2',
        _pct(audit_clos, audit_total),
        {'total': audit_total, 'clos': audit_clos,
         'en_cours': audit_total - audit_clos})

    # ── Critère 4 — Procédures publiées (clause 7.5) ────────────────────────
    refs = (ProcedureQualite.objects
            .filter(company=company)
            .values_list('reference', flat=True)
            .distinct())
    refs = sorted(set(refs))
    proc_total = len(refs)
    proc_en_vigueur = 0
    for ref in refs:
        courante = procedure_qualite_courante(company, ref)
        if (courante is not None
                and courante.statut == ProcedureQualite.Statut.EN_VIGUEUR):
            proc_en_vigueur += 1
    crit_proc = _critere(
        'procedures_publiees', 'Procédures qualité publiées', '7.5',
        _pct(proc_en_vigueur, proc_total),
        {'references': proc_total, 'en_vigueur': proc_en_vigueur,
         'brouillon_ou_obsolete': proc_total - proc_en_vigueur})

    # ── Critère 5 — Couverture ITP (clauses 8.5 / 8.6) ──────────────────────
    releve_qs = ReleveControle.objects.filter(company=company)
    releve_total = releve_qs.count()
    releve_renseignes = releve_qs.filter(conforme__isnull=False).count()
    crit_itp = _critere(
        'couverture_itp', 'Couverture des plans d\'inspection (ITP)', '8.5/8.6',
        _pct(releve_renseignes, releve_total),
        {'releves': releve_total, 'renseignes': releve_renseignes,
         'plans_chantier': PlanInspectionChantier.objects.filter(
             company=company).count()})

    # ── Critère 6 — Satisfaction client (clause 9.1.2) ──────────────────────
    moyenne = satisfaction_moyenne(company)
    nb_retours = RetourClientQualite.objects.filter(company=company).count()
    if moyenne is None or not _SATISFACTION_NOTE_MAX:
        satisfaction_pct = None
    else:
        satisfaction_pct = round(
            100.0 * moyenne / _SATISFACTION_NOTE_MAX, 2)
    crit_satisfaction = _critere(
        'satisfaction_client', 'Satisfaction client', '9.1.2',
        satisfaction_pct,
        {'moyenne': moyenne, 'note_max': _SATISFACTION_NOTE_MAX,
         'nb_retours': nb_retours})

    criteres = [
        crit_ncr, crit_capa, crit_audit, crit_proc, crit_itp,
        crit_satisfaction,
    ]

    # ── Score global pondéré (un critère sans donnée compte pour 0) ─────────
    poids_total = sum(c['poids'] for c in criteres)
    if poids_total:
        somme_ponderee = sum(
            c['score_effectif'] * c['poids'] for c in criteres)
        score_global = round(somme_ponderee / poids_total, 2)
    else:
        score_global = 0.0

    if score_global >= 85:
        niveau = 'avance'
    elif score_global >= 60:
        niveau = 'intermediaire'
    else:
        niveau = 'initial'

    return {
        'score_global': score_global,
        'niveau': niveau,
        'nb_criteres': len(criteres),
        'nb_criteres_sans_donnee': sum(1 for c in criteres if c['no_data']),
        'criteres': criteres,
    }


# ── QHSE21 — Résumé de criticité d'une évaluation des risques ───────────────

def criticite_summary(evaluation):
    """Résumé de criticité d'une ``EvaluationRisque`` (lecture seule, QHSE21).

    Agrège les ``LigneEvaluationRisque`` de l'évaluation :

    * ``nb_lignes`` — nombre de lignes ;
    * ``criticite_max`` / ``criticite_moyenne`` — criticité maximale et moyenne
      (None si aucune ligne — garde-fou division par zéro) ;
    * ``par_niveau`` — répartition par bande de criticité (faible ≤ 4,
      moyenne 5–9, élevée 10–15, critique ≥ 16).

    Aucune mutation, aucun accès cross-app.
    """
    crits = list(
        evaluation.lignes.values_list('criticite', flat=True))
    nb = len(crits)
    par_niveau = {'faible': 0, 'moyenne': 0, 'elevee': 0, 'critique': 0}
    for c in crits:
        if c <= 4:
            par_niveau['faible'] += 1
        elif c <= 9:
            par_niveau['moyenne'] += 1
        elif c <= 15:
            par_niveau['elevee'] += 1
        else:
            par_niveau['critique'] += 1
    moyenne = round(sum(crits) / nb, 2) if nb else None
    return {
        'nb_lignes': nb,
        'criticite_max': max(crits) if nb else None,
        'criticite_moyenne': moyenne,
        'par_niveau': par_niveau,
    }


# ── QHSE22 — Document unique requis avant pose (gate statut chantier) ───────

def document_unique_valide(company, chantier_id):
    """État du « document unique » (DUERP) d'un chantier (lecture seule, QHSE22).

    DÉCISION (règle de blocage) — un chantier ne peut passer à la **pose** que
    s'il dispose d'un document unique d'évaluation des risques *exploitable* :
    au moins une ``EvaluationRisque`` ``validee`` portant **au moins une ligne**
    de risque. Une évaluation en ``brouillon``/``archivee``, ou validée mais
    vide (aucune ligne), ne lève PAS l'exigence.

    Référence LÂCHE au chantier par ``chantier_id`` — aucun import cross-app de
    ``installations``. Scopé société : ne regarde QUE les évaluations de
    ``company``. Renvoie un dict détaillé :

    * ``chantier_id`` — l'identifiant interrogé (entier) ;
    * ``valide`` — ``True`` ssi un DUERP validé non vide existe ;
    * ``evaluation_id`` — l'id de l'évaluation validée non vide la plus récente
      qui lève l'exigence (``None`` si aucune) ;
    * ``reference`` — sa référence (``''`` si aucune) ;
    * ``nb_validees`` — nombre d'évaluations validées rattachées au chantier ;
    * ``nb_validees_avec_lignes`` — combien d'entre elles portent ≥ 1 ligne ;
    * ``motif`` — code de refus lisible quand ``valide`` est ``False``
      (``aucune_evaluation`` / ``aucune_validee`` / ``validee_sans_lignes``),
      ``None`` quand l'exigence est levée.

    Aucune mutation, aucune dépendance cross-app.
    """
    from django.db.models import Count

    validees = list(
        EvaluationRisque.objects
        .filter(company=company,
                chantier_id=chantier_id,
                statut=EvaluationRisque.Statut.VALIDEE)
        .annotate(nb_lignes=Count('lignes'))
        .order_by('-id'))

    avec_lignes = [ev for ev in validees if ev.nb_lignes > 0]
    leveuse = avec_lignes[0] if avec_lignes else None

    total_chantier = EvaluationRisque.objects.filter(
        company=company, chantier_id=chantier_id).exists()

    if leveuse is not None:
        motif = None
    elif not total_chantier:
        motif = 'aucune_evaluation'
    elif not validees:
        motif = 'aucune_validee'
    else:
        motif = 'validee_sans_lignes'

    return {
        'chantier_id': chantier_id,
        'valide': leveuse is not None,
        'evaluation_id': leveuse.id if leveuse is not None else None,
        'reference': leveuse.reference if leveuse is not None else '',
        'nb_validees': len(validees),
        'nb_validees_avec_lignes': len(avec_lignes),
        'motif': motif,
    }


# ── QHSE34 — Statistiques TF / TG (taux de fréquence / gravité) ────────────

# Constantes normatives des indicateurs sécurité du travail (OIT / usage).
# TF = (accidents avec arrêt × 1 000 000) / heures travaillées.
# TG = (jours d'arrêt × 1 000) / heures travaillées.
TF_BASE_HEURES = 1_000_000
TG_BASE_HEURES = 1_000


def heures_travaillees_chantiers(chantier_ids, company=None):
    """Somme des heures travaillées de plusieurs chantiers, lue depuis RH.

    Lecture cross-app CONFORME : les heures de main-d'œuvre vivent dans ``rh``
    (``FeuilleTemps``) et sont lues via le SÉLECTEUR ``rh`` lecture-seule
    ``labour_hours_for_installation`` (FG167) — jamais par un import de
    ``rh.models``. Chaque chantier (référence lâche par id) est sommé ; le total
    est renvoyé en ``Decimal``. Une liste vide renvoie ``Decimal('0')``.

    Sert d'entrée « heures travaillées depuis RH » au calcul TF / TG (QHSE34).
    """
    from decimal import Decimal

    total = Decimal('0')
    if not chantier_ids:
        return total
    # Import function-local pour éviter tout cycle d'import au démarrage.
    from apps.rh.selectors import labour_hours_for_installation

    for cid in chantier_ids:
        if cid in (None, ''):
            continue
        try:
            res = labour_hours_for_installation(cid, company=company)
        except Exception:  # pragma: no cover - défensif (RH absent / erreur)
            continue
        total += res.get('total_heures') or Decimal('0')
    return total


def statistiques_tf_tg(company, heures_travaillees, date_debut=None,
                       date_fin=None, jours_perdus=None):
    """Taux de fréquence (TF) et de gravité (TG) des accidents (QHSE34).

    Indicateurs sécurité standards calculés sur le registre QHSE des incidents
    (``Incident`` — QHSE29), scopé société :

    * ``TF`` = (accidents avec arrêt × ``1 000 000``) / heures travaillées ;
    * ``TG`` = (jours d'arrêt × ``1 000``) / heures travaillées.

    Les ``heures_travaillees`` sont fournies en entrée — typiquement la somme des
    feuilles de temps RH (cf. ``heures_travaillees_chantiers``, qui lit ``rh`` via
    son sélecteur, jamais par import de modèle). Le nombre d'accidents AVEC ARRÊT
    est dérivé du registre QHSE : on retient les ``Incident`` de type
    ``accident`` sur la période. Le QHSE ne stocke pas les jours d'arrêt
    (détail RH) : ``jours_perdus`` est donc fourni en entrée (0 par défaut) — le
    TG reste calculable dès qu'il est connu.

    Renvoie un dict (TF / TG ``None`` si ``heures_travaillees`` ≤ 0, indéfini) :
    ``{
        'heures_travaillees': Decimal,
        'accidents_avec_arret': int,
        'jours_perdus': int,
        'tf': Decimal | None,
        'tg': Decimal | None,
        'periode': {'debut': str|None, 'fin': str|None},
    }``. Lecture seule, aucune mutation, aucun import cross-app de modèle.
    """
    from decimal import Decimal

    try:
        heures = Decimal(str(heures_travaillees or 0))
    except (TypeError, ValueError, ArithmeticError):
        heures = Decimal('0')

    qs = Incident.objects.filter(
        company=company, type_incident=Incident.TypeIncident.ACCIDENT)
    if date_debut is not None:
        qs = qs.filter(date_incident__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_incident__lte=date_fin)
    accidents = qs.count()

    try:
        jours = int(jours_perdus) if jours_perdus is not None else 0
    except (TypeError, ValueError):
        jours = 0
    if jours < 0:
        jours = 0

    if heures > 0:
        tf = (Decimal(accidents) * TF_BASE_HEURES / heures).quantize(
            Decimal('0.01'))
        tg = (Decimal(jours) * TG_BASE_HEURES / heures).quantize(
            Decimal('0.01'))
    else:
        tf = None
        tg = None

    return {
        'heures_travaillees': heures,
        'accidents_avec_arret': accidents,
        'jours_perdus': jours,
        'tf': tf,
        'tg': tg,
        'periode': {
            'debut': date_debut.isoformat() if date_debut else None,
            'fin': date_fin.isoformat() if date_fin else None,
        },
    }


# ── QHSE35 — Inspections / permis dans le digest + calendrier ──────────────

# Statuts d'inspection encore « ouverts » pour le digest : une inspection
# ANNULÉE n'a plus d'échéance à suivre.
STATUTS_INSPECTION_OUVERTS = (
    InspectionSecurite.Statut.PLANIFIEE,
    InspectionSecurite.Statut.REALISEE,
)


def inspections_a_venir(company, within_days=30, today=None,
                        inclure_passees=True):
    """Inspections sécurité (QHSE33) planifiées dans la fenêtre du digest.

    Lecture cadrée société : retient les inspections NON annulées dont la
    ``date_prevue`` est renseignée et tombe au plus tard dans ``within_days``
    jours (aujourd'hui + ``within_days`` inclus). Par défaut ``inclure_passees``
    garde aussi les inspections dont la date prévue est déjà passée (à solder /
    reprogrammer) ; ``inclure_passees=False`` ne garde que les échéances à venir.
    Triée par date la plus proche d'abord. Lecture seule.
    """
    from datetime import timedelta

    from django.utils import timezone

    if company is None:
        return InspectionSecurite.objects.none()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0
    if today is None:
        today = timezone.localdate()
    limite = today + timedelta(days=within_days)
    qs = InspectionSecurite.objects.filter(
        company=company,
        statut__in=STATUTS_INSPECTION_OUVERTS,
        date_prevue__isnull=False,
        date_prevue__lte=limite,
    )
    if not inclure_passees:
        qs = qs.filter(date_prevue__gte=today)
    return qs.order_by('date_prevue', 'id')


def calendrier_qhse(company, within_days=30, today=None):
    """Digest / calendrier QHSE unifié des échéances à venir (QHSE35).

    Agrège, sur une seule fenêtre ``within_days``, les échéances QHSE
    actionnables d'une société, chacune normalisée en *événement de calendrier* :

    * inspections sécurité planifiées (``inspections_a_venir``) → ``date_prevue`` ;
    * permis de travail expirant ou expirés (``permis_travail_expirant``) →
      ``date_fin`` ;
    * déclarations CNSS approchant l'échéance ou hors délai
      (``declarations_cnss_a_echeance``) → ``date_limite``.

    Chaque événement est un dict homogène :
    ``{
        'type': 'inspection' | 'permis' | 'declaration_cnss',
        'id': int,
        'titre': str,
        'date': str (ISO),       # date de l'échéance
        'en_retard': bool,       # échéance déjà passée
        'reference': str,
        'chantier_id': int|None,
    }``

    Le digest renvoyé : ``{'today': str, 'within_days': int, 'total': int,
    'inspections': N, 'permis': M, 'declarations_cnss': K,
    'evenements': [...]}`` — les événements triés par date croissante. Toujours
    scopé société ; lecture seule, aucune mutation.
    """
    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    try:
        within_days = int(within_days)
    except (TypeError, ValueError):
        within_days = 30
    if within_days < 0:
        within_days = 0

    evenements = []

    for insp in inspections_a_venir(
            company, within_days=within_days, today=today):
        evenements.append({
            'type': 'inspection',
            'id': insp.id,
            'titre': insp.titre,
            'date': insp.date_prevue.isoformat(),
            'en_retard': insp.date_prevue < today,
            'reference': insp.reference,
            'chantier_id': insp.chantier_id,
        })

    for permis in permis_travail_expirant(
            company, within_days=within_days, inclure_expires=True):
        evenements.append({
            'type': 'permis',
            'id': permis.id,
            'titre': permis.titre,
            'date': permis.date_fin.isoformat(),
            'en_retard': permis.date_fin < today,
            'reference': permis.reference,
            'chantier_id': permis.chantier_id,
        })

    for decl in declarations_cnss_a_echeance(
            company, within_days=within_days, today=today):
        evenements.append({
            'type': 'declaration_cnss',
            'id': decl.id,
            'titre': decl.numero_declaration or 'Déclaration CNSS',
            'date': decl.date_limite.isoformat(),
            'en_retard': decl.date_limite < today,
            'reference': decl.numero_declaration or '',
            'chantier_id': None,
        })

    evenements.sort(key=lambda e: (e['date'], e['type'], e['id']))

    nb_inspections = sum(1 for e in evenements if e['type'] == 'inspection')
    nb_permis = sum(1 for e in evenements if e['type'] == 'permis')
    nb_cnss = sum(
        1 for e in evenements if e['type'] == 'declaration_cnss')

    return {
        'today': today.isoformat(),
        'within_days': within_days,
        'total': len(evenements),
        'inspections': nb_inspections,
        'permis': nb_permis,
        'declarations_cnss': nb_cnss,
        'evenements': evenements,
    }


# ── QHSE38 — Conformités environnementales à relancer ──────────────────────

def conformites_a_relancer(company, today=None):
    """Conformités environnementales à renouveler ou expirées (QHSE38).

    Lecture cadrée société : retient les conformités dont la ``date_expiration``
    est renseignée et dont l'état RÉEL recalculé (``statut_calcule(today)``) est
    ``a_renouveler`` (échéance dans la fenêtre de préalerte) ou ``expire``
    (échéance déjà passée — ce qui doit alerter le plus). Les conformités sans
    échéance ou encore largement valides sont exclues. Triée par échéance la plus
    proche d'abord. Lecture seule.
    """
    from django.utils import timezone

    if company is None:
        return []
    if today is None:
        today = timezone.localdate()
    qs = (ConformiteEnvironnementale.objects
          .filter(company=company, date_expiration__isnull=False)
          .select_related('responsable')
          .order_by('date_expiration', 'id'))
    a_relancer = []
    for conf in qs:
        etat = conf.statut_calcule(today)
        if etat in (
                ConformiteEnvironnementale.Statut.A_RENOUVELER,
                ConformiteEnvironnementale.Statut.EXPIRE):
            a_relancer.append(conf)
    return a_relancer


# ── QHSE40 — Export reporting des indicateurs ESG ──────────────────────────

def export_esg(company, annee=None):
    """Export reporting des indicateurs ESG d'une société (QHSE40).

    Agrège les ``IndicateurESG`` (lecture seule, scopée société) en un export
    plat groupé par pilier (environnement / social / gouvernance), prêt pour un
    reporting extra-financier (CSRD-like). Un filtre ``annee`` optionnel borne la
    période. Chaque indicateur est normalisé en ligne homogène (code, libellé,
    valeur, cible, unité, période, cible atteinte). Renvoie :

    ``{
        'annee': int|None,
        'total': int,
        'piliers': {
            'environnement': {'nb': N, 'cibles_atteintes': M, 'lignes': [...]},
            'social': {...},
            'gouvernance': {...},
        },
        'lignes': [...],   # à plat, tous piliers confondus
    }``. Aucune mutation, aucun import cross-app.
    """
    if company is None:
        return {'annee': annee, 'total': 0, 'piliers': {}, 'lignes': []}

    qs = IndicateurESG.objects.filter(company=company)
    if annee not in (None, ''):
        qs = qs.filter(annee=annee)
    qs = qs.order_by('pilier', 'code', 'id')

    piliers = {
        IndicateurESG.Pilier.ENVIRONNEMENT: {
            'nb': 0, 'cibles_atteintes': 0, 'lignes': []},
        IndicateurESG.Pilier.SOCIAL: {
            'nb': 0, 'cibles_atteintes': 0, 'lignes': []},
        IndicateurESG.Pilier.GOUVERNANCE: {
            'nb': 0, 'cibles_atteintes': 0, 'lignes': []},
    }
    lignes = []
    for ind in qs:
        atteinte = ind.atteinte_cible
        ligne = {
            'id': ind.id,
            'pilier': ind.pilier,
            'code': ind.code,
            'libelle': ind.libelle,
            'valeur': str(ind.valeur) if ind.valeur is not None else None,
            'cible': str(ind.cible) if ind.cible is not None else None,
            'unite': ind.unite,
            'annee': ind.annee,
            'periode': ind.periode,
            'atteinte_cible': atteinte,
        }
        lignes.append(ligne)
        bucket = piliers.get(ind.pilier)
        if bucket is not None:
            bucket['nb'] += 1
            if atteinte:
                bucket['cibles_atteintes'] += 1
            bucket['lignes'].append(ligne)

    return {
        'annee': annee if annee not in (None, '') else None,
        'total': len(lignes),
        'piliers': piliers,
        'lignes': lignes,
    }


# ── XQHS1 — Étapes légales AT/MP (checklist datée) ──────────────────────────

def etapes_at_a_echeance(company, within_hours=48, now=None):
    """Étapes AT/MP non réalisées à échéance imminente ou déjà hors délai.

    Scopé société. Retient les étapes ``fait_le`` vide dont ``echeance`` tombe
    au plus tard dans ``within_hours`` heures (y compris déjà dépassées) ; les
    étapes sans échéance fixe (suivi ITT, certificat de guérison, conciliation)
    sont exclues de cette fenêtre de rappel. Lecture seule, triée par échéance
    la plus proche d'abord.
    """
    from datetime import timedelta

    from django.utils import timezone

    if company is None:
        return EtapeDeclarationAt.objects.none()
    try:
        within_hours = int(within_hours)
    except (TypeError, ValueError):
        within_hours = 48
    if within_hours < 0:
        within_hours = 0
    if now is None:
        now = timezone.now()
    limite = now + timedelta(hours=within_hours)
    return (EtapeDeclarationAt.objects
            .filter(company=company,
                    fait_le__isnull=True,
                    echeance__isnull=False,
                    echeance__lte=limite)
            .select_related('declaration', 'declaration__accident_travail')
            .order_by('echeance'))


def etapes_declaration(declaration):
    """Étapes légales AT/MP d'une déclaration CNSS, triées par échéance."""
    return declaration.etapes.all().order_by('echeance', 'id')


# ── XQHS3 — Contrôle qualité à la réception fournisseur (advisory) ─────────

def reception_controle_ouvert(reception_id):
    """Un contrôle qualité de réception est-il encore OUVERT pour cette
    réception fournisseur (XQHS3) ?

    Point d'accès ADVISORY pour ``stock`` (badge « contrôle en attente ») —
    lecture seule, ne bloque jamais le flux stock. Renvoie ``True`` si AU
    MOINS UN ``ControleReception`` de cette réception a le verdict
    ``en_attente``. Non scopé société explicitement (l'appelant, ``stock``,
    fournit un id déjà résolu dans sa propre société) — mais reste sûr car
    ``reception_id`` est une clé étrangère opaque, jamais un identifiant
    global partagé entre sociétés.
    """
    return ControleReception.objects.filter(
        reception_id=reception_id,
        verdict=ControleReception.Verdict.EN_ATTENTE,
    ).exists()


def controles_reception_de(reception_id, company=None):
    """Contrôles réception d'une réception fournisseur donnée (lecture seule)."""
    qs = ControleReception.objects.filter(reception_id=reception_id)
    if company is not None:
        qs = qs.filter(company=company)
    return qs.select_related('plan', 'controleur', 'non_conformite')


# ── XQHS4 — Pareto qualité (codes de défauts) ───────────────────────────────

def pareto_defauts(company, *, periode=None, chantier_id=None, famille=None):
    """Top causes de défaut (comptes + % cumulé), agrégées sur NCR + relevés
    en échec + incidents (XQHS4).

    ``periode`` filtre sur ``date_creation`` au format ``YYYY-MM`` (mois),
    ``chantier_id`` filtre les NCR/incidents rattachés à ce chantier,
    ``famille`` restreint aux codes de cette famille. Renvoie une liste
    ``[{'code', 'libelle', 'famille', 'nb', 'pct', 'pct_cumule'}, ...]`` triée
    par nombre décroissant. Lecture seule, scopée société.
    """
    if company is None:
        return []

    def _filtre_periode(qs, champ):
        if not periode:
            return qs
        try:
            annee, mois = periode.split('-')
            return qs.filter(**{
                f'{champ}__year': int(annee), f'{champ}__month': int(mois)})
        except (ValueError, AttributeError):
            return qs

    ncr_qs = NonConformite.objects.filter(
        company=company, code_defaut__isnull=False)
    ncr_qs = _filtre_periode(ncr_qs, 'date_creation')
    if chantier_id is not None:
        ncr_qs = ncr_qs.filter(chantier_id=chantier_id)

    releve_qs = ReleveControle.objects.filter(
        company=company, code_defaut__isnull=False, conforme=False)
    releve_qs = _filtre_periode(releve_qs, 'date_creation')

    incident_qs = Incident.objects.filter(
        company=company, code_defaut__isnull=False)
    incident_qs = _filtre_periode(incident_qs, 'date_creation')
    if chantier_id is not None:
        incident_qs = incident_qs.filter(chantier_id=chantier_id)

    if famille not in (None, ''):
        ncr_qs = ncr_qs.filter(code_defaut__famille=famille)
        releve_qs = releve_qs.filter(code_defaut__famille=famille)
        incident_qs = incident_qs.filter(code_defaut__famille=famille)

    compteur = {}
    for qs in (ncr_qs, releve_qs, incident_qs):
        for code_id, code, libelle, famille_val in qs.values_list(
                'code_defaut_id', 'code_defaut__code',
                'code_defaut__libelle', 'code_defaut__famille'):
            entry = compteur.setdefault(code_id, {
                'code': code, 'libelle': libelle, 'famille': famille_val,
                'nb': 0,
            })
            entry['nb'] += 1

    lignes = sorted(compteur.values(), key=lambda e: (-e['nb'], e['code']))
    total = sum(e['nb'] for e in lignes) or 1
    cumul = 0
    for ligne in lignes:
        ligne['pct'] = round(ligne['nb'] / total * 100, 1)
        cumul += ligne['nb']
        ligne['pct_cumule'] = round(cumul / total * 100, 1)
    return lignes


def taux_conformite_premier_passage(
        company, *, chantier_id=None, equipe_id=None):
    """Taux de conformité premier-passage des relevés de contrôle (XQHS4).

    Un relevé est « premier passage conforme » si ``conforme=True`` — le
    dénominateur ne compte que les relevés déjà STATUÉS (``conforme`` non
    nul). Scopé société ; ``chantier_id`` filtre via le plan chantier (référence
    lâche ``installations.Chantier``). ``equipe_id`` réservé pour une future
    ventilation par équipe (pas encore de modèle équipe côté qhse — no-op si
    fourni, gardé pour compatibilité de signature).
    """
    if company is None:
        return {'total_statues': 0, 'conformes': 0, 'taux': None}

    qs = ReleveControle.objects.filter(
        company=company, conforme__isnull=False)
    if chantier_id is not None:
        qs = qs.filter(plan_chantier__chantier_id=chantier_id)

    total = qs.count()
    conformes = qs.filter(conforme=True).count()
    taux = round(conformes / total * 100, 1) if total else None
    return {'total_statues': total, 'conformes': conformes, 'taux': taux}


# ── XQHS6 — SCAR par fournisseur (advisory, exposé au scorecard stock) ──────

def scar_count_par_fournisseur(company, fournisseur_id):
    """Compte SCAR ouvertes/répétées d'un fournisseur (XQHS6).

    Point d'entrée destiné à être lu par ``apps.stock`` (le scorecard
    fournisseur l'affiche en ADVISORY, jamais un import de modèle qhse côté
    stock). Renvoie ``{'total': int, 'ouvertes': int}`` — ``ouvertes`` exclut
    les SCAR ``close``.
    """
    qs = DemandeActionFournisseur.objects.filter(
        company=company, fournisseur_id=fournisseur_id)
    total = qs.count()
    ouvertes = qs.exclude(
        statut=DemandeActionFournisseur.Statut.CLOSE).count()
    return {'total': total, 'ouvertes': ouvertes}


# ── XQHS11 — Heatmap constats-par-clause + readiness multi-référentiel ─────

def constats_par_clause(company, referentiel=None):
    """Heatmap des non-conformités d'audit agrégées par clause ISO (XQHS11).

    Compte les ``ReponseCritere`` NON CONFORMES dont le critère porte une
    ``clause`` (les critères sans clause sont exclus — rien à cartographier).
    Renvoie une liste de dicts ``{'clause': str, 'referentiel': str,
    'nb_non_conformes': int}`` triée par nb décroissant.
    """
    qs = ReponseCritere.objects.filter(
        company=company, resultat=ReponseCritere.Resultat.NON_CONFORME,
        critere__clause__gt='')
    if referentiel:
        qs = qs.filter(critere__referentiel=referentiel)

    counts = {}
    for clause, ref in qs.values_list('critere__clause', 'critere__referentiel'):
        key = (clause, ref)
        counts[key] = counts.get(key, 0) + 1

    result = [
        {'clause': clause, 'referentiel': ref, 'nb_non_conformes': nb}
        for (clause, ref), nb in counts.items()
    ]
    result.sort(key=lambda item: -item['nb_non_conformes'])
    return result


def readiness_multi_referentiel(company):
    """Readiness étendu par référentiel (9001/14001/45001, XQHS11).

    Pour chaque référentiel avec des clauses seedées, calcule le % de clauses
    couvertes par AU MOINS UN critère audité CONFORME (une clause « couverte »
    a une ``ReponseCritere`` conforme sur un critère qui la référence).
    Renvoie ``{referentiel: {'total_clauses': int, 'couvertes': int, 'pct':
    float|None}}``.
    """
    result = {}
    referentiels = ClauseNorme.objects.filter(
        company=company).values_list('referentiel', flat=True).distinct()
    for referentiel in referentiels:
        clauses = set(
            ClauseNorme.objects.filter(
                company=company, referentiel=referentiel
            ).values_list('numero', flat=True))
        total = len(clauses)
        if total == 0:
            result[referentiel] = {
                'total_clauses': 0, 'couvertes': 0, 'pct': None}
            continue

        clauses_conformes = set(
            CritereAudit.objects.filter(
                company=company, referentiel=referentiel,
                qhse_reponses__resultat=ReponseCritere.Resultat.CONFORME,
            ).values_list('clause', flat=True))
        couvertes = len(clauses & clauses_conformes)
        pct = round(couvertes / total * 100, 1)
        result[referentiel] = {
            'total_clauses': total, 'couvertes': couvertes, 'pct': pct}
    return result


# ── XQHS13 — Trajectoire baseline → cible vs réel (cockpit) ────────────────

def trajectoire_objectif(objectif):
    """Trajectoire baseline→cible vs réel d'un ``ObjectifQhse`` (XQHS13).

    Renvoie ``{'baseline': ..., 'cible': ..., 'echeance': ..., 'points':
    [{'periode': str, 'valeur': Decimal, 'atteint': bool|None}, ...]}`` —
    ``points`` est l'historique des ``RevueObjectif`` triées chronologiquement
    (ordre croissant, pour un tracé de courbe direct côté frontend).
    """
    revues = list(
        objectif.revues.order_by('date_revue', 'id').values(
            'periode', 'valeur_constatee', 'atteint', 'date_revue'))
    return {
        'baseline': objectif.valeur_baseline,
        'cible': objectif.valeur_cible,
        'echeance': objectif.echeance,
        'points': [
            {
                'periode': r['periode'],
                'valeur': r['valeur_constatee'],
                'atteint': r['atteint'],
                'date_revue': r['date_revue'],
            }
            for r in revues
        ],
    }


def objectifs_revue_due(company, today=None):
    """Objectifs dont la revue périodique est due (XQHS13, relance).

    « Due » = aucune ``RevueObjectif`` dans la fenêtre de fréquence depuis la
    dernière revue (ou jamais revu). Renvoie la liste des ``ObjectifQhse``.
    """
    from datetime import timedelta

    from django.utils import timezone

    if today is None:
        today = timezone.localdate()

    jours_par_frequence = {
        ObjectifQhse.Frequence.MENSUELLE: 30,
        ObjectifQhse.Frequence.TRIMESTRIELLE: 90,
        ObjectifQhse.Frequence.SEMESTRIELLE: 180,
        ObjectifQhse.Frequence.ANNUELLE: 365,
    }

    dus = []
    for objectif in ObjectifQhse.objects.filter(company=company):
        derniere = objectif.revues.order_by('-date_revue', '-id').first()
        if derniere is None or derniere.date_revue is None:
            dus.append(objectif)
            continue
        delai = jours_par_frequence.get(objectif.frequence_revue, 90)
        if today >= derniere.date_revue + timedelta(days=delai):
            dus.append(objectif)
    return dus


# ── XQHS15 — % conformité de lecture par procédure (cockpit) ───────────────

def conformite_lecture_procedure(company, reference):
    """% de conformité de lecture pour une référence de procédure (XQHS15).

    Agrège TOUTES les diffusions de TOUTES les versions de la ``reference``
    (une référence versionnée reste UNE procédure du point de vue du cockpit).
    Renvoie ``{'total': int, 'lus': int, 'pct': float|None}``.
    """
    diffusions = DiffusionProcedure.objects.filter(
        company=company, procedure__reference=reference)
    total = 0
    lus = 0
    for diffusion in diffusions:
        accuses = diffusion.accuses_lecture.all()
        total += accuses.count()
        lus += accuses.filter(lu_le__isnull=False).count()
    pct = round(lus / total * 100, 1) if total else None
    return {'total': total, 'lus': lus, 'pct': pct}


# ── XQHS20 — Registre des aspects & impacts environnementaux (ISO 14001) ───

def aspects_environnementaux_a_revoir(company, today=None):
    """Aspects environnementaux dont la revue est due (XQHS20, pattern
    ``conformites_a_relancer`` QHSE38) : ``date_revue`` absente OU dépassée.
    Agrégation PURE — aucune mutation."""
    from django.utils import timezone

    from .models import AspectEnvironnemental

    if today is None:
        today = timezone.localdate()
    qs = AspectEnvironnemental.objects.filter(company=company)
    return [
        aspect for aspect in qs
        if aspect.date_revue is None or aspect.date_revue <= today
    ]


# ── XQHS22 — Coût de la non-qualité (CoQ), interne uniquement ──────────────

def cout_non_qualite(company, annee):
    """Rollup du coût de la non-qualité (XQHS22), ventilé par catégorie
    (défaillance interne / défaillance externe / prévention-évaluation) et par
    mois. Agrégation PURE — aucune mutation. Montants INTERNES uniquement
    (jamais exposés côté client — gardé par ``cout_non_qualite_voir`` côté vue).

    Catégorisation :
      * défaillance INTERNE — NCR sans ticket SAV d'origine (chantier/retouche).
      * défaillance EXTERNE — NCR nées d'un ticket SAV (garantie/panne client)
        + incidents (déjà survenus, coût de correction).
      * prévention-évaluation — comptage simple des audits/inspections (pas de
        coût direct saisi ici : indicateur d'effort, pas un montant).

    Renvoie ``{'annee': int, 'interne': Decimal, 'externe': Decimal,
    'prevention_evaluation_count': int, 'par_mois': [...], 'total': Decimal}``.
    """
    from decimal import Decimal

    from .models import ActionCorrectivePreventive, Audit, Incident, \
        InspectionSecurite, NonConformite

    interne = Decimal('0')
    externe = Decimal('0')
    par_mois = {}

    def _bucket(mois):
        return par_mois.setdefault(
            mois, {'mois': mois, 'interne': Decimal('0'), 'externe': Decimal('0')})

    ncrs = NonConformite.objects.filter(
        company=company, date_creation__year=annee)
    for ncr in ncrs:
        cout = ncr.cout_reel if ncr.cout_reel is not None else ncr.cout_estime
        cout = cout or Decimal('0')
        est_externe = bool(getattr(ncr, 'ticket_sav_id', None))
        if est_externe:
            externe += cout
        else:
            interne += cout
        mois = ncr.date_creation.strftime('%Y-%m')
        bucket = _bucket(mois)
        bucket['externe' if est_externe else 'interne'] += cout

    capas = ActionCorrectivePreventive.objects.filter(
        company=company, date_creation__year=annee)
    for capa in capas:
        cout = capa.cout or Decimal('0')
        interne += cout
        mois = capa.date_creation.strftime('%Y-%m')
        _bucket(mois)['interne'] += cout

    incidents = Incident.objects.filter(
        company=company, date_creation__year=annee)
    for incident in incidents:
        cout = incident.cout or Decimal('0')
        externe += cout
        mois = incident.date_creation.strftime('%Y-%m')
        _bucket(mois)['externe'] += cout

    prevention_evaluation_count = (
        Audit.objects.filter(company=company, date_creation__year=annee).count()
        + InspectionSecurite.objects.filter(
            company=company, date_creation__year=annee).count()
    )

    return {
        'annee': annee,
        'interne': interne,
        'externe': externe,
        'prevention_evaluation_count': prevention_evaluation_count,
        'par_mois': [par_mois[k] for k in sorted(par_mois)],
        'total': interne + externe,
    }


# ── XQHS23 — Pont SAV ↔ NCR : taux de défaillance par produit ──────────────

def taux_defaillance_par_produit(company):
    """NCR d'origine SAV (``ticket_sav`` posé) groupées par produit, via les
    équipements du parc lus par ``sav.selectors.produits_par_tickets`` (jamais
    un import direct de ``sav.models``/``stock.models``).

    Renvoie une liste triée par nombre de NCR décroissant ::

        [{'produit_id': int|None, 'produit_nom': str|None, 'nb_ncr': int}, …]

    Une entrée ``produit_id=None`` regroupe les NCR dont le ticket n'a pas
    d'équipement identifié (ticket sans appareil précis)."""
    from .models import NonConformite

    ncrs = NonConformite.objects.filter(
        company=company, ticket_sav_id__isnull=False)
    ticket_ids = list(ncrs.values_list('ticket_sav_id', flat=True))
    if not ticket_ids:
        return []

    from apps.sav.selectors import produits_par_tickets

    mapping = produits_par_tickets(company, ticket_ids)

    comptes = {}
    for ncr in ncrs:
        info = mapping.get(ncr.ticket_sav_id) or {
            'produit_id': None, 'produit_nom': None}
        cle = info['produit_id']
        bucket = comptes.setdefault(
            cle, {'produit_id': cle, 'produit_nom': info['produit_nom'],
                  'nb_ncr': 0})
        bucket['nb_ncr'] += 1

    return sorted(
        comptes.values(), key=lambda b: b['nb_ncr'], reverse=True)
