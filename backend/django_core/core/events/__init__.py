"""Couche d'événements métier (M6) — petit bus d'événements interne basé sur
les signaux Django, pour découpler les apps du cœur métier.

Une app émettrice (ex. ``ventes``) envoie un événement ; les apps intéressées
(``crm``, ``installations``, ``audit``…) s'y abonnent via un récepteur câblé
dans leur ``apps.py`` (``ready()``). Cela évite qu'une app importe directement
les ``models`` / ``services`` d'une autre uniquement pour réagir à un changement
d'état : l'émetteur ne connaît pas ses abonnés.

``core`` est une app de fondation : elle ne dépend d'aucune app métier, donc
placer le bus ici n'introduit aucun cycle d'import.

Carte des trois couches (M4)
----------------------------

Le repo est organisé en trois couches, chacune ne dépendant QUE de couches en
dessous d'elle ; les réactions inter-app montantes passent par ce bus, jamais
par un import direct des ``models`` / ``views`` d'une autre app :

* **Fondation** — ``authentication``, ``roles``, ``records``, ``customfields``,
  ``core`` (dont ce bus). Ne dépend d'aucune app métier.
* **Cœur métier** — ``crm``, ``stock``, ``ventes``, ``installations``, ``sav``.
  Se parlent via ``services.py`` / ``selectors.py`` (jamais les ``models`` /
  ``views`` d'une autre), et réagissent aux autres via ce bus.
* **Satellites** — ``reporting``, ``automation``, ``monitoring``,
  ``notifications``, ``publicapi``, ``audit``, ``documents``, ``dataimport``,
  ``contact``. Observent le cœur métier ; le cœur métier ne les importe pas.

M4 a supprimé la dernière arête montante ``ventes → audit`` : ``ventes`` émet
désormais ``document_pdf_generated`` et le satellite ``audit`` s'y abonne
(``apps/audit/receivers.py``) pour journaliser le PDF, sans que ``ventes``
importe ``apps.audit``.

Événements disponibles
----------------------

``module_toggled``
    ODY25 — Émis à CHAQUE bascule RÉELLE d'un ``core.ModuleToggle`` (une app
    installée ou désinstallée pour une société), aux DEUX seuls sites qui
    écrivent cet état : ``core.feature_flags.activer_module`` et
    ``core.feature_flags.desactiver_module``. Émis UNIQUEMENT sur un
    FRANCHISSEMENT — ré-activer une app déjà active, ou désactiver une app déjà
    désactivée, n'émet RIEN (le journal de la boutique ne doit pas se remplir de
    lignes « rien n'a changé »). Une bascule en CASCADE émet un événement PAR
    module réellement basculé : le journal montre l'effet complet, pas seulement
    le module cliqué. Arguments du signal :

    * ``toggle`` — l'instance ``core.ModuleToggle`` après écriture ;
    * ``company`` — la société (posée côté serveur, jamais du corps) ;
    * ``module`` — la clé de module (chaîne LIBRE : ``core`` ne connaît aucun
      module métier, contrat import-linter) ;
    * ``actif`` — le NOUVEL état (``True`` = installée) ;
    * ``user`` — l'utilisateur qui bascule (peut être ``None`` : bascule
      système, commande de gestion, provisioning) ;
    * ``raison`` — le motif éventuel porté par le toggle.

    Abonné dans ce repo : ``records`` (``apps/records/receivers.py``, câblé
    dans son ``apps.py`` ``ready()``). Il historise la bascule dans le CHATTER
    GÉNÉRIQUE ``records.Activity`` (ARC8) plutôt que dans un 14ᵉ modèle de
    journal maison — c'est exactement la convergence qu'ARC8 existe pour
    obtenir. La cible du chatter est le ``ModuleToggle`` lui-même : la société
    du journal est donc CELLE du toggle, et l'isolation multi-tenant est
    STRUCTURELLE (pas un filtre qu'on peut oublier).

    L'abonné n'est PAS dans ``core`` (patron émetteur=abonné de
    ``contrat_signe``/``incident_declared``) pour une raison de contrat :
    ``records.services`` — seul point d'écriture autorisé du chatter — importe
    les ``selectors`` de crm/ventes/stock (VX210(c)), donc un
    ``core → records.services`` créerait la chaîne ``core → apps.crm``
    interdite par ``core-foundation-is-a-base-layer``. ``core`` ne lit du
    journal que ``records.models`` (module sans dépendance métier), via
    ``core.feature_flags.journal_modules``.

Contrat transactionnel des abonnés (APAR48)
-------------------------------------------

Les signaux sont SYNCHRONES : un abonné tourne DANS la transaction de
l'émetteur. Un abonné ANNEXE (best-effort : notification, case « Premiers
pas », ticket SAV, provision GR/IR…) porte ``@abonne_best_effort`` : il
tourne dans son PROPRE point de sauvegarde, son erreur est journalisée
(``logger.exception``) et n'annule ni l'action émettrice (encaissement,
synchro terrain, étape BPM) ni les autres abonnés. Un abonné OBLIGATOIRE
(lettrage compta, création du chantier, dés-acceptation) n'en porte pas :
son erreur annule l'action en bloc. Jamais d'``except: pass`` nu.

* ``facture_payee`` — best-effort : onboarding, notifications.
* ``intervention_completed`` — best-effort : onboarding, sav.
* ``workflow_etape_activee`` — best-effort : notifications (l'émetteur
  ``core.workflow._emit_etape_activee`` isole aussi l'envoi).
* ``reception_fournisseur_confirmee`` / ``reception_fournisseur_annulee`` /
  ``bon_commande_cree`` / ``facture_fournisseur_creee`` — best-effort :
  installations (GR/IR, séries, réservations, rattachement BC).
"""
import functools
import logging

