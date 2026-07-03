"""Activités planifiées (style Odoo) et pièces jointes — génériques.

Les deux modèles se rattachent à N'IMPORTE quel enregistrement métier via
contenttypes (Lead, Client, Chantier, Ticket SAV…), sans coupler les apps.
Tout est company-stampé côté serveur et filtré par société, comme le reste.

ALLOWED_TARGETS borne explicitement les modèles que l'on peut cibler : on ne
laisse jamais le navigateur attacher une activité/un fichier à un modèle
arbitraire.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

# (app_label, model) autorisés comme cibles d'activité / pièce jointe / lien GED.
# Registre unique partagé : Activity, Comment, TaggedItem, Attachment (records)
# ET DocumentLien (GED). GED6 ajoute le bon de commande (`ventes.boncommande`)
# pour pouvoir rattacher un document GED à toute la chaîne devis→commande→facture.
ALLOWED_TARGETS = {
    ('crm', 'lead'),
    ('crm', 'client'),
    ('ventes', 'devis'),
    ('ventes', 'boncommande'),
    ('ventes', 'facture'),
    ('installations', 'installation'),
    ('sav', 'ticket'),
    ('outillage', 'outillage'),
    # DC27 — taxonomie de tags transversale : le produit catalogue devient
    # une cible taggable (clients/devis/factures/chantiers/tickets l'étaient
    # déjà), pour adosser tout le vocabulaire au registre `records.Tag`.
    ('stock', 'produit'),
    # DC33 — GED : liens polymorphes (DocumentLien) vers le fournisseur et la
    # fiche employé, en plus des cibles Lead/Client/Devis/Facture/Chantier déjà
    # présentes — l'identité n'est jamais recopiée sur le document, on ne fait
    # que pointer via ContentType. (Active aussi tags/PJ sur ces objets.)
    ('stock', 'fournisseur'),
    ('rh', 'dossieremploye'),
    # QHSE8 — photos de contrôle (avant/pendant/après) rattachées à un relevé
    # de contrôle ITP, et pièces jointes d'une non-conformité (NCR).
    ('qhse', 'relevecontrole'),
    ('qhse', 'nonconformite'),
    # XKB10 — pièces jointes/images d'un article de la base de connaissances
    # (éditeur Markdown : insertion d'image dans le corps). XKB13 réutilise la
    # MÊME entrée pour les commentaires génériques (records.Comment) sur les
    # articles KB.
    ('kb', 'kbarticle'),
}


class ActivityType(models.Model):
    """Type d'activité configurable (Appel, Email, Réunion, Relance, À faire)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='activity_types')
    nom = models.CharField(max_length=80)
    icone = models.CharField(max_length=8, blank=True, default='')
    ordre = models.PositiveIntegerField(default=0)
    # Décalage par défaut (jours) proposé quand on planifie la suite.
    delai_defaut_jours = models.PositiveIntegerField(default=0)
    est_systeme = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'nom']
        verbose_name = "Type d'activité"

    def __str__(self):
        return self.nom


class Activity(models.Model):
    """Activité planifiée rattachée à un enregistrement (générique)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='activities')

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    activity_type = models.ForeignKey(
        ActivityType, on_delete=models.PROTECT, related_name='activities')
    summary = models.CharField(max_length=255, blank=True, default='')
    note = models.TextField(blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
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
        return f'{self.activity_type} — {self.summary or self.due_date}'


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
