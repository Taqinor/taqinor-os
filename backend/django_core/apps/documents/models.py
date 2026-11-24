"""Modèles de l'app documents — le dossier contractuel d'un chantier.

L'app documents reste d'abord un générateur de PDF (PV, bon de livraison,
dossier de remise, attestations : aucun modèle). Les deux modèles ci-dessous
portent le DOSSIER CONTRACTUEL (docs/contrats/conception.md § 3) : les quatre
actes d'un chantier (cinq lignes, la livraison ayant deux variantes prêtes) et
les textes par défaut de la société.

Règles : ``company`` toujours posée côté serveur (jamais lue d'un corps de
requête) ; le chantier est une FK chaîne (``installations.Installation``),
jamais un import de modèle ; un acte n'est jamais supprimé (annulé, avec son
statut d'avant gardé) ; un acte signé ne perd jamais sa preuve.
"""
from django.conf import settings
from django.db import models


class ActeContractuel(models.Model):
    """Un acte du dossier contractuel d'un chantier (une ligne par acte et par
    variante : cinq lignes par chantier)."""

    class Type(models.TextChoices):
        CONTRAT_INSTALLATION = 'contrat_installation', "Contrat d'installation"
        PV_LIVRAISON = 'pv_livraison', 'Livraison du matériel'
        PV_RECEPTION = 'pv_reception', 'Réception des travaux'
        CLOTURE_GARANTIES = 'cloture_garanties', 'Quitus et certificat de garantie'

    class Variante(models.TextChoices):
        AUCUNE = '', 'Aucune'
        RESTE_A_REGLER = 'reste_a_regler', 'Reste à régler'
        TRANCHE_REGLEE = 'tranche_reglee', 'Tranche réglée'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EMIS = 'emis', 'Émis'
        SIGNE = 'signe', 'Signé'
        ANNULE = 'annule', 'Annulé'

    class ModeSignature(models.TextChoices):
        AUCUN = '', 'Aucun'
        SUR_PLACE = 'sur_place', 'Sur place'
        PAPIER = 'papier', 'Sur papier'
        DISTANCE = 'distance', 'À distance'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='actes_contractuels',
    )
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.PROTECT,
        related_name='actes_contractuels',
    )
    type = models.CharField(max_length=30, choices=Type.choices)
    variante = models.CharField(
        max_length=20, choices=Variante.choices, blank=True, default='')
    reference = models.CharField(max_length=60, blank=True, default='')
    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.BROUILLON)
    version = models.PositiveIntegerField(default=1)
    # Personnalisations de l'acte, par section (jamais un montant) ; les
    # sections de TEXTE de la traduction arabe vivent dans ``surcharges_ar``.
    surcharges = models.JSONField(default=dict, blank=True)
    surcharges_ar = models.JSONField(default=dict, blank=True)
    # Contenus figés à l'émission (français, traduction arabe) ; null tant que
    # l'acte est un brouillon.
    contenu = models.JSONField(null=True, blank=True)
    contenu_ar = models.JSONField(null=True, blank=True)
    emis_le = models.DateTimeField(null=True, blank=True)
    emis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='actes_contractuels_emis',
    )
    signe_le = models.DateTimeField(null=True, blank=True)
    signataire_nom = models.CharField(max_length=150, blank=True, default='')
    # Trace de la signature (PNG en data-URL).
    signature_client = models.TextField(blank=True, default='')
    mode_signature = models.CharField(
        max_length=20, choices=ModeSignature.choices, blank=True, default='')
    # Empreinte SHA-256 du contenu figé, adresse IP, agent, utilisateur.
    preuve = models.JSONField(default=dict, blank=True)
    statut_avant_annulation = models.CharField(
        max_length=20, blank=True, default='')
    motif_annulation = models.CharField(max_length=255, blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='actes_contractuels_crees',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'chantier', 'type', 'variante'],
                name='documents_acte_unique_par_chantier'),
        ]
        indexes = [
            models.Index(fields=['company', 'chantier'],
                         name='documents_acte_co_chantier'),
        ]

    def __str__(self):
        return f'{self.reference or self.type} ({self.get_statut_display()})'


class ModeleActe(models.Model):
    """Textes par défaut d'un type d'acte pour une société (sections texte
    seulement — jamais un montant)."""

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,  # on_delete: donnée propre à la société — supprimée avec elle (multi-tenant)
        related_name='modeles_actes',
    )
    type = models.CharField(max_length=30, choices=ActeContractuel.Type.choices)
    surcharges = models.JSONField(default=dict, blank=True)
    surcharges_ar = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modeles_actes_modifies',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'type'],
                name='documents_modele_acte_unique'),
        ]

    def __str__(self):
        return f'Modèle {self.get_type_display()}'
