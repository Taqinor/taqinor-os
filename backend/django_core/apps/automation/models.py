"""Moteur d'automatisations sans code (N72 / N73).

Une règle ``AutomationRule`` est un « si ceci → alors cela » que le founder
compose dans Paramètres. Elle réagit aux ÉVÉNEMENTS PROPRES de l'application
(signaux Django ``post_save`` sur les modèles existants : Lead, Devis, Facture,
chantier, équipement, stock), trouve les règles activées de la même société qui
correspondent au déclencheur, et exécute leurs actions EN PROCESSUS — aucun
courtier de messages, aucun n8n.

Tout est ADDITIF et OPT-IN : sans règle, rien ne change. Chaque exécution est
journalisée dans ``AutomationRun``. Quand une action est marquée « nécessite
approbation » (N73), une ``AutomationApproval`` en attente est créée au lieu de
lancer l'action ; l'approbation par un palier propriétaire (admin/responsable)
relance l'action différée.

Les envois (WhatsApp / email / SMS) RÉUTILISENT les canaux existants et restent
sans effet (no-op journalisé) quand ils ne sont pas configurés. Jamais de prix
d'achat ni de marge exposés.
"""
from django.conf import settings
from django.db import models


class TriggerType(models.TextChoices):
    """Événements internes de l'application qu'une règle peut écouter."""
    LEAD_STAGE_CHANGE = 'lead_stage_change', "Changement d'étape d'un lead"
    DEVIS_ACCEPTED = 'devis_accepted', 'Devis accepté'
    CHANTIER_STATUS = 'chantier_status', "Chantier atteint un statut"
    FACTURE_OVERDUE = 'facture_overdue', 'Facture en retard'
    WARRANTY_EXPIRING = 'warranty_expiring', 'Garantie proche expiration'
    MAINTENANCE_DUE = 'maintenance_due', 'Visite de maintenance due'
    STOCK_BELOW_THRESHOLD = 'stock_below_threshold', 'Stock sous le seuil'
    # XPLT3 — déclencheur temporel GÉNÉRIQUE : « champ date ± N jours » sur un
    # objet au choix (whitelist fermée, voir DATE_TRIGGER_TARGETS). Distinct
    # des 3 déclencheurs FIXES ci-dessus (horizons codés en dur).
    DATE_ECHEANCE_CHAMP = 'date_echeance_champ', 'Échéance de champ (± N jours)'
    # XPLT4 — webhook entrant générique : le POST externe reçu sur l'URL
    # tokenisée de la règle devient le contexte des conditions/actions.
    WEBHOOK_INBOUND = 'webhook_inbound', 'Webhook entrant'
    # XPRJ23 — étapes du projet (gestion_projet), émis DEPUIS le module (jamais
    # via un signal Django cross-app) ; config {'statut': …} avec les enums
    # PROPRES à gestion_projet (jamais STAGES.py, règle #2).
    PROJET_STATUS_CHANGE = (
        'projet_status_change', 'Changement de statut de projet')
    PROJET_PHASE_CHANGE = (
        'projet_phase_change', 'Changement de phase de projet')
    # ARC34 — déclencheur GÉNÉRIQUE de changement d'état : « le champ statut de
    # tel modèle vient de changer ». Les couples (model, field) AUTORISÉS
    # viennent du REGISTRE plateforme (surface ``automation_state_fields`` des
    # manifestes ``apps/<x>/platform.py`` — voir
    # ``record_state_change_targets()`` ci-dessous), validés à la CRÉATION de
    # la règle (serializer). Ouvre contrats/rh/sav/qhse… à l'automatisation
    # no-code SANS nouvelle migration du framework par app. Émis DEPUIS les
    # services des apps propriétaires (jamais leurs modèles) — pilotes ARC34 :
    # ``apps.contrats.services`` (statut Contrat) et ``apps.sav.services``
    # (statut Ticket). Les conditions optionnelles du ``trigger_config``
    # réutilisent l'évaluateur d'arbre FG367 (``core.rules``) — jamais un
    # nouvel évaluateur. Le catalogue FERMÉ ci-dessus reste INTOUCHÉ, et le
    # chemin parallèle ``gestion_projet`` (appel direct ``engine.evaluate()``,
    # XPRJ23 ci-dessus) est CONSERVÉ tel quel.
    RECORD_STATE_CHANGE = (
        'record_state_change', "Changement d'état d'un enregistrement")


