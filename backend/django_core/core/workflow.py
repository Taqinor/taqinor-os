"""FG366 — Moteur de workflow multi-étapes (BPM) + SLA / escalades.

Services PURS et GÉNÉRIQUES qui pilotent les modèles de ``core.models``
(``WorkflowDefinition``/``WorkflowStepDefinition``/``WorkflowInstance``/
``WorkflowStepInstance``). Aucun import d'app métier : la cible d'une instance
est désignée via ``contenttypes`` (fondation Django), donc ce moteur fait
tourner une chaîne d'approbation sur n'importe quel modèle sans le connaître.

Principes de conception
-----------------------

* **Déterminisme testable.** Toute fonction qui dépend du temps reçoit ``now``
  (ou ``today``) en argument — JAMAIS d'appel interne à ``timezone.now()`` au
  cœur de la logique. ``demarrer_workflow`` accepte ``now`` pour figer le départ
  et calculer les échéances SLA ; ``etapes_sla_depassees`` reçoit ``now``.
* **Multi-tenant.** ``company`` est imposé côté serveur partout : les instances
  et étapes copient la société passée, jamais une valeur du corps de requête.
* **SLA.** Pour une étape dont la définition porte ``sla_heures``,
  ``sla_echeance = started + sla_heures``. Sans ``sla_heures``, pas de minuterie
  (``sla_echeance`` reste vide → jamais en dépassement).

API publique
------------

* ``demarrer_workflow(definition, target, company, user=None, now=None)``
  instancie l'instance + toutes les étapes (en attente) et active la première.
* ``approuver_etape`` / ``rejeter_etape`` enregistrent une décision sur l'étape
  courante puis ``avancer`` fait progresser séquentiellement.
* ``avancer(instance, now=None)`` passe à l'étape suivante (auto-approuve les
  étapes ``type_approbation == 'auto'``) et clôt l'instance à la fin.
* ``etapes_sla_depassees(company, now)`` (sélecteur) liste les étapes en attente
  dont l'échéance SLA est passée — base des escalades.
* ``escalader_etape(step, now=None)`` marque une étape ``escalade``.

RÈGLE D'ARCHITECTURE (ARC10) — ce moteur EST LE moteur d'approbation
--------------------------------------------------------------------

**Toute NOUVELLE approbation multi-étapes passe par ce moteur
``core.WorkflowDefinition``/``WorkflowInstance``** — plus jamais un cinquième
mécanisme d'approbation ad hoc. Historiquement cinq mécanismes coexistaient
(``automation.AutomationApproval``, ``contrats.RegleApprobation``/
``EtapeApprobation``, ``ged.DemandeApprobation``, ``installations.DemandeAchat``,
et ce moteur BPM) ; l'agrégateur ``apps/reporting/approbations.py`` les remonte
déjà tous dans une boîte unique (source 5 = ce moteur, via
``pending_steps_for_company`` / ``decide_step``). Les nouveaux besoins
n'ajoutent pas de sixième chemin : ils installent un modèle FG369
(``core.workflow_templates``) et attachent une ``WorkflowInstance`` à leur
cible métier par ``contenttypes`` — sans que ``core`` n'importe l'app.

Pilote domaine vivant : la **clôture de non-conformité qhse** (hors règle #4,
volontairement) tourne sur ce moteur via le modèle FG369 ``cloture_ncr`` et les
services ``apps/qhse/services.py`` (``demarrer_workflow_cloture_ncr`` /
``approuver_etape_cloture_ncr`` / ``rejeter_etape_cloture_ncr`` /
``escalader_workflow_cloture_ncr``). Créée → approuvée → rejetée → escaladée,
couvertes en tests.

Successeur pour la **configurabilité UI** : ``parametres.ApprovalPolicy``
(FG25) porte les politiques déclaratives (type d'action + seuil + palier
d'approbateur) éditables par l'admin ; c'est la couche de configuration qui
alimentera à terme la sélection/instanciation de ces définitions de workflow —
ce moteur reste l'EXÉCUTION, FG25 la CONFIGURATION.
"""
import datetime
import hashlib
import json
import re

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from core.models import (
    WorkflowInstance,
    WorkflowStepInstance,
)

