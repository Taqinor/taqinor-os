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
    'valider_definition_steps',
    'cohorte_approbation',
    'approuver_en_masse',
    'register_source_conformite',
    'decisions_conformite',
    # NTWFL25 — versionnement des définitions.
    'derniere_version_active',
    'instances_actives',
    'a_des_instances_actives',
    'forker_definition',
    'editer_etapes_definition',
    'migrer_instance_vers_version',
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
        # NTWFL25 — épinglage : l'instance retient la version sur laquelle
        # elle démarre, et n'en bouge plus (sauf migration MANUELLE).
        definition_version=getattr(definition, 'version', 1) or 1,
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


def _champ_visible(champ_nom, formulaire, donnees):
    """NTWFL12 — un champ sans condition est toujours visible ; une
    condition (format core.rules) est évaluée contre les AUTRES réponses
    déjà saisies (``donnees``)."""
    regle = (formulaire.champs_conditionnels or {}).get(champ_nom) or {}
    visible_si = regle.get('visible_si')
    if not visible_si:
        return True
    from core.rules import evaluate_condition_group
    return evaluate_condition_group(visible_si, donnees)


def _formulaire_incomplet(step):
    """NTWFL12 — ``True`` si ``step.step_def.formulaire`` exige un champ
    (``requis``) actuellement VISIBLE (cf. ``_champ_visible``) mais absent/
    vide de ``step.donnees_formulaire``. Sans formulaire rattaché : toujours
    ``False`` (comportement historique inchangé). Une section répétable
    (``type == 'section'`` avec ``repetable``) ne porte pas de valeur
    directe — seuls les champs simples sont vérifiés ici."""
    formulaire = step.step_def.formulaire
    if formulaire is None:
        return False
    donnees = step.donnees_formulaire or {}
    for champ in formulaire.schema or []:
        if not isinstance(champ, dict) or champ.get('type') == 'section':
            continue
        if not champ.get('requis'):
            continue
        nom = champ.get('nom')
        if not _champ_visible(nom, formulaire, donnees):
            continue
        valeur = donnees.get(nom)
        if valeur in (None, '', [], {}):
            return True
    return False


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


def _steps_du_groupe(instance, step):
    """NTWFL10 — étapes de ``instance`` partageant le MÊME
    ``step_def.groupe_parallele`` que ``step`` (``step`` inclus). Sans
    groupe (``groupe_parallele`` vide), renvoie ``[step]`` seul —
    comportement séquentiel inchangé."""
    groupe = step.step_def.groupe_parallele
    if not groupe:
        return [step]
    return list(
        instance.step_instances
        .filter(step_def__groupe_parallele=groupe)
        .select_related('step_def')
        .order_by('ordre', 'id')
    )


