"""Activités planifiées (style Odoo) et pièces jointes — génériques.

Les deux modèles se rattachent à N'IMPORTE quel enregistrement métier via
contenttypes (Lead, Client, Chantier, Ticket SAV…), sans coupler les apps.
Tout est company-stampé côté serveur et filtré par société, comme le reste.

ALLOWED_TARGETS borne explicitement les modèles que l'on peut cibler : on ne
laisse jamais le navigateur attacher une activité/un fichier à un modèle
arbitraire.

ARC30 — PILOTÉE PAR LE REGISTRE (``core.platform``). Avant ARC30, les 19
cibles historiques étaient un ``set`` littéral figé ici : une nouvelle cible
exigeait de modifier CE fichier (l'anti-leçon Odoo). Elles sont désormais
DÉCLARÉES par leurs apps propriétaires dans les manifestes
``apps/<x>/platform.py`` (surface ``record_targets``, format ``'app.model'``).
``ALLOWED_TARGETS`` est désormais un OBJET PARESSEUX
(:class:`_LazyAllowedTargets`) qui se comporte comme un ``set`` immuable en
lecture (``in``, itération, ``len``) mais calcule son contenu à la PREMIÈRE
UTILISATION en unionnant ``core.platform.record_targets(company=None)`` (tous
les manifestes, gatage société non pertinent ici — ``ALLOWED_TARGETS`` borne
la forme des URLs/modèles acceptés, pas leur visibilité par société) sur
TOUTES les apps installées. Résolution PARESSEUSE À DESSEIN : au moment où ce
module est importé (chargement des apps Django), le registre applicatif n'est
pas garanti prêt — le calcul n'a lieu qu'au premier ``in``/itération, bien
après le démarrage. Chaque app propriétaire déclare désormais sa/ses cible(s)
dans son propre ``platform.py`` (``record_targets``) — ajouter une cible = une
ligne dans le manifeste de l'app, jamais plus une modification de ce fichier.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class _LazyAllowedTargets:
    """Vue ``frozenset``-like sur ``core.platform.record_targets()``, calculée
    au premier accès (jamais à l'import de ce module — ``core`` /
    ``django.apps`` peuvent ne pas être prêts à ce moment).

    Se comporte comme l'ancien ``set`` littéral pour tous les usages existants
    du dépôt (``in``, itération, ``len``) — DROP-IN replacement, non-régression
    garantie par test (le set résolu == les 19 couples historiques).
    """

    def _resolve(self):
        from core import platform
        return {
            tuple(cle.split('.', 1))
            for cle in platform.record_targets(company=None)
        }

    def __contains__(self, item):
        return item in self._resolve()

    def __iter__(self):
        return iter(self._resolve())

    def __len__(self):
        return len(self._resolve())

    def __repr__(self):
        return f'_LazyAllowedTargets({sorted(self._resolve())!r})'

    def __eq__(self, other):
        if isinstance(other, _LazyAllowedTargets):
            return self._resolve() == other._resolve()
        return self._resolve() == other


# (app_label, model) autorisés comme cibles d'activité / pièce jointe / lien GED.
# Registre unique partagé : Activity, Comment, TaggedItem, Attachment (records)
# ET DocumentLien (GED). Source de vérité désormais RÉPARTIE : chaque app
# déclare ses cibles dans son ``platform.py`` (surface ``record_targets``,
# voir ``core.platform``) — cette variable en reste l'UNION paresseuse.
ALLOWED_TARGETS = _LazyAllowedTargets()


class ActivityType(models.Model):
    """Type d'activité configurable (Appel, Email, Réunion, Relance, À faire)."""

    # ZSAL1 — enchaînement Odoo-style : à la clôture d'une activité de ce
    # type, on peut ne rien faire (AUCUN), juste PROPOSER une activité de
    # suivi au front (SUGGERER), ou la CRÉER automatiquement (DECLENCHER).
    class ModeEnchainement(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        SUGGERER = 'suggerer', 'Suggérer'
        DECLENCHER = 'declencher', 'Déclencher'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='activity_types')
    nom = models.CharField(max_length=80)
    icone = models.CharField(max_length=8, blank=True, default='')
    ordre = models.PositiveIntegerField(default=0)
    # Décalage par défaut (jours) proposé quand on planifie la suite.
    delai_defaut_jours = models.PositiveIntegerField(default=0)
    est_systeme = models.BooleanField(default=False)

    # ZSAL1 — chaînage additif, tous par défaut inertes (mode=aucun) donc
    # aucun changement de comportement pour les types existants.
    type_suivant = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='types_precedents',
        verbose_name='Type suivant suggéré/déclenché')
    mode_enchainement = models.CharField(
        max_length=10, choices=ModeEnchainement.choices,
        default=ModeEnchainement.AUCUN, verbose_name="Mode d'enchaînement")
    delai_jours = models.PositiveIntegerField(
        default=0, verbose_name='Délai (jours) avant la suite')

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Type d'activité"

    def __str__(self):
        return self.nom