# XPLT3 — whitelist FERMÉE (app_label, model) -> {champ date autorisé: label}
# pour le déclencheur DATE_ECHEANCE_CHAMP. On ne laisse jamais une règle
# pointer un modèle/champ arbitraire : seuls ces couples sont évaluables.
# ARC34 ne la touche PAS : le déclencheur temporel XPLT3 garde son littéral
# fermé ; seule la whitelist du NOUVEAU déclencheur RECORD_STATE_CHANGE est
# pilotée par le registre (fonction ci-dessous).
DATE_TRIGGER_TARGETS = {
    ('ventes', 'devis'): {
        'date_validite': 'Date de validité du devis',
    },
    ('crm', 'lead'): {
        'relance_date': 'Date de relance du lead',
    },
}


def record_state_change_targets(company=None):
    """ARC34 — whitelist des couples (modèle, champ d'état) automatisables via
    ``TriggerType.RECORD_STATE_CHANGE``, PILOTÉE PAR LE REGISTRE plateforme.

    Contrairement à ``DATE_TRIGGER_TARGETS`` (littéral fermé ci-dessus,
    conservé tel quel pour le déclencheur temporel XPLT3), cette whitelist est
    DÉCLARÉE par les apps propriétaires dans leurs manifestes
    ``apps/<x>/platform.py`` (surface ``automation_state_fields`` — voir
    ``core.platform``) : ajouter un couple automatisable = une ligne dans le
    manifeste de l'app, jamais une migration du framework automation.

    Renvoie ``{'app.model': {champ, ...}}`` (clés minuscules). Résolution à
    l'APPEL (jamais à l'import de ce module — le registre applicatif n'est pas
    garanti prêt au chargement) ; gatée ``ModuleToggle`` quand ``company`` est
    fourni ; robuste au registre indisponible (dict vide, jamais d'exception).
    """
    try:
        from core import platform
        entries = platform.automation_state_fields(company=company)
    except Exception:  # pragma: no cover - registre indisponible
        return {}
    out = {}
    for entry in entries:
        model = (entry.get('model') or '').strip().lower()
        field = (entry.get('field') or '').strip()
        if model and field:
            out.setdefault(model, set()).add(field)
    return out


class ActionType(models.TextChoices):
    """Actions qu'une règle peut exécuter en réaction au déclencheur."""
    SEND_WHATSAPP = 'send_whatsapp', 'Envoyer un WhatsApp'
    SEND_EMAIL = 'send_email', 'Envoyer un email'
    SEND_SMS = 'send_sms', 'Envoyer un SMS'
    CREATE_ACTIVITY = 'create_activity', 'Créer une activité / tâche'
    ASSIGN_RECORD = 'assign_record', 'Assigner un enregistrement'
    SET_FIELD = 'set_field', 'Mettre à jour un champ'
    CREATE_SAV_TICKET = 'create_sav_ticket', 'Créer un ticket SAV'


class CanalMessage(models.TextChoices):
    """Canal d'envoi d'un modèle de message d'automatisation."""
    EMAIL = 'email', 'Email'
    WHATSAPP = 'whatsapp', 'WhatsApp'
    DOC = 'doc', 'Document'


# Sujet/corps par défaut par canal. Tant qu'aucun ``ModeleMessage`` n'est
# enregistré pour la société + le canal, ces valeurs s'appliquent — le
# comportement reste IDENTIQUE à l'ancien sujet codé en dur
# « Notification Taqinor ». Le corps reste vide par défaut (l'action retombe
# alors sur ``action_config['body']`` ou un modèle Paramètres, inchangé).
MODELE_MESSAGE_DEFAULTS = {
    CanalMessage.EMAIL: {'objet': 'Notification Taqinor', 'corps': ''},
    CanalMessage.WHATSAPP: {'objet': '', 'corps': ''},
    CanalMessage.DOC: {'objet': 'Notification Taqinor', 'corps': ''},
}


