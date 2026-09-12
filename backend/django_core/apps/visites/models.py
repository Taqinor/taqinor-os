"""Modèles du module « Visites terrain » (``apps.visites``) — VTA2.

VT1 — VISITE TECHNIQUE TERRAIN
------------------------------
Le commercial se déplace, capture des photos par SLOT NOMMÉ (checklist code :
``apps/visites/visite_checklist.py``) et relève des mesures ; le bureau
d'études donne — ou refuse — le FEU VERT au calepinage. Deux invariants du
groupe VT, inchangés par le move :

  * ``statut`` est un layer DOCUMENT INTERNE (comme ``Devis.statut``) : il
    n'entre JAMAIS en contact avec le funnel commercial de ``STAGES.py``, qui
    reste la seule échelle du pipeline lead ;
  * le modèle STOCKE des mesures et des photos, il n'émet AUCUN verdict :
    aucun seuil « dégagement suffisant » n'est codé nulle part — c'est un
    humain qui juge à la validation.

Les photos ne créent PAS un second magasin de fichiers : chaque média pointe
une ``records.Attachment`` (MinIO ``erp-uploads``) rattachée au LEAD, donc
visible dans l'AttachmentsPanel existant.

VTA2 — LE MOVE, STATE-ONLY
--------------------------
Ces deux modèles vivaient dans ``apps.crm.models``. Ils sont relogés ici SANS
toucher une seule donnée (``SeparateDatabaseAndState``, zéro SQL) :

  * ``db_table`` est FIGÉ sur les noms physiques historiques
    (``crm_visiteterrain`` / ``crm_visitemedia``) — sans cette ligne, Django
    chercherait ``visites_visiteterrain`` et la migration d'état mentirait sur
    la base réelle ;
  * la FK ``lead`` devient une référence **STRING** (``'crm.Lead'``) : elle
    était une référence de classe, ce qui rendrait
    ``apps.visites.models -> apps.crm.models`` statique et casserait le contrat
    ``independence`` d'import-linter que ce move existe pour honorer ;
  * les noms d'index sont conservés à l'identique (``crm_vterr_*`` /
    ``crm_vmedia_*``) : ils existent déjà en base, les renommer produirait du
    SQL, donc un move qui n'en serait plus un.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class VisiteTerrain(TenantModel):
    """Une visite technique terrain sur un lead (VT1)."""

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_COURS = 'en_cours', 'En cours'
        TERMINEE = 'terminee', 'Terminée'
        VALIDEE = 'validee', 'Validée (feu vert)'
        A_REFAIRE = 'a_refaire', 'À refaire'

    class Assemblage(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        EN_COURS = 'en_cours', 'En cours'
        OK = 'ok', 'Terminé'
        ECHEC = 'echec', 'Échec'

    #: Référence STRING (jamais la classe) : ``apps.visites.models`` n'importe
    #: AUCUN modèle de domaine — contrat ``independence`` d'import-linter (M3).
    lead = models.ForeignKey(
        'crm.Lead',
        # on_delete: composant du lead — une visite technique n'a aucun sens
        # sans le lead qu'elle documente (miroir de LeadActivity).
        on_delete=models.CASCADE,
        related_name='visites_terrain',
        verbose_name='Lead',
    )
    commercial = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='visites_terrain',
        verbose_name='Commercial terrain',
    )
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut de la visite')
    date_prevue = models.DateField(
        null=True, blank=True, verbose_name='Date prévue')
    date_realisee = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de réalisation')
    notes = models.TextField(
        blank=True, default='', verbose_name='Notes de visite')
    #: Mesures saisies, par catégorie de la checklist :
    #: ``{'toiture': {'longueur_m': 12.5, …}, 'tableau': {…}}``.
    mesures = models.JSONField(
        default=dict, blank=True, verbose_name='Mesures relevées')
    #: Clé MinIO de l'image de toit ASSEMBLÉE (VT9), vide tant qu'absente.
    photo_toit_key = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='Clé MinIO du toit assemblé')
    assemblage_etat = models.CharField(
        max_length=10, choices=Assemblage.choices, default=Assemblage.AUCUN,
        verbose_name="État de l'assemblage")
    assemblage_erreur = models.TextField(
        blank=True, default='', verbose_name="Erreur d'assemblage")
    #: VT11 — drapage de l'image assemblée sur le contour du toit :
    #: ``{'coins': [[lat, lng] × 4]}``. NULL tant que non calé.
    texture_calage = models.JSONField(
        null=True, blank=True, verbose_name='Calage de la texture')

    class Meta:
        # Table PHYSIQUE historique — le move ne déplace AUCUNE donnée.
        db_table = 'crm_visiteterrain'
        verbose_name = 'Visite technique terrain'
        verbose_name_plural = 'Visites techniques terrain'
        ordering = ['-date_prevue', '-id']
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='crm_vterr_comp_statut_idx'),
            models.Index(fields=['company', 'commercial'],
                         name='crm_vterr_comp_com_idx'),
        ]

    def __str__(self):
        return f'Visite {self.pk} — {self.lead_id} ({self.statut})'

    @property
    def modifiable(self):
        """Une visite VALIDÉE est gelée (feu vert donné) — VT3."""
        return self.statut != self.Statut.VALIDEE

    @property
    def raison_lecture_seule(self):
        """Phrase FR expliquant le gel, ou chaîne vide si modifiable."""
        if self.modifiable:
            return ''
        return ("Visite validée par le bureau d'études : elle est en lecture "
                'seule. Demander un renvoi pour la rouvrir.')


class VisiteMedia(TenantModel):
    """Une photo rattachée à un SLOT de la checklist d'une visite (VT1)."""

    visite = models.ForeignKey(
        VisiteTerrain,
        on_delete=models.CASCADE,  # on_delete: composant du parent (la visite)
        related_name='medias',
        verbose_name='Visite',
    )
    attachment = models.ForeignKey(
        'records.Attachment',
        # on_delete: le média EST le fichier — sans sa pièce jointe il ne
        # resterait qu'une tuile vide qui ferait mentir la complétude.
        on_delete=models.CASCADE,
        related_name='visite_medias',
        verbose_name='Pièce jointe',
    )
    slot_code = models.CharField(
        max_length=60, verbose_name='Slot de checklist')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    a_refaire = models.BooleanField(
        default=False, verbose_name='À refaire')
    motif_refaire = models.TextField(
        blank=True, default='', verbose_name='Motif du renvoi')
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Latitude de la prise de vue')
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        verbose_name='Longitude de la prise de vue')

    class Meta:
        # Table PHYSIQUE historique — le move ne déplace AUCUNE donnée.
        db_table = 'crm_visitemedia'
        verbose_name = 'Photo de visite'
        verbose_name_plural = 'Photos de visite'
        ordering = ['id']
        indexes = [
            models.Index(fields=['visite', 'slot_code'],
                         name='crm_vmedia_visite_slot_idx'),
        ]

    def __str__(self):
        return f'{self.slot_code} — visite {self.visite_id}'