import django.dispatch
from django.db import transaction as _transaction

from .parked import *  # noqa: F401,F403
from .facturation import *  # noqa: F401,F403
from .devis import *  # noqa: F401,F403
from .stock import *  # noqa: F401,F403
from .lead import *  # noqa: F401,F403
from .acquisition import *  # noqa: F401,F403
from .chantiers import *  # noqa: F401,F403
from .sav import *  # noqa: F401,F403
from .calepinage import *  # noqa: F401,F403

_logger = logging.getLogger(__name__)


def abonne_best_effort(func):
    """APAR48 — isole un abonné ANNEXE du bus dans son point de sauvegarde.

    L'abonné s'exécute sous ``transaction.atomic()`` : une erreur base (ou
    toute autre exception) annule SEULEMENT ce qu'il a écrit, est journalisée
    par ``logger.exception`` et n'est jamais remontée à l'émetteur — la
    transaction englobante reste utilisable, les autres abonnés tournent.
    À poser SOUS ``@receiver`` (c'est l'enveloppe qui est abonnée). Le
    marqueur ``abonne_best_effort = True`` permet aux tests de distinguer
    les abonnés annexes des obligatoires."""
    nom = f'{func.__module__}.{func.__qualname__}'

    @functools.wraps(func)
    def enveloppe(*args, **kwargs):
        try:
            with _transaction.atomic():
                return func(*args, **kwargs)
        except Exception:  # noqa: BLE001 — best-effort, journalisé
            _logger.exception('Abonné best-effort %s en échec (isolé)', nom)
            return None

    enveloppe.abonne_best_effort = True
    return enveloppe


# Émis par le kit DocumentMetier (SCA30, ``core.documents``) quand un document
# métier change de statut via ``changer_statut()`` gardé côté service. GÉNÉRIQUE
# (un seul signal pour tout document composant le kit) — le cycle de vie PROPRE
# du document, DISTINCT du cycle d'APPROBATION qui reste ARC10/WorkflowDefinition.
# EXCLUSION PERMANENTE (règle #4) : Devis/Facture/BonCommande/Avoir ne sont
# JAMAIS rétrofittés sur le kit ; ce signal ne les concerne donc jamais.
# Arguments : instance (le document), ancien_statut, nouveau_statut,
# user (peut être None), company. Aucun abonné obligatoire (pose du seam pour
# audit/notifications/KPI d'un futur type de document construit sur le kit).
document_statut_change = django.dispatch.Signal()


# NTADM40 — ``apps.entites`` émet ces 2 événements à la création/désactivation
# d'une ``Entite`` (jamais de suppression dure). Permet à d'autres apps de
# réagir (ex. invalider un cache d'agrégats par entité) sans import direct de
# ``apps.entites.models``. Arguments des deux signaux : ``entite`` (instance
# ``Entite``), ``user`` (peut être None).
entite_created = django.dispatch.Signal()
entite_deactivated = django.dispatch.Signal()


