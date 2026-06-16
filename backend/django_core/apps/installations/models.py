"""
Module Chantiers / Installations — l'objet pivot de l'après-vente.

Le chantier (Installation) est créé une fois le devis signé/accepté. C'est le
dossier de réalisation auquel tout l'après-vente (interventions, mise en
service, et plus tard parc équipements / garanties / SAV) viendra s'attacher.

Trois couches de statuts INDÉPENDANTES coexistent dans l'OS, à ne jamais
mélanger :
  1. l'étape du lead (STAGES.py — l'entonnoir commercial) ;
  2. le statut du document devis/facture (ventes) ;
  3. le statut du CHANTIER ci-dessous (réalisation physique).

Cet enum est une liste FERMÉE, en ordre d'entonnoir. « annulé » n'est PAS une
étape : c'est un drapeau (avec motif), comme « Perdu » sur un lead.
"""
from django.conf import settings
from django.db import models


class Installation(models.Model):
    class Statut(models.TextChoices):
        A_PLANIFIER = 'a_planifier', 'À planifier'
        PLANIFIE = 'planifie', 'Planifié'
        POSE_EN_COURS = 'pose_en_cours', 'Pose en cours'
        POSE = 'pose', 'Posé'
        RACCORDEMENT_ONEE = 'raccordement_onee', 'Raccordement ONEE'
        MISE_EN_SERVICE = 'mise_en_service', 'Mise en service'
        CLOTURE = 'cloture', 'Clôturé'

    # Ordre d'entonnoir (pour le tri des vues — JAMAIS alphabétique).
    STATUT_ORDER = [
        Statut.A_PLANIFIER,
        Statut.PLANIFIE,
        Statut.POSE_EN_COURS,
        Statut.POSE,
        Statut.RACCORDEMENT_ONEE,
        Statut.MISE_EN_SERVICE,
        Statut.CLOTURE,
    ]

    class Raccordement(models.TextChoices):
        MONOPHASE = 'monophase', 'Monophasé'
        TRIPHASE = 'triphase', 'Triphasé'

    class TypeInstallation(models.TextChoices):
        RESIDENTIEL = 'residentiel', 'Résidentiel'
        INDUSTRIEL = 'industriel', 'Industriel / Commercial'
        AGRICOLE = 'agricole', 'Agricole (pompage)'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='installations',
    )
    reference = models.CharField(max_length=50)

    # ── Liens (pivot) ──
    client = models.ForeignKey(
        'crm.Client', on_delete=models.PROTECT,
        related_name='installations',
    )
    # Devis d'origine. SET_NULL pour ne jamais perdre un chantier réalisé si le
    # devis est supprimé. Un seul chantier par devis (garde dans le service).
    devis = models.ForeignKey(
        'ventes.Devis', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations',
    )
    bon_commande = models.ForeignKey(
        'ventes.BonCommande', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations',
    )
    # Lead d'origine — pour le lien retour vers la fiche prospect.
    lead = models.ForeignKey(
        'crm.Lead', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations',
    )

    # ── Adresse du SITE (lieu physique des panneaux) — distincte de l'adresse
    #    de facturation du client. Pré-remplie depuis le lead, éditable. ──
    site_adresse = models.TextField(blank=True, null=True)
    site_ville = models.CharField(max_length=120, blank=True, null=True)
    gps_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)
    gps_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True)

    # ── Caractéristiques techniques (gelées à la création) ──
    puissance_installee_kwc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    # Raccordement GELÉ ici : la valeur engagée du chantier (copiée du lead),
    # indépendante d'une modification ultérieure du lead.
    raccordement = models.CharField(
        max_length=12, choices=Raccordement.choices, blank=True, null=True)
    type_installation = models.CharField(
        max_length=20, choices=TypeInstallation.choices, blank=True, null=True)

    technicien_responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installations_techniques',
    )

    statut = models.CharField(
        max_length=20, choices=Statut.choices, default=Statut.A_PLANIFIER)

    # ── Annulation : un DRAPEAU avec motif, pas une étape (comme « Perdu »). ──
    annule = models.BooleanField(default=False)
    motif_annulation = models.CharField(max_length=255, blank=True, null=True)

    # ── Dates clés ──
    date_pose_prevue = models.DateField(null=True, blank=True)
    date_pose_reelle = models.DateField(null=True, blank=True)
    date_mise_en_service = models.DateField(null=True, blank=True)

    # ── Mise en service (commissioning) ──
    mes_pv_notes = models.TextField(blank=True, null=True)
    mes_production_test = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    mes_tension = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True)

    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='installations_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Chantier'
        verbose_name_plural = 'Chantiers'
        ordering = ['-date_creation']
        unique_together = [('company', 'reference')]
        indexes = [
            models.Index(fields=['company', 'statut']),
        ]

    def __str__(self):
        return self.reference


