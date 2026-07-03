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
    ActionCorrectivePreventive, CampagneRappel, CauseIncident,
    CheckinSecurite, ControleReception,
    DeclarationCnss, Derogation, ElementRappel, EtapeDeclarationAt,
    NonConformite,
    NotationFinChantier, PlanControleReception, PlanInspectionChantier,
    PointControleModele,
    ProcedureQualite, ReleveThermographie, ReponseCritere, ReleveControle,
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


# ── XMFG13 — Pont Contrôle qualité d'assemblage → NCR ────────────────────────

@transaction.atomic
def creer_ncr_depuis_controle_assemblage(*, company, ordre_id, titre,
                                         description='', gravite=None,
                                         signale_par=None):
    """Crée une non-conformité (NCR) à partir d'un item de checklist QC en
    échec sur un ordre d'assemblage (XMFG13). Écriture FINE, cross-app
    conforme : l'appelant (`installations`) ne fait que passer les données déjà
    résolues (id + titre + description) — jamais d'import du modèle
    `installations.OrdreAssemblage` ici. Lien lâche via FK chaîne
    `ordre_assemblage`. Idempotent : une seule NCR ouverte par (ordre, titre) ;
    ré-appeler renvoie la NCR existante. Renvoie ``(ncr, created)``."""
    existante = NonConformite.objects.filter(
        company=company, ordre_assemblage_id=ordre_id, titre=titre,
        statut__in=[NonConformite.Statut.OUVERTE,
                    NonConformite.Statut.EN_TRAITEMENT]).first()
    if existante is not None:
        return existante, False

    ncr = NonConformite.objects.create(
        company=company,
        titre=titre,
        description=description,
        origine="Contrôle qualité d'assemblage",
        gravite=gravite or NonConformite.Gravite.MINEURE,
        ordre_assemblage_id=ordre_id,
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
    """Clôture une non-conformité — conditionnée à l'efficacité des CAPA (QHSE13)
    ET à une disposition posée (XQHS2).

    La clôture n'est autorisée que si (a) toutes les CAPA de la NCR sont
    vérifiées efficaces (cf. ``ncr_capa_bloquantes``) ET (b) une disposition a
    été posée (``disposition`` non vide). Lève ``ValueError`` sinon. Idempotent
    si déjà clôturée. Renvoie la NCR.
    """
    if ncr.statut == NonConformite.Statut.CLOTUREE:
        return ncr
    bloquantes = ncr_capa_bloquantes(ncr)
    if bloquantes:
        raise ValueError(
            "Clôture impossible : %d action(s) corrective(s) non vérifiée(s) "
            "efficace(s)." % len(bloquantes))
    if not ncr.disposition:
        raise ValueError(
            "Clôture impossible : aucune disposition n'a été posée sur "
            "cette non-conformité.")
    ncr.statut = NonConformite.Statut.CLOTUREE
    ncr.save(update_fields=['statut'])
    return ncr


# ── XQHS2 — Disposition de la NCR + dérogations ─────────────────────────────

@transaction.atomic
def poser_disposition(
        ncr, disposition, *, disposition_par=None, cout_disposition=None,
        fournisseur=None, creer_capa_retouche=False, capa_description=''):
    """Pose la disposition d'une non-conformité (XQHS2).

    ``disposition_par``/``disposition_le`` sont posés CÔTÉ SERVEUR (jamais lus
    du corps). Si ``disposition == RETOUCHE`` et ``creer_capa_retouche=True``,
    pré-remplit une CAPA corrective liée (mêmes valeurs par défaut que le
    linkage NCR→CAPA existant). Si ``disposition == RETOUR_FOURNISSEUR``, le
    ``fournisseur`` (référence FK-chaîne ``stock.Fournisseur``) est requis et
    posé. Renvoie la NCR mise à jour.
    """
    from django.utils import timezone

    valeurs_valides = {c.value for c in NonConformite.Disposition}
    if disposition not in valeurs_valides:
        raise ValueError(f'Disposition invalide : {disposition!r}')

    ncr.disposition = disposition
    ncr.disposition_par = disposition_par
    ncr.disposition_le = timezone.now()
    if cout_disposition is not None:
        ncr.cout_disposition = cout_disposition
    if disposition == NonConformite.Disposition.RETOUR_FOURNISSEUR:
        ncr.fournisseur = fournisseur
    ncr.save(update_fields=[
        'disposition', 'disposition_par', 'disposition_le',
        'cout_disposition', 'fournisseur'])

    if (disposition == NonConformite.Disposition.RETOUCHE
            and creer_capa_retouche):
        ActionCorrectivePreventive.objects.create(
            company=ncr.company,
            non_conformite=ncr,
            type_action=ActionCorrectivePreventive.Type.CORRECTIVE,
            description=capa_description or (
                f'Retouche suite à disposition NCR « {ncr.titre} »'),
        )
    return ncr


def derogations_a_relancer(company, today=None):
    """Dérogations actives à échéance imminente ou déjà expirées (XQHS2).

    Même logique de préalerte que ``ConformiteEnvironnementale`` (QHSE38) :
    retient les dérogations non clôturées dont ``date_expiration`` tombe dans
    la fenêtre ``prealerte_jours`` (ou déjà passée). Scopé société.
    """
    from datetime import timedelta

    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    qs = Derogation.objects.filter(
        company=company, date_expiration__isnull=False
    ).exclude(statut=Derogation.Statut.CLOTUREE)
    return [
        d for d in qs
        if d.date_expiration <= today + timedelta(days=d.prealerte_jours or 0)
    ]


def relancer_derogations(company, today=None):
    """Relance les dérogations à échéance imminente/dépassée (best-effort)."""
    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    derogs = derogations_a_relancer(company, today=today)
    notifiees = 0
    items = []
    for derog in derogs:
        titre = 'Dérogation à échéance'
        corps = (
            f'La dérogation liée à la non-conformité '
            f'« {derog.non_conformite.titre} » expire le '
            f'{derog.date_expiration.isoformat()}.')
        if derog.approbateur_id is not None:
            _notifier_derogation(derog.approbateur, titre, corps, company)
            notifiees += 1
        items.append({
            'derogation_id': derog.id,
            'non_conformite_id': derog.non_conformite_id,
            'date_expiration': derog.date_expiration.isoformat(),
        })
    return {'total': len(derogs), 'notifiees': notifiees, 'items': items}


def _notifier_derogation(user, titre, corps, company):
    """Notifie l'approbateur d'une dérogation à échéance (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/non-conformites', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


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


# ── QHSE38 — Relances des conformités environnementales ────────────────────

def relancer_conformites(company, today=None):
    """Relance les conformités environnementales à renouveler / expirées (QHSE38).

    Pour chaque conformité à relancer (cf. ``selectors.conformites_a_relancer``),
    émet une notification in-app au responsable (best-effort via
    ``notifications.notify`` — jamais d'exception remontée ; une conformité sans
    responsable est comptée mais non notifiée). Réutilise l'``EventType``
    existant ``MAINTENANCE_DUE`` (échéance interne) pour rester additif.

    Renvoie un *digest* : ``{'total': N, 'notifiees': M, 'sans_responsable': K,
    'items': [...]}`` où ``items`` résume chaque conformité (id, intitulé,
    échéance, état recalculé, responsable). Ne mute aucune conformité.
    """
    from django.utils import timezone

    from apps.qhse.selectors import conformites_a_relancer

    if today is None:
        today = timezone.localdate()
    confs = list(conformites_a_relancer(company, today=today))

    notifiees = 0
    sans_responsable = 0
    items = []
    for conf in confs:
        etat = conf.statut_calcule(today)
        echeance = conf.date_expiration
        titre = 'Conformité environnementale à renouveler'
        corps = (
            f"La conformité « {conf.intitule} » "
            f"(échéance {echeance.isoformat() if echeance else '—'}) "
            f"est à l'état « {conf.Statut(etat).label} ».")
        if conf.responsable_id is not None:
            _notifier_conformite(conf.responsable, titre, corps, company)
            notifiees += 1
        else:
            sans_responsable += 1
        items.append({
            'conformite_id': conf.id,
            'intitule': conf.intitule,
            'echeance': echeance.isoformat() if echeance else None,
            'etat': etat,
            'responsable_id': conf.responsable_id,
        })

    return {
        'total': len(confs),
        'notifiees': notifiees,
        'sans_responsable': sans_responsable,
        'items': items,
    }


def _notifier_conformite(user, titre, corps, company):
    """Notifie un responsable d'une conformité à renouveler (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/conformites-environnementales', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── XQHS1 — Chaîne d'étapes légales AT/MP (loi 18-12) ────────────────────────

# Délai par type d'étape, exprimé en HEURES pour rester précis sur le délai de
# 48 h (avis employeur). Les autres délais légaux (5 j) sont donnés en jours
# convertis en heures. Les étapes sans délai légal fixe (suivi ITT, certificat
# de guérison, conciliation) n'ont pas d'échéance calculée automatiquement
# (``echeance=None``) — elles restent pilotables manuellement.
DELAI_HEURES_PAR_ETAPE = {
    EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR: 48,
    EtapeDeclarationAt.TypeEtape.DOSSIER_ASSUREUR: 5 * 24,
    EtapeDeclarationAt.TypeEtape.INFORMATION_INSPECTION: 5 * 24,
    EtapeDeclarationAt.TypeEtape.CERTIFICAT_MEDICAL: 5 * 24,
}

# Étapes systématiquement instanciées à la création d'une déclaration.
ETAPES_STANDARD = [
    EtapeDeclarationAt.TypeEtape.AVIS_EMPLOYEUR,
    EtapeDeclarationAt.TypeEtape.DOSSIER_ASSUREUR,
    EtapeDeclarationAt.TypeEtape.INFORMATION_INSPECTION,
    EtapeDeclarationAt.TypeEtape.CERTIFICAT_MEDICAL,
    EtapeDeclarationAt.TypeEtape.SUIVI_ITT,
    EtapeDeclarationAt.TypeEtape.CERTIFICAT_GUERISON,
]


@transaction.atomic
def instancier_etapes_at(declaration):
    """Instancie la checklist des étapes légales AT/MP d'une déclaration CNSS.

    Idempotent : réutilise les étapes déjà créées pour cette déclaration (une
    seule par ``type_etape``, contrainte d'unicité) et n'ajoute que celles
    manquantes. L'échéance de chaque étape est calculée côté serveur à partir
    de ``declaration.date_accident`` + son délai légal (cf.
    ``DELAI_HEURES_PAR_ETAPE``) ; les étapes sans délai fixe restent sans
    échéance. La ``conciliation`` n'est instanciée QUE si
    ``conciliation_statut`` n'est pas ``non_requise`` (elle est facultative
    selon le dossier).

    Renvoie la liste des ``EtapeDeclarationAt`` de la déclaration (créées +
    déjà existantes).
    """
    from datetime import datetime, time, timedelta

    from django.utils import timezone

    types_a_creer = list(ETAPES_STANDARD)
    if (declaration.conciliation_statut !=
            DeclarationCnss.ConciliationStatut.NON_REQUISE):
        types_a_creer.append(EtapeDeclarationAt.TypeEtape.CONCILIATION)

    existantes = {
        e.type_etape: e
        for e in declaration.etapes.all()
    }

    base_dt = None
    if declaration.date_accident is not None:
        base_dt = timezone.make_aware(
            datetime.combine(declaration.date_accident, time.min))

    for type_etape in types_a_creer:
        if type_etape in existantes:
            continue
        delai_h = DELAI_HEURES_PAR_ETAPE.get(type_etape)
        echeance = (
            base_dt + timedelta(hours=delai_h)
            if (base_dt is not None and delai_h is not None) else None)
        etape = EtapeDeclarationAt.objects.create(
            company=declaration.company,
            declaration=declaration,
            type_etape=type_etape,
            echeance=echeance,
        )
        existantes[type_etape] = etape

    return list(declaration.etapes.all())


@transaction.atomic
def marquer_etape_faite(etape, fait_le=None):
    """Marque une étape AT/MP comme réalisée (``fait_le`` posé côté serveur)."""
    from django.utils import timezone
    etape.fait_le = fait_le or timezone.now()
    etape.save(update_fields=['fait_le', 'statut'])
    return etape


def relancer_etapes_at_en_retard(company, now=None):
    """Relance (notification) les étapes AT/MP à échéance imminente ou dépassée.

    Réutilise le pattern ``relancer_capa_en_retard``/``relancer_conformites`` :
    best-effort, ne mute aucune étape, renvoie un digest
    ``{'total', 'notifiees', 'items'}``.
    """
    from django.utils import timezone

    from apps.qhse.selectors import etapes_at_a_echeance

    if now is None:
        now = timezone.now()
    etapes = list(etapes_at_a_echeance(company, now=now))

    notifiees = 0
    items = []
    for etape in etapes:
        titre = 'Étape AT/MP à échéance'
        corps = (
            f'« {etape.get_type_etape_display()} » de la déclaration CNSS '
            f'accident#{etape.declaration.accident_travail_id} '
            f'({etape.get_statut_display()}).')
        responsable = getattr(
            etape.declaration.accident_travail, 'employe', None)
        cible = getattr(responsable, 'user', None)
        if cible is not None:
            _notifier_etape_at(cible, titre, corps, company)
            notifiees += 1
        items.append({
            'etape_id': etape.id,
            'type_etape': etape.type_etape,
            'echeance': etape.echeance.isoformat() if etape.echeance else None,
            'statut': etape.statut_calcule(now),
            'declaration_id': etape.declaration_id,
        })

    return {'total': len(etapes), 'notifiees': notifiees, 'items': items}


def _notifier_etape_at(user, titre, corps, company):
    """Notifie un responsable d'une étape AT/MP à échéance (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify
        notify(user, EventType.MAINTENANCE_DUE, titre, body=corps,
               link='/qhse/declarations-cnss', company=company)
    except Exception:  # pragma: no cover - défensif
        pass


# ── XQHS3 — Contrôle qualité à la réception fournisseur ──────────────────────

def plans_actifs_pour_produit(company, produit_id, categorie_id=None):
    """Plans de contrôle réception ACTIFS couvrant ce produit (ou sa catégorie).

    Un plan peut couvrir un produit précis OU une catégorie entière. Scopé
    société. Lecture seule.
    """
    from django.db.models import Q
    qs = PlanControleReception.objects.filter(company=company, actif=True)
    filtre = Q(produit_id=produit_id)
    if categorie_id is not None:
        filtre |= Q(categorie_id=categorie_id)
    return list(qs.filter(filtre))


@transaction.atomic
def instancier_controles_reception(reception, company):
    """Instancie les ``ControleReception`` déclenchés par une réception
    confirmée (XQHS3), abonné à ``core.events.reception_fournisseur_confirmee``.

    Pour CHAQUE ligne de la réception, résout le produit (et sa catégorie) et
    crée un ``ControleReception`` par plan actif qui le couvre — idempotent
    (contrainte d'unicité société+réception+plan : un second appel pour la même
    réception ne duplique rien).

    ``reception`` est l'instance ``stock.ReceptionFournisseur`` (accédée en
    lecture directe ici car on est dans le récepteur de l'événement qu'elle a
    elle-même émis — pas un import de ``stock.models`` en dehors de ce
    contexte réactif). Renvoie la liste des ``ControleReception`` créés.
    """
    crees = []
    lignes = list(reception.lignes.select_related('produit').all())
    for ligne in lignes:
        produit = ligne.produit
        if produit is None:
            continue
        categorie_id = getattr(produit, 'categorie_id', None)
        plans = plans_actifs_pour_produit(company, produit.id, categorie_id)
        for plan in plans:
            controle, created = ControleReception.objects.get_or_create(
                company=company, reception_id=reception.id, plan=plan,
                defaults={'produit_id': produit.id},
            )
            if created:
                crees.append(controle)
    return crees


@transaction.atomic
def statuer_controle_reception(
        controle, verdict, *, controleur=None, notes=''):
    """Pose le verdict d'un contrôle réception (XQHS3).

    ``controleur``/``date_controle`` posés côté serveur. Un verdict ``refuse``
    crée automatiquement une NCR pré-remplie (pont XQHS3→XQHS2) via
    ``lever_ncr_controle_reception`` — idempotent (ne recrée pas de NCR si une
    est déjà liée). Renvoie le contrôle mis à jour.
    """
    from django.utils import timezone

    valeurs_valides = {c.value for c in ControleReception.Verdict}
    if verdict not in valeurs_valides:
        raise ValueError(f'Verdict invalide : {verdict!r}')

    controle.verdict = verdict
    controle.controleur = controleur
    controle.notes = notes or controle.notes
    controle.date_controle = timezone.now()
    controle.save(update_fields=[
        'verdict', 'controleur', 'notes', 'date_controle'])

    if verdict == ControleReception.Verdict.REFUSE:
        lever_ncr_controle_reception(controle)
    return controle


def lever_ncr_controle_reception(controle):
    """Lève une NCR pré-remplie depuis un contrôle réception refusé (XQHS3).

    Idempotent : si ``controle.non_conformite`` est déjà posée, ne recrée rien.
    """
    if controle.non_conformite_id is not None:
        return controle.non_conformite
    ncr = NonConformite.objects.create(
        company=controle.company,
        titre=f'[Réception] Contrôle refusé — {controle.plan.nom}',
        description=(
            controle.notes or
            f'Contrôle qualité à la réception #{controle.reception_id} '
            f'refusé sur le plan « {controle.plan.nom} ».'),
        origine=f'Contrôle réception — {controle.plan.nom}',
        gravite=NonConformite.Gravite.MAJEURE,
    )
    controle.non_conformite = ncr
    controle.save(update_fields=['non_conformite'])
    return ncr


# ── XFSM14 — Thermographie IR : NCR auto sur sévérité maximale ─────────────

@transaction.atomic
def enregistrer_releve_thermographie(
        *, company, equipement_ref, delta_t=None,
        campagne=ReleveThermographie.Campagne.SUIVI,
        chantier_id=None, attachment_id=None,
        seuil_a_surveiller=None, seuil_intervention=None,
        releve_par=None, note=''):
    """Crée un relevé de thermographie et lève une NCR si sévérité maximale.

    Le classement (``classe_severite``) est dérivé automatiquement du
    ``delta_t`` et des seuils au ``save()``. Une classe ``intervention_requise``
    déclenche la levée d'une NCR liée (idempotent par relevé : chaque relevé ne
    lève sa NCR qu'une fois, gérée par l'appelant qui ne repasse pas par ici sur
    un relevé déjà persisté).
    """
    releve = ReleveThermographie(
        company=company, equipement_ref=equipement_ref, delta_t=delta_t,
        campagne=campagne, chantier_id=chantier_id,
        attachment_id=attachment_id, releve_par=releve_par, note=note,
    )
    if seuil_a_surveiller is not None:
        releve.seuil_a_surveiller = seuil_a_surveiller
    if seuil_intervention is not None:
        releve.seuil_intervention = seuil_intervention
    releve.save()

    if (releve.classe_severite == ReleveThermographie.Severite.INTERVENTION_REQUISE
            and releve.ncr_id is None):
        ncr = NonConformite.objects.create(
            company=company,
            titre=f'[Thermographie IR] {equipement_ref}',
            description=(
                note or
                f'Point chaud détecté (ΔT={delta_t}°C) sur {equipement_ref} — '
                f'intervention requise (IEC 62446-3).'),
            origine='Thermographie IR',
            gravite=NonConformite.Gravite.MAJEURE,
            chantier_id=chantier_id,
        )
        releve.ncr = ncr
        releve.save(update_fields=['ncr'])
    return releve


def comparer_campagnes_thermographie(company, equipement_ref):
    """Compare la dernière ``recette`` (baseline) et le dernier ``suivi`` d'un
    équipement (XFSM14). Renvoie ``{'recette': releve|None, 'suivi': releve|None,
    'delta': Decimal|None}`` — ``delta`` = évolution ΔT entre les deux.
    """
    qs = ReleveThermographie.objects.filter(
        company=company, equipement_ref=equipement_ref)
    recette = qs.filter(
        campagne=ReleveThermographie.Campagne.RECETTE
    ).order_by('-date_releve', '-id').first()
    suivi = qs.filter(
        campagne=ReleveThermographie.Campagne.SUIVI
    ).order_by('-date_releve', '-id').first()
    delta = None
    if recette is not None and suivi is not None \
            and recette.delta_t is not None and suivi.delta_t is not None:
        delta = suivi.delta_t - recette.delta_t
    return {'recette': recette, 'suivi': suivi, 'delta': delta}


# ── XFSM24 — Check-in travailleur isolé avec escalade ───────────────────────

def _notifier_escalade_checkin(checkin):
    """Notifie le responsable + téléphone du site (best-effort, sans erreur)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        # XFSM8 — téléphone du site, si dispo, est intégré dans le corps du
        # message (le canal d'envoi effectif reste `notify`, best-effort).
        responsables = checkin.company.users.filter(
            role_legacy__in=('responsable', 'admin', 'manager'))
        corps = (
            f'{checkin.technicien} — check-out prévu dépassé sur '
            f'{checkin.site_ref or "site"} (intervention '
            f'{checkin.intervention_id or "?"}).')
        for resp in responsables:
            notify(resp, EventType.MAINTENANCE_DUE,
                   'Escalade check-in sécurité', body=corps,
                   link='/qhse/checkins', company=checkin.company)
    except Exception:  # pragma: no cover - défensif
        pass