# NTUX7 — Émis par TOUTE app qui soft-supprime (archive/annule) un
# enregistrement, pour alimenter la corbeille transverse 30 jours SANS créer un
# modèle « éléments supprimés » par app. Abonné dans ce repo : ``trash``
# (``apps/trash/receivers.py`` → ``ElementSupprime``). L'émetteur ne connaît pas
# la corbeille, et ``apps.trash`` n'importe aucune app métier (la cible est
# pointée par ``contenttypes``). Arguments : ``instance`` (l'objet
# soft-supprimé), ``company``, ``user`` (peut être None), ``type_libelle``
# (libellé de type lisible, ex. « Devis » — à défaut le nom du ContentType),
# ``libelle`` (snapshot d'affichage — à défaut ``str(instance)``), ``donnees``
# (dict best-effort, AFFICHAGE SEUL, jamais réinjecté à la restauration).
record_soft_deleted = django.dispatch.Signal()

# ODY25 — une app est INSTALLÉE ou DÉSINSTALLÉE pour une société (bascule réelle
# d'un ``core.ModuleToggle``, franchissement uniquement). Arguments : toggle,
# company, module, actif, user (peut être None), raison. Abonné dans ce repo :
# ``records`` (``apps/records/receivers.py`` → chatter générique ARC8 sur le
# toggle) — voir la docstring du module ci-dessus.
module_toggled = django.dispatch.Signal()

# AUD816 — une ÉDITION EN MASSE a été appliquée (``core.bulk_edit``). Ce
# chemin écrit par ``queryset.update()`` : il court-circuite ``Model.save()``,
# ``full_clean()`` et TOUS les signaux — donc l'audit générique par
# ``post_save`` (``apps.audit.signals.TRACKED_MODELS``) ne voit RIEN passer.
# Cet événement est le SEUL canal par lequel une opération de masse laisse une
# trace, et il permet à ``core`` (fondation) de la produire sans importer
# ``apps.audit`` (contrat import-linter ``core-foundation-is-a-base-layer``).
# Émis UNE fois par lot réellement appliqué (jamais si 0 ligne modifiée).
# Arguments : ``target`` (nom logique de la cible), ``label``, ``fields``
# (liste des champs écrits), ``count`` (nb de lignes modifiées), ``company``,
# ``user`` (peut être None). Abonné : ``apps/audit/receivers.py``.
bulk_edit_applied = django.dispatch.Signal()


# ===========================================================================
# NTPLT9/10 — Outbox transactionnel FIABLE (façade au-dessus des signaux M6).
#
# ``emit_reliable(event, **kwargs)`` écrit une ligne ``core.OutboxEvent`` DANS la
# transaction appelante puis, via ``transaction.on_commit``, émet l'événement
# synchrone M6 EXISTANT inchangé (les abonnés actuels ne voient aucune
# différence). Un worker (``core.dispatch_outbox``) livre ensuite la ligne aux
# handlers DURABLES enregistrés par ``subscribe_durable`` — « aucun événement
# perdu, même sur crash ». ``core`` reste fondation : aucun import d'app métier.
# ===========================================================================

# Registre {event_name: [(handler_name, handler, rejouable)]}. Peuplé par les
# apps dans leur ``ready()`` via ``subscribe_durable``.
_DURABLE_HANDLERS: dict = {}


def subscribe_durable(name, handler, *, rejouable=False, handler_name=None):
    """Abonne un handler DURABLE à l'événement ``name`` (livré par l'outbox).

    ``handler(outbox_event)`` reçoit l'instance ``OutboxEvent`` livrée. Doit
    être IDEMPOTENT (la livraison est at-least-once ; la dédup par
    ``(event_id, handler_name)`` garantit l'effet exactement-une-fois).
    ``rejouable=True`` autorise le rejeu ciblé support (NTPLT13). Ré-abonner le
    même ``handler_name`` remplace (idempotent au rechargement d'app)."""
    hname = handler_name or getattr(handler, '__name__', repr(handler))
    entries = _DURABLE_HANDLERS.setdefault(name, [])
    entries[:] = [e for e in entries if e[0] != hname]
    entries.append((hname, handler, bool(rejouable)))


def durable_handlers(name):
    """Handlers durables (liste de tuples) enregistrés pour ``name``."""
    return list(_DURABLE_HANDLERS.get(name, []))


def clear_durable_handlers():
    """Vide le registre des handlers durables (test uniquement)."""
    _DURABLE_HANDLERS.clear()


def _jsonify(value):
    """Rend une valeur JSON-sérialisable pour le payload d'outbox.

    Une instance de modèle → ``{'_model': 'app.Model', 'pk': ...}`` ; un
    datetime → ISO ; les primitives telles quelles ; sinon ``str(value)``.
    """
    from datetime import date, datetime
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonify(v) for k, v in value.items()}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    meta = getattr(value, '_meta', None)
    pk = getattr(value, 'pk', None)
    if meta is not None and pk is not None:
        return {'_model': f'{meta.app_label}.{meta.model_name}', 'pk': pk}
    return str(value)