__all__ = [
    'demarrer_workflow',
    'avancer',
    'approuver_etape',
    'rejeter_etape',
    'escalader_etape',
    'etape_courante_de',
    'etapes_sla_depassees',
    'flag_overdue_steps',
    'instance_en_cours_pour',
    'demarrer_depuis_matrice',
    'decide_step',
    'register_delegation_resolver',
    'delegants_actifs_pour',
    'register_business_day_advance',
    'etapes_a_mi_sla',
    'marquer_rappel_envoye',
]


def _resolve_now(now):
    """Retourne ``now`` tel quel, ou ``timezone.now()`` par défaut.

    On centralise ce SEUL point de défaut pour que les couches internes
    reçoivent toujours un ``now`` explicite (déterminisme)."""
    return now if now is not None else timezone.now()


# NTWFL4 — résolveur de calendrier ouvré, branché par
# ``apps.notifications.apps.ready()`` (jamais un import direct de cette app
# depuis ``core`` : contrat import-linter core-foundation-is-a-base-layer).
# Signature : ``fn(started: datetime, sla_heures: int, company) -> datetime``.
_business_day_advance_resolver = None


def register_business_day_advance(fn):
    """Enregistre le résolveur de calendrier ouvré (NTWFL4).

    Appelé par ``apps.notifications.apps.ready()`` avec
    ``calendar_utils.ajouter_heures_ouvrees``. Un second appel REMPLACE le
    résolveur (utile aux tests qui veulent l'isoler)."""
    global _business_day_advance_resolver
    _business_day_advance_resolver = fn


def _sla_echeance(started, sla_heures, *, calendrier_ouvre=False, company=None):
    """``started + sla_heures`` (datetime) ou ``None`` si pas de SLA.

    NTWFL4 — ``calendrier_ouvre=True`` (avec ``company``) délègue au
    résolveur de calendrier ouvré enregistré (heures OUVRÉES : les jours non
    ouvrés/fériés de la société sont sautés) ; ``calendrier_ouvre=False``
    (défaut) ou sans résolveur enregistré garde le calcul HISTORIQUE en
    heures brutes — comportement strictement inchangé."""
    if not sla_heures:
        return None
    if (calendrier_ouvre and company is not None
            and _business_day_advance_resolver is not None):
        try:
            return _business_day_advance_resolver(started, sla_heures, company)
        except Exception:  # pragma: no cover - défensif, jamais bloquant
            pass
    return started + datetime.timedelta(hours=sla_heures)


@transaction.atomic
def demarrer_workflow(definition, target, company, user=None, now=None):
    """Instancie un workflow sur ``target`` et active sa première étape.

    Crée une ``WorkflowInstance`` (cible générique via contenttypes) plus une
    ``WorkflowStepInstance`` par ``WorkflowStepDefinition`` de la définition,
    en calculant l'échéance SLA de chaque étape à partir de ``started`` (= now).
    La première étape devient ``etape_courante = 1`` ; les étapes ``auto`` en
    tête sont franchies immédiatement par ``avancer``.

    ``company`` est imposé sur l'instance ET chaque étape. ``now`` est passé
    pour un calcul SLA déterministe.
    """
    started = _resolve_now(now)
    ct = ContentType.objects.get_for_model(target.__class__)

    instance = WorkflowInstance.objects.create(
        company=company,
        definition=definition,
        content_type=ct,
        object_id=target.pk,
        statut=WorkflowInstance.STATUT_EN_COURS,
        etape_courante=1,
        started_le=started,
    )

    step_defs = list(definition.steps.order_by('ordre', 'id'))
    for sd in step_defs:
        WorkflowStepInstance.objects.create(
            company=company,
            instance=instance,
            step_def=sd,
            ordre=sd.ordre,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            sla_echeance=_sla_echeance(
                started, sd.sla_heures,
                calendrier_ouvre=getattr(sd, 'calendrier_ouvre', False),
                company=company),
        )

    if not step_defs:
        # Définition sans étape → instance terminée d'emblée.
        instance.statut = WorkflowInstance.STATUT_TERMINE
        instance.ended_le = started
        instance.save(update_fields=['statut', 'ended_le', 'updated_at'])
        return instance

    # Franchit immédiatement les étapes 'auto' en tête de file.
    avancer(instance, now=started, _from_start=True)
    return instance