@transaction.atomic
def escalader_checkins_en_retard(company=None, now=None):
    """Escalade tout check-in dont le check-out prévu est dépassé sans
    check-out réel (XFSM24). Idempotent : un check-in déjà escaladé
    (``escalade_declenchee=True``) n'est jamais re-notifié.

    Renvoie la liste des check-ins escaladés dans cet appel.
    """
    from django.utils import timezone

    if now is None:
        now = timezone.now()
    qs = CheckinSecurite.objects.filter(
        heure_checkout_reelle__isnull=True,
        escalade_declenchee=False,
        heure_checkout_prevue__isnull=False,
    )
    if company is not None:
        qs = qs.filter(company=company)

    escalades = []
    for checkin in qs:
        if checkin.en_retard(now=now):
            checkin.escalade_declenchee = True
            checkin.escalade_le = now
            checkin.save(update_fields=['escalade_declenchee', 'escalade_le'])
            _notifier_escalade_checkin(checkin)
            escalades.append(checkin)
    return escalades


# ── XQHS5 — Campagne de rappel / containment par produit-lot-série ─────────

@transaction.atomic
def peupler_campagne_rappel(campagne):
    """Peuple les ``ElementRappel`` d'une campagne depuis le parc réel.

    Lit le parc UNIQUEMENT via ``sav.selectors.equipements_par_produit``
    (jamais un import de ``apps.sav.models``). Idempotent : ré-appelée, elle
    n'ajoute que les équipements pas encore présents dans la campagne
    (contrainte unique ``(campagne, equipement_id)``).

    Renvoie la liste des ``ElementRappel`` créés dans cet appel.
    """
    from apps.sav.selectors import equipements_par_produit

    equipements = equipements_par_produit(
        campagne.company, campagne.produit_id,
        serie_debut=campagne.serie_debut or None,
        serie_fin=campagne.serie_fin or None,
    )
    existants = set(
        ElementRappel.objects.filter(campagne=campagne)
        .values_list('equipement_id', flat=True)
    )
    crees = []
    for eq in equipements:
        if eq['id'] in existants:
            continue
        element = ElementRappel.objects.create(
            company=campagne.company, campagne=campagne,
            equipement_id=eq['id'], numero_serie=eq.get('numero_serie') or '',
            installation_id=eq.get('installation_id'),
        )
        crees.append(element)
    return crees


