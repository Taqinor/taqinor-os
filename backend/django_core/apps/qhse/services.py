"""Services QHSE — orchestration intra-app.

``instancier_plan_chantier`` ouvre un ``PlanInspectionChantier`` à partir d'un
modèle ITP (``PlanInspectionModele``) sur un chantier (référence lâche par id)
et matérialise un ``ReleveControle`` par point de contrôle du modèle. L'opération
est idempotente : ré-appelée pour le même couple (modèle, chantier, société),
elle réutilise le plan existant et n'ajoute que les relevés manquants.
"""
from decimal import Decimal

from django.db import transaction

from .models import (
    ActionCorrectivePreventive, CauseIncident, NonConformite,
    NotationFinChantier, PlanInspectionChantier, PointControleModele,
    ProcedureQualite, ReponseCritere, ReleveControle,
)


@transaction.atomic
def instancier_plan_chantier(modele, chantier_id, company, date_ouverture=None):
    """Crée (ou réutilise) le plan d'inspection d'un chantier et ses relevés.

    * ``modele`` — un ``PlanInspectionModele`` de la même société.
    * ``chantier_id`` — référence lâche au chantier (jamais un import
      ``installations``).
    * ``company`` — la société, posée côté serveur.

    Idempotent : un seul ``PlanInspectionChantier`` par (modèle, chantier,
    société) ; un seul ``ReleveControle`` par point du modèle. Ré-appeler la
    fonction ne duplique rien et complète seulement les relevés manquants
    (utile si le modèle a gagné des points entre-temps).

    Retourne le ``PlanInspectionChantier``.
    """
    if modele.company_id != company.id:
        raise ValueError("Le modèle d'ITP appartient à une autre société.")

    plan, _ = PlanInspectionChantier.objects.get_or_create(
        company=company,
        modele=modele,
        chantier_id=chantier_id,
        defaults={'date_ouverture': date_ouverture},
    )

    existants = set(
        plan.releves.values_list('point_id', flat=True))
    points = PointControleModele.objects.filter(plan=modele)
    a_creer = [
        ReleveControle(company=company, plan_chantier=plan, point=point)
        for point in points
        if point.id not in existants
    ]
    if a_creer:
        ReleveControle.objects.bulk_create(a_creer)

    return plan


# ── QHSE11 — Pont Réserve (installations.Reserve) → NCR ─────────────────────

@transaction.atomic
def creer_ncr_depuis_reserve(reserve_id, company, signale_par=None,
                             gravite=None):
    """Crée une non-conformité (NCR) à partir d'une réserve de chantier.

    Pont cross-app conforme : la ``Reserve`` est lue via le sélecteur LECTURE
    SEULE de ``installations`` (``reserve_scoped`` / ``reserve_resume``) — jamais
    par un import de ``installations.models`` — et la NCR garde un lien lâche
    (FK chaîne ``installations.Reserve``).

    Idempotent : une seule NCR par réserve. Ré-appeler la fonction renvoie la
    NCR existante sans en créer une seconde. Renvoie ``(ncr, created)``.

    Lève ``ValueError`` si la réserve n'existe pas dans la société.
    """
    from apps.installations.selectors import reserve_resume, reserve_scoped

    reserve = reserve_scoped(company, reserve_id)
    if reserve is None:
        raise ValueError("Réserve introuvable dans votre société.")

    existante = NonConformite.objects.filter(
        company=company, reserve_id=reserve.id).first()
    if existante is not None:
        return existante, False

    resume = reserve_resume(reserve)
    description = resume['description']
    titre = (
        f'Réserve · {description[:80]}' if description
        else f'Réserve #{resume["id"]}')
    ncr = NonConformite.objects.create(
        company=company,
        titre=titre,
        description=description,
        origine='Réserve de fin de chantier',
        gravite=gravite or NonConformite.Gravite.MINEURE,
        chantier_id=resume['chantier_id'],
        reserve_id=reserve.id,
        signale_par=signale_par,
    )
    return ncr, True


# ── QHSE12 — Relances CAPA en retard (notifications / digest) ───────────────