@transaction.atomic
def avancer(instance, now=None, _from_start=False):
    """Fait progresser l'instance après une décision (ou au démarrage).

    Auto-approuve toute étape ``type_approbation == 'auto'`` rencontrée, puis
    s'arrête sur la première étape ``en_attente`` non-auto (qui devient
    ``etape_courante``). Si plus aucune étape n'est en attente, l'instance est
    terminée. ``now`` est passé pour horodater déterministiquement.

    NTWFL10 — groupe parallèle (``step_def.groupe_parallele``) : la marche
    ORDRE PAR ORDRE existante fait déjà tout le travail d'attente (émergent,
    sans code dédié) — tant qu'un membre du groupe reste ``en_attente``,
    ``_avancer_pointeur`` s'y arrête (il cherche le prochain ``ordre``
    strictement supérieur, PEU IMPORTE son statut, donc un membre du groupe
    encore en attente est toujours retrouvé avant l'étape suivante). Seule
    la NOTIFICATION de fan-out (tous les membres à la fois) a besoin d'un
    traitement dédié — voir plus bas. Un rejet dans un groupe termine
    l'instance immédiatement (``rejeter_etape``), exactement comme un rejet
    séquentiel classique — aucun code dédié non plus.
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
        # NTWFL10 — groupe parallèle : fan-out (notifie TOUS les membres
        # encore en attente) SEULEMENT au premier arrêt sur le groupe
        # (aucun membre encore décidé) — évite de re-notifier à chaque
        # ré-entrée dans la boucle après la décision d'UN SEUL membre
        # (celle-ci ne fait qu'avancer le pointeur vers le membre suivant
        # encore en attente, cf. docstring de ``avancer`` ci-dessus).
        membres = _steps_du_groupe(instance, step)
        if len(membres) > 1:
            deja_decides = [
                m for m in membres
                if m.statut != WorkflowStepInstance.STATUT_EN_ATTENTE]
            if not deja_decides:
                for membre in membres:
                    _emit_etape_activee(membre, instance.company)
            return instance

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
def approuver_etape(instance, user=None, commentaire='', now=None, step=None):
    """Approuve l'étape courante puis avance séquentiellement.

    ``step`` (NTWFL10, optionnel) désigne PRÉCISÉMENT l'étape à approuver —
    nécessaire pour un groupe parallèle où PLUSIEURS étapes sont en attente
    À LA FOIS (``etape_courante_de`` n'en résout qu'une). Sans ``step``
    (défaut), résout ``etape_courante_de(instance)`` comme avant —
    comportement historique STRICTEMENT inchangé pour tout appelant
    existant qui ne passe pas ce paramètre.

    Lève ``ValueError`` si l'instance n'est pas en cours ou n'a pas d'étape
    active en attente, ou (NTWFL12) si un formulaire dynamique requis n'est
    pas complété (``step.donnees_formulaire``).
    """
    moment = _resolve_now(now)
    if instance.statut != WorkflowInstance.STATUT_EN_COURS:
        raise ValueError("Aucune étape en attente à approuver.")
    cible = step if step is not None else etape_courante_de(instance)
    if cible is None or cible.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
        raise ValueError("Aucune étape en attente à approuver.")
    if _formulaire_incomplet(cible):
        raise ValueError(
            "Le formulaire de cette étape doit être complété avant "
            "l'approbation.")
    cible.statut = WorkflowStepInstance.STATUT_APPROUVE
    cible.assignee = user
    cible.decided_le = moment
    if commentaire:
        cible.commentaire = commentaire
    cible.save(update_fields=[
        'statut', 'assignee', 'decided_le', 'commentaire', 'updated_at'])
    avancer(instance, now=moment)
    return cible


@transaction.atomic
def rejeter_etape(instance, user=None, commentaire='', now=None, step=None):
    """Rejette l'étape courante : l'instance est terminée (chaîne stoppée).

    ``step`` (NTWFL10, optionnel) — même rôle que sur ``approuver_etape`` :
    désigne l'étape à rejeter dans un groupe parallèle. NTWFL10 — un rejet
    dans un groupe parallèle rejette l'ENSEMBLE (pas de logique de
    quorum) : ce comportement est DÉJÀ celui-ci (l'instance termine
    immédiatement, sans code dédié — les autres membres du groupe, encore
    ``en_attente``, cessent simplement d'apparaître dans les listes
    d'attente puisque celles-ci sont bornées à ``instance__statut=en_cours``).

    Lève ``ValueError`` si aucune étape n'est en attente.
    """
    moment = _resolve_now(now)
    if instance.statut != WorkflowInstance.STATUT_EN_COURS:
        raise ValueError("Aucune étape en attente à rejeter.")
    cible = step if step is not None else etape_courante_de(instance)
    if cible is None or cible.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
        raise ValueError("Aucune étape en attente à rejeter.")
    cible.statut = WorkflowStepInstance.STATUT_REJETE
    cible.assignee = user
    cible.decided_le = moment
    if commentaire:
        cible.commentaire = commentaire
    cible.save(update_fields=[
        'statut', 'assignee', 'decided_le', 'commentaire', 'updated_at'])
    _terminer(instance, moment)
    return cible


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
    existant qui ne passe pas ce paramètre.

    NTWFL10 — passe désormais ``step=step`` à ``approuver_etape``/
    ``rejeter_etape`` : décide PRÉCISÉMENT l'étape que l'agrégateur affichait
    (nécessaire pour un groupe parallèle, où plusieurs étapes de la MÊME
    instance sont en attente à la fois — sans ce paramètre, une résolution
    via ``etape_courante_de`` déciderait toujours le même membre). Pour une
    instance séquentielle classique (un seul membre en attente), ``step``
    EST déjà l'étape que ``etape_courante_de`` aurait résolue — comportement
    identique."""
    if on_behalf_of is not None:
        commentaire = (
            f'[Décidé par {user} au nom de {on_behalf_of}] {commentaire}'
        ).strip()
    if approve:
        return approuver_etape(
            step.instance, user=user, commentaire=commentaire, now=now,
            step=step)
    return rejeter_etape(
        step.instance, user=user, commentaire=commentaire, now=now,
        step=step)


# ── NTWFL16 — approbation groupée « identique » depuis l'inbox XKB1 ──────────
#
# L'inbox laisse cocher PLUSIEURS lignes. Une approbation groupée n'est
# légitime que si les lignes cochées sont réellement INTERCHANGEABLES : même
# type d'objet (``WorkflowInstance.content_type``) ET même palier
# (``WorkflowStepInstance.ordre``). Sinon un seul clic décide des choses de
# natures différentes — exactement ce que la traçabilité doit interdire.
#
# TRAÇABILITÉ : chaque ligne retenue est décidée SÉPARÉMENT via
# ``decide_step`` — N décisions journalisées (une ``WorkflowStepInstance``
# avec son ``assignee``/``decided_le``/``commentaire`` par item), JAMAIS une
# seule écriture globale pour N objets. Le commentaire unique saisi par
# l'approbateur est recopié sur chacune.


def cohorte_approbation(step):
    """Clé d'interchangeabilité d'une étape : (type d'objet, palier).

    Deux étapes ne sont approuvables en un seul geste que si cette clé est
    IDENTIQUE — même ``content_type`` de cible et même ``ordre`` d'étape
    (le palier de la chaîne). Lecture pure, aucune écriture."""
    return (step.instance.content_type_id, step.ordre)


def _signature_formulaire(step):
    """Signature comparable du formulaire d'une étape (NTWFL16).

    ``(formulaire_id, réponses canoniques)`` — ``(None, '{}')`` pour une
    étape sans formulaire rattaché. Sert à n'accepter dans un même geste que
    des lignes « sans formulaire requis » OU « avec formulaire identique
    pré-rempli »."""
    try:
        donnees = json.dumps(
            step.donnees_formulaire or {}, sort_keys=True, default=str)
    except (TypeError, ValueError):  # pragma: no cover - défensif
        donnees = repr(step.donnees_formulaire)
    return (step.step_def.formulaire_id, donnees)


@transaction.atomic
def approuver_en_masse(steps, *, user=None, commentaire='', now=None):
    """NTWFL16 — approuve d'un seul geste N étapes INTERCHANGEABLES.

    ``steps`` est un itérable de ``WorkflowStepInstance`` DÉJÀ bornées à la
    société de l'appelant (la vue les résout via
    ``pending_steps_for_company``) ; ``commentaire`` est le commentaire UNIQUE
    saisi pour le lot ; ``now`` est passé explicitement (déterminisme).

    Retourne ``{'cohorte': (content_type_id, ordre), 'decisions': [étapes
    décidées], 'exclusions': [{'step_id', 'motif'}]}`` — une ligne écartée
    porte TOUJOURS un motif explicite en français, jamais un silence.

    Sont écartées : une étape qui n'est plus en attente, une étape dont le
    processus n'est plus en cours, une étape dont un formulaire requis
    (NTWFL12) n'est pas complété, et une étape dont le formulaire diverge de
    celui des autres lignes retenues.

    Lève ``ValueError`` si la sélection est vide ou mélange plusieurs
    cohortes (types d'objet ou paliers différents) — aucune approbation
    « à peu près identique » n'est acceptée."""
    moment = _resolve_now(now)
    selection = list(steps)
    if not selection:
        raise ValueError("Aucune étape sélectionnée.")

    cohortes = {cohorte_approbation(s) for s in selection}
    if len(cohortes) > 1:
        raise ValueError(
            "L'approbation groupée exige le MÊME type d'objet et le MÊME "
            f"palier pour toutes les lignes : {len(cohortes)} combinaisons "
            "distinctes ont été sélectionnées.")
    cohorte = next(iter(cohortes))

    exclusions = []
    candidats = []
    for step in selection:
        if step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE:
            exclusions.append({
                'step_id': step.pk,
                'motif': "Cette étape n'est plus en attente de décision.",
            })
            continue
        if step.instance.statut != WorkflowInstance.STATUT_EN_COURS:
            exclusions.append({
                'step_id': step.pk,
                'motif': "Le processus de cet élément n'est plus en cours.",
            })
            continue
        if _formulaire_incomplet(step):
            exclusions.append({
                'step_id': step.pk,
                'motif': (
                    "Formulaire requis non complété : cet élément est exclu "
                    "de l'approbation groupée, décidez-le individuellement."),
            })
            continue
        candidats.append(step)

    reference = _signature_formulaire(candidats[0]) if candidats else None
    retenus = []
    for step in candidats:
        if _signature_formulaire(step) != reference:
            exclusions.append({
                'step_id': step.pk,
                'motif': (
                    "Formulaire différent de celui des autres lignes "
                    "sélectionnées : cet élément est exclu de l'approbation "
                    "groupée."),
            })
            continue
        retenus.append(step)

    decisions = [
        decide_step(step, approve=True, user=user, commentaire=commentaire,
                    now=moment)
        for step in retenus
    ]
    return {
        'cohorte': cohorte,
        'decisions': decisions,
        'exclusions': exclusions,
    }


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


# ── NTWFL34 — piste d'audit EXTERNE des décisions d'approbation ──────────────
#
# Un auditeur externe demande « montrez-moi toutes les décisions d'approbation
# du mois de mars, qui a décidé, en combien de temps, et au nom de qui ». Cette
# piste doit couvrir TOUTES les sources d'approbation de la maison, or ``core``
# est une couche de FONDATION : il ne peut pas importer ``apps.automation``
# ni aucune autre app métier pour aller lire leurs décisions.
#
# Même patron que ``register_delegation_resolver`` / le registre de calendrier
# ouvré : chaque app BRANCHE sa source dans son ``apps.py ready()``, ``core``
# n'en connaît que la signature. La source native FG366 (ce moteur) est
# toujours présente, sans registre. Chaque source est appelée en BEST-EFFORT :
# une app qui casse ne fait jamais tomber le rapport entier, elle disparaît
# simplement de la ligne — et le rapport DIT lesquelles ont échoué plutôt que
# de laisser croire à une piste complète.

SOURCE_CONFORMITE_BPM = 'workflow'

#: ``{nom: fn(company, periode) -> [ligne, ...]}`` — branché par les apps.
_sources_conformite = {}

#: Motif posé par ``decide_step`` quand la décision est prise « au nom de ».
_MOTIF_DELEGATION = re.compile(
    r'^\[Décidé par .+? au nom de (?P<delegant>.+?)\]')


def register_source_conformite(nom, fn):
    """Enregistre une source de décisions pour la piste d'audit (NTWFL34).

    ``fn(company, periode) -> [{'source', 'objet', 'montant', 'approbateur',
    'decide_le', 'delai_heures', 'delegation'}, ...]``. Appelée par le
    ``ready()`` de l'app propriétaire des décisions. Un second appel du même
    ``nom`` REMPLACE la source (jamais d'accumulation silencieuse)."""
    _sources_conformite[nom] = fn


def _delegation_depuis_commentaire(commentaire):
    """Nom du délégant si la décision a été prise « au nom de », sinon ''."""
    trouve = _MOTIF_DELEGATION.match(commentaire or '')
    return trouve.group('delegant') if trouve else ''


def _decisions_conformite_bpm(company, periode=None):
    """Décisions du moteur BPM FG366 (source NATIVE de ``core``).

    ``montant`` reste VIDE : une ``WorkflowInstance`` ne porte aucun montant
    (sa cible générique n'est pas introspectée pour en devenir un) — mieux
    vaut une colonne vide qu'un chiffre déduit. Les sources branchées par les
    apps, qui connaissent leurs objets, la remplissent."""
    qs = (
        WorkflowStepInstance.objects
        .filter(company=company, decided_le__isnull=False)
        .exclude(statut=WorkflowStepInstance.STATUT_EN_ATTENTE)
        .select_related('instance', 'instance__definition',
                        'instance__content_type', 'assignee')
    )
    if periode:
        try:
            annee, mois = (int(p) for p in str(periode).split('-')[:2])
        except (TypeError, ValueError):
            pass
        else:
            qs = qs.filter(decided_le__year=annee, decided_le__month=mois)

    lignes = []
    for step in qs.order_by('decided_le', 'id'):
        ct = step.instance.content_type
        cible = (f'{ct.app_label}.{ct.model} #{step.instance.object_id}'
                 if ct else f'#{step.instance.object_id}')
        delai = None
        if step.created_at and step.decided_le:
            delai = round(
                (step.decided_le - step.created_at).total_seconds() / 3600.0, 4)
        lignes.append({
            'source': SOURCE_CONFORMITE_BPM,
            'objet': (f'{step.instance.definition.code} '
                      f'#{step.instance_id} → {cible}'),
            'etape': step.step_def.nom if step.step_def_id else '',
            'decision': step.get_statut_display(),
            'montant': None,
            'approbateur': (str(step.assignee) if step.assignee_id else ''),
            'decide_le': step.decided_le,
            'delai_heures': delai,
            'delegation': _delegation_depuis_commentaire(step.commentaire),
        })
    return lignes


def decisions_conformite(company, periode=None):
    """NTWFL34 — TOUTES les décisions d'approbation d'une société.

    ``periode`` : chaîne ``'AAAA-MM'`` (un mois) ou ``None`` (tout
    l'historique). Renvoie ``{'periode', 'decisions', 'sources',
    'sources_en_erreur'}`` : ``decisions`` est trié par date de décision (les
    lignes sans date en dernier), ``sources`` liste les sources réellement
    interrogées et ``sources_en_erreur`` celles qui ont échoué — un rapport
    d'audit ne prétend JAMAIS être complet quand il ne l'est pas.

    Toujours borné à ``company`` ; ``None`` renvoie un rapport vide."""
    rapport = {'periode': periode or None, 'decisions': [],
               'sources': [], 'sources_en_erreur': []}
    if company is None:
        return rapport

    fournisseurs = [(SOURCE_CONFORMITE_BPM, _decisions_conformite_bpm)]
    fournisseurs += sorted(_sources_conformite.items())

    lignes = []
    for nom, fn in fournisseurs:
        try:
            produites = list(fn(company, periode) or [])
        except Exception:  # noqa: BLE001 — une source cassée n'emporte pas tout
            rapport['sources_en_erreur'].append(nom)
            continue
        rapport['sources'].append(nom)
        for ligne in produites:
            ligne.setdefault('source', nom)
            lignes.append(ligne)

    lignes.sort(key=_cle_tri_conformite)
    rapport['decisions'] = lignes
    return rapport


def _cle_tri_conformite(ligne):
    """Clé de tri d'une ligne d'audit : date de décision, puis source, objet.

    Trie sur l'HORODATAGE (float) plutôt que sur le ``datetime`` lui-même :
    une source branchée par une app pourrait renvoyer un datetime naïf, et
    comparer un naïf à un aware lèverait ``TypeError`` en plein rapport."""
    moment = ligne.get('decide_le')
    try:
        horodatage = moment.timestamp()
    except (AttributeError, ValueError, OSError, OverflowError):
        horodatage = 0.0
    return (moment is None, horodatage,
            str(ligne.get('source') or ''), str(ligne.get('objet') or ''))


# ── NTWFL9 — validation d'une définition AVANT sauvegarde ───────────────────

def _champ(step, nom, defaut=None):
    """Lit ``nom`` sur ``step``, qu'il s'agisse d'un ``dict`` (payload brut,
    ex. venant d'un sérialiseur) ou d'une instance de modèle."""
    if isinstance(step, dict):
        return step.get(nom, defaut)
    return getattr(step, nom, defaut)


def valider_definition_steps(steps):
    """NTWFL9 — valide une liste d'étapes AVANT sauvegarde d'une définition.

    ``steps`` : liste de ``dict``/instances portant au moins ``ordre``,
    ``type_approbation``, ``role_requis``, ``etape_alternative_si_echec``
    (le format exact du payload du sérialiseur ou des instances
    ``WorkflowStepDefinition`` — les deux sont acceptés). Renvoie une liste
    d'erreurs en FRANÇAIS (vide = définition valide) ; NE LÈVE JAMAIS.

    Règles vérifiées :
      * au moins UNE étape ;
      * chaque étape ``manuelle`` (``APPROBATION_MANUELLE``) porte un
        ``role_requis`` non vide (aucun « assigné par défaut » distinct
        n'existe sur ce modèle — ``role_requis`` est le seul champ
        d'assignation) ;
      * aucune boucle infinie via ``etape_alternative_si_echec`` (NTWFL7) :
        suit la chaîne d'alternatives de chaque étape et détecte un cycle.
    """
    from core.models import WorkflowStepDefinition

    erreurs = []
    if not steps:
        erreurs.append(
            'Une définition de workflow doit comporter au moins une étape.')
        return erreurs

    par_ordre = {}
    for s in steps:
        ordre = _champ(s, 'ordre')
        if ordre is not None:
            par_ordre[ordre] = s

    for s in steps:
        ordre = _champ(s, 'ordre')
        nom = _champ(s, 'nom') or f'#{ordre}'
        if (_champ(s, 'type_approbation')
                == WorkflowStepDefinition.APPROBATION_MANUELLE
                and not _champ(s, 'role_requis')):
            erreurs.append(
                f'L\'étape « {nom} » (approbation manuelle) doit préciser '
                'un rôle requis.')

    boucles_signalees = set()
    for s in steps:
        depart = _champ(s, 'ordre')
        alt = _champ(s, 'etape_alternative_si_echec')
        if not alt:
            continue
        vus = {depart}
        courant = alt
        while courant:
            if courant in vus:
                if depart not in boucles_signalees:
                    nom = _champ(s, 'nom') or f'#{depart}'
                    erreurs.append(
                        f'L\'étape « {nom} » forme une boucle infinie via '
                        'ses étapes alternatives.')
                    boucles_signalees.add(depart)
                break
            vus.add(courant)
            suivante = par_ordre.get(courant)
            courant = (
                _champ(suivante, 'etape_alternative_si_echec')
                if suivante is not None else None)

    return erreurs


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
    # NTWFL25 — la lignée ``code`` peut porter plusieurs versions : on réutilise
    # la DERNIÈRE version active ; à défaut, la plus récente quelle qu'elle
    # soit (comportement historique préservé — sans ce repli, une lignée
    # entièrement désactivée referait naître une v1 et collisionnerait sur
    # l'unicité (société, code, version)).
    lignee = WorkflowDefinition.objects.filter(company=company, code=code)
    definition = lignee.filter(actif=True).order_by('-version', '-id').first()
    if definition is None:
        definition = lignee.order_by('-version', '-id').first()
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


# ── NTWFL25 — versionnement des définitions et migration MANUELLE d'instance ─
#
# Le problème que cela règle : jusqu'ici, éditer les étapes d'une définition
# changeait la structure SOUS LES PIEDS des instances déjà en cours — une
# approbation démarrée sur 3 paliers pouvait se retrouver, au milieu du
# parcours, avec 5 paliers dont deux qu'on n'avait jamais vus, ou pire, sans
# l'étape où elle attendait. Désormais un ``code`` désigne une LIGNÉE :
#
#   * une édition STRUCTURELLE alors que des instances tournent FORKE la
#     version suivante (``version + 1``, ``definition_precedente`` chaînée) et
#     désactive l'ancienne — les instances en cours ne bougent PAS, les
#     nouvelles démarrent sur la dernière version active ;
#   * sans instance, la mutation EN PLACE reste autorisée (compat rétroactive :
#     un brouillon qu'on retouche ne fabrique pas une v2 pour rien) ;
#   * faire AVANCER une instance bloquée vers la nouvelle structure reste un
#     geste MANUEL et explicite (``migrer_instance_vers_version``), jamais un
#     effet de bord : l'administrateur déclare lui-même la correspondance
#     ancien→nouvel index d'étape. Deviner ce mapping serait exactement le
#     risque que le versionnement existe pour supprimer.
#
# Le patron « historique en lecture seule » est celui de
# ``contrats.VersionContrat`` / ``kb.KbArticleVersion`` (cités comme référence,
# jamais modifiés par cette tâche).

#: Champs d'une étape recopiés/appliqués lors d'un fork ou d'une édition.
CHAMPS_ETAPE = (
    'nom', 'type_approbation', 'sla_heures', 'role_requis', 'escalade_vers',
    'calendrier_ouvre', 'condition_transition', 'etape_alternative_si_echec',
    'groupe_parallele', 'formulaire',
)


def derniere_version_active(company, code):
    """La définition ACTIVE la plus récente de la lignée ``code``.

    C'est elle que démarrent les nouvelles instances. ``None`` si la lignée
    n'existe pas ou n'a plus de version active."""
    from core.models import WorkflowDefinition
    return (WorkflowDefinition.objects
            .filter(company=company, code=code, actif=True)
            .order_by('-version', '-id')
            .first())


def instances_actives(definition):
    """Les instances de ``definition`` encore EN COURS."""
    return definition.instances.filter(statut=WorkflowInstance.STATUT_EN_COURS)


def a_des_instances_actives(definition):
    """Vrai si au moins une instance de ``definition`` tourne encore."""
    return instances_actives(definition).exists()


def _etapes_jamais_instanciees(definition):
    """Vrai si AUCUNE instance (même terminée) ne référence ces étapes.

    ``WorkflowStepInstance.step_def`` est en PROTECT : une étape déjà jouée ne
    peut pas être supprimée. C'est aussi la bonne règle métier — l'historique
    d'une instance terminée ne se réécrit pas."""
    return not WorkflowStepInstance.objects.filter(
        step_def__definition=definition).exists()


def _valeurs_etape(source):
    """Extrait les champs d'étape d'un ``dict`` ou d'un objet étape."""
    if isinstance(source, dict):
        return {champ: source[champ] for champ in CHAMPS_ETAPE
                if champ in source}
    return {champ: getattr(source, champ) for champ in CHAMPS_ETAPE}


def _materialiser_etapes(definition, etapes):
    """Crée les ``WorkflowStepDefinition`` de ``definition``, renumérotées 1..n.

    ``etapes`` est une liste de ``dict`` (ou d'étapes existantes à recopier) :
    l'ordre de la liste FAIT l'ordre, ce qui garantit l'unicité
    (definition, ordre) sans faire confiance à un index envoyé par un client.
    """
    from core.models import WorkflowStepDefinition
    creees = []
    for index, source in enumerate(etapes, start=1):
        valeurs = _valeurs_etape(source)
        valeurs.setdefault('nom', f'Étape {index}')
        creees.append(WorkflowStepDefinition.objects.create(
            definition=definition, ordre=index, **valeurs))
    return creees


@transaction.atomic
def forker_definition(definition, etapes=None):
    """Crée la version SUIVANTE de ``definition`` (NTWFL25).

    ``etapes`` décrit la nouvelle structure ; ``None`` recopie la structure
    actuelle (simple montée de version). L'ancienne version passe
    ``actif=False`` — elle devient de l'historique en lecture seule, que les
    instances déjà démarrées continuent d'exécuter sans être touchées.
    """
    from core.models import WorkflowDefinition

    if etapes is None:
        etapes = list(definition.steps.order_by('ordre', 'id'))

    version_max = (WorkflowDefinition.objects
                   .filter(company=definition.company, code=definition.code)
                   .order_by('-version')
                   .values_list('version', flat=True)
                   .first()) or definition.version

    nouvelle = WorkflowDefinition.objects.create(
        company=definition.company,
        code=definition.code,
        nom=definition.nom,
        description=definition.description,
        actif=True,
        version=version_max + 1,
        definition_precedente=definition,
    )
    _materialiser_etapes(nouvelle, etapes)

    if definition.actif:
        definition.actif = False
        definition.save(update_fields=['actif', 'updated_at'])
    return nouvelle


@transaction.atomic
def editer_etapes_definition(definition, etapes):
    """Applique une édition STRUCTURELLE — en place, ou en forkant (NTWFL25).

    Retourne ``(definition_cible, forkee)``. ``forkee=True`` signifie qu'une
    NOUVELLE version porte les étapes demandées et que ``definition`` est
    restée intacte pour les instances qui l'exécutent.

    Le fork s'impose dès qu'une instance a matérialisé ces étapes — en cours
    (elle attendrait une étape disparue) comme terminée (son historique ne se
    réécrit pas, et ``step_def`` est en PROTECT). Une définition jamais
    instanciée mute EN PLACE : c'est la compatibilité rétroactive attendue.
    """
    if a_des_instances_actives(definition) or not _etapes_jamais_instanciees(
            definition):
        return forker_definition(definition, etapes), True

    definition.steps.all().delete()
    _materialiser_etapes(definition, etapes)
    return definition, False


def _valider_mapping(instance, nouvelle_definition, mapping_etapes):
    """Contrôle le mapping ancien→nouvel index avant toute écriture.

    Lève ``ValueError`` (message FR, actionnable) au premier défaut. Le
    mapping est EXIGÉ exhaustif sur les étapes déjà DÉCIDÉES : abandonner
    silencieusement une décision prise serait perdre de l'audit.
    """
    if instance.statut != WorkflowInstance.STATUT_EN_COURS:
        raise ValueError(
            'Seule une instance EN COURS peut être migrée vers une autre '
            'version.')
    if nouvelle_definition.pk == instance.definition_id:
        raise ValueError(
            "L'instance exécute déjà cette version de la définition.")
    if nouvelle_definition.company_id != instance.company_id:
        raise ValueError(
            'La définition cible appartient à une autre société.')
    if nouvelle_definition.code != instance.definition.code:
        raise ValueError(
            'La définition cible appartient à une autre lignée de processus '
            f'(« {nouvelle_definition.code} » au lieu de '
            f'« {instance.definition.code} »).')
    if not isinstance(mapping_etapes, dict) or not mapping_etapes:
        raise ValueError(
            "Le mapping ancien→nouvel index d'étape est obligatoire : la "
            'migration est un geste manuel, jamais une déduction.')

    try:
        mapping = {int(ancien): int(nouveau)
                   for ancien, nouveau in mapping_etapes.items()}
    except (TypeError, ValueError):
        raise ValueError(
            "Le mapping d'étapes doit associer des index entiers.")

    ordres_cibles = set(
        nouvelle_definition.steps.values_list('ordre', flat=True))
    inconnus = sorted(set(mapping.values()) - ordres_cibles)
    if inconnus:
        raise ValueError(
            'Étapes inexistantes dans la version cible : '
            f"{', '.join(str(o) for o in inconnus)}.")

    if len(set(mapping.values())) != len(mapping):
        raise ValueError(
            "Deux étapes d'origine ne peuvent pas viser la même étape "
            'cible.')

    steps = {step.ordre: step for step in instance.step_instances.all()}
    orphelins = sorted(set(mapping) - set(steps))
    if orphelins:
        raise ValueError(
            "Étapes inexistantes dans l'instance à migrer : "
            f"{', '.join(str(o) for o in orphelins)}.")

    decidees_non_mappees = sorted(
        ordre for ordre, step in steps.items()
        if step.statut != WorkflowStepInstance.STATUT_EN_ATTENTE
        and ordre not in mapping)
    if decidees_non_mappees:
        raise ValueError(
            'Étapes déjà décidées sans correspondance dans le mapping : '
            f"{', '.join(str(o) for o in decidees_non_mappees)}. Le mapping "
            'doit être exhaustif sur les décisions prises.')

    if instance.etape_courante not in mapping:
        raise ValueError(
            f"L'étape courante ({instance.etape_courante}) doit figurer dans "
            "le mapping : c'est elle qui décide où l'instance reprend.")

    return mapping, steps


@transaction.atomic
def migrer_instance_vers_version(instance, nouvelle_definition,
                                 mapping_etapes, now=None):
    """Déplace MANUELLEMENT une instance en cours vers une autre version.

    ``mapping_etapes`` — ``{ancien_ordre: nouvel_ordre}`` — est fourni par
    l'administrateur : jamais deviné, jamais automatique (une correspondance
    devinée ferait sauter ou rejouer une approbation). Il doit couvrir toutes
    les étapes DÉJÀ DÉCIDÉES ainsi que l'étape courante.

    Effet, sans rien perdre :
      * chaque étape mappée est RE-POINTÉE sur l'étape correspondante de la
        version cible (sa décision, son décideur, sa date et son commentaire
        sont conservés tels quels) ;
      * les étapes EN ATTENTE non mappées sont supprimées (il n'y a rien à
        perdre) et remplacées par les étapes de la version cible qu'aucune
        étape mappée ne couvre déjà ;
      * l'instance est ré-épinglée (``definition`` + ``definition_version``) et
        reprend à ``mapping_etapes[etape_courante]``.

    Lève ``ValueError`` (message FR) si le mapping n'est pas recevable —
    AVANT toute écriture.
    """
    moment = _resolve_now(now)
    mapping, steps = _valider_mapping(
        instance, nouvelle_definition, mapping_etapes)

    etapes_cibles = {
        step.ordre: step
        for step in nouvelle_definition.steps.order_by('ordre', 'id')
    }

    # Les étapes EN ATTENTE que l'administrateur n'a pas mappées disparaissent.
    for ordre, step in list(steps.items()):
        if (ordre not in mapping
                and step.statut == WorkflowStepInstance.STATUT_EN_ATTENTE):
            step.delete()
            steps.pop(ordre)

    for ancien_ordre, nouvel_ordre in sorted(mapping.items()):
        step = steps[ancien_ordre]
        cible = etapes_cibles[nouvel_ordre]
        step.step_def = cible
        step.ordre = nouvel_ordre
        step.sla_echeance = _sla_echeance(
            step.created_at or moment, cible.sla_heures,
            calendrier_ouvre=cible.calendrier_ouvre,
            company=instance.company)
        step.save(update_fields=['step_def', 'ordre', 'sla_echeance',
                                 'updated_at'])

    couverts = set(mapping.values())
    for ordre, cible in etapes_cibles.items():
        if ordre in couverts:
            continue
        WorkflowStepInstance.objects.create(
            company=instance.company,
            instance=instance,
            step_def=cible,
            ordre=ordre,
            statut=WorkflowStepInstance.STATUT_EN_ATTENTE,
            sla_echeance=_sla_echeance(
                moment, cible.sla_heures,
                calendrier_ouvre=cible.calendrier_ouvre,
                company=instance.company),
        )

    instance.definition = nouvelle_definition
    instance.definition_version = nouvelle_definition.version
    instance.etape_courante = mapping[instance.etape_courante]
    instance.save(update_fields=['definition', 'definition_version',
                                 'etape_courante', 'updated_at'])
    return instance