class ModeleMessage(models.Model):
    """Modèle de message éditable par société et par canal (DC18).

    Remplace le sujet d'email codé en dur (« Notification Taqinor ») par un
    modèle stocké et modifiable : un ``objet`` (sujet) et un ``corps`` par
    canal (email / WhatsApp / doc). Tant qu'aucun modèle n'est enregistré pour
    la société + le canal, ``resolve`` retombe sur ``MODELE_MESSAGE_DEFAULTS``
    — le comportement reste donc identique à l'ancien sujet codé en dur.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='automation_modeles_message')
    canal = models.CharField(
        max_length=20, choices=CanalMessage.choices)
    objet = models.CharField(max_length=255, blank=True, default='')
    corps = models.TextField(blank=True, default='')
    enabled = models.BooleanField(default=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Modèle de message"
        verbose_name_plural = "Modèles de message"
        ordering = ['canal', 'id']
        unique_together = [('company', 'canal')]
        indexes = [
            models.Index(
                fields=['company', 'canal', 'enabled'],
                name='automation_modmsg_idx'),
        ]

    def __str__(self):
        return f'{self.company_id}:{self.canal}'

    @classmethod
    def resolve(cls, company, canal):
        """Renvoie ``(objet, corps)`` pour (société, canal).

        Retombe sur ``MODELE_MESSAGE_DEFAULTS`` quand aucun modèle ACTIVÉ n'est
        enregistré (ou que ses champs sont vides) — comportement préservé.
        """
        default = MODELE_MESSAGE_DEFAULTS.get(
            canal, {'objet': '', 'corps': ''})
        row = None
        if company is not None:
            try:
                row = cls.objects.filter(
                    company=company, canal=canal, enabled=True).first()
            except Exception:  # pragma: no cover - défensif
                row = None
        if row is None:
            return default['objet'], default['corps']
        objet = (row.objet or '').strip() or default['objet']
        corps = (row.corps or '').strip() or default['corps']
        return objet, corps


class AutomationRule(models.Model):
    """Règle d'automatisation éditable (N72), par société.

    ``trigger_config`` et ``action_config`` sont des dictionnaires JSON libres
    interprétés par le moteur selon ``trigger_type`` / ``action_type`` (ex.
    ``trigger_config={'stage': 'SIGNED'}`` ou
    ``action_config={'field': 'priorite', 'value': 'haute'}``).

    ``requires_approval`` (N73) : quand vrai, la correspondance crée une
    approbation en attente au lieu de lancer l'action ; l'approbation relance
    l'action différée.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='automation_rules')
    nom = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)

    trigger_type = models.CharField(
        max_length=40, choices=TriggerType.choices)
    trigger_config = models.JSONField(default=dict, blank=True)

    action_type = models.CharField(
        max_length=40, choices=ActionType.choices)
    action_config = models.JSONField(default=dict, blank=True)

    # N73 — l'action passe par une étape d'approbation propriétaire.
    requires_approval = models.BooleanField(default=False)
    # Seuil configurable au-delà duquel l'approbation s'applique (ex. remise %).
    # Vide = l'approbation s'applique inconditionnellement quand
    # requires_approval est vrai.
    approval_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)

    ordre = models.PositiveIntegerField(default=0)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Règle d'automatisation"
        verbose_name_plural = "Règles d'automatisation"
        ordering = ['ordre', 'id']
        indexes = [
            models.Index(fields=['company', 'enabled', 'trigger_type']),
        ]

    def __str__(self):
        return self.nom