class Activity(models.Model):
    """Activité planifiée rattachée à un enregistrement (générique).

    ARC8 — sert AUSSI d'entrée de chatter unifiée (le « mail.thread » maison).
    Les 13 modèles ``*Activity`` maison (crm.LeadActivity, sav.TicketActivity,
    contrats.ContratActivity…) partagent tous la même forme
    ``kind/field/old/new/body/user/timestamp`` ; les champs additifs ci-dessous
    (tous nullable/vides par défaut) permettent à ``records.Activity`` de porter
    une entrée de chatter — note manuelle (``kind=note``) ou journal de
    changement (``kind=modification``) — sans dépendre d'un ``ActivityType``.
    """

    # ARC8 — familles d'entrées du chatter générique (alignées sur les 13
    # modèles maison qu'il vise à remplacer à terme).
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='activities')

    # XKB4 — un « à-faire personnel » n'a PAS de cible métier : content_type/
    # object_id sont donc nullable (additif, rétro-compatible — toute activité
    # existante garde sa cible). `personnelle=True` marque ce cas et rend
    # l'activité visible du SEUL créateur (jamais listée pour un collègue).
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    personnelle = models.BooleanField(
        default=False, verbose_name='À-faire personnel')

    # ARC8 — ``activity_type`` devient nullable : une entrée de CHATTER (note ou
    # journal de changement) n'est pas une activité planifiée et n'a donc pas de
    # type. Additif et rétro-compatible : toute activité PLANIFIÉE existante
    # garde son type (non nul), le contrat 1:1 est préservé.
    activity_type = models.ForeignKey(
        ActivityType, on_delete=models.PROTECT, related_name='activities',
        null=True, blank=True)
    # ARC8 — champs de chatter (nullable/vides par défaut) : une activité
    # planifiée « classique » les laisse à leur défaut et se comporte comme
    # avant. ``kind`` vide = activité planifiée ; ``kind`` renseigné = entrée
    # de chatter.
    kind = models.CharField(
        max_length=15, choices=Kind.choices, blank=True, default='',
        verbose_name='Type de chatter')
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    summary = models.CharField(max_length=255, blank=True, default='')
    note = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    # VX85(a) — « Reporter » (picker ⏰ Plus tard : ce soir/demain/lundi/+1
    # semaine/perso) est NON DESTRUCTIF : il pose `snoozed_until` sans toucher
    # `due_date`. Tant que `snoozed_until` est dans le futur, l'activité est
    # exclue de `mine`/`ma-file` ; une fois échu elle réapparaît avec sa
    # `due_date` d'ORIGINE intacte. `due_date` reste réservée aux vrais
    # changements d'échéance (bouton « Reporter » distinct, inchangé).
    snoozed_until = models.DateField(
        null=True, blank=True,
        verbose_name='Reportée (snooze) jusqu\'au')
    # VX210(a) — horodatage de la POSE du snooze (distinct de `snoozed_until`,
    # l'échéance de réveil) : sert de borne « depuis » pour évaluer un
    # `snooze_trigger_event` (VX210(c) — un événement survenu AVANT le snooze
    # ne doit jamais le réveiller rétroactivement). Nul tant qu'aucun snooze
    # n'a jamais été posé.
    snoozed_at = models.DateTimeField(null=True, blank=True)
    # VX210(c) — déclencheur de réveil optionnel, format fermé `<clé>:<id>`
    # (``client_reply:<lead_id>`` / ``devis_signed:<devis_id>`` /
    # ``stock_arrive:<produit_id>`` — voir ``services.SNOOZE_TRIGGER_PREFIXES``).
    # Le sweep `reveiller_snoozes` réveille l'item dès que L'UN des deux
    # (l'échéance `snoozed_until` OU cet événement) survient en premier —
    # jamais les deux nécessaires. Vide = comportement VX85 inchangé (horloge
    # seule).
    snooze_trigger_event = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Déclencheur de réveil (VX210)')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activities_assignees')

    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activities_faites')

    # Marqueur pour l'activité « Relance » auto-gérée depuis Lead.relance_date :
    # une seule activité de ce genre par lead, synchronisée, jamais dupliquée.
    auto_relance = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activities_creees')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['done', 'due_date', 'id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['assigned_to', 'done']),
        ]
        verbose_name = 'Activité'

    def __str__(self):
        # ARC8 — une entrée de chatter n'a pas d'activity_type : on retombe
        # proprement sur le type de chatter (kind) puis le résumé/échéance.
        head = self.activity_type or self.get_kind_display() or 'Activité'
        return f'{head} — {self.summary or self.body or self.due_date or ""}'.strip()


