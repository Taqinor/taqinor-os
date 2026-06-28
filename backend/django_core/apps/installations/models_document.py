"""
FG297 — Contrôle documentaire de projet (plans & révisions).

Registre versionné des documents techniques d'un chantier :
  * ``DocumentProjet`` : un document technique rattaché au chantier (schéma
    unifilaire, calepinage, note de calcul, autre). Porte le titre, le type,
    et un lien optionnel vers une pièce jointe MinIO (records.Attachment).
  * ``RevisionDocument`` : une révision numérotée du document (indice de
    révision, date, auteur, fichier/pièce jointe, notes). Chaque document
    peut avoir N révisions ; la révision la plus récente est la version
    courante.

Additif, multi-tenant (FK ``company`` posée côté serveur). Aucune migration
destructive. Toutes les related_name sont préfixées ``inst_`` pour éviter
les collisions avec d'éventuels futurs modèles similaires dans d'autres apps.
"""
from django.conf import settings
from django.db import models

from .models_installation import Installation


class DocumentProjet(models.Model):
    """FG297 — document technique d'un chantier (un enregistrement par
    document, N révisions). Le ``type_doc`` classe le document : schéma
    unifilaire, calepinage, note de calcul, ou autre libellé libre.

    Multi-tenant (société posée côté serveur). Le fichier courant est porté
    par la dernière ``RevisionDocument`` ; ce modèle garde le titre et le
    type stables à travers les révisions."""

    class TypeDoc(models.TextChoices):
        SCHEMA_UNIFILAIRE = 'schema_unifilaire', "Schéma unifilaire"
        CALEPINAGE = 'calepinage', 'Calepinage'
        NOTE_CALCUL = 'note_calcul', "Note de calcul"
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='inst_documents_projet')
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE,
        related_name='inst_documents')
    type_doc = models.CharField(
        max_length=20, choices=TypeDoc.choices, default=TypeDoc.AUTRE)
    titre = models.CharField(max_length=200)
    notes = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Document de projet'
        verbose_name_plural = 'Documents de projet'
        ordering = ['installation_id', 'type_doc', 'titre']
        indexes = [
            models.Index(
                fields=['company', 'installation'],
                name='inst_docproj_co_inst_idx'),
        ]

    def __str__(self):
        return f'{self.installation_id} · {self.get_type_doc_display()} — {self.titre}'


class RevisionDocument(models.Model):
    """FG297 — révision d'un document de projet. L'indice (``indice``) suit
    la convention alphabétique marocaine (A, B, C… ou 0, 1, 2…) — c'est un
    champ texte libre, trié par date de révision. L'auteur est posé côté
    serveur (utilisateur courant). Le fichier est un lien optionnel vers une
    pièce jointe MinIO (records.Attachment, string-FK pour rester découplé).

    Multi-tenant (société posée côté serveur)."""

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='inst_revisions_document')
    document = models.ForeignKey(
        DocumentProjet, on_delete=models.CASCADE,
        related_name='inst_revisions')
    indice = models.CharField(max_length=10, default='A')
    date_revision = models.DateField()
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inst_revisions_document_auteur')
    # Fichier : pièce jointe MinIO via records.Attachment (string-FK découplée).
    fichier = models.ForeignKey(
        'records.Attachment', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inst_revisions_document')
    notes = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Révision de document'
        verbose_name_plural = 'Révisions de document'
        ordering = ['document_id', '-date_revision', '-date_creation']
        indexes = [
            models.Index(
                fields=['company', 'document'],
                name='inst_revdoc_co_doc_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'indice'],
                name='inst_revdoc_doc_indice_uniq'),
        ]

    def __str__(self):
        return f'Rev.{self.indice} — {self.document_id} ({self.date_revision})'