def instance_en_cours_pour(target, company, definition_code=None):
    """Sélecteur : la ``WorkflowInstance`` EN COURS attachée à ``target``.

    Résout la cible générique (``content_type`` + ``object_id``) sans que
    ``core`` ait à connaître le modèle métier — n'importe quelle app peut
    demander « quel workflow tourne actuellement sur cet objet ? ». Bornée à la
    société (multi-tenant, jamais de fuite) et, optionnellement, à un
    ``definition_code`` (utile quand plusieurs types de workflow peuvent viser
    le même objet). Retourne la plus récente ou ``None``.
    """
    ct = ContentType.objects.get_for_model(target.__class__)
    qs = WorkflowInstance.objects.filter(
        company=company,
        content_type=ct,
        object_id=target.pk,
        statut=WorkflowInstance.STATUT_EN_COURS,
    )
    if definition_code is not None:
        qs = qs.filter(definition__code=definition_code)
    return qs.order_by('-id').first()


def etape_courante_de(instance):
    """Retourne la ``WorkflowStepInstance`` active (ou ``None``)."""
    if instance.statut != WorkflowInstance.STATUT_EN_COURS:
        return None
    return (
        instance.step_instances
        .filter(ordre=instance.etape_courante)
        .order_by('id')
        .first()
    )


def _contexte_cible(instance):
    """NTWFL7 — sérialise superficiellement ``instance.target`` (la cible
    générique via contenttypes) en un ``dict`` PLAT ``{champ: valeur}`` pour
    ``core.rules.evaluate_condition_group``. Générique : introspecte les
    champs CONCRETS du modèle cible sans jamais importer son type (``core``
    reste fondation). ``{}`` si la cible est absente/introspection
    impossible — une garde sans contexte disponible échoue prudemment
    (feuilles ``core.rules`` : champ absent ⇒ ``False``)."""
    target = getattr(instance, 'target', None)
    if target is None:
        return {}
    try:
        return {f.name: getattr(target, f.name, None)
                for f in target._meta.fields}
    except Exception:  # pragma: no cover - défensif
        return {}


def _garde_transition_ok(step, instance):
    """NTWFL7 — ``True`` si la garde ``condition_transition`` de l'étape est
    vérifiée (ou absente — comportement inchangé : toujours franchie)."""
    condition = step.step_def.condition_transition
    if not condition:
        return True
    from core.rules import evaluate_condition_group
    return evaluate_condition_group(condition, _contexte_cible(instance))


def _router_vers_alternative(step, instance, moment):
    """NTWFL7 — route vers ``step.step_def.etape_alternative_si_echec`` (un
    ``ordre`` de la MÊME définition) quand la garde échoue : l'étape
    courante est marquée ``ignoree`` (branche non empruntée) et le pointeur
    saute directement à l'étape alternative. Renvoie ``True`` si une route a
    été prise, ``False`` sinon (pas d'alternative configurée, ou ``ordre``
    introuvable — traité comme « pas d'alternative » plutôt que de planter)."""
    ordre_alt = step.step_def.etape_alternative_si_echec
    if not ordre_alt:
        return False
    cible = (
        instance.step_instances.filter(ordre=ordre_alt).order_by('id').first()
    )
    if cible is None:
        return False
    step.statut = WorkflowStepInstance.STATUT_IGNOREE
    step.decided_le = moment
    step.save(update_fields=['statut', 'decided_le', 'updated_at'])
    instance.etape_courante = ordre_alt
    instance.save(update_fields=['etape_courante', 'updated_at'])
    return True