def _resolve_company(company, kwargs):
    """Déduit la société : arg explicite, sinon kwargs, sinon objet portant
    ``company``. Renvoie l'instance/None (jamais une exception)."""
    if company is not None:
        return company
    if 'company' in kwargs and kwargs['company'] is not None:
        return kwargs['company']
    for value in kwargs.values():
        c = getattr(value, 'company', None)
        if c is not None:
            return c
    return None


def emit_reliable(event, *, sender=None, company=None, emitted_by=None,
                  **kwargs):
    """Émet un événement de façon FIABLE : outbox + signal M6 synchrone.

    Écrit une ligne ``OutboxEvent`` dans la transaction courante (payload
    JSON-sérialisé, enveloppe versionnée NTPLT12) puis, sur commit, envoie le
    signal M6 existant ``events.<event>`` avec les kwargs d'origine — les
    abonnés synchrones actuels sont préservés à l'identique. Renvoie
    l'``OutboxEvent`` créé (ou ``None`` si l'événement est inconnu du bus).
    """
    from django.db import transaction

    from core.models import OutboxEvent

    signal = globals().get(event)
    if not isinstance(signal, django.dispatch.Signal):
        # Événement inconnu du bus : on n'écrit rien (contrat catalogue NTPLT12
        # le fera échouer en test) et on ne casse pas l'appelant.
        return None

    resolved_company = _resolve_company(company, kwargs)
    payload = {k: _jsonify(v) for k, v in kwargs.items()}
    row = OutboxEvent.objects.create(
        company=resolved_company,
        event_name=event,
        payload=payload,
    )

    send_kwargs = dict(kwargs)

    def _send_sync():
        signal.send(sender=sender or 'core.emit_reliable', **send_kwargs)

    transaction.on_commit(_send_sync)
    return row


# NTWFL5 — Émis par ``core.workflow.avancer`` (moteur BPM FG366) exactement
# quand une ``WorkflowStepInstance`` devient la nouvelle étape ACTIVE
# (manuelle/par rôle, en attente de décision) — comble YEVNT8 pour FG366 :
# aujourd'hui aucune notification ne part à la création d'une étape
# d'approbation BPM (les 4 autres sources de l'agrégateur XKB1 sont déjà
# câblées, voir ``apps/notifications/signals.py``). Émission best-effort,
# jamais bloquante pour le moteur BPM. Arguments : ``step``
# (``core.WorkflowStepInstance``, la nouvelle étape courante), ``company``.
# Abonné dans ce repo : notifications (``apps/notifications/signals.py``,
# notifie les managers de la société — ``core`` n'a aucune notion
# d'assignation par utilisateur, seulement ``step_def.role_requis``).
workflow_etape_activee = django.dispatch.Signal()


# ── NTUX32 — Événements des objets UX (apps.uxviews / apps.trash) ───────────
# Émis par les apps NTUX (le SEUL point d'écriture de leur état), abonnés par
# ``apps.publicapi`` (webhook sortant, voir
# ``apps/publicapi/uxviews_event_receivers.py``) — jamais un import direct
# ``uxviews``/``trash`` → ``publicapi`` : l'app émet sur le bus, sans savoir
# qui écoute (même patron que ``btp_reserve_levee`` ci-dessus).

# Émis EXACTEMENT quand une ``SavedView`` (NTUX1) est CRÉÉE ou SUPPRIMÉE avec
# ``visibilite=EQUIPE`` (jamais sur une simple modification de filtres — ça,
# c'est NTUX39/notifications). Arguments : ``view`` (l'instance ``SavedView``
# — peut être un objet déjà supprimé de la base, ne lire que ses attributs
# scalaires), ``company``, ``user`` (peut être ``None``),
# ``action`` (``'partagee'`` ou ``'suppression'``).
saved_view_shared = django.dispatch.Signal()

# Émis EXACTEMENT quand ``apps.trash.services.restaurer`` restaure avec succès
# la cible d'une entrée de corbeille (NTUX7) — jamais sur une restauration
# refusée/déjà faite. Arguments : ``element`` (l'``ElementSupprime`` fermé),
# ``obj`` (l'objet métier restauré, peut être ``None`` si la cible avait
# disparu), ``company``, ``user`` (peut être ``None``).
record_restored = django.dispatch.Signal()