class AutomationRun(models.Model):
    """Journal d'UNE exécution de règle (N72) — chaque tentative est tracée."""

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Réussi'
        SKIPPED = 'skipped', 'Ignoré'
        FAILED = 'failed', 'Échec'
        PENDING_APPROVAL = 'pending_approval', "En attente d'approbation"
        NOOP = 'noop', 'Sans effet'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='automation_runs')
    rule = models.ForeignKey(
        AutomationRule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='runs')
    # Référence libre vers l'objet déclencheur (label + id), sans FK rigide :
    # le moteur écoute des modèles hétérogènes.
    target_model = models.CharField(max_length=120, blank=True, default='')
    target_id = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SUCCESS)
    message = models.TextField(blank=True, default='')

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Exécution d'automatisation"
        verbose_name_plural = "Exécutions d'automatisation"
        ordering = ['-timestamp', '-id']
        indexes = [
            models.Index(fields=['company', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.rule_id}:{self.status}@{self.timestamp:%Y-%m-%d %H:%M}'


class AutomationApproval(models.Model):
    """Étape d'approbation propriétaire (N73) pour une action différée.

    Quand une règle correspond mais que son action exige une approbation, on
    crée une approbation EN ATTENTE au lieu de lancer l'action. Un palier
    propriétaire (admin/responsable) approuve — ce qui relance l'action
    différée — ou rejette.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        APPROVED = 'approved', 'Approuvé'
        REJECTED = 'rejected', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='automation_approvals')
    rule = models.ForeignKey(
        AutomationRule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approvals')

    # Référence vers l'objet concerné (label + id) — l'action différée s'y
    # rapplique à l'approbation.
    target_model = models.CharField(max_length=120, blank=True, default='')
    target_id = models.PositiveIntegerField(null=True, blank=True)

    # Description lisible de l'action en attente + son contexte gelé.
    description = models.CharField(max_length=255, blank=True, default='')
    context = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='automation_approvals_requested')
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='automation_approvals_decided')
    decided_at = models.DateTimeField(null=True, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Approbation d'automatisation"
        verbose_name_plural = "Approbations d'automatisation"
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f'{self.rule_id}:{self.status}'


# ── XKB2 — Types de demandes d'approbation ad-hoc configurables ─────────────
#
# Distinct de `parametres.ApprovalPolicy` (FG25 — politiques déclaratives
# seuil+palier sur des types d'action EXISTANTS, consultées par les chemins
# d'écriture) : ici c'est la couche demande/soumission ad-hoc générique
# (note de frais, déplacement, achat hors catalogue…) qu'un admin définit
# librement, alimentant la boîte d'approbations XKB1
# (``AutomationApprovalViewSet`` / futur agrégateur ``reporting``).

class ApprovalFieldKey(models.TextChoices):
    """Champs optionnels qu'un type de demande peut exiger/afficher."""
    MONTANT = 'montant', 'Montant'
    TIERS = 'tiers', 'Tiers'
    DATE_DEBUT = 'date_debut', 'Date de début'
    DATE_FIN = 'date_fin', 'Date de fin'
    QUANTITE = 'quantite', 'Quantité'
    REFERENCE = 'reference', 'Référence'


class ApprovalRequestType(models.Model):
    """Type de demande d'approbation ad-hoc, défini par un admin (XKB2).

    ``champs_requis`` / ``champs_optionnels`` listent des clés parmi
    ``ApprovalFieldKey`` : un champ requis doit être renseigné dans
    ``ApprovalRequest.payload`` à la soumission, sinon rejet (400 FR).

    ``palier_approbateur`` réutilise les mêmes paliers que
    ``parametres.ApprovalPolicy.ApproverTier`` (chaîne libre ici pour éviter
    tout couplage cross-app — validée par les mêmes valeurs côté serializer).
    """

    class ApproverTier(models.TextChoices):
        RESPONSABLE = 'responsable', 'Responsable (ou plus)'
        ADMIN = 'admin', 'Administrateur uniquement'

    class SequenceApprobateurs(models.TextChoices):
        # ZCTR8 — ordre des approbateurs quand min_approbations > 1.
        PARALLELE = 'parallele', 'Parallèle (tous notifiés d’emblée)'
        SEQUENTIEL = 'sequentiel', 'Séquentiel (rang par rang)'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='approval_request_types')
    nom = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default='')
    enabled = models.BooleanField(default=True)

    champs_requis = models.JSONField(default=list, blank=True)
    champs_optionnels = models.JSONField(default=list, blank=True)

    palier_approbateur = models.CharField(
        max_length=20, choices=ApproverTier.choices,
        default=ApproverTier.ADMIN)

    # ZCTR8 — mode d'ordonnancement des approbateurs. Rétrocompat : PARALLELE
    # (défaut) = comportement XKB1/XKB2 inchangé (tous les approbateurs du
    # palier voient la demande dès la soumission).
    sequence_approbateurs = models.CharField(
        max_length=12, choices=SequenceApprobateurs.choices,
        default=SequenceApprobateurs.PARALLELE)

    # ZCTR7 — nombre minimum d'approbations FAVORABLES distinctes avant que la
    # demande passe APPROVED. Rétrocompat : 1 = comportement XKB2 inchangé
    # (une seule décision suffit).
    min_approbations = models.PositiveIntegerField(default=1)
    # ZCTR7 — la soumission est refusée (400 FR) tant qu'aucune pièce jointe
    # n'est rattachée. Rétrocompat : False = comportement XKB2 inchangé.
    piece_jointe_obligatoire = models.BooleanField(default=False)
    # ZCTR7 — config granulaire par champ : {'montant': 'requis'|'optionnel'|
    # 'masque', ...}. Vide = comportement XKB2 inchangé (seuls champs_requis/
    # champs_optionnels comptent).
    champs_config = models.JSONField(default=dict, blank=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Type de demande d'approbation"
        verbose_name_plural = "Types de demande d'approbation"
        ordering = ['nom', 'id']
        indexes = [
            models.Index(fields=['company', 'enabled']),
        ]

    def __str__(self):
        return self.nom

    def _label_for(self, champ):
        return ApprovalFieldKey(champ).label \
            if champ in ApprovalFieldKey.values else champ

    def required_fields(self):
        """Union de ``champs_requis`` (XKB2) et des champs marqués « requis »
        dans ``champs_config`` (ZCTR7) — les deux mécanismes coexistent."""
        requis = set(self.champs_requis or [])
        for champ, mode in (self.champs_config or {}).items():
            if mode == 'requis':
                requis.add(champ)
        return requis

    def validate_payload(self, payload):
        """Renvoie une liste d'erreurs FR (vide = payload valide).

        Un champ listé dans ``champs_requis`` OU marqué « requis » dans
        ``champs_config`` (ZCTR7) doit être présent et non vide dans
        ``payload`` (dict soumis par le demandeur).
        """
        errors = []
        payload = payload or {}
        for champ in self.required_fields():
            value = payload.get(champ)
            if value in (None, '', [], {}):
                errors.append(
                    f'Le champ « {self._label_for(champ)} » est requis.')
        return errors


class ApprovalRequest(models.Model):
    """Demande d'approbation ad-hoc soumise par un employé (XKB2).

    Alimente la boîte d'approbations XKB1 au même titre qu'``AutomationApproval``
    (déclenchées, elles, par le moteur de règles) — deux origines, une seule
    boîte de décision côté propriétaire.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'En attente'
        APPROVED = 'approved', 'Approuvé'
        REJECTED = 'rejected', 'Rejeté'
        # ZCTR8 — renvoyée à l'émetteur pour complément ; NI approuvée NI
        # rejetée. Le demandeur peut re-soumettre (ré-éditer puis re-passer
        # PENDING) — la ré-édition reste hors du périmètre serveur ici (le
        # frontend rouvre un nouveau cycle en mettant à jour `payload` puis
        # en appelant l'action dédiée `resoumettre`, voir services.py).
        INFO_REQUESTED = 'info_requested', "Complément d'information demandé"

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='approval_requests')
    request_type = models.ForeignKey(
        ApprovalRequestType, on_delete=models.PROTECT,
        related_name='requests')

    demandeur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approval_requests_soumises')
    payload = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING)

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approval_requests_decidees')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True, default='')
    # XKB3 — posé quand ``decided_by`` a décidé EN TANT QUE suppléant d'une
    # délégation active (au nom du délégant). Vide = décision directe,
    # comportement XKB2 inchangé.
    decided_on_behalf_of = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approval_requests_deleguees')

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Demande d'approbation"
        verbose_name_plural = "Demandes d'approbation"
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f'{self.request_type_id}:{self.status}'


class ApprovalDecision(models.Model):
    """UNE décision d'approbateur sur une ``ApprovalRequest`` (ZCTR7).

    Distinct de ``ApprovalRequest.decided_by`` (qui reste le DERNIER
    décideur / celui qui a clos la demande, pour compat XKB2) : ici on
    trace CHAQUE décision favorable/défavorable, ce qui permet le seuil
    ``min_approbations`` (N approbateurs DISTINCTS avant clôture).
    """

    class Decision(models.TextChoices):
        APPROVE = 'approve', 'Favorable'
        REJECT = 'reject', 'Défavorable'

    request = models.ForeignKey(
        ApprovalRequest, on_delete=models.CASCADE, related_name='decisions')
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approval_decisions')
    decision = models.CharField(max_length=10, choices=Decision.choices)
    note = models.CharField(max_length=255, blank=True, default='')
    # XKB3 — décision prise « au nom de » ce délégant (délégation active).
    on_behalf_of = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approval_decisions_deleguees')

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Décision d'approbation"
        verbose_name_plural = "Décisions d'approbation"
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(fields=['request', 'decision']),
        ]

    def __str__(self):
        return f'{self.request_id}:{self.decided_by_id}:{self.decision}'


# ── XKB3 — Délégation d'approbation (suppléant) ──────────────────────────────

class ApprovalDelegation(models.Model):
    """Délégation d'absence : pendant [date_debut, date_fin], les demandes en
    attente du délégant apparaissent aussi chez le suppléant (XKB1) et sa
    décision porte la mention « au nom de ». Retour automatique à l'expiration
    (aucun état à réinitialiser : la plage de dates fait foi à chaque lecture).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='approval_delegations')
    delegant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='approval_delegations_donnees')
    suppleant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='approval_delegations_recues')
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Délégation d'approbation"
        verbose_name_plural = "Délégations d'approbation"
        ordering = ['-date_debut', '-id']
        indexes = [
            models.Index(fields=['company', 'delegant']),
            models.Index(fields=['company', 'suppleant']),
        ]

    def __str__(self):
        return f'{self.delegant_id} -> {self.suppleant_id}'

    def is_active(self, at=None):
        from django.utils import timezone
        at = at or timezone.now()
        return self.date_debut <= at <= self.date_fin