def _emit_etape_activee(step, company):
    """NTWFL5 — émet ``core.events.workflow_etape_activee`` (best-effort,
    jamais bloquant : une notification cassée ne doit jamais empêcher le
    moteur BPM d'avancer)."""
    try:
        from core.events import workflow_etape_activee
        workflow_etape_activee.send(
            sender='core.workflow', step=step, company=company)
    except Exception:  # pragma: no cover - défensif
        pass


def _steps_apres(instance, ordre):
    """Étapes dont l'``ordre`` est strictement supérieur, triées."""
    return list(
        instance.step_instances
        .filter(ordre__gt=ordre)
        .order_by('ordre', 'id')
    )


@transaction.atomic
def avancer(instance, now=None, _from_start=False):
    """Fait progresser l'instance après une décision (ou au démarrage).

    Auto-approuve toute étape ``type_approbation == 'auto'`` rencontrée, puis
    s'arrête sur la première étape ``en_attente`` non-auto (qui devient
    ``etape_courante``). Si plus aucune étape n'est en attente, l'instance est
    terminée. ``now`` est passé pour horodater déterministiquement.
    """
    moment = _resolve_now(now)
    if instance.statut != WorkflowInstance.STATUT_EN_COURS:
        return instance

    while True:
        step = etape_courante_de(instance)
        if step is None:
            # Plus d'étape à l'ordre courant → cherche la suivante en attente.
            suivantes = _steps_apres(instance, instance.etape_courante)
            pending = [s for s in suivantes
                       if s.statut == WorkflowStepInstance.STATUT_EN_ATTENTE]
            if not pending:
                _terminer(instance, moment)
                return instance
            instance.etape_courante = pending[0].ordre
            instance.save(update_fields=['etape_courante', 'updated_at'])
            continue

        if step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
            # Déjà décidée (approuvée au démarrage…) → passe à la suivante.
            _avancer_pointeur(instance, step, moment)
            continue

        if step.step_def.type_approbation == \
                step.step_def.APPROBATION_AUTO:
            # NTWFL7 — garde de transition AVANT l'auto-approbation.
            if not _garde_transition_ok(step, instance):
                route_prise = _router_vers_alternative(step, instance, moment)
                if route_prise:
                    continue
                # Pas d'alternative valide : reste EN ATTENTE (comme une
                # étape manuelle bloquée) plutôt que de forcer l'avancement.
                _emit_etape_activee(step, instance.company)
                return instance
            step.statut = WorkflowStepInstance.STATUT_APPROUVE
            step.decided_le = moment
            step.save(update_fields=['statut', 'decided_le', 'updated_at'])
            _avancer_pointeur(instance, step, moment)
            continue

        # Étape manuelle / par rôle en attente : on s'arrête ici.
        # NTWFL5 — signale qu'une étape vient de devenir ACTIVE (comble
        # YEVNT8 pour FG366 : aujourd'hui aucune notification ne part à la
        # création). Émission SYNCHRONE, best-effort côté abonné (jamais
        # bloquant pour le moteur BPM lui-même).
        _emit_etape_activee(step, instance.company)
        return instance


def _avancer_pointeur(instance, step, moment):
    """Déplace ``etape_courante`` vers la prochaine étape, ou termine."""
    suivantes = _steps_apres(instance, step.ordre)
    if not suivantes:
        _terminer(instance, moment)
        return
    instance.etape_courante = suivantes[0].ordre
    instance.save(update_fields=['etape_courante', 'updated_at'])


def _terminer(instance, moment):
    instance.statut = WorkflowInstance.STATUT_TERMINE
    instance.ended_le = moment
    instance.save(update_fields=['statut', 'ended_le', 'updated_at'])


@transaction.atomic
def approuver_etape(instance, user=None, commentaire='', now=None):
    """Approuve l'étape courante puis avance séquentiellement.

    Lève ``ValueError`` si l'instance n'est pas en cours ou n'a pas d'étape
    active en attente.
    """
    moment = _resolve_now(now)
    step = etape_courante_de(instance)
    if step is None or step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
        raise ValueError("Aucune étape en attente à approuver.")
    step.statut = WorkflowStepInstance.STATUT_APPROUVE
    step.assignee = user
    step.decided_le = moment
    if commentaire:
        step.commentaire = commentaire
    step.save(update_fields=[
        'statut', 'assignee', 'decided_le', 'commentaire', 'updated_at'])
    avancer(instance, now=moment)
    return step