# NTWFL18 — Émis par le balayage journalier ``core.dossiers
# .notifier_echeances_depassees`` pour CHAQUE dossier transverse (NTWFL17)
# dont l'échéance est dépassée alors qu'il est encore ouvert. Dédupliqué à la
# source par ``Dossier.dernier_rappel_echeance_le`` : un dossier en retard
# n'émet qu'UNE fois par jour, quel que soit le nombre de passages du job
# (même discipline anti-double-notification que NTWFL5 sur les étapes BPM).
# ``core`` ne connaît aucun canal : il émet, et ``apps.notifications``
# notifie le propriétaire. Émission best-effort, jamais bloquante pour le
# balayage des dossiers suivants. Arguments : ``dossier`` (l'instance
# ``core.Dossier``), ``company``, ``proprietaire`` (``CustomUser`` ou
# ``None`` si le dossier n'a pas de propriétaire désigné).
dossier_echeance_depassee = django.dispatch.Signal()


# NTP2P38 — ADAPTATION DE PÉRIMÈTRE, pour le 3ᵉ événement prévu au plan
# (``facture_fournisseur_exception_3voies``) : le rapprochement 3 voies est
# FG131 et vit intégralement dans les services de la comptabilité
# (``evaluer_rapprochement`` est le seul endroit où un écart reçu↔facturé est
# calculé et où le statut « en écart » est posé), app qui n'appartient pas à
# la lane de ce commit. Aucun signal n'est déclaré ici tant que son émetteur
# ne l'est pas : un signal jamais émis serait un seam creux, pas un contrat
# (même arbitrage que pour ``scm.score_fournisseur_degrade`` plus haut). La
# tâche qui touchera ``apps/compta`` l'ajoutera ici, sans rien casser.

# ── NTI18N43 — Bascule de langue (société ou client) ────────────────────────
# Une intégration tierce synchronisée (un CRM externe, un outil d'e-mailing)
# doit savoir qu'un client est passé au français ou à l'arabe : sinon elle
# continue d'écrire dans l'ancienne langue, et c'est le client qui le
# découvre. Émis quand la langue de DOCUMENT d'un client change, ou quand la
# langue par DÉFAUT de la société change ; consommé par ``apps.publicapi``
# (webhook sortant ``langue_changed``, voir
# ``apps/publicapi/i18n_event_receivers.py``) — jamais un import direct de
# ``publicapi`` depuis l'app qui écrit la langue (même patron que
# ``btp_reserve_levee`` plus haut).
#
# Arguments : ``company``, ``portee`` (``'client'`` ou ``'societe'``),
# ``client_id`` (``int`` ou ``None`` pour une bascule société),
# ``ancienne_langue``, ``nouvelle_langue`` (codes courts, ex. ``'fr'`` /
# ``'ar'``), ``user`` (peut être ``None``).
langue_changed = django.dispatch.Signal()

#: NTI18N43 — portées reconnues de la bascule de langue.
PORTEE_LANGUE_CLIENT = 'client'
PORTEE_LANGUE_SOCIETE = 'societe'


def emettre_langue_changed(company, *, ancienne_langue, nouvelle_langue,
                           portee=PORTEE_LANGUE_CLIENT, client_id=None,
                           user=None, sender=None):
    """Émet ``langue_changed`` — BEST-EFFORT, et seulement si ça a bougé.

    L'app qui ÉCRIT la langue appelle cette fonction en UNE ligne, plutôt que
    de re-coder la garde « la valeur a-t-elle réellement changé ? » et le
    try/except à chaque point d'écriture (le chemin le plus sûr pour qu'un des
    points l'oublie). Retourne ``True`` si un événement est parti.

    Une langue identique avant/après n'émet RIEN : un webhook ne doit pas
    partir parce qu'un formulaire a été ré-enregistré sans changement.
    """
    avant = (ancienne_langue or '').strip().lower()
    apres = (nouvelle_langue or '').strip().lower()
    if avant == apres:
        return False
    try:
        langue_changed.send(
            sender=sender or 'core.events',
            company=company,
            portee=portee,
            client_id=client_id,
            ancienne_langue=avant,
            nouvelle_langue=apres,
            user=user)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        import logging
        logging.getLogger(__name__).warning(
            'NTI18N43 : émission langue_changed échouée (%s %s → %s)',
            portee, avant, apres, exc_info=True)
    return True