# ── XPLT4 — Webhook ENTRANT générique alimentant une règle ──────────────────

def _generate_webhook_token():
    import secrets
    return secrets.token_urlsafe(32)


def _generate_webhook_secret():
    import secrets
    return secrets.token_urlsafe(32)


class IncomingWebhookTrigger(models.Model):
    """URL tokenisée d'entrée pour UNE règle ``AutomationRule`` de type
    ``WEBHOOK_INBOUND`` (XPLT4). Un POST externe valide sur
    ``/api/public/hooks/<token>/`` alimente le JSON reçu comme contexte des
    conditions/actions de la règle.

    La société est résolue UNIQUEMENT par le token (jamais par le payload) —
    même discipline que les autres webhooks entrants du repo (crm site-lead).
    ``hmac_secret`` est optionnel : quand posé, l'appelant doit signer le
    corps en HMAC-SHA256 (en-tête ``X-Signature``) — sinon l'endpoint reste
    ouvert au token seul (compromis simplicité/sécurité laissé à l'admin).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='incoming_webhook_triggers')
    rule = models.OneToOneField(
        AutomationRule, on_delete=models.CASCADE,
        related_name='incoming_webhook')

    token = models.CharField(
        max_length=64, unique=True, default=_generate_webhook_token)
    hmac_secret = models.CharField(max_length=128, blank=True, default='')
    enabled = models.BooleanField(default=True)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Webhook entrant (automatisation)'
        verbose_name_plural = 'Webhooks entrants (automatisation)'
        ordering = ['-date_creation', '-id']
        indexes = [
            models.Index(fields=['token']),
        ]

    def __str__(self):
        return f'{self.rule_id}:{self.token[:8]}…'

    def rotate_token(self):
        """Régénère le token : l'ancien devient immédiatement invalide (404)."""
        self.token = _generate_webhook_token()
        self.save(update_fields=['token', 'date_modification'])
        return self.token


class AutomationRunArchive(models.Model):
    """YOPSB11 — copie FROIDE d'un ``AutomationRun`` archivé.

    Le journal des exécutions (`AutomationRun`) est append-only et grossit sans
    borne. La politique de rétention YOPSB11 déplace les exécutions anciennes
    ici (par lots) puis les supprime de la table vive. Schéma miroir SANS index
    chaud, FK dénormalisées en identifiants entiers (aucune cascade sur
    l'archive)."""

    original_id = models.BigIntegerField(
        help_text="PK de l'AutomationRun d'origine (table vive).")
    company_id = models.BigIntegerField(null=True, blank=True)
    rule_id = models.BigIntegerField(null=True, blank=True)
    target_model = models.CharField(max_length=120, blank=True, default='')
    target_id = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20)
    message = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField()
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Exécution d'automatisation (archive)"
        verbose_name_plural = "Exécutions d'automatisation (archive)"

    def __str__(self):
        return f'archive:{self.original_id}'