@transaction.atomic
def rejeter_etape(instance, user=None, commentaire='', now=None):
    """Rejette l'étape courante : l'instance est terminée (chaîne stoppée).

    Lève ``ValueError`` si aucune étape n'est en attente.
    """
    moment = _resolve_now(now)
    step = etape_courante_de(instance)
    if step is None or step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
        raise ValueError("Aucune étape en attente à rejeter.")
    step.statut = WorkflowStepInstance.STATUT_REJETE
    step.assignee = user
    step.decided_le = moment
    if commentaire:
        step.commentaire = commentaire
    step.save(update_fields=[
        'statut', 'assignee', 'decided_le', 'commentaire', 'updated_at'])
    _terminer(instance, moment)
    return step


@transaction.atomic
def escalader_etape(step, now=None):
    """Marque une étape ``escalade`` (décision d'escalade après dépassement)."""
    moment = _resolve_now(now)
    step.statut = WorkflowStepInstance.STATUT_ESCALADE
    step.decided_le = moment
    step.save(update_fields=['statut', 'decided_le', 'updated_at'])
    return step


def etapes_sla_depassees(company, now):
    """Sélecteur : étapes ``en_attente`` d'une société dont le SLA est dépassé.

    ``now`` est OBLIGATOIRE et passé explicitement (déterminisme — pas de
    ``timezone.now()`` interne). Une étape est en dépassement si elle est
    encore en attente, porte une ``sla_echeance`` et que ``sla_echeance < now``.
    Bornée à l'instance encore en cours. Triée par échéance la plus ancienne.
    """
    return list(
        WorkflowStepInstance.objects.filter(
            company=company,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            sla_echeance__isnull=False,
            sla_echeance__lt=now,
            instance__statut=WorkflowInstance.STATUT_EN_COURS,
        ).order_by('sla_echeance', 'id')
    )


def flag_overdue_steps(company, now):
    """Escalade en masse les étapes en dépassement SLA d'une société.

    Retourne la liste des étapes escaladées. ``now`` est passé explicitement.
    """
    overdue = etapes_sla_depassees(company, now)
    for step in overdue:
        escalader_etape(step, now=now)
    return overdue


# ── NTWFL5 — relance à mi-SLA (comble YEVNT9 pour FG366) ────────────────────

def etapes_a_mi_sla(company, now):
    """Sélecteur : étapes ``en_attente`` dont AU MOINS 50 % du délai SLA
    s'est écoulé depuis le départ de l'instance, jamais encore relancées.

    ``now`` est OBLIGATOIRE (déterminisme). Une étape est éligible si : elle
    est encore en attente, porte une ``sla_echeance`` (sans SLA configuré,
    jamais de rappel), son instance est en cours et porte ``started_le``,
    ``dernier_rappel_le`` est vide (jamais deux rappels pour la même étape)
    et l'instant à mi-chemin entre ``started_le`` et ``sla_echeance`` est
    déjà passé. Triée par échéance la plus proche d'abord."""
    candidats = (
        WorkflowStepInstance.objects.filter(
            company=company,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            sla_echeance__isnull=False,
            dernier_rappel_le__isnull=True,
            instance__statut=WorkflowInstance.STATUT_EN_COURS,
            instance__started_le__isnull=False,
        )
        .select_related('instance')
        .order_by('sla_echeance', 'id')
    )
    resultat = []
    for step in candidats:
        debut = step.instance.started_le
        fin = step.sla_echeance
        if fin <= debut:
            continue
        mi_chemin = debut + (fin - debut) / 2
        if now >= mi_chemin:
            resultat.append(step)
    return resultat