class Tag(models.Model):
    """FG9 — Tag partagé entre modules (vocabulaire contrôlé par société).

    Un tag appartient à UNE société et peut être appliqué à N'IMPORTE quel
    enregistrement via TaggedItem (ContentType). Vocabulaire additivement
    contrôlé : on ne crée jamais un tag à la volée sans le passer par l'API.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='tags')
    nom = models.CharField(max_length=80)
    # Couleur hex optionnelle pour le chip UI (ex. '#3b82f6'). Vide = défaut.
    couleur = models.CharField(max_length=7, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom']
        unique_together = [('company', 'nom')]
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        indexes = [
            models.Index(fields=['company', 'nom']),
        ]

    def __str__(self):
        return self.nom


class TaggedItem(models.Model):
    """FG9 — Association entre un Tag et un enregistrement quelconque.

    Utilise le même mécanisme ContentType que Activity/Attachment.
    Mêmes ALLOWED_TARGETS ; company déduit du tag (jamais du corps de requête).
    """
    tag = models.ForeignKey(
        Tag, on_delete=models.CASCADE, related_name='tagged_items')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('tag', 'content_type', 'object_id')]
        ordering = ['tag__nom']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = 'Tag appliqué'
        verbose_name_plural = 'Tags appliqués'

    def __str__(self):
        return f'{self.tag} → {self.content_type.model}:{self.object_id}'


class Comment(models.Model):
    """FG7 — Commentaire générique rattaché à un enregistrement (GenericForeignKey).

    Supporte les @mentions : les noms d'utilisateur mentionnés dans le corps
    (`@username`) sont résolus et notifiés (via `notifications.notify()`).

    Mêmes cibles autorisées (ALLOWED_TARGETS) que Activity/Attachment.
    Company + auteur toujours posés côté serveur."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='comments')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='comments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # XKB13 — résolution de fil (générique, réutilisable par toute app cible ;
    # introduit pour les commentaires d'article KB). Champ additif : un
    # commentaire non résolu (défaut) se comporte comme aujourd'hui.
    resolved = models.BooleanField(default=False, verbose_name='Résolu')

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['company', 'created_at']),
        ]
        verbose_name = 'Commentaire'
        verbose_name_plural = 'Commentaires'

    def __str__(self):
        return f'Commentaire #{self.pk} par {self.author_id}'


class Attachment(models.Model):
    """Pièce jointe rattachée à un enregistrement (générique), stockée MinIO."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='attachments')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Clé objet MinIO (bucket erp-uploads) — le fichier ne quitte jamais le
    # stockage objet ; rien n'est commité dans le dépôt.
    file_key = models.CharField(max_length=500)
    filename = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    mime = models.CharField(max_length=120, blank=True, default='')
    # N5 — phase de chantier (avant / pendant / après) pour la galerie groupée.
    # Vide par défaut (usages génériques : leads, tickets…). Additif.
    phase = models.CharField(max_length=12, blank=True, default='')

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='attachments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'id']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
        verbose_name = 'Pièce jointe'

    def __str__(self):
        return self.filename


class Follower(models.Model):
    """XKB34 — abonnement d'un utilisateur à un enregistrement (générique).

    Même mécanisme ContentType que Activity/Comment/Attachment (bornée aux
    mêmes ``ALLOWED_TARGETS``). ``sous_type`` est un filtre OPTIONNEL et
    purement déclaratif (ex. ``'etape'`` pour ne recevoir que les changements
    d'étape) — vide = tout notifier. Company posée côté serveur, jamais lue du
    corps de requête. Purement additif : ne modifie aucun comportement
    existant tant que personne ne suit rien."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='followers')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='enregistrements_suivis')
    # Filtre déclaratif optionnel, ex. 'etape' = notifier seulement les
    # changements d'étape. Vide = tous les événements du chatter.
    sous_type = models.CharField(max_length=40, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'content_type', 'object_id', 'sous_type')]
        ordering = ['-created_at', 'id']
        indexes = [
            models.Index(fields=['content_type', 'object_id'],
                         name='records_follower_ct_oid_idx'),
            models.Index(fields=['user'], name='records_follower_user_idx'),
        ]
        verbose_name = 'Abonné (follower)'
        verbose_name_plural = 'Abonnés (followers)'

    def __str__(self):
        return f'{self.user_id} suit {self.content_type.model}:{self.object_id}'