def relancer_capa_en_retard(company, today=None):
    """Relance les CAPA en retard d'une société (notification au responsable).

    Pour chaque CAPA échue et non résolue (cf. ``selectors.capa_en_retard``),
    émet une notification in-app au responsable (best-effort via
    ``notifications.notify`` — jamais d'exception remontée ; une CAPA sans
    responsable est comptée mais non notifiée). Réutilise l'``EventType``
    existant ``MAINTENANCE_DUE`` (échéance interne dépassée) pour rester additif.

    Renvoie un *digest* : ``{'total': N, 'notifiees': M, 'sans_responsable': K,
    'items': [...]}`` où ``items`` résume chaque CAPA en retard (id, description,
    échéance, responsable, jours de retard). Ne mute aucune CAPA.
    """
    from django.utils import timezone

    from apps.qhse.selectors import capa_en_retard

    if today is None:
        today = timezone.localdate()
    retards = list(capa_en_retard(company, today=today))

    notifiees = 0
    sans_responsable = 0
    items = []
    for capa in retards:
        jours = (today - capa.echeance).days
        ncr = capa.non_conformite
        titre = 'CAPA en retard'
        corps = (
            f"L'action « {capa.description[:80]} » liée à la non-conformité "
            f"« {ncr.titre} » est en retard de {jours} jour(s) "
            f"(échéance {capa.echeance.isoformat()}).")
        if capa.responsable_id is not None:
            _notifier_capa(capa.responsable, titre, corps, company)
            notifiees += 1
        else:
            sans_responsable += 1
        items.append({
            'capa_id': capa.id,
            'description': capa.description,
            'echeance': capa.echeance.isoformat(),
            'jours_retard': jours,
            'responsable_id': capa.responsable_id,
            'non_conformite_id': capa.non_conformite_id,
        })

    return {
        'total': len(retards),
        'notifiees': notifiees,
        'sans_responsable': sans_responsable,
        'items': items,
    }