def marquer_rappel_envoye(step, now=None):
    """Marque ``step`` comme relancée à l'instant ``now`` (défaut : maintenant).

    Empêche tout second rappel pour la même étape (``etapes_a_mi_sla`` ne la
    renverra plus, ``dernier_rappel_le`` n'étant plus vide)."""
    moment = _resolve_now(now)
    step.dernier_rappel_le = moment
    step.save(update_fields=['dernier_rappel_le', 'updated_at'])
    return step


# ── XKB1 — boîte d'approbations centralisée (lecture cross-app) ──────────────

def pending_steps_for_company(company):
    """XKB1 — étapes BPM ``en_attente`` d'une société (instances en cours).

    Sélecteur LECTURE SEULE utilisé par l'agrégateur d'approbations
    (``apps/reporting``) : ``core`` reste la fondation, aucune app métier
    n'est importée ici. Triée par échéance SLA la plus proche d'abord (NULL en
    dernier), puis id."""
    from django.db.models import F
    return list(
        WorkflowStepInstance.objects.filter(
            company=company,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            instance__statut=WorkflowInstance.STATUT_EN_COURS,
        ).select_related('instance', 'step_def')
        .order_by(F('sla_echeance').asc(nulls_last=True), 'id')
    )


def decide_step(
        step, *, approve, user=None, commentaire='', now=None,
        on_behalf_of=None):
    """XKB1 — approuve/rejette une étape BPM en attente en résolvant son
    ``WorkflowInstance`` propriétaire (l'agrégateur ne connaît que l'étape).

    ``approve=True`` → ``approuver_etape`` ; ``approve=False`` →
    ``rejeter_etape``. Délègue entièrement à ces fonctions existantes (mêmes
    garde-fous, même transaction atomique).

    NTWFL3 — ``on_behalf_of`` (délégant, optionnel) journalise la décision
    comme prise « au nom de » ce délégant : AUCUNE nouvelle colonne (le
    modèle ``WorkflowStepInstance`` reste inchangé, cf. Files de la tâche) —
    la mention est préfixée dans le ``commentaire`` existant. ``None``
    (défaut) préserve EXACTEMENT le comportement historique pour tout appel
    existant qui ne passe pas ce paramètre."""
    if on_behalf_of is not None:
        commentaire = (
            f'[Décidé par {user} au nom de {on_behalf_of}] {commentaire}'
        ).strip()
    if approve:
        return approuver_etape(
            step.instance, user=user, commentaire=commentaire, now=now)
    return rejeter_etape(
        step.instance, user=user, commentaire=commentaire, now=now)


# ── NTWFL3 — délégation de vacances (XKB3) branchée sur le moteur BPM ───────
#
# ``core`` reste FONDATION (contrat import-linter
# core-foundation-is-a-base-layer) : il n'importe JAMAIS ``apps.automation``.
# Le résolveur réel (``ApprovalDelegation.delegants_actifs_pour``) est
# enregistré par ``apps.automation.apps.AutomationConfig.ready()`` — même
# patron que ``core.retention.register_retention_policy``. Sans app
# ``automation`` chargée (ou en tests qui n'en ont pas besoin), le registre
# reste ``None`` et toute résolution renvoie une liste vide (neutre).
_delegation_resolver = None


def register_delegation_resolver(fn):
    """Enregistre ``fn(suppleant, company, at=None) -> [delegant_id, ...]``.

    Appelé par ``apps.automation.apps.ready()`` (NTWFL3). Un second appel
    REMPLACE le résolveur (utile aux tests qui veulent l'isoler) — jamais
    d'accumulation silencieuse."""
    global _delegation_resolver
    _delegation_resolver = fn


def delegants_actifs_pour(suppleant, company, at=None):
    """NTWFL3 — IDs des délégants pour lesquels ``suppleant`` détient une
    délégation ACTIVE (via le résolveur enregistré, cf. ci-dessus). Liste
    vide si aucun résolveur enregistré ou aucune délégation active — ne
    lève jamais (une délégation ne doit jamais faire planter une décision)."""
    if _delegation_resolver is None:
        return []
    try:
        return list(_delegation_resolver(suppleant, company, at=at) or [])
    except Exception:  # pragma: no cover - défensif
        return []