# ── NTOBS26 — Incidents publics (page d'état) sur le bus ────────────────────
# Une intégration tierce (webhook sortant, page de statut miroir) doit savoir
# qu'un incident vient de s'ouvrir/se résoudre — système (``company=None``,
# visible de tous les tenants) ou spécifique à une société. Émis par
# le ``receivers.py`` de la page d'état (le SEUL point d'écriture du statut
# d'un incident public), consommé par ``apps.publicapi`` (webhook sortant),
# jamais un import direct ``statuspage`` -> ``publicapi``. Arguments :
# ``incident`` (l'instance ``IncidentPublic``), ``company`` (peut être
# ``None`` : incident système).
incident_opened = django.dispatch.Signal()
incident_resolved = django.dispatch.Signal()

# NTOBS26 — Émis par
# ``core.maintenance_windows.MaintenanceWindowListCreateView.perform_create``
# à la CRÉATION d'une fenêtre de maintenance : ANNONCE immédiate côté webhook
# sortant — distinct du rappel in-app 24h/1h avant l'échéance, qui reste porté
# par ``core.notify_registry`` (``_notifier_fenetre``, inchangé). Arguments :
# ``fenetre`` (l'instance ``MaintenanceWindow``), ``company`` (peut être
# ``None`` : annonce système large), ``user`` (peut être ``None``).
maintenance_window_announced = django.dispatch.Signal()

# ── NTOBS30-reste — Actions Fiabilité auditées (apps.audit) ────────────────
# Sur les 5 actions Fiabilité listées par le plan NTOBS30 (création
# MaintenanceWindow, lancement export de réversibilité, publication
# post-mortem, émission crédit SLA, édition SlaCreditPolicy), les 4 qui
# vivent dans ``core`` (``core`` NE PEUT JAMAIS importer ``apps.audit`` —
# contrat import-linter ``core-foundation-is-a-base-layer``) émettent ici ;
# ``apps.audit.receivers`` s'y abonne (M4, même patron que
# ``document_pdf_generated``/``bulk_edit_applied`` plus haut). La publication
# de post-mortem (5ᵉ action) vit dans la page d'état — pas ``core`` —
# et appelle déjà ``apps.audit.recorder`` directement (satellite → satellite,
# aucune contrainte import-linter).
#
# LIMITE ASSUMÉE (héritée de la lane NTOBS30 d'origine, voir la docstring de
# ``apps/statuspage/tests/test_ntobs30_postmortem_audit_log.py``) : la 5ᵉ
# action « édition SlaCreditPolicy » n'a AUCUNE vue d'écriture dans ce dépôt
# (``SlaCreditPolicy`` — ``core/sla.py`` — n'est exposée par aucun viewset ni
# admin ; seule écriture existante = ORM direct / seed). Aucun signal
# ``sla_credit_policy_edited`` n'est déclaré ici tant que son émetteur ne
# l'est pas : un signal jamais émis serait un seam creux, pas un contrat
# (même arbitrage que ``facture_fournisseur_exception_3voies`` plus haut).

# Émis par ``core.maintenance_windows.MaintenanceWindowListCreateView.
# perform_create`` à la CRÉATION d'une fenêtre de maintenance (même site que
# ``maintenance_window_announced`` ci-dessus — DEUX signaux distincts pour
# DEUX abonnés distincts : publicapi webhook vs audit trail interne).
# Arguments : ``fenetre`` (l'instance ``MaintenanceWindow``), ``company``
# (peut être ``None``), ``user``.
maintenance_window_created = django.dispatch.Signal()

# Émis par ``core.export_registry.declencher_export_reversibilite`` au
# DÉCLENCHEMENT d'un export de réversibilité (avant même que la tâche Celery
# ne le construise — l'action auditée est la DEMANDE, pas son aboutissement).
# Arguments : ``run`` (l'``ExportReversibiliteRun`` fraîchement créé,
# ``statut='en_cours'``), ``company``, ``user`` (le demandeur).
export_reversibilite_declenche = django.dispatch.Signal()

# Émis par ``core.sla.sla_credit_statut`` quand un humain trace la décision
# ``emis``/``refuse`` sur un crédit SLA (``SlaSnapshot.credit_statut``).
# N'ÉMET jamais l'avoir lui-même (cf. docstring de la vue) — seulement le
# FAIT qu'un humain a décidé. Arguments : ``snapshot`` (le ``SlaSnapshot``),
# ``company``, ``ancien_statut``, ``nouveau_statut``, ``user``.
sla_credit_statut_change = django.dispatch.Signal()