def _notifier_capa(user, titre, corps, company):
    """Notifie un responsable d'une CAPA en retard (best-effort, sans erreur)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/capa', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── QHSE13 — Vérification d'efficacité CAPA (clôture conditionnée) ──────────

@transaction.atomic
def verifier_efficacite_capa(capa, efficace, verifiee_par=None, commentaire=''):
    """Enregistre la vérification d'efficacité d'une CAPA (QHSE13).

    Une CAPA ne peut être vérifiée qu'une fois RÉALISÉE (le traitement est
    terminé, on en mesure l'effet). Selon le verdict :

    * ``efficace=True``  → la CAPA passe au statut ``VERIFIEE`` (elle devient
      clôturable au niveau de la non-conformité) ;
    * ``efficace=False`` → l'action n'a pas réglé l'écart : la CAPA repasse
      ``EN_COURS`` pour relancer le traitement.

    Pose ``efficace`` / ``commentaire_verification`` / ``date_verification`` /
    ``verifiee_par``. Lève ``ValueError`` si la CAPA n'est pas réalisée.
    Renvoie la CAPA.
    """
    from django.utils import timezone

    S = ActionCorrectivePreventive.Statut
    if capa.statut not in (S.REALISEE, S.VERIFIEE):
        raise ValueError(
            "La CAPA doit être réalisée avant la vérification d'efficacité.")

    capa.efficace = bool(efficace)
    capa.commentaire_verification = commentaire or ''
    capa.date_verification = timezone.now()
    capa.verifiee_par = verifiee_par
    capa.statut = S.VERIFIEE if capa.efficace else S.EN_COURS
    capa.save(update_fields=[
        'efficace', 'commentaire_verification', 'date_verification',
        'verifiee_par', 'statut'])
    return capa


# ── QHSE16 — Audit : score + levée de NCR ──────────────────────────────────

@transaction.atomic
def calculer_score_audit(audit):
    """Calcule et stocke le score pondéré d'un ``Audit`` (% conforme, 0–100).

    Seuls les critères avec résultat ``CONFORME`` ou ``NON_CONFORME`` entrent
    dans le calcul (les ``NA`` sont exclus des numérateur ET dénominateur). Si
    aucun critère applicable n'est renseigné, le score reste ``None``.

    Retourne l'``Audit`` avec ``score`` mis à jour et sauvegardé.
    """
    reponses = list(
        audit.qhse_reponses.select_related('critere').all()
    )
    poids_conforme = Decimal('0')
    poids_total = Decimal('0')
    for rep in reponses:
        if rep.resultat == ReponseCritere.Resultat.NA:
            continue
        poids = Decimal(rep.critere.poids)
        poids_total += poids
        if rep.resultat == ReponseCritere.Resultat.CONFORME:
            poids_conforme += poids

    if poids_total == 0:
        audit.score = None
    else:
        audit.score = (poids_conforme / poids_total * 100).quantize(
            Decimal('0.01'))
    audit.save(update_fields=['score'])
    return audit


@transaction.atomic
def lever_ncr_audit(audit, signale_par=None):
    """Lève une ``NonConformite`` pour chaque réponse non conforme de l'audit.

    Idempotent : si une NCR est déjà enregistrée pour une ``ReponseCritere``
    (``ncr_id`` non nul), elle n'est pas dupliquée. Seules les réponses
    ``NON_CONFORME`` sans NCR existante génèrent une nouvelle NCR.

    Retourne un dict ``{'creees': [ncr_id, ...], 'existantes': [ncr_id, ...]}``.
    """
    reponses_nc = list(
        audit.qhse_reponses.filter(
            resultat=ReponseCritere.Resultat.NON_CONFORME
        ).select_related('critere').all()
    )

    creees = []
    existantes = []
    for rep in reponses_nc:
        if rep.ncr_id is not None:
            existantes.append(rep.ncr_id)
            continue
        titre = (
            f'[Audit] {rep.critere.intitule[:120]}'
        )
        description = rep.note or (
            f'Non-conformité détectée lors de l\'audit du '
            f'{audit.date_audit or "date inconnue"} '
            f'sur le critère « {rep.critere.intitule} ».'
        )
        ncr = NonConformite.objects.create(
            company=audit.company,
            titre=titre,
            description=description,
            origine=f'Audit — {audit.grille.nom}',
            gravite=NonConformite.Gravite.MINEURE,
            chantier_id=audit.chantier_id,
            signale_par=signale_par,
        )
        rep.ncr_id = ncr.id
        rep.save(update_fields=['ncr_id'])
        creees.append(ncr.id)

    return {'creees': creees, 'existantes': existantes}


def ncr_capa_bloquantes(ncr):
    """CAPA qui empêchent la clôture d'une non-conformité (QHSE13).

    Une NCR ne peut être clôturée que si CHACUNE de ses CAPA est vérifiée
    efficace (``statut=VERIFIEE`` ET ``efficace=True``). Renvoie la liste des
    CAPA non encore vérifiées efficaces. Lecture seule.
    """
    S = ActionCorrectivePreventive.Statut
    return [
        capa for capa in ncr.actions.all()
        if not (capa.statut == S.VERIFIEE and capa.efficace is True)
    ]


@transaction.atomic
def cloturer_ncr(ncr):
    """Clôture une non-conformité — conditionnée à l'efficacité des CAPA (QHSE13).

    La clôture n'est autorisée que si toutes les CAPA de la NCR sont vérifiées
    efficaces (cf. ``ncr_capa_bloquantes``). Lève ``ValueError`` avec la liste
    des CAPA bloquantes sinon. Idempotent si déjà clôturée. Renvoie la NCR.
    """
    if ncr.statut == NonConformite.Statut.CLOTUREE:
        return ncr
    bloquantes = ncr_capa_bloquantes(ncr)
    if bloquantes:
        raise ValueError(
            "Clôture impossible : %d action(s) corrective(s) non vérifiée(s) "
            "efficace(s)." % len(bloquantes))
    ncr.statut = NonConformite.Statut.CLOTUREE
    ncr.save(update_fields=['statut'])
    return ncr


# ── QHSE17 — Score de notation fin de chantier ──────────────────────────────

@transaction.atomic
def calculer_score_notation(notation):
    """Calcule et stocke le score pondéré d'une ``NotationFinChantier``.

    Agrège les ``ItemNotation`` conformes (``conforme=True``) pondérés en
    pourcentage du total des items renseignés (``conforme`` non nul). Les items
    dont ``conforme`` est ``None`` (pas encore évalués) sont exclus du calcul
    (identique au comportement NA des audits). Si aucun item n'est renseigné,
    ``score`` reste ``None`` et ``verdict`` reste ``None``.

    Le ``verdict`` (``passe`` / ``echec``) est dérivé automatiquement : score ≥
    ``seuil_passage`` → PASSE, score < seuil_passage → ECHEC.

    Retourne la ``notation`` avec ``score`` et ``verdict`` mis à jour et sauvegardés.
    """
    items = list(notation.items.all())
    poids_conforme = Decimal('0')
    poids_total = Decimal('0')
    for item in items:
        if item.conforme is None:
            continue
        poids = Decimal(item.poids)
        poids_total += poids
        if item.conforme:
            poids_conforme += poids

    if poids_total == 0:
        notation.score = None
        notation.verdict = None
    else:
        notation.score = (poids_conforme / poids_total * 100).quantize(
            Decimal('0.01'))
        seuil = Decimal(notation.seuil_passage)
        notation.verdict = (
            NotationFinChantier.Verdict.PASSE
            if notation.score >= seuil
            else NotationFinChantier.Verdict.ECHEC
        )
    notation.save(update_fields=['score', 'verdict'])
    return notation


# ── QHSE18 — Procédure qualité versionnée (docs qualité GED) ────────────────

@transaction.atomic
def nouvelle_version_procedure(company, reference, titre, *, contenu='',
                               document_id=None, auteur=None,
                               date_application=None):
    """Crée la version SUIVANTE d'une procédure qualité (additif, non destructif).

    La version est calculée côté serveur : ``max(version de la référence) + 1``
    pour ce couple (société, ``reference``), via un ``select_for_update`` qui
    sérialise les créations concurrentes (jamais ``count()+1``). La première
    version d'une référence inédite est la v1. Rien n'est écrasé : chaque appel
    AJOUTE une ligne, préservant l'historique complet (comme
    ``ged.services.add_version``).

    Le ``document_id`` est une référence lâche au document GED (jamais un import
    cross-app de ``ged.models``). La nouvelle version naît en ``brouillon`` ;
    l'entrée en vigueur passe par ``activer_procedure``.

    Renvoie la ``ProcedureQualite`` créée.
    """
    last = (ProcedureQualite.objects
            .select_for_update()
            .filter(company=company, reference=reference)
            .order_by('-version')
            .first())
    next_version = (last.version + 1) if last else 1
    return ProcedureQualite.objects.create(
        company=company,
        reference=reference,
        titre=titre,
        version=next_version,
        statut=ProcedureQualite.Statut.BROUILLON,
        contenu=contenu or '',
        document_id=document_id,
        auteur=auteur,
        date_application=date_application,
    )


@transaction.atomic
def activer_procedure(procedure, date_application=None):
    """Met une version de procédure EN VIGUEUR et rend les autres obsolètes.

    Une seule version d'une référence est ``en_vigueur`` à la fois : cette
    version passe ``EN_VIGUEUR`` et toutes les autres versions de la même
    référence (même société) qui étaient en vigueur deviennent ``OBSOLETE``.
    L'historique reste intact (aucune suppression). Renvoie la ``procedure``.
    """
    from django.utils import timezone

    S = ProcedureQualite.Statut
    (ProcedureQualite.objects
        .filter(company=procedure.company, reference=procedure.reference,
                statut=S.EN_VIGUEUR)
        .exclude(pk=procedure.pk)
        .update(statut=S.OBSOLETE))
    procedure.statut = S.EN_VIGUEUR
    procedure.date_application = date_application or timezone.localdate()
    procedure.save(update_fields=['statut', 'date_application'])
    return procedure


# ── QHSE22 — Gate « document unique requis avant pose » ─────────────────────

# Messages de refus lisibles par motif (rendu côté appelant — p. ex.
# ``installations`` qui GATE la transition vers « pose »).
_DUER_MOTIF_MESSAGES = {
    'aucune_evaluation': (
        "Aucun document unique d'évaluation des risques (DUERP) n'a été créé "
        "pour ce chantier ; il est requis avant la pose."),
    'aucune_validee': (
        "Le document unique d'évaluation des risques (DUERP) du chantier n'est "
        "pas validé ; il doit l'être avant la pose."),
    'validee_sans_lignes': (
        "Le document unique d'évaluation des risques (DUERP) validé ne contient "
        "aucun risque évalué ; au moins une ligne est requise avant la pose."),
}


def exiger_document_unique(company, chantier_id):
    """Exige un document unique validé avant la pose (gate, QHSE22).

    Porte publique pour les autres apps (typiquement ``installations``, qui
    l'appelle pour GATER la transition d'un chantier vers « pose ») : laisse
    passer SI ``selectors.document_unique_valide`` confirme un DUERP ``validee``
    non vide pour le chantier (scopé société), sinon lève une
    ``django.core.exceptions.ValidationError`` au message clair selon le motif
    (aucune évaluation / aucune validée / validée sans lignes).

    Référence LÂCHE au chantier par ``chantier_id`` — aucun import cross-app de
    ``installations`` ici ; l'appelant fournit l'id et capte l'exception. Aucune
    mutation. Retourne le dict de statut (cf. ``document_unique_valide``) en cas
    de succès, ce qui en fait aussi un assertion réutilisable.
    """
    from django.core.exceptions import ValidationError

    from .selectors import document_unique_valide

    statut = document_unique_valide(company, chantier_id)
    if not statut['valide']:
        message = _DUER_MOTIF_MESSAGES.get(
            statut['motif'],
            "Un document unique d'évaluation des risques validé est requis "
            "avant la pose.")
        raise ValidationError(message, code=statut['motif'] or 'duer_requis')
    return statut


# ── QHSE31 — Analyse d'incident (arbre des causes) → CAPA ───────────────────

@transaction.atomic
def generer_capa_depuis_analyse(analyse, *, description=None,
                                type_action=None, responsable=None,
                                echeance=None, cause_racine=None):
    """Génère une CAPA à partir d'une analyse d'incident (QHSE31).

    Mirroir EXACT du linkage NCR → CAPA déjà en place (cf. ``lever_ncr_audit`` /
    ``creer_ncr_depuis_reserve``) : la ``ActionCorrectivePreventive`` existante
    porte un FK NON nul vers ``NonConformite``. On crée donc, à la PREMIÈRE
    génération, une NCR-pont depuis l'``Incident`` de l'analyse (origine
    « Analyse d'incident »), on la rattache à l'analyse (``analyse.non_conformite``)
    puis on crée la CAPA sur cette NCR. Les générations suivantes RÉUTILISENT la
    NCR-pont (jamais de doublon) et ajoutent une CAPA de plus.

    La ``cause_racine`` de la CAPA est, par défaut, le libellé de la cause racine
    de l'arbre (si présente), sinon la synthèse de l'analyse. Renvoie la CAPA
    créée.
    """
    company = analyse.company
    incident = analyse.incident

    ncr = analyse.non_conformite
    if ncr is None:
        titre = f'Analyse incident — {incident.titre}'[:255]
        ncr = NonConformite.objects.create(
            company=company,
            titre=titre,
            description=analyse.synthese or analyse.description or '',
            origine="Analyse d'incident",
            gravite=NonConformite.Gravite.MINEURE,
            chantier_id=incident.chantier_id,
            signale_par=analyse.analyste,
        )
        analyse.non_conformite = ncr
        analyse.save(update_fields=['non_conformite'])

    if cause_racine is None:
        racine = analyse.causes.filter(
            type_cause=CauseIncident.TypeCause.CAUSE_RACINE).first()
        cause_racine = racine.libelle if racine else (analyse.synthese or '')

    capa = ActionCorrectivePreventive.objects.create(
        company=company,
        non_conformite=ncr,
        type_action=(
            type_action or ActionCorrectivePreventive.Type.CORRECTIVE),
        description=description or (
            f"Action corrective suite à l'analyse de l'incident "
            f"« {incident.titre} »."),
        cause_racine=cause_racine or '',
        responsable=responsable,
        echeance=echeance,
    )
    return capa


# ── QHSE33 — Inspection sécurité planifiée → NCR ───────────────────────────

@transaction.atomic
def lever_ncr_inspection(inspection, gravite=None, signale_par=None):
    """Lève une non-conformité (NCR) depuis une inspection sécurité (QHSE33).

    Conditionnée à un résultat NON CONFORME : une inspection conforme ou en
    attente ne lève pas de NCR (``ValueError``). Idempotent : une seule NCR par
    inspection — ré-appelée, elle renvoie ``(ncr, False)``. La NCR garde la
    référence lâche au chantier (``chantier_id``) et reprend les observations
    comme description. ``company``/``signale_par`` posés côté serveur.

    Renvoie ``(ncr, created)``.
    """
    from .models import InspectionSecurite, NonConformite

    if inspection.resultat != InspectionSecurite.Resultat.NON_CONFORME:
        raise ValueError(
            'Seule une inspection NON CONFORME peut lever une NCR.')

    if inspection.ncr_id is not None:
        return inspection.ncr, False

    company = inspection.company
    titre = f'Inspection sécurité — {inspection.titre}'[:255]
    ncr = NonConformite.objects.create(
        company=company,
        titre=titre,
        description=inspection.observations or '',
        origine='Inspection sécurité',
        gravite=gravite or NonConformite.Gravite.MINEURE,
        chantier_id=inspection.chantier_id,
        signale_par=signale_par,
    )
    inspection.ncr = ncr
    inspection.save(update_fields=['ncr'])
    return ncr, True