# ── NTWFL2 — démarrage piloté par la matrice d'approbation (NTWFL1) ─────────

def _signature_definition_matrice(type_objet, chaine_paliers):
    """Code STABLE d'une ``WorkflowDefinition`` générée depuis une chaîne de
    paliers : deux appels avec la MÊME chaîne (même ``type_objet``, mêmes
    paliers dans le même ordre) retombent sur le même ``code`` — la
    définition est réutilisée (mise en cache) au lieu d'être recréée à
    chaque démarrage. Une chaîne modifiée par l'admin (palier ajouté/modifié)
    change le hash et matérialise une NOUVELLE définition (les instances déjà
    démarrées sur l'ancienne restent intactes, ``WorkflowInstance.definition``
    est en PROTECT)."""
    base = re.sub(r'[^a-z0-9]+', '_', str(type_objet or '').lower()).strip('_')
    base = base or 'objet'
    payload = json.dumps(chaine_paliers or [], sort_keys=True, default=str)
    digest = hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]
    return f'matrice_{base}_{digest}'[:64]


def _definition_depuis_matrice(company, matrice):
    """Construit (ou réutilise) la ``WorkflowDefinition``/``WorkflowStepDefinition``
    correspondant à une ligne ``core.MatriceApprobation`` (NTWFL1) — comble
    l'écart entre la matrice DÉCLARATIVE et le moteur d'EXÉCUTION : sans ce
    pont les deux ne se déclenchaient jamais l'un l'autre. ``None`` si la
    matrice ne porte aucun palier (rien à démarrer)."""
    from core.models import WorkflowDefinition, WorkflowStepDefinition

    paliers = matrice.chaine_paliers or []
    if not paliers:
        return None

    code = _signature_definition_matrice(matrice.type_objet, paliers)
    definition = WorkflowDefinition.objects.filter(
        company=company, code=code).first()
    if definition is not None:
        return definition

    nom = f'Matrice {matrice.type_objet}'
    if matrice.departement:
        nom = f'{nom} — {matrice.departement}'
    definition = WorkflowDefinition.objects.create(
        company=company, code=code, nom=nom,
        description=(
            'Définition générée automatiquement depuis '
            'core.MatriceApprobation (NTWFL2) — ne pas éditer à la main, '
            "modifier la matrice d'approbation source à la place."))
    for i, palier in enumerate(paliers, start=1):
        palier = palier if isinstance(palier, dict) else {}
        WorkflowStepDefinition.objects.create(
            definition=definition,
            ordre=i,
            nom=palier.get('nom') or f"Palier {palier.get('palier', i)}",
            type_approbation=WorkflowStepDefinition.APPROBATION_MANUELLE,
            role_requis=palier.get('role_requis') or '',
        )
    return definition


def demarrer_depuis_matrice(
        target, type_objet, montant, company, *,
        departement=None, user=None, now=None):
    """NTWFL2 — résout ``core.MatriceApprobation`` (NTWFL1) pour
    (``type_objet``, ``montant``, ``departement``) et démarre un
    ``WorkflowInstance`` conforme sur ``target``.

    Renvoie ``None`` — SANS RIEN CRÉER — si aucune ligne de matrice active ne
    couvre le cas : l'appelant garde alors son comportement PRÉEXISTANT
    inchangé (c'est le point d'entrée additif qui « comble l'écart entre la
    matrice déclarative et le moteur d'exécution qui aujourd'hui ne se
    déclenchent jamais l'un l'autre »). Avec une matrice couvrante, la
    ``WorkflowDefinition`` est construite À LA VOLÉE (ou réutilisée par
    signature de chaîne, voir ``_definition_depuis_matrice``) puis
    ``demarrer_workflow`` instancie et active la première étape normalement.
    """
    from core.selectors import resoudre_matrice

    matrice = resoudre_matrice(
        company, type_objet, montant=montant, departement=departement)
    if matrice is None:
        return None
    definition = _definition_depuis_matrice(company, matrice)
    if definition is None:
        return None
    return demarrer_workflow(definition, target, company, user=user, now=now)
