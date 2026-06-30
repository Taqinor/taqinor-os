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
    ActionCorrectivePreventive, Audit, DeclarationCnss, EvaluationRisque,
    NonConformite, NotationFinChantier, PermisTravail, PlanInspectionChantier,
    ProcedureQualite, ReleveControle, ReleveCourbeIV, RetourClientQualite,
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