def _notifier_element_rappel(element, responsable):
    """Notifie le responsable d'un élément de rappel à traiter (best-effort)."""
    try:
        from apps.notifications.models import EventType
        from apps.notifications.services import notify

        corps = (
            f'Campagne « {element.campagne.titre} » — équipement '
            f'{element.numero_serie or element.equipement_id} à traiter.')
        notify(responsable, EventType.MAINTENANCE_DUE,
               'Élément de campagne de rappel', body=corps,
               link='/qhse/campagnes-rappel', company=element.company)
    except Exception:  # pragma: no cover - défensif
        pass


@transaction.atomic
def notifier_elements_rappel(campagne):
    """Notifie le responsable de campagne pour chaque élément ``à_notifier``
    et fait avancer son statut à ``notifie`` (XQHS5).

    Renvoie la liste des ``ElementRappel`` notifiés dans cet appel.
    """
    from django.utils import timezone

    if campagne.responsable_id is None:
        return []
    a_notifier = list(
        campagne.elements.filter(statut=ElementRappel.Statut.A_NOTIFIER))
    now = timezone.now()
    for element in a_notifier:
        _notifier_element_rappel(element, campagne.responsable)
        element.statut = ElementRappel.Statut.NOTIFIE
        element.notifie_le = now
        element.save(update_fields=['statut', 'notifie_le'])
    return a_notifier