class Intervention(models.Model):
    class Type(models.TextChoices):
        POSE = 'pose', 'Pose'
        RACCORDEMENT = 'raccordement', 'Raccordement'
        MISE_EN_SERVICE = 'mise_en_service', 'Mise en service'
        CONTROLE = 'controle', 'Contrôle'
        DEPANNAGE = 'depannage', 'Dépannage'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='interventions',
    )
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='interventions',
    )
    # Lien OPTIONNEL vers un ticket SAV : résoudre un ticket peut enregistrer
    # une ou plusieurs interventions (visites terrain) contre lui, sans créer
    # de concept « visite » parallèle. Additif, nullable — le comportement
    # chantier→intervention existant reste intact.
    ticket = models.ForeignKey(
        'sav.Ticket', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    type_intervention = models.CharField(max_length=20, choices=Type.choices)
    date_prevue = models.DateField(null=True, blank=True)
    date_realisee = models.DateField(null=True, blank=True)
    technicien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='interventions',
    )
    compte_rendu = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='interventions_creees',
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ordre de travail"
        verbose_name_plural = "Ordres de travail"
        ordering = ['-date_prevue', '-date_creation']

    def __str__(self):
        return f"{self.get_type_intervention_display()} — {self.installation_id}"


class TypeIntervention(models.Model):
    """Type d'ordre de travail / intervention, géré (Paramètres → Chantiers).

    Promotion de l'ancien enum Intervention.Type (pose, raccordement, mise en
    service, contrôle, dépannage) vers une liste de référence éditable, scopée
    par société. Le champ `Intervention.type_intervention` reste un CharField :
    cette liste fournit le libellé + l'ordre ; aucun ordre de travail existant
    ne change. Additif.

    Un type utilisé par un ordre de travail ne peut pas être supprimé (garde
    côté viewset, message français clair).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='types_intervention')
    # Clé stable (anglais/slug) stockée dans Intervention.type_intervention.
    key = models.CharField(max_length=40)
    label = models.CharField(max_length=120)
    ordre = models.PositiveIntegerField(default=100)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['ordre', 'label']
        unique_together = [('company', 'key')]
        verbose_name = "Type d'intervention"
        verbose_name_plural = "Types d'intervention"

    def __str__(self):
        return self.label


class InstallationActivity(models.Model):
    """Historique « chatter » d'un chantier — même modèle que LeadActivity.

    Entrées automatiques (création + changements de champs suivis, dont le
    statut) et notes manuelles. L'utilisateur et la société sont toujours
    posés côté serveur, jamais lus du corps de la requête.
    """
    class Kind(models.TextChoices):
        CREATION = 'creation', 'Création'
        MODIFICATION = 'modification', 'Modification'
        NOTE = 'note', 'Note'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='installation_activities',
    )
    installation = models.ForeignKey(
        Installation, on_delete=models.CASCADE, related_name='activites')
    kind = models.CharField(max_length=15, choices=Kind.choices)
    field = models.CharField(max_length=100, blank=True, null=True)
    field_label = models.CharField(max_length=150, blank=True, null=True)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='installation_activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité chantier'
        verbose_name_plural = 'Activités chantier'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['installation', '-created_at'])]

    def __str__(self):
        return f"{self.installation_id} {self.kind} {self.field or ''}".strip()