@transaction.atomic
def planifier_remplacement_element_rappel(element, *, client, created_by):
    """Crée l'intervention SAV de remplacement pour un élément (XQHS5).

    Passe par ``sav.services.create_corrective_ticket`` (jamais un import de
    modèle SAV). Fait avancer l'élément à ``planifie`` et enregistre
    ``ticket_sav_id`` (référence LÂCHE).
    """
    from apps.sav.services import create_corrective_ticket

    installation = None
    if element.installation_id:
        from apps.installations.models import Installation
        installation = Installation.objects.filter(
            pk=element.installation_id).first()

    ticket = create_corrective_ticket(
        company=element.company, client=client, installation=installation,
        description=(
            f'Remplacement — campagne de rappel « {element.campagne.titre} » '
            f'({element.numero_serie or element.equipement_id}).'),
        created_by=created_by,
    )
    element.ticket_sav_id = ticket.id
    element.statut = ElementRappel.Statut.PLANIFIE
    element.save(update_fields=['ticket_sav_id', 'statut'])
    return element


@transaction.atomic
def cloturer_campagne_rappel(campagne, date_verification_efficacite):
    """Clôture une campagne après vérification d'efficacité (XQHS5).

    N'autorise la clôture que si tous les éléments sont ``remplace`` ou
    ``clos`` (traitement terminé) — sinon lève ``ValueError``.
    """
    en_cours = campagne.elements.exclude(
        statut__in=[ElementRappel.Statut.REMPLACE, ElementRappel.Statut.CLOS]
    ).count()
    if en_cours:
        raise ValueError(
            f'{en_cours} élément(s) non traités — clôture impossible.')
    campagne.statut = CampagneRappel.Statut.CLOTUREE
    campagne.date_verification_efficacite = date_verification_efficacite
    campagne.save(update_fields=['statut', 'date_verification_efficacite'])
    campagne.elements.filter(
        statut=ElementRappel.Statut.REMPLACE
    ).update(statut=ElementRappel.Statut.CLOS)
    return campagne
